import tempfile
import unittest
from pathlib import Path

from business.ResumeAdvisor import recommend
from visualization.Workbench import format_assessment


class ResumeAdvisorTests(unittest.TestCase):
    def test_basic_assessment_only_shows_resume_match_and_source(self):
        output = format_assessment({
            'file': 'FullStack.pdf', 'score': 4.9,
            'modification_needed': False, 'recommendation': 'Skip',
            'summary': 'Missing required experience.', 'source': 'Local match'
        })
        self.assertEqual(len(output.splitlines()), 3)
        self.assertIn('Recommended: FullStack.pdf', output)
        self.assertIn('Match: ★★  4.9/10', output)
        self.assertIn('Local assessment', output)
        self.assertNotIn('Modify:', output)
        self.assertNotIn('Priority:', output)
        self.assertNotIn('Missing required experience.', output)

    def test_ai_assessment_names_the_actual_model(self):
        output = format_assessment({
            'file': 'FullStack.pdf', 'score': 8.1,
            'modification_needed': False, 'recommendation': 'Apply',
            'summary': 'Strong match.', 'source': 'AI', 'model': 'gpt-5.6-terra'
        })
        self.assertIn('AI assessment · gpt-5.6-terra', output)

    def test_api_failure_details_are_not_part_of_basic_results(self):
        output = format_assessment({
            'file': 'QA.pdf', 'score': 4.9,
            'modification_needed': False, 'recommendation': 'Skip',
            'summary': 'Local fallback.', 'source': 'Local match',
            'api_error': 'OpenAI API: Model access denied.'
        })
        self.assertIn('Local assessment', output)
        self.assertNotIn('OpenAI API: Model access denied.', output)

    def test_local_resume_recommendation(self):
        with tempfile.TemporaryDirectory() as folder:
            backend = Path(folder, 'backend.txt')
            analyst = Path(folder, 'analyst.txt')
            backend.write_text('Python AWS Docker SQL', encoding='utf-8')
            analyst.write_text('Excel Tableau data analysis', encoding='utf-8')
            result, errors = recommend('Build Python services using AWS and Docker', [backend, analyst], 'local')
            self.assertEqual(result['file'], 'backend.txt')
            self.assertEqual(result['source'], 'Local match')
            self.assertGreaterEqual(result['score'], 7)
            self.assertEqual(result['recommendation'], 'Apply')
            self.assertIn('summary', result)
            self.assertEqual(errors, [])

    def test_hard_experience_requirement_can_make_role_a_skip(self):
        with tempfile.TemporaryDirectory() as folder:
            full_stack = Path(folder, 'FullStack_Resume.pdf.txt')
            java = Path(folder, 'Java_Resume.pdf.txt')
            full_stack.write_text('Full-Stack Developer intern React TypeScript REST SQL', encoding='utf-8')
            java.write_text('Java Developer intern React TypeScript REST SQL Agile', encoding='utf-8')
            job = '''Full stack role using React, TypeScript, C# and .NET.
            Qualifications: Minimum 4+ years professional experience excluding internship.
            Strong React and TypeScript. Strong C# and .NET experience.'''
            result, _ = recommend(job, [full_stack, java], 'local')
            self.assertEqual(result['file'], 'FullStack_Resume.pdf.txt')
            self.assertEqual(result['recommendation'], 'Skip')
            self.assertLess(result['score'], 5)
            self.assertFalse(result['modification_needed'])

    def test_job_title_selects_specialized_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            sde = Path(folder, 'SDE_Resume.txt')
            qa = Path(folder, 'QA_Resume.txt')
            sde.write_text('Software developer', encoding='utf-8')
            qa.write_text('Quality assurance analyst and tester', encoding='utf-8')
            result, _ = recommend('Quality Assurance Developer', [sde, qa], 'local')
            self.assertEqual(result['file'], 'QA_Resume.txt')

    def test_quality_engineering_title_beats_generic_full_stack_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            full_stack = Path(folder, 'FullStack_Resume.txt')
            qa = Path(folder, 'QA_Resume.txt')
            full_stack.write_text('Python JavaScript TypeScript React SQL REST Agile', encoding='utf-8')
            qa.write_text('Python Playwright TypeScript API testing regression testing', encoding='utf-8')
            job = '''Quality Engineering Specialist
            Build automated tests with Python and TypeScript. Work with REST APIs,
            developers, agile teams, SQL services, and full-stack applications.'''
            result, _ = recommend(job, [full_stack, qa], 'local')
            self.assertEqual(result['file'], 'QA_Resume.txt')


if __name__ == '__main__':
    unittest.main()
