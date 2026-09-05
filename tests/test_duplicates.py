import json
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from business.DuplicateService import DuplicateService, Posting, canonical_url, fetch_posting, parse_posting
from persistence.DataAccess import DataAccess
from persistence.DataAccessJob import DataAccessJob
from business.AnalyticsService import AnalyticsService
from business.EmailClassifier import EmailClassifier
from parsers.EmailParser import EmailParser


class DuplicateTests(unittest.TestCase):
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

    def test_resume_management_and_sync_timestamp(self):
        self.db.add_resume('Full Stack—0905', 'C:/resumes/full-stack-0905.pdf')
        resume_id = self.db.get_resumes()[0][0]
        self.db.update_resume(resume_id, name='Full Stack—0906', file_path='C:/resumes/full-stack-0906.pdf')
        saved = self.db.get_resumes()[0]
        self.assertEqual(saved[1], 'Full Stack—0906')
        self.assertEqual(saved[2], 'C:/resumes/full-stack-0906.pdf')
        self.db.update_resume(resume_id, enabled=0)
        self.assertEqual(self.db.get_resumes()[0][3], 0)
        self.db.update_last_sync_date('2026/09/05')
        self.assertTrue(self.db.get_last_sync_at().startswith('2026-'))
        self.db.delete_resume(resume_id)
        self.assertEqual(self.db.get_resumes(), [])
        self.assertEqual(self.db.get_setting('assessment_model', 'default'), 'default')
        self.db.set_setting('assessment_model', 'gpt-6-astra')
        self.assertEqual(self.db.get_setting('assessment_model'), 'gpt-6-astra')

    def test_structured_page_and_ambiguous_page(self):
        node = {'@type': 'JobPosting', 'title': 'Engineer', 'hiringOrganization': {'name': 'Acme'}, 'description': '<p>Work &amp; build</p>'}
        page = '<script type="application/ld+json">' + json.dumps({'@graph': [node]}) + '</script>'
        result = parse_posting('https://example.com/job', page)
        self.assertEqual(result.company, 'Acme')
        self.assertIn('Work & build', result.description)
        self.assertTrue(parse_posting('https://example.com/job', '<title>Sign in</title>').warning)

    def test_blocked_job_board_uses_browser_fallback(self):
        url = 'https://ca.indeed.com/viewjob?jk=abc123'
        browser_result = Posting(url, 'Acme', 'Engineer', 'Build software')
        with patch('business.DuplicateService._fetch_direct', return_value=Posting(url, warning='blocked')), \
                patch('business.DuplicateService._fetch_with_browser', return_value=browser_result):
            self.assertEqual(fetch_posting(url).position, 'Engineer')

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
