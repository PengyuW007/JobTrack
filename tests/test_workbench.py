import unittest
import queue
import sqlite3
from unittest.mock import MagicMock, patch

from business.DuplicateService import Posting
from persistence.DataAccess import DataAccess
from visualization.Workbench import Workbench


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
                for width, height in [(900, 680), (1100, 760), (1400, 900)]:
                    root.geometry(f'{width}x{height}+10000+10000')
                    root.deiconify()
                    root.update()
                    for panel in [view.job_check, view.analysis_frame, view.history_label, view.resumes_box, view.overview]:
                        x = panel.winfo_rootx() - root.winfo_rootx()
                        y = panel.winfo_rooty() - root.winfo_rooty()
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, 0)
                        self.assertLessEqual(x + panel.winfo_width(), width)
                        self.assertLessEqual(y + panel.winfo_height(), height)
                    self.assertIs(view.job_check.master, view.left)
                    self.assertIs(view.analysis_frame.master, view.left)
                    for panel in [view.history_label, view.resumes_box, view.overview]:
                        self.assertIs(panel.master, view.right)
                    self.assertGreater(view.analysis_text.winfo_height(), 80)
                    self.assertGreater(view.canvas.get_tk_widget().winfo_height(), 70)
                    for tab in range(2):
                        view.input_tabs.select(tab)
                        root.update()
                        self.assertGreater(view.analysis_text.winfo_height(), 80)
                        for parent in [view.job_check, view.resumes_box, view.overview]:
                            def check_children(widget):
                                for child in widget.winfo_children():
                                    if not child.winfo_ismapped():
                                        continue
                                    self.assertLessEqual(child.winfo_rootx() + child.winfo_width(), parent.winfo_rootx() + parent.winfo_width() + 1)
                                    self.assertLessEqual(child.winfo_rooty() + child.winfo_height(), parent.winfo_rooty() + parent.winfo_height() + 1)
                                    check_children(child)
                            check_children(parent)
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
