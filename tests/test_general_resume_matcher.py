import unittest

from business import GeneralResumeMatcher as general
from business import TechnicalResumeMatcher as technical
from business.ResumeAdvisor import local_recommendation, matching_engine


class GeneralResumeMatcherTests(unittest.TestCase):
    def test_unknown_occupations_use_owned_evidence(self):
        cases = [
            ("CNC Machinist", "Inspect precision components", "Inspected precision components"),
            ("HVAC Technician", "Repair ventilation equipment", "Repaired ventilation equipment"),
            ("Dental Hygienist", "Provide patient care", "Provided patient care"),
            ("Early Childhood Educator", "Prepare classroom activities", "Prepared classroom activities"),
            ("Forklift Operator", "Operate warehouse equipment", "Operated warehouse equipment"),
            ("Restaurant Manager", "Manage restaurant inventory", "Managed restaurant inventory"),
            ("Accountant", "Prepare financial reports", "Prepared financial reports"),
            ("Recruiter", "Manage candidate interviews", "Managed candidate interviews"),
            ("Sales Associate", "Manage customer accounts", "Managed customer accounts"),
            ("Museum Conservator", "Inspect historical artifacts", "Inspected historical artifacts"),
        ]
        for title, duty, delivery in cases:
            with self.subTest(title=title):
                job = title + "\nResponsibilities\n" + duty
                self.assertIs(matching_engine(job), general)
                for resumes in [
                    [("A.txt", "Experience\n" + delivery), ("B.txt", "Built Python backend APIs.")],
                    [("B.txt", "Built Python backend APIs."), ("A.txt", "Experience\n" + delivery)],
                ]:
                    result = local_recommendation(job, resumes)
                    self.assertEqual(result["file"], "A.txt")
                    self.assertEqual(result["state"], "recommended")

    def test_tools_do_not_route_accountants_to_software(self):
        self.assertIs(matching_engine(
            "Accountant\nResponsibilities\nPrepare financial reports using Python and SQL."), general)
        for job in [
            "Mobile Nurse\nResponsibilities\nManage mobile patient care.",
            "Quality Engineer\nResponsibilities\nInspect manufacturing quality assurance processes.",
            "Software Sales Representative\nResponsibilities\nManage customer accounts.",
        ]:
            self.assertIs(matching_engine(job), general)

    def test_missing_qualifications_are_review_not_skip(self):
        for requirement in ["Active nursing license required.", "Bachelor degree required.",
                            "5 years payroll experience required.", "Quux scheduling tool required.",
                            "Communication skills required.", "RN or RPN required."]:
            with self.subTest(requirement=requirement):
                result = local_recommendation(
                    "Coordinator\nResponsibilities\nManage patient schedules.\nRequirements\n" + requirement,
                    [("R.txt", "Experience\nManaged patient schedules.")])
                self.assertEqual(result["state"], "provisional")
                self.assertEqual(result["recommendation"], "Consider")
                self.assertTrue(result["candidates"][0]["gaps"])

    def test_skills_and_aspirations_do_not_prove_delivery(self):
        for text in ["Skills: Inspect precision components.",
                     "I have not inspected precision components.",
                     "I would like to inspect precision components."]:
            result = local_recommendation(
                "Machinist\nResponsibilities\nInspect precision components.", [("R.txt", text)])
            self.assertEqual(result["state"], "provisional")

    def test_optional_keywords_do_not_outweigh_mandatory_evidence(self):
        job = ("Coordinator\nResponsibilities\nManage patient schedules.\n"
               "Requirements\nPrepare patient reports.\nNice to have\nUse Quux software.")
        result = local_recommendation(job, [
            ("A.txt", "Experience\nManaged patient schedules.\nPrepared patient reports."),
            ("B.txt", "Experience\nManaged patient schedules.\nUsed Quux software.")])
        self.assertEqual(result["file"], "A.txt")
        self.assertEqual(result["state"], "recommended")

    def test_unknown_language_and_empty_input_are_unassessable(self):
        for job in ["", "护理人员\n职责\n照顾病人", "Comptable\nPréparer les rapports financiers."]:
            result = local_recommendation(job, [("A.txt", "Prepared financial reports.")])
            self.assertEqual(result["state"], "insufficient")
            self.assertNotEqual(result["recommendation"], "Skip")

    def test_ties_survive_renaming_and_order(self):
        job = "Machinist\nResponsibilities\nInspect precision components."
        for resumes in [[("A.txt", "Inspected precision components."),
                         ("B.txt", "Inspected precision components.")],
                        [("Z.txt", "Inspected precision components."),
                         ("A.txt", "Inspected precision components.")]]:
            result = local_recommendation(job, resumes)
            self.assertEqual(result["state"], "close")
            self.assertEqual(len(result["alternatives"]), 2)

    def test_experience_is_scoped_and_not_inferred_from_dates(self):
        job = ("Payroll Clerk\nResponsibilities\nPrepare payroll reports.\n"
               "Requirements\n5 years payroll experience required.")
        for experience in ["8 years professional experience.",
                           "2 years payroll experience.", "2010 - 2026"]:
            with self.subTest(experience=experience):
                result = local_recommendation(job, [
                    ("R.txt", "Experience\nPrepared payroll reports.\n" + experience)])
                self.assertEqual(result["state"], "provisional")
        result = local_recommendation(job, [
            ("R.txt", "Experience\nPrepared payroll reports.\n7 years payroll experience.")])
        self.assertEqual(result["state"], "recommended")

    def test_unlisted_tool_is_retained_and_can_match(self):
        result = local_recommendation(
            "Coordinator\nResponsibilities\nManage patient schedules using Quuxware.",
            [("R.txt", "Experience\nManaged patient schedules using Quuxware.")])
        self.assertEqual(result["state"], "recommended")
        self.assertIn("Quuxware", result["job"]["skills"][0])

    def test_job_board_sections_exclude_metadata_company_and_benefits(self):
        job = """Position: Marketing Coordinator
Reports To: Senior Brand Manager
Location: Toronto, ON
About Example Beverages
We make fictional beverages for local communities.
Job Responsibilities
Support planning and execution of marketing campaigns and product launches.
Coordinate marketing deliverables with creative and sales teams.
Job Requirements And Competencies
Bachelor's degree in Marketing is preferred.
Previous experience in consumer marketing is an asset.
Must Haves:
Strong planning and analytical skills.
Strong proficiency across social media platforms including Instagram and TikTok.
G-level driver's license with clean driver's abstract.
Perks
Three weeks vacation and a product allowance.
Our Team Culture
Everyone participates in innovation days.
Equity Statement
We are an equal opportunity employer.
"""
        profile = general.job_profile(job, "Marketing Coordinator")
        combined = "\n".join(profile["responsibilities"] + profile["skills"])
        self.assertEqual(len(profile["responsibilities"]), 2)
        self.assertIn("marketing campaigns", combined)
        self.assertIn("Planning and analytical skills", profile["skills"])
        self.assertNotIn("Senior Brand Manager", combined)
        self.assertNotIn("fictional beverages", combined)
        self.assertNotIn("vacation", combined)
        self.assertNotIn("equal opportunity", combined)
        self.assertEqual(len(profile["preferred"]), 2)
        self.assertEqual(len(profile["required"]), 3)

        result = general.local_recommendation(job, [(
            "Marketing.txt",
            "Experience\nPlanned marketing campaigns and product launches.\n"
            "Coordinated deliverables with creative and sales teams.\n"
            "Analyzed campaign performance and managed Instagram content."
        )], job_title="Marketing Coordinator")
        from visualization.Workbench import format_assessment
        output = format_assessment(result)
        self.assertIn("Responsibilities\n• Support planning", output)
        self.assertIn("Core skills\n• Planning and analytical skills", output)
        self.assertNotIn("About Example Beverages", output)
        self.assertNotIn("Three weeks vacation", output)

    def test_placeholder_only_job_is_insufficient(self):
        job = ("About Example Company\nWe value collaboration.\n"
               "Responsibilities\n<<<TO BE ADDED BY HIRING MANAGER>>>\n"
               "Qualifications\n<<<TO BE ADDED BY HIRING MANAGER>>>")
        result = general.local_recommendation(job, [("A.txt", "Managed marketing campaigns.")],
                                              job_title="Marketing Coordinator")
        self.assertEqual(result["state"], "insufficient")
        self.assertIsNone(result["file"])

    def test_common_must_have_headings_are_not_requirements_themselves(self):
        for heading in ("Must Haves:",
                        "Must-Have Candidate Qualities\nCandidates should demonstrate:"):
            with self.subTest(heading=heading):
                profile = general.job_profile(
                    "Coordinator\n" + heading + "\nStrong planning skills.", "Coordinator")
                self.assertEqual([item["source"] for item in profile["required"]],
                                 ["Strong planning skills."])

    def test_existing_formatter_accepts_general_results(self):
        from visualization.Workbench import format_assessment
        for job in [
            "Machinist\nResponsibilities\nInspect precision components.",
            "Machinist\nResponsibilities\nInspect precision components.\nRequirements\nLicense required.",
            "护理人员\n职责\n照顾病人",
        ]:
            result = local_recommendation(job, [("R.txt", "Inspected precision components.")])
            output = format_assessment(result)
            self.assertIn(result["summary"], output)
            self.assertNotIn("Skip", output)

    def test_software_routing_and_result_are_unchanged(self):
        cases = [
            "Full Stack Developer\nBuild React web interfaces and Python APIs.",
            "Software Engineer\nBuild C++ backend services using Linux.",
            "DevOps Software Quality Automation Tools Engineer\nBuild test automation using Python Playwright.",
            "Java Developer\nBuild Java Spring Boot backend APIs using SQL.",
            "Mobile Developer\nBuild Flutter Android mobile applications using Kotlin.",
            "Customer Support Developer\nDevelop database connectors using Java and JDBC.",
            "Build Python services using AWS and Docker",
        ]
        resumes = [("A.txt", "Built React web interfaces and Python backend APIs."),
                   ("B.txt", "Built Java Spring Boot backend APIs using SQL."),
                   ("C.txt", "Built Flutter Android mobile applications using Kotlin.")]
        for job in cases:
            with self.subTest(job=job):
                self.assertIs(matching_engine(job), technical)
                self.assertEqual(local_recommendation(job, resumes),
                                 technical.local_recommendation(job, resumes))


if __name__ == "__main__":
    unittest.main()
