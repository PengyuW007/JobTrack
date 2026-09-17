import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from business.ResumeAdvisor import recommend, local_recommendation, detected_skills, job_profile, resume_profile
from visualization.Workbench import format_assessment


class ResumeAdvisorTests(unittest.TestCase):
    def test_skills_do_not_match_inside_other_words(self):
        self.assertEqual(detected_skills('JavaScript interesting excellent'), {'javascript'})

    def test_optional_mobile_and_company_copy_do_not_override_core_role(self):
        job = '''Software Developer
        Our data platform helps leaders. Collaborate with Design.
        The Role
        Build full-stack web features and automated tests.
        Requirements
        JavaScript TypeScript SQL .NET
        Nice to Have
        Flutter mobile frameworks
        What We Offer
        Healthcare and marketing events'''
        resumes = [('Mobile.txt', 'Built Flutter mobile apps using JavaScript TypeScript SQL.'),
                   ('FullStack.txt', 'Built full-stack web features using JavaScript TypeScript SQL.'),
                   ('QA.txt', 'SQL test automation')]
        result = local_recommendation(job, resumes)
        self.assertEqual(result['file'], 'FullStack.txt')
        self.assertLess(result['score'], 8)

    def test_direction_changes_ranking_without_inflating_score(self):
        job = 'DevOps Software Quality Automation Tools Engineer\nBuild test automation using Python SQL.'
        result = local_recommendation(job, [('FullStack.txt', 'Built full-stack features using Python SQL.'), ('QA.txt', 'Built test automation using Python.')])
        self.assertEqual(result['file'], 'QA.txt')
        self.assertEqual(result['score'], 6.7)  # Python + test automation, with SQL absent.

    def test_mobile_role_still_selects_mobile_resume(self):
        result = local_recommendation('Mobile Developer\nBuild Flutter Android applications.',
                                      [('FullStack.txt', 'Built web frontend and backend using SQL.'), ('Mobile.txt', 'Built Flutter Android mobile applications.')])
        self.assertEqual(result['file'], 'Mobile.txt')

    def test_assessment_shows_uncertainty_and_reason_without_stars(self):
        output = format_assessment({
            'file': 'FullStack.pdf', 'score': 4.9,
            'modification_needed': False, 'recommendation': 'Skip',
            'summary': 'Missing required experience.', 'source': 'Local match'
        })
        self.assertIn('Provisional choice: FullStack.pdf', output)
        self.assertIn('Local assessment', output)
        self.assertNotIn('Modify:', output)
        self.assertNotIn('Priority:', output)
        self.assertIn('Missing required experience.', output)
        self.assertNotIn('★', output)
        self.assertNotIn('/10', output)

    def test_local_resume_recommendation(self):
        with tempfile.TemporaryDirectory() as folder:
            backend = Path(folder, 'backend.txt')
            analyst = Path(folder, 'analyst.txt')
            backend.write_text('Built Python services using AWS Docker SQL.', encoding='utf-8')
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
            full_stack.write_text('Built full-stack web features as an intern using React TypeScript REST SQL.', encoding='utf-8')
            java.write_text('Built Java backend APIs as an intern using React TypeScript REST SQL Agile.', encoding='utf-8')
            job = '''Full Stack Developer
            Build web frontend and backend features using React, TypeScript, C# and .NET.
            Qualifications: Minimum 4+ years professional experience excluding internship.
            Strong React and TypeScript. Strong C# and .NET experience.'''
            result, _ = recommend(job, [full_stack, java], 'local')
            self.assertEqual(result['file'], 'FullStack_Resume.pdf.txt')
            self.assertEqual(result['state'], 'provisional')
            self.assertNotEqual(result['recommendation'], 'Apply')
            self.assertTrue(any('experience not verified' in gap for gap in result['candidates'][0]['gaps']))

    def test_job_title_selects_specialized_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            sde = Path(folder, 'SDE_Resume.txt')
            qa = Path(folder, 'QA_Resume.txt')
            sde.write_text('Software developer', encoding='utf-8')
            qa.write_text('Built test automation as a quality assurance analyst using Python.', encoding='utf-8')
            result, _ = recommend('Quality Assurance Developer\nBuild test automation using Python.', [sde, qa], 'local')
            self.assertEqual(result['file'], 'QA_Resume.txt')

    def test_quality_engineering_title_beats_generic_full_stack_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            full_stack = Path(folder, 'FullStack_Resume.txt')
            qa = Path(folder, 'QA_Resume.txt')
            full_stack.write_text('Python JavaScript TypeScript React SQL REST Agile', encoding='utf-8')
            qa.write_text('Built API testing and regression testing using Python Playwright TypeScript.', encoding='utf-8')
            job = '''Quality Engineering Specialist
            Build automated tests with Python and TypeScript. Work with REST APIs,
            developers, agile teams, SQL services, and full-stack applications.'''
            result, _ = recommend(job, [full_stack, qa], 'local')
            self.assertEqual(result['file'], 'QA_Resume.txt')

    def test_generic_title_uses_full_description_for_specialization(self):
        with tempfile.TemporaryDirectory() as folder:
            full_stack = Path(folder, 'FullStack_Resume.txt')
            java = Path(folder, 'Java_Resume.txt')
            full_stack.write_text('Built full-stack web features using Python React TypeScript AWS.', encoding='utf-8')
            java.write_text('Built backend APIs using Python React TypeScript AWS Java.', encoding='utf-8')
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
            full_stack.write_text('Built full-stack web features using React TypeScript Python AWS.', encoding='utf-8')
            java.write_text('Built backend APIs using React TypeScript Python AWS Java Spring SQL.', encoding='utf-8')
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

    def test_fullstack_cannot_be_overridden_by_shared_mobile_keywords(self):
        job = 'Full Stack Developer\nBuild React TypeScript SQL Python AWS Docker REST web interfaces and backend APIs.'
        result = local_recommendation(job, [('FullStack.txt', 'Built web frontend and backend using React TypeScript SQL.'),
                                            ('Mobile.txt', 'Built Android mobile apps using React TypeScript SQL Python AWS Docker REST.')])
        self.assertEqual(result['file'], 'FullStack.txt')
        self.assertNotEqual(result['state'], 'recommended')

    def test_java_fullstack_uses_delivery_evidence_not_language_label(self):
        job = 'Java Full Stack Software Engineer\nBuild React web interfaces and Spring Boot APIs using Java SQL.'
        result = local_recommendation(job, [('Java.txt', 'Built Java Spring Boot backend APIs using SQL. React.'),
                                            ('Other.txt', 'Built React web interfaces and Java Spring Boot APIs using SQL.')])
        self.assertEqual(result['file'], 'Other.txt')
        self.assertEqual(result['state'], 'recommended')
        self.assertNotIn('java', result['job']['roles'])

    def test_mobile_collaboration_does_not_define_generic_engineer_direction(self):
        job = 'Software Engineer\nBuild React web interfaces and Python SQL APIs. Collaborate with the mobile team.'
        result = local_recommendation(job, [('Mobile.txt', 'Built mobile applications using React Python SQL.'),
                                            ('Web.txt', 'Built React web interfaces and Python SQL APIs.')])
        self.assertEqual(result['file'], 'Web.txt')
        self.assertNotIn('mobile', result['job']['roles'])

    def test_skill_aliases_and_react_native_are_distinct(self):
        self.assertEqual(detected_skills('React Native Node.js NextJS PostgreSQL SpringBoot'),
                         {'react native', 'node', 'next.js', 'postgres', 'spring boot'})

    def test_or_requirement_and_negation(self):
        job = 'Backend Developer\nBuild backend APIs.\nRequirements\nJava or Python required.\nC++ not required.'
        result = local_recommendation(job, [('Python.txt', 'Built backend APIs using Python.')])
        self.assertEqual(result['state'], 'recommended')
        self.assertEqual(len(result['job']['required']), 1)
        self.assertEqual(result['candidates'][0]['gaps'], [])

    def test_mixed_and_or_and_negation_require_review(self):
        for requirement in ['Java or Python and SQL required.', 'Java or Python, SQL required.',
                            'Java not required but Python required.']:
            with self.subTest(requirement=requirement):
                result = local_recommendation('Backend Developer\nBuild backend APIs.\nRequirements\n'+requirement,
                                              [('R.txt', 'Built backend APIs using Java Python SQL.')])
                self.assertNotEqual(result['state'], 'recommended')
                self.assertTrue(result['candidates'][0]['gaps'])

    def test_every_candidate_is_checked_for_experience_before_selection(self):
        job = 'Full Stack Developer\nBuild React web interfaces and Python APIs.\nRequirements\n5+ years professional experience.'
        result = local_recommendation(job, [('A.txt', 'Built React web interfaces and Python APIs. Intern.'),
                                            ('B.txt', 'Built React web interfaces and Python APIs. 7 years professional experience.')])
        self.assertEqual(result['file'], 'B.txt')
        self.assertEqual(result['state'], 'recommended')

    def test_unknown_years_are_not_guessed_and_international_is_not_intern(self):
        self.assertIsNone(resume_profile('International projects. Intern. 2020 - 2026')['professional_years'])
        job = 'Backend Developer\nBuild Python APIs.\nRequirements\nAt least 5 years professional experience.'
        result = local_recommendation(job, [('R.txt', 'Built Python backend APIs for international projects.')])
        self.assertEqual(result['state'], 'provisional')
        self.assertTrue(any('experience not verified' in gap for gap in result['candidates'][0]['gaps']))

    def test_company_age_and_preferred_experience_do_not_become_required(self):
        job = 'Backend Developer\nOur company has 20 years experience. Build Python backend APIs.\nNice to have\n5 years experience preferred.'
        self.assertIsNone(job_profile(job)['minimum_years'])

    def test_requirements_following_optional_section_are_core(self):
        job = 'Full Stack Developer\nNice to have\nFlutter\nResponsibilities\nBuild React web interfaces and Python APIs.\nRequirements\nSQL required.'
        profile = job_profile(job)
        self.assertIn('sql', profile['skills'])
        self.assertNotIn('sql', profile['optional_skills'])
        self.assertIn('flutter', profile['optional_skills'])

    def test_input_with_only_a_title_and_tools_is_insufficient(self):
        result = local_recommendation('Full Stack Developer\nReact SQL', [('R.txt', 'Built React web interfaces and SQL backend APIs.')])
        self.assertEqual(result['state'], 'insufficient')
        self.assertIsNone(result['file'])

    def test_wrong_direction_and_zero_overlap_do_not_force_a_choice(self):
        result = local_recommendation('Full Stack Developer\nBuild React web interfaces and Python APIs.',
                                      [('Mobile.txt', 'Built Android apps using Flutter.')])
        self.assertEqual(result['state'], 'none')
        self.assertIsNone(result['file'])
        self.assertNotIn('Recommended:', format_assessment(result))

    def test_same_evidence_cannot_be_resolved_by_file_order(self):
        job = 'Backend Developer\nBuild Python backend APIs.'
        for resumes in [[('A.txt', 'Built Python backend APIs.'), ('B.txt', 'Built Python backend APIs.')],
                        [('B.txt', 'Built Python backend APIs.'), ('A.txt', 'Built Python backend APIs.')]]:
            self.assertEqual(local_recommendation(job, resumes)['state'], 'close')

    def test_filename_changes_do_not_change_evidence_ranking(self):
        job = 'Full Stack Developer\nBuild React web interfaces and Python APIs.'
        for name in ['Mobile.txt', 'Java.txt', 'FullStack.txt', 'Resume.txt']:
            result = local_recommendation(job, [(name, 'Built React web interfaces and Python APIs.'),
                                                ('Web.txt', 'Built Flutter Android mobile apps.')])
            self.assertEqual(result['file'], name)
            self.assertEqual(result['state'], 'recommended')

    def test_confirmed_label_without_project_evidence_is_not_enough(self):
        result = local_recommendation('Full Stack Developer\nBuild React web interfaces and Python APIs.',
                                      [('R.txt', 'React Python')], resume_profiles={'R.txt': {'roles': ['full stack']}})
        self.assertEqual(result['state'], 'provisional')

    def test_unreadable_and_empty_resumes_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            readable, empty, missing = [Path(folder, name) for name in ['R.txt', 'Empty.txt', 'Missing.txt']]
            readable.write_text('Built Python backend APIs.', encoding='utf-8')
            empty.write_text('', encoding='utf-8')
            result, errors = recommend('Build Python backend APIs.', [readable, empty, missing])
            self.assertEqual(result['state'], 'provisional')
            self.assertEqual((result['readable_count'], result['requested_count']), (1, 3))
            self.assertEqual(len(errors), 2)

    def test_negated_or_aspirational_resume_text_is_not_project_evidence(self):
        for text in ['I have not built React web interfaces and Python APIs.',
                     'I would like to build React web interfaces and Python APIs.',
                     'Requirements: build React web interfaces and Python APIs.']:
            with self.subTest(text=text):
                result = local_recommendation('Full Stack Developer\nBuild React web interfaces and Python APIs.', [('R.txt', text)])
                self.assertNotEqual(result['state'], 'recommended')
                self.assertEqual(result['candidates'][0]['project_overlap'], [])

    def test_supporting_mobile_colleagues_does_not_override_web_work(self):
        profile = job_profile('Software Engineer\nBuild React web interfaces and Python APIs.\nSupport colleagues working on mobile applications.')
        self.assertEqual(profile['roles'], ['full stack'])

    def test_skill_list_is_not_delivery_evidence(self):
        profile = resume_profile('Software Developer. Skills: test automation, design patterns, leadership, Python.')
        self.assertEqual(profile['project_skills'], {})

    def test_unsupported_required_technology_is_not_silently_ignored(self):
        result = local_recommendation('Backend Developer\nBuild Python backend APIs.\nRequirements\nClojure required.',
                                      [('R.txt', 'Built Python backend APIs.')])
        self.assertEqual(result['state'], 'provisional')
        self.assertTrue(any('Clojure required' in gap for gap in result['candidates'][0]['gaps']))

    def test_education_requirement_needs_review_when_not_assessed(self):
        result = local_recommendation('Backend Developer\nBuild Python backend APIs.\nRequirements\nBachelor degree required.',
                                      [('R.txt', 'Built Python backend APIs.')])
        self.assertEqual(result['state'], 'provisional')

    def test_total_professional_years_do_not_prove_skill_specific_years(self):
        result = local_recommendation('Backend Developer\nBuild Python backend APIs.\nRequirements\n5 years Python experience required.',
                                      [('R.txt', 'Built Python backend APIs. 8 years professional experience.')])
        self.assertEqual(result['state'], 'provisional')

    def test_partial_known_requirements_still_report_unparsed_parts(self):
        for requirement in ['Python and Clojure required.', 'Python and distributed systems required.',
                            'Experience with Clojure using Python required.']:
            with self.subTest(requirement=requirement):
                result = local_recommendation('Backend Developer\nBuild Python backend APIs.\nRequirements\n'+requirement,
                                              [('R.txt', 'Built Python backend APIs.')])
                self.assertEqual(result['state'], 'provisional')
                self.assertTrue(any(requirement in gap for gap in result['candidates'][0]['gaps']))


    def test_invalid_pdf_does_not_abort_other_resume_comparisons(self):
        from pypdf.errors import PdfReadError
        with tempfile.TemporaryDirectory() as folder:
            readable = Path(folder) / 'Good.txt'
            readable.write_text('Built Python backend APIs.', encoding='utf-8')
            broken = Path(folder) / 'Broken.pdf'
            with patch('pypdf.PdfReader', side_effect=PdfReadError('synthetic invalid PDF')):
                result, errors = recommend('Backend Developer\nBuild Python backend APIs.', [readable, broken])
            self.assertEqual(result['readable_count'], 1)
            self.assertEqual(result['state'], 'provisional')
            self.assertEqual(len(errors), 1)
            self.assertIn('Broken.pdf', errors[0])

    def test_multiple_experience_constraints_are_not_reduced_to_first(self):
        result = local_recommendation('Backend Developer\nBuild Python backend APIs.\nRequirements\n3 years Python experience required.\n5 years backend experience required.',
                                      [('R.txt', 'Built Python backend APIs. 4 years professional experience with Python.')])
        self.assertEqual(result['state'], 'provisional')
        self.assertTrue(result['job']['experience_uncertain'])

    def test_mixed_required_and_preferred_clause_needs_review(self):
        result = local_recommendation('Backend Developer\nBuild Python backend APIs.\nRequirements\nJava required but Python preferred.',
                                      [('R.txt', 'Built Python backend APIs.')])
        self.assertEqual(result['state'], 'provisional')
        self.assertTrue(any('Java required' in gap for gap in result['candidates'][0]['gaps']))

    def test_multiple_principal_directions_never_clear_on_one_direction(self):
        result = local_recommendation('Full Stack / Mobile Developer\nBuild React Native mobile applications.',
                                      [('R.txt', 'Built React Native mobile applications.')])
        self.assertEqual(result['state'], 'provisional')
        self.assertTrue(any('multiple principal directions' in gap for gap in result['candidates'][0]['gaps']))


if __name__ == '__main__':
    unittest.main()
