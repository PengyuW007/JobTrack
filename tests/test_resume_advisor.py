import tempfile
import unittest
from pathlib import Path

from business.ResumeAdvisor import recommend
from visualization.Workbench import format_assessment


class ResumeAdvisorTests(unittest.TestCase):
    def test_compact_assessment_contains_every_decision(self):
        output = format_assessment({
            'file': 'FullStack.pdf', 'score': 4.9,
            'modification_needed': False, 'recommendation': 'Skip',
            'summary': 'Missing required experience.', 'source': 'Local match'
        })
        self.assertEqual(len(output.splitlines()), 5)
        self.assertIn('Modify: No', output)
        self.assertIn('Priority: Skip', output)
        self.assertIn('Local assessment', output)

    def test_ai_assessment_names_the_actual_model(self):
        output = format_assessment({
            'file': 'FullStack.pdf', 'score': 8.1,
            'modification_needed': False, 'recommendation': 'Apply',
            'summary': 'Strong match.', 'source': 'AI', 'model': 'gpt-5.6-terra'
        })
        self.assertIn('AI assessment · gpt-5.6-terra', output)

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


if __name__ == '__main__':
    unittest.main()
