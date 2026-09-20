import unittest
import queue
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from business.DuplicateService import Posting
from persistence.DataAccess import DataAccess
from visualization.Workbench import (Workbench, compact_job_location, format_posting_meta,
                                     format_technical_terms, review_description_blocks,
                                     role_tag_label, skill_label)


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.view = Workbench.__new__(Workbench)
        self.view.events = queue.Queue()
        self.view.root = MagicMock()
        self.view.db = MagicMock()
        self.view.db.get_last_sync_at.return_value = '2026-09-16 09:42'
        self.view.posting = Posting('https://example.com/job', 'Acme', 'Full Stack Developer', 'Build web apps')
        self.view.duplicates = MagicMock()
        self.view.duplicates.search.return_value = []
        self.view.results = MagicMock()
        self.view.sync_button = MagicMock()
        self.view.sync_status = MagicMock()
        self.view.lookup_status = MagicMock()
        self.view.url = MagicMock()
        self.view.url.get.return_value = self.view.posting.url
        self.view._job_version, self.view._resume_version = 2, 3
        for name in ['refresh_chart', 'show_empty_history', 'set_history_visible', 'set_analysis', 'show_posting']:
            setattr(self.view, name, MagicMock())

    def test_sync_refreshes_history_without_reassessing_resume_or_fetching(self):
        self.view.duplicates.search.return_value = [dict(company='Acme', position='Full Stack Developer', score=100,
            applications=[{'date': '2026-09-15', 'channel': 'Company website'}])]
        self.view.events.put(('sync', (None, 0)))
        self.view.poll()
        self.view.duplicates.search.assert_called_once_with(self.view.posting)
        self.view.refresh_chart.assert_called_once()
        self.view.set_analysis.assert_not_called()
        self.view.results.insert.assert_called_once()
        self.assertIn('Previously applied', self.view.lookup_status.set.call_args.args[0])

    def test_sync_failure_refreshes_partial_saved_history_and_keeps_assessment(self):
        self.view.events.put(('sync', ('TimeoutError', 0)))
        self.view.poll()
        self.view.duplicates.search.assert_called_once()
        self.view.set_analysis.assert_not_called()
        self.assertIn('Sync incomplete', self.view.sync_status.set.call_args.args[0])

    def test_sync_completion_uses_current_posting(self):
        current = Posting('https://example.com/other', 'Other', 'Backend Developer')
        self.view.posting = current
        self.view.events.put(('sync', (None, 0)))
        self.view.poll()
        self.view.duplicates.search.assert_called_once_with(current)

    def test_sync_after_clear_does_not_restore_old_history(self):
        self.view.posting = None
        self.view.events.put(('sync', (None, 0)))
        self.view.poll()
        self.view.duplicates.search.assert_not_called()
        self.view.set_analysis.assert_not_called()

    def test_possible_match_is_not_presented_as_exact_application(self):
        self.view.duplicates.search.return_value = [dict(company='Acme', position='Full Stack Developer', score=55,
            applications=[{'date': '2026-09-15', 'channel': 'Unknown'}])]
        self.view.refresh_history()
        self.assertIn('Possible', self.view.lookup_status.set.call_args.args[0])

    def test_pasted_jd_without_identifiers_is_not_a_negative_history_result(self):
        self.view.posting = Posting('', '', '', 'Build software')
        self.view.refresh_history()
        self.view.duplicates.search.assert_not_called()
        self.assertIn('unavailable', self.view.lookup_status.set.call_args.args[0])

    def test_stale_resume_result_is_ignored_even_for_same_url(self):
        self.view.events.put(('resume', ((2, 2), {}, [])))
        self.view.poll()
        self.view.set_analysis.assert_not_called()

    def test_stale_fetch_does_not_end_new_fetch(self):
        self.view.analyzing = True
        self.view.events.put(('posting', (1, self.view.posting)))
        self.view.poll()
        self.assertTrue(self.view.analyzing)
        self.view.show_posting.assert_not_called()

    def test_startup_sync_requires_existing_connection(self):
        self.view.start_sync = MagicMock()
        with patch('visualization.Workbench.Path.is_file', return_value=False):
            self.view.startup_sync()
        self.view.start_sync.assert_not_called()
        with patch('visualization.Workbench.Path.is_file', return_value=True):
            self.view.startup_sync()
        self.view.start_sync.assert_called_once_with(automatic=True)

    def test_automatic_sync_is_noninteractive_and_duplicate_sync_is_blocked(self):
        state = {'state': 'normal'}
        self.view.sync_button.__getitem__.side_effect = lambda key: state[key]
        self.view.sync_button.configure.side_effect = lambda **kwargs: state.update(kwargs)
        self.view.synchronize = MagicMock(return_value=0)
        with patch('visualization.Workbench.threading.Thread') as thread:
            self.view.start_sync(automatic=True)
            self.view.start_sync()
            thread.assert_called_once()
            thread.call_args.kwargs['target']()
        self.assertFalse(self.view.synchronize.call_args.kwargs['interactive'])

    def test_resume_row_delete_action_confirms_before_removing(self):
        self.view.resume_table = MagicMock()
        self.view.resume_table.identify_region.return_value = 'cell'
        self.view.resume_table.identify_column.return_value = '#4'
        self.view.resume_table.identify_row.return_value = '7'
        self.view.remove_resume = MagicMock()
        event = SimpleNamespace(x=170, y=12, x_root=400, y_root=300)
        with patch('visualization.Workbench.messagebox.askyesno', return_value=True):
            result = self.view._resume_table_click(event)
        self.view.resume_table.selection_set.assert_called_once_with('7')
        self.view.remove_resume.assert_called_once()
        self.assertEqual(result, 'break')

    def test_resume_row_double_click_toggles_use_outside_actions(self):
        self.view.resume_table = MagicMock()
        self.view.resume_table.identify_column.return_value = '#2'
        self.view.resume_table.identify_row.return_value = '7'
        self.view.toggle_resume = MagicMock()
        result = self.view._resume_table_double_click(SimpleNamespace(x=40, y=12))
        self.view.resume_table.selection_set.assert_called_once_with('7')
        self.view.toggle_resume.assert_called_once()
        self.assertEqual(result, 'break')

    def test_url_lookup_immediately_shows_analyzing_state(self):
        self.view._clear_job_result = MagicMock()
        self.view._set_job_details_visible = MagicMock()
        self.view.show_empty_history = MagicMock()
        self.view.job_title = MagicMock()
        self.view.job_meta = MagicMock()
        self.view.input_status = MagicMock()
        self.view.review_button = MagicMock()
        with patch('visualization.Workbench.threading.Thread') as thread:
            self.view.lookup_url()
        self.assertTrue(self.view.analyzing)
        self.view.job_title.set.assert_called_once_with('Analyzing job link…')
        self.view.input_status.set.assert_called_once_with('Analyzing…')
        self.view.lookup_status.set.assert_called_once_with('Waiting for job analysis')
        self.view.show_empty_history.assert_called_once_with('Analyzing job description…')
        self.view.set_analysis.assert_called_once_with('Analyzing job description…')
        self.view._set_job_details_visible.assert_called_once_with(True)
        thread.return_value.start.assert_called_once()

    def test_saved_pasted_jd_changes_add_action_to_edit(self):
        self.view.jd_description = MagicMock()
        self.view.jd_description.get.return_value = 'Complete job description'
        self.view.jd_title = MagicMock()
        self.view.jd_title.get.return_value = 'Software Engineer'
        self.view.jd_company = MagicMock()
        self.view.jd_company.get.return_value = 'Example Labs'
        self.view.pasted_jd_summary = MagicMock()
        self.view.pasted_jd_summary_label = MagicMock()
        self.view.open_jd_editor_button = MagicMock()
        self.view._refresh_pasted_jd_entry()
        self.view.pasted_jd_summary.set.assert_called_once_with('Software Engineer · Example Labs')
        self.view.open_jd_editor_button.configure.assert_called_once_with(text='Edit JD', style='TButton')

    def test_review_jd_formats_collapsed_headings_and_section_items(self):
        description = (
            'Job Requisition ID # 26WD Position Overview Build reliable products. '
            'Work with customers. Responsibilities Design scalable APIs. Maintain the platform. '
            'Minimum Qualifications 2-3 years of experience. Experience with Python. '
            'Preferred Qualifications AWS experience. Learn More About Autodesk! '
            'We create software for designers. Salary Transparency The expected range is listed.'
        )
        blocks = review_description_blocks(description)
        self.assertIn(('heading', 'Position Overview'), blocks)
        self.assertIn(('heading', 'Responsibilities'), blocks)
        self.assertIn(('heading', 'Minimum Qualifications'), blocks)
        self.assertIn(('heading', 'Preferred Qualifications'), blocks)
        self.assertIn(('heading', 'Learn More About Autodesk'), blocks)
        self.assertIn(('heading', 'Salary Transparency'), blocks)
        self.assertIn(('bullet', 'Design scalable APIs.'), blocks)
        self.assertIn(('bullet', 'Experience with Python.'), blocks)
        self.assertIn(('paragraph', 'We create software for designers.'), blocks)
        self.assertLess(blocks.index(('heading', 'Responsibilities')),
                        blocks.index(('heading', 'Minimum Qualifications')))

    def test_job_summary_uses_compact_north_american_location(self):
        posting = Posting(
            'https://example.com/job', 'Autodesk Canada Co.', 'Software Engineer', 'Build APIs',
            location='AMER - Canada - Ontario - Toronto - University Ave, Canada',
            work_mode='Hybrid',
        )
        self.assertEqual(compact_job_location(posting.location), ('Toronto, ON', 'University Ave'))
        self.assertEqual(format_posting_meta(posting),
                         'Autodesk Canada Co. · Toronto, ON · Hybrid — University Ave')
        posting.work_mode = 'Remote'
        self.assertEqual(format_posting_meta(posting),
                         'Autodesk Canada Co. · Toronto, ON · Remote')

    def test_skill_labels_preserve_technology_casing(self):
        self.assertEqual([skill_label(value) for value in ('aws', 'css', 'graphql', 'sql', 'javascript')],
                         ['AWS', 'CSS', 'GraphQL', 'SQL', 'JavaScript'])
        self.assertEqual(format_technical_terms('aws, graphql, node.js, mysql and ci/cd'),
                         'AWS, GraphQL, Node.js, MySQL and CI/CD')
        self.assertEqual(role_tag_label('qa'), 'QA')


class DesktopLayoutTests(unittest.TestCase):
    def test_panels_fit_supported_desktop_sizes_without_page_scrolling(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {type(error).__name__}')
        root.withdraw()
        db = DataAccess.__new__(DataAccess)
        db.conn = sqlite3.connect(':memory:')
        db.cursor = db.conn.cursor()
        db.create_tables()
        try:
            with patch('visualization.Workbench.tk.Tk', return_value=root), patch.object(Workbench, 'startup_sync'):
                view = Workbench(db)
                self.assertTrue(view.url_entry.bind('<<Paste>>'))
                url_tab = view.input_tabs.nametowidget(view.input_tabs.tabs()[0])
                button_labels = [child.cget('text') for child in url_tab.winfo_children()
                                 if child.winfo_class() == 'TButton']
                self.assertEqual(button_labels, ['Clear'])
                self.assertEqual(view.input_tabs.tab(1, 'text'), 'Paste JD')
                self.assertEqual(view.pasted_jd_summary.get(), 'No pasted JD yet')
                self.assertEqual(view.open_jd_editor_button.cget('text'), 'Add JD')
                self.assertEqual(tuple(view.resume_table['columns']), ('use', 'name', 'edit', 'delete'))
                self.assertEqual(view.resume_table.heading('edit', 'text'), 'Edit')
                self.assertEqual(view.resume_table.heading('delete', 'text'), 'Delete')
                for width, height in [(900, 760), (1100, 760), (1400, 900)]:
                    root.geometry(f'{width}x{height}+10000+10000')
                    root.deiconify()
                    root.update()
                    self.assertLessEqual(abs(view.left.winfo_width() - view.right.winfo_width()), 1)
                    self.assertEqual(view.job_check.winfo_height(), view.resumes_box.winfo_height())
                    self.assertEqual(view.job_check.winfo_height(), 240)
                    self.assertLessEqual(abs(
                        (view.analysis_frame.winfo_rooty() + view.analysis_frame.winfo_height()) -
                        (view.overview.winfo_rooty() + view.overview.winfo_height())), 1)
                    initial_job_height = view.job_check.winfo_height()
                    view._set_job_details_visible(True)
                    root.update()
                    self.assertEqual(view.job_check.winfo_height(), initial_job_height)
                    view._set_job_details_visible(False)
                    for panel in [view.job_check, view.analysis_frame, view.history_label, view.resumes_box, view.overview]:
                        x = panel.winfo_rootx() - root.winfo_rootx()
                        y = panel.winfo_rooty() - root.winfo_rooty()
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, 0)
                        self.assertLessEqual(x + panel.winfo_width(), width)
                        self.assertLessEqual(y + panel.winfo_height(), height)
                    self.assertIs(view.job_check.master, view.left)
                    self.assertIs(view.analysis_frame.master, view.left)
                    self.assertIs(view.history_label.master, view.left)
                    for panel in [view.resumes_box, view.overview]:
                        self.assertIs(panel.master, view.right)
                    self.assertTrue(view.analysis_empty.winfo_ismapped())
                    self.assertGreater(view.canvas.get_tk_widget().winfo_height(), 70)
                    tab_heights = []
                    for tab in range(2):
                        view.input_tabs.select(tab)
                        root.update()
                        tab_heights.append(view.job_check.winfo_height())
                        self.assertEqual(view.job_check.winfo_height(), view.resumes_box.winfo_height())
                        for parent in [view.job_check, view.resumes_box, view.overview]:
                            def check_children(widget):
                                for child in widget.winfo_children():
                                    if not child.winfo_ismapped():
                                        continue
                                    self.assertLessEqual(child.winfo_rootx() + child.winfo_width(), parent.winfo_rootx() + parent.winfo_width() + 1)
                                    self.assertLessEqual(child.winfo_rooty() + child.winfo_height(), parent.winfo_rooty() + parent.winfo_height() + 1)
                                    check_children(child)
                            check_children(parent)
                    self.assertEqual(len(set(tab_heights)), 1)
                    self.assertEqual(int(view.results.cget('height')), 4)
                root.geometry('900x760+10000+10000')
                root.update()
                view.open_jd_editor()
                root.update()
                dialogs = [child for child in root.winfo_children() if child.winfo_class() == 'Toplevel']
                self.assertEqual(len(dialogs), 1)
                dialog = dialogs[0]
                self.assertLess(dialog.winfo_width(), root.winfo_width())
                self.assertLess(dialog.winfo_height(), root.winfo_height())
                dialog.grab_release()
                dialog.destroy()
                result = {
                    'state': 'recommended', 'summary': 'Supported', 'job': {'roles': ['full stack']},
                    'alternatives': [],
                    'candidates': [
                        {'name': 'Mobile', 'roles': ['mobile'], 'confirmed_roles': [],
                         'compatibility': -1, 'project_overlap': ['kotlin'], 'gaps': ['Missing: web'],
                         'rank': (-1, 0, 0, 0, 0, 0), 'evidence': []},
                        {'name': 'Full Stack', 'roles': ['full stack'], 'confirmed_roles': [],
                         'compatibility': 2, 'project_overlap': ['react', 'sql'], 'gaps': [],
                         'rank': (2, 1, 1, 1, 1, 0), 'evidence': []},
                    ],
                }
                view.set_analysis('Recommended: Full Stack', result)
                for width, height in [(900, 760), (1100, 760), (1400, 900)]:
                    root.geometry(f'{width}x{height}+10000+10000')
                    root.update()
                    self.assertFalse(view.analysis_empty.winfo_ismapped())
                    self.assertGreater(view.analysis_text.winfo_height(), 40)
                    self.assertEqual(int(view.results.cget('height')), 4)
                    self.assertLessEqual(abs(
                        (view.analysis_frame.winfo_rooty() + view.analysis_frame.winfo_height()) -
                        (view.overview.winfo_rooty() + view.overview.winfo_height())), 1)
                    for panel in [view.job_check, view.history_label, view.analysis_frame,
                                  view.resumes_box, view.overview]:
                        self.assertLessEqual(panel.winfo_rooty() + panel.winfo_height(),
                                             root.winfo_rooty() + height)
                rows = view.comparison_table.get_children()
                self.assertEqual(view.comparison_table.item(rows[0], 'values')[0], 'Full Stack')
                self.assertEqual(view.comparison_table.item(rows[0], 'values')[3], 'Best fit')
                self.assertEqual(view.comparison_table.item(rows[1], 'values')[3], 'Role mismatch')
                view.analysis_tabs.select(1)
                root.update()
                self.assertFalse(view.comparison_scroll_x.winfo_ismapped())
                view.show_job_tags({'roles': ['full stack'], 'required': [
                    {'skills': ['react', 'spring boot', 'sql']}],
                    'skills': ['react', 'spring boot', 'sql', 'aws', 'css', 'graphql']})
                self.assertEqual([child.cget('text') for child in view.job_tags.winfo_children()],
                                 ['Full Stack', 'React', 'Spring Boot', 'SQL', 'AWS', 'CSS'])
        finally:
            root.destroy()
            db.close()


class GmailAuthorizationTests(unittest.TestCase):
    def test_automatic_sync_does_not_start_first_time_authorization(self):
        from main import get_gmail_service
        with patch('main.os.path.exists', return_value=False), patch('main.InstalledAppFlow') as flow:
            with self.assertRaises(PermissionError):
                get_gmail_service(interactive=False)
            flow.from_client_secrets_file.assert_not_called()

    def test_revoked_automatic_authorization_requests_manual_reconnection(self):
        from main import get_gmail_service
        from google.auth.exceptions import RefreshError
        creds = MagicMock(expired=True, refresh_token=True)
        creds.refresh.side_effect = RefreshError('Synthetic refresh failure')
        with patch('main.os.path.exists', return_value=True), \
                patch('main.Credentials.from_authorized_user_file', return_value=creds), \
                patch('main.InstalledAppFlow') as flow, patch('main.os.remove') as remove:
            with self.assertRaises(PermissionError):
                get_gmail_service(interactive=False)
            flow.from_client_secrets_file.assert_not_called()
            remove.assert_not_called()

    def test_valid_automatic_authorization_reuses_token(self):
        from main import get_gmail_service
        creds = MagicMock(expired=False, valid=True)
        with patch('main.os.path.exists', return_value=True), \
                patch('main.Credentials.from_authorized_user_file', return_value=creds), \
                patch('main.build', return_value='synthetic-service') as build, \
                patch('main.InstalledAppFlow') as flow:
            self.assertEqual(get_gmail_service(interactive=False), 'synthetic-service')
            build.assert_called_once_with('gmail', 'v1', credentials=creds)
            flow.from_client_secrets_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
