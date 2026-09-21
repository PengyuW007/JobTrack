import json
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from business.DuplicateService import (DuplicateService, Posting, _fetch_direct,
                                       _fetch_with_browser, canonical_url,
                                       description_usable, fetch_posting, parse_posting)
from persistence.DataAccess import DataAccess
from persistence.DataAccessJob import DataAccessJob
from business.AnalyticsService import AnalyticsService
from business.EmailClassifier import EmailClassifier
from parsers.EmailParser import EmailParser


class DuplicateTests(unittest.TestCase):
    def test_posting_location_and_explicit_work_mode(self):
        node = {'@type': 'JobPosting', 'title': 'Engineer',
                'jobLocation': {'address': {'addressLocality': 'Toronto', 'addressRegion': 'ON'}},
                'description': 'This is a hybrid role. Build APIs.'}
        def parse():
            return parse_posting('https://example.com/job',
                '<script type="application/ld+json">' + json.dumps(node) + '</script>')
        self.assertEqual(parse().location, 'Toronto, ON')
        self.assertEqual(parse().work_mode, 'Hybrid')
        node['description'] = 'Remote interviews are available. Collaborate with remote teams.'
        self.assertEqual(parse().work_mode, '')
        node['jobLocationType'] = 'TELECOMMUTE'
        self.assertEqual(parse().work_mode, 'Remote')
        del node['jobLocation']
        self.assertEqual(parse().location, '')

    def setUp(self):
        self.db = DataAccess.__new__(DataAccess)
        self.db.conn = sqlite3.connect(':memory:')
        self.db.cursor = self.db.conn.cursor()
        self.db.create_tables()
        self.job = SimpleNamespace(gmail_id='one', application_key='acme-engineer', company='Acme',
            position='Software Engineer', sender='hr@acme.com', created_date='2020-02-03 10:00:00 EST',
            last_updated_date='2020-02-03 10:00:00 EST', status='Applied', assessment_count=0,
            interview_count=0, offer=0, subject='Application received', body_preview='Thanks')
        self.db.insert_job(self.job)
        self.service = DuplicateService(self.db.conn)

    def tearDown(self):
        self.db.close()

    def test_tracking_parameters_but_not_job_ids(self):
        self.assertEqual(canonical_url('https://example.com/job?id=1&utm_source=email'), canonical_url('https://example.com/job?id=1'))
        self.assertNotEqual(canonical_url('https://example.com/job?id=1'), canonical_url('https://example.com/job?id=2'))

    def test_indeed_and_linkedin_tracking_urls(self):
        self.assertEqual(
            canonical_url('https://ca.indeed.com/viewjob?jk=abc123&from=shareddesktop_copy'),
            'https://ca.indeed.com/viewjob?jk=abc123'
        )
        self.assertEqual(
            canonical_url('https://www.linkedin.com/jobs/view/software-engineer-987654/?trk=public_jobs'),
            'https://linkedin.com/jobs/view/987654'
        )

    def test_full_email_evidence_and_all_dates_outside_chart(self):
        self.db.save_evidence(self.job, 'x' * 700 + ' https://example.com/jobs/1?utm_source=email')
        self.job.gmail_id = 'two'
        self.job.created_date = '2022-01-01 12:00:00 EST'
        self.db.save_evidence(self.job, 'Applied again')
        self.assertEqual(AnalyticsService(DataAccessJob(self.db.conn), '2026-01-01', '2026-12-31').get_total_applications(), 0)
        result = self.service.search(Posting('https://example.com/jobs/1'))[0]
        self.assertEqual(result['score'], 100)
        self.assertIn('2020-02-03', result['dates'])
        self.assertIn('2022-01-01', result['dates'])

    def test_repost_description_and_different_company(self):
        description = 'Build distributed systems with Python and SQL. ' * 5
        self.service.save_snapshot(self.job.application_key, Posting('https://example.com/old', 'Acme', 'Software Engineer', description))
        result = self.service.search(Posting('https://example.com/new', 'Acme', 'Software Engineer', description))[0]
        self.assertEqual(result['score'], 95)
        self.assertEqual(self.service.search(Posting('https://example.com/new', 'Other', 'Software Engineer', description)), [])

    def test_title_only_is_not_definitive(self):
        match = self.service.search(Posting('https://example.com/new', 'Acme', 'Software Engineer'))[0]
        self.assertEqual(match['score'], 80)
        self.assertEqual(match['dates'], '2020-02-03')
        self.assertEqual(self.service.search(Posting('https://example.com/new', '', 'Software Engineer')), [])

    def test_schema_migration_is_idempotent(self):
        self.db.create_tables()
        self.assertEqual(len(DataAccessJob(self.db.conn).get_all_jobs()), 1)

    def test_reclassified_gmail_message_moves_to_new_application(self):
        self.job.application_key = 'acme-quality-engineer'
        self.job.position = 'Quality Engineer'

        self.db.insert_job(self.job)
        self.db.save_evidence(self.job, 'Quality engineering application')

        jobs = DataAccessJob(self.db.conn).get_all_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].application_key, 'acme-quality-engineer')

    def test_resume_management_and_sync_timestamp(self):
        self.db.add_resume('Full Stack—0905', 'C:/resumes/full-stack-0905.pdf')
        resume_id = self.db.get_resumes()[0][0]
        self.db.update_resume(resume_id, name='Full Stack—0906', file_path='C:/resumes/full-stack-0906.pdf')
        saved = self.db.get_resumes()[0]
        self.assertEqual(saved[1], 'Full Stack—0906')
        self.assertEqual(saved[2], 'C:/resumes/full-stack-0906.pdf')
        self.db.update_resume(resume_id, enabled=0)
        self.assertEqual(self.db.get_resumes()[0][3], 0)
        self.db.update_last_sync_date('2026/09/05', 1788624000)
        self.assertTrue(self.db.get_last_sync_at().startswith('2026-'))
        self.assertEqual(self.db.get_last_sync_epoch(), 1788624000)
        self.db.mark_gmail_scanned('message-1', 2)
        self.db.conn.commit()
        self.assertEqual(self.db.get_scanned_gmail_ids(2), {'message-1'})
        self.db.clear_gmail_scan_progress()
        self.db.conn.commit()
        self.assertEqual(self.db.get_scanned_gmail_ids(2), set())
        self.db.delete_resume(resume_id)
        self.assertEqual(self.db.get_resumes(), [])
        self.assertEqual(self.db.get_setting('assessment_model', 'default'), 'default')
        self.db.set_setting('assessment_model', 'gpt-6-astra')
        self.assertEqual(self.db.get_setting('assessment_model'), 'gpt-6-astra')

    def test_structured_page_and_ambiguous_page(self):
        node = {'@type': 'JobPosting', 'title': 'Engineer', 'hiringOrganization': {'name': 'Acme'}, 'description': '<p>Work &amp; build</p>'}
        page = ('<div class></div><script type="application/ld+json">' +
                json.dumps({'@graph': [node]}) + '</script>')
        result = parse_posting('https://example.com/job', page)
        self.assertEqual(result.company, 'Acme')
        self.assertIn('Work & build', result.description)
        self.assertTrue(parse_posting('https://example.com/job', '<title>Sign in</title>').warning)

    def test_structured_description_retains_sections_and_related_job_boundary(self):
        from business.ResumeAdvisor import job_profile
        node = {'@type': 'JobPosting', 'title': 'Full Stack Developer',
                'description': '<h2>Responsibilities</h2><p>Build React web interfaces and Python APIs.</p>'
                               '<h2>Requirements</h2><ul><li>SQL required.</li></ul>'
                               '<h2>Similar jobs</h2><p>Mobile Flutter Java jobs.</p>'}
        posting = parse_posting('https://example.com/job', '<script type="application/ld+json">'+json.dumps(node)+'</script>')
        self.assertIn('\nRequirements\n', posting.description)
        profile = job_profile(posting.description, posting.position)
        self.assertNotIn('flutter', profile['skills'])
        self.assertIn('sql', profile['skills'])

    def test_visible_job_text_replaces_placeholder_structured_description(self):
        node = {'@type': 'JobPosting', 'title': 'Service Desk Technician',
                'description': '<h2>Responsibilities</h2><p>&lt;&lt;&lt;TO BE ADDED BY HIRING MANAGER&gt;&gt;&gt;</p>'}
        page = ('<script type="application/ld+json">' + json.dumps(node) + '</script>'
                '<div class="sfdc_richtext"><h3>Position Overview</h3>'
                '<p>Support 5,755 service desk tickets annually.</p>'
                '<h3>Key Responsibilities</h3><ul><li>Administer Microsoft 365.</li></ul></div>')
        posting = parse_posting('https://example.com/job', page)
        self.assertTrue(description_usable(posting.description))
        self.assertIn('5,755 service desk tickets', posting.description)
        self.assertNotIn('TO BE ADDED', posting.description)

    def test_placeholder_structured_description_uses_browser_fallback(self):
        url = 'https://example.com/job'
        placeholder = Posting(url, '', 'Service Desk Technician',
                              '<<<TO BE ADDED BY HIRING MANAGER>>>')
        rendered = Posting(url, 'Acme', 'Service Desk Technician',
                           'Responsibilities\nAdminister Microsoft 365.')
        with patch('business.DuplicateService._fetch_direct', return_value=placeholder), \
                patch('business.DuplicateService._fetch_with_browser', return_value=rendered) as browser:
            self.assertEqual(fetch_posting(url), rendered)
            browser.assert_called_once_with(url)

    def test_unresolved_placeholder_is_not_returned_as_a_ready_jd(self):
        url = 'https://example.com/job'
        placeholder = Posting(url, 'Acme', 'Coordinator',
                              '<<<TO BE ADDED BY HIRING MANAGER>>>')
        with patch('business.DuplicateService._fetch_direct', return_value=placeholder), \
                patch('business.DuplicateService._fetch_with_browser', return_value=placeholder):
            posting = fetch_posting(url)
        self.assertEqual(posting.position, 'Coordinator')
        self.assertEqual(posting.description, '')
        self.assertIn('complete description', posting.warning)

    def test_browser_runtime_failure_tries_the_next_browser(self):
        url = 'https://example.com/job'
        node = {'@type': 'JobPosting', 'title': 'Engineer',
                'description': 'Responsibilities: Build reliable systems.'}
        failing, working = MagicMock(), MagicMock()
        failing.get.side_effect = RuntimeError('browser disconnected')
        working.execute_script.return_value = 'complete'
        working.page_source = '<script type="application/ld+json">' + json.dumps(node) + '</script>'
        with patch('business.DuplicateService._browser_candidates', return_value=('edge', 'chrome')), \
                patch('business.DuplicateService._create_driver', side_effect=(failing, working)):
            posting = _fetch_with_browser(url)
        self.assertEqual(posting.position, 'Engineer')
        failing.quit.assert_called_once()
        working.quit.assert_called_once()

    def test_title_without_description_uses_browser_fallback(self):
        url = 'https://example.com/job'
        full = Posting(url, 'Acme', 'Full Stack Developer', 'Build React web interfaces and Python APIs.')
        with patch('business.DuplicateService._fetch_direct', return_value=Posting(url, 'Acme', 'Full Stack Developer')), \
                patch('business.DuplicateService._fetch_with_browser', return_value=full) as browser:
            self.assertEqual(fetch_posting(url), full)
            browser.assert_called_once_with(url)

    def test_pasted_description_history_uses_company_and_title(self):
        matches = self.service.search(Posting('', 'Acme', 'Software Engineer', 'Build software'))
        self.assertEqual(matches[0]['score'], 80)

    def test_resume_direction_metadata_is_removed_with_reference(self):
        self.db.add_resume('Sample', 'C:/fictional/sample.txt')
        resume_id = self.db.get_resumes()[0][0]
        key = f'resume_roles_{resume_id}'
        self.db.set_setting(key, '["backend"]')
        self.db.update_resume(resume_id, name='Renamed')
        self.assertEqual(self.db.get_setting(key), '["backend"]')
        self.db.delete_resume(resume_id)
        self.assertIsNone(self.db.get_setting(key))

    def test_blocked_job_board_uses_browser_fallback(self):
        url = 'https://ca.indeed.com/viewjob?jk=abc123'
        browser_result = Posting(url, 'Acme', 'Engineer', 'Build software')
        with patch('business.DuplicateService._fetch_direct', return_value=Posting(url, warning='blocked')), \
                patch('business.DuplicateService._fetch_with_browser', return_value=browser_result):
            self.assertEqual(fetch_posting(url).position, 'Engineer')

    def test_company_site_uses_browser_fallback(self):
        url = 'https://careers.example.com/jobs/123'
        browser_result = Posting(url, 'Acme', 'Engineer', 'Build software')
        with patch('business.DuplicateService._fetch_direct', return_value=Posting(url, warning='blocked')), \
                patch('business.DuplicateService._fetch_with_browser', return_value=browser_result):
            self.assertEqual(fetch_posting(url).position, 'Engineer')

    def test_same_site_job_iframe_is_parsed(self):
        url = 'https://careers.example.com/jobs/123/job'
        outer = b'<iframe src="?in_iframe=1"></iframe>'
        node = {'@type': 'JobPosting', 'title': 'Engineer',
                'hiringOrganization': {'name': 'Acme'}, 'description': 'Build software'}
        inner = ('<script type="application/ld+json">' + json.dumps(node) + '</script>').encode()

        def response(body):
            result = MagicMock()
            result.__enter__.return_value = result
            result.is_redirect = False
            result.encoding = 'utf-8'
            result.iter_content.return_value = [body]
            return result

        public_address = [(None, None, None, None, ('8.8.8.8', 443))]
        with patch('business.DuplicateService.socket.getaddrinfo', return_value=public_address), \
                patch('business.DuplicateService.requests.get', side_effect=(response(outer), response(inner))):
            posting = _fetch_direct(url)

        self.assertEqual(posting.company, 'Acme')
        self.assertEqual(posting.position, 'Engineer')

    def test_thank_you_for_your_application_is_imported(self):
        subject = 'Thank you for your application to PolicyMe'
        self.assertTrue(EmailClassifier.is_job_related(subject))
        self.assertEqual(EmailClassifier.detect_status(subject, subject), 'Applied')
        self.assertEqual(EmailParser.extract_company('Workable <noreply@example.com>', subject, ''), 'PolicyMe')

    def test_same_company_is_shown_when_original_role_is_missing(self):
        job = SimpleNamespace(
            gmail_id='policyme', application_key='policyme_', company='PolicyMe', position='',
            sender='PolicyMe <hello@policyme.com>', created_date='2026-08-05 09:00:00 EDT',
            last_updated_date='2026-08-05 09:00:00 EDT', status='Applied', assessment_count=0,
            interview_count=0, offer=0, subject='Thank you for your application to PolicyMe', body_preview='Received'
        )
        self.db.insert_job(job)
        matches = self.service.search(Posting('https://linkedin.com/jobs/view/4419905573', 'PolicyMe', 'Software Engineer (Remote)', 'Build software'))
        policyme = next(match for match in matches if match['company'] == 'PolicyMe')
        self.assertEqual(policyme['score'], 55)
        self.assertIn('original role unavailable', policyme['reason'])

    def test_application_channel_is_inferred_from_confirmation_email(self):
        self.assertEqual(
            DuplicateService._application_channel(
                'Your application was submitted',
                'AutoNotification@myworkday.com confirms your application.'
            ),
            'Workday',
        )
        self.assertEqual(
            DuplicateService._application_channel(
                'Your application was sent',
                'You applied using LinkedIn Easy Apply.'
            ),
            'LinkedIn Easy Apply',
        )


if __name__ == '__main__':
    unittest.main()
