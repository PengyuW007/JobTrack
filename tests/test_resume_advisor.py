import tempfile
import unittest
from pathlib import Path

from business.ResumeAdvisor import recommend, local_recommendation, detected_skills
from visualization.Workbench import format_assessment


class ResumeAdvisorTests(unittest.TestCase):
    def test_skills_do_not_match_inside_other_words(self):
        self.assertEqual(detected_skills('JavaScript interesting excellent'), {'javascript'})

    def test_optional_mobile_and_company_copy_do_not_override_core_role(self):
        job = '''Software Developer
        Our data platform helps leaders. Collaborate with Design.
        The Role
        Deliver software features and automated tests.
        Requirements
        JavaScript TypeScript SQL .NET
        Nice to Have
        Flutter mobile frameworks
        What We Offer
        Healthcare and marketing events'''
        resumes = [('Mobile.txt', 'JavaScript TypeScript SQL Flutter'),
                   ('FullStack.txt', 'JavaScript TypeScript SQL'),
                   ('QA.txt', 'SQL test automation')]
        result = local_recommendation(job, resumes)
        self.assertEqual(result['file'], 'FullStack.txt')
        self.assertLess(result['score'], 8)

    def test_direction_changes_ranking_without_inflating_score(self):
        job = 'DevOps Software Quality Automation Tools Engineer\nPython SQL'
        result = local_recommendation(job, [('FullStack.txt', 'Python SQL'), ('QA.txt', 'Python')])
        self.assertEqual(result['file'], 'QA.txt')
        self.assertEqual(result['score'], 5.0)

    def test_mobile_role_still_selects_mobile_resume(self):
        result = local_recommendation('Mobile Developer\nFlutter Android',
                                      [('FullStack.txt', 'Flutter Android'), ('Mobile.txt', 'Flutter Android')])
        self.assertEqual(result['file'], 'Mobile.txt')

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

    def test_generic_title_uses_full_description_for_specialization(self):
        with tempfile.TemporaryDirectory() as folder:
            full_stack = Path(folder, 'FullStack_Resume.txt')
            java = Path(folder, 'Java_Resume.txt')
            full_stack.write_text('Python React TypeScript AWS', encoding='utf-8')
            java.write_text('Python React TypeScript AWS Java', encoding='utf-8')
            introduction = "\n".join(f'Company introduction line {index}' for index in range(15))
            job = f'''Software Engineer
            {introduction}
            Build full-stack web features with React, TypeScript, Python, and AWS.'''
            result, _ = recommend(job, [java, full_stack], 'local')
            self.assertEqual(result['file'], 'FullStack_Resume.txt')

    def test_linkedin_related_content_does_not_change_resume_track(self):
        with tempfile.TemporaryDirectory() as folder:
            full_stack = Path(folder, 'FullStack_Resume.txt')
            java = Path(folder, 'Java_Resume.txt')
            full_stack.write_text('React TypeScript Python AWS', encoding='utf-8')
            java.write_text('React TypeScript Python AWS Java Spring SQL', encoding='utf-8')
            job = '''Software Engineer
            Build full-stack web features using React, TypeScript, Python, and AWS.
            Show more Show less
            Similar jobs
            Java Software Engineer jobs using Java, Spring, and SQL.'''
            result, _ = recommend(job, [java, full_stack], 'local')
            self.assertEqual(result['file'], 'FullStack_Resume.txt')

    def test_non_technical_job_selects_specialized_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            developer = Path(folder, 'Software_Resume.txt')
            marketing = Path(folder, 'Marketing_Resume.txt')
            developer.write_text('Python Java SQL Docker', encoding='utf-8')
            marketing.write_text('Content marketing social media CRM lead generation', encoding='utf-8')
            job = '''Digital Marketing Specialist
            Plan content marketing campaigns, manage social media, and use CRM analytics.'''
            result, _ = recommend(job, [developer, marketing], 'local')
            self.assertEqual(result['file'], 'Marketing_Resume.txt')


if __name__ == '__main__':
    unittest.main()
