"""Fixed validation set for general matching; not a hiring-accuracy benchmark."""
import tempfile
import unittest
from pathlib import Path

from business import GeneralResumeMatcher as general
from business.ResumeAdvisor import local_recommendation, recommend


SECTORS = [
    ("healthcare", "Registered Nurse", "Coordinate discharge plans", "nursing", "CNO registration"),
    ("education", "Early Childhood Educator", "Plan play based learning activities", "childcare", "RECE registration"),
    ("finance", "Financial Analyst", "Prepare monthly variance reports", "financial analysis", "CPA designation"),
    ("sales", "Customer Service Representative", "Resolve customer account enquiries", "customer service", "sales licence"),
    ("marketing", "Marketing Coordinator", "Coordinate product launch campaigns", "marketing", "marketing certificate"),
    ("logistics", "Logistics Coordinator", "Schedule warehouse shipments", "logistics", "forklift licence"),
    ("trades", "Electrician", "Repair industrial electrical systems", "electrical", "Red Seal certificate"),
    ("hospitality", "Cook", "Prepare banquet menu items", "commercial kitchen", "food handler certificate"),
    ("administration", "Project Coordinator", "Track project schedules and budgets", "project coordination", "PMP certificate"),
]

# A second clear role per sector makes 18 deterministic ranking cases.
SECOND_ROLES = [
    ("healthcare", "Personal Support Worker", "Document resident care observations"),
    ("education", "Classroom Assistant", "Support classroom learning routines"),
    ("finance", "Staff Accountant", "Reconcile general ledger accounts"),
    ("sales", "Inside Sales Representative", "Manage customer sales orders"),
    ("marketing", "Graphic Designer", "Create digital campaign assets"),
    ("logistics", "Delivery Driver", "Deliver customer orders safely"),
    ("trades", "HVAC Technician", "Maintain commercial ventilation equipment"),
    ("hospitality", "Hotel Front Desk Agent", "Process guest arrivals and departures"),
    ("administration", "HR Coordinator", "Coordinate employee onboarding records"),
]


class CrossIndustryValidationTests(unittest.TestCase):
    def test_clear_cross_industry_top_choice_and_invariance(self):
        correct = total = 0
        cases = [(sector, role, duty) for sector, role, duty, _, _ in SECTORS] + SECOND_ROLES
        for sector, role, duty in cases:
            delivered = duty.replace("Coordinate", "Coordinated").replace("Plan", "Planned")
            delivered = delivered.replace("Prepare", "Prepared").replace("Schedule", "Scheduled")
            delivered = delivered.replace("Repair", "Repaired").replace("Track", "Tracked")
            delivered = delivered.replace("Document", "Documented").replace("Support", "Supported")
            delivered = delivered.replace("Reconcile", "Reconciled").replace("Manage", "Managed")
            delivered = delivered.replace("Create", "Created").replace("Deliver", "Delivered")
            delivered = delivered.replace("Maintain", "Maintained").replace("Process", "Processed")
            for good_name, other_name in (("A.txt", "B.txt"), ("Z.txt", "A.txt")):
                resumes = [(good_name, "Experience\n" + delivered),
                           (other_name, "Experience\nMaintained unrelated office records.")]
                for order in (resumes, list(reversed(resumes))):
                    with self.subTest(sector=sector, role=role, names=(good_name, other_name),
                                      reversed=order is not resumes):
                        result = local_recommendation(
                            f"{role}\nResponsibilities\n{duty}.", order)
                        total += 1
                        correct += result["file"] == good_name
                        self.assertEqual(result["file"], good_name)
                        self.assertEqual(result["state"], "recommended")
        self.assertGreaterEqual(correct / total, .95)

    def test_every_sector_covers_requirement_boundaries(self):
        classification_correct = classification_total = 0
        for sector, role, duty, specialty, credential in SECTORS:
            job = (f"{role}\nResponsibilities\n{duty}.\n"
                   f"Requirements\nStrong communication skills.\n{credential} required.\n"
                   f"Bachelor degree required.\n5 years {specialty} experience required.\n"
                   f"Must have\nUse Quuxware software.\n"
                   f"Nice to have\nSupervisory experience is an asset.\n"
                   f"Diploma or equivalent experience required.")
            profile = general.job_profile(job, role)
            by_source = {item["source"]: item for item in profile["criteria"]}

            expectations = {
                "Strong communication skills.": ("transferable", "required"),
                f"{credential} required.": ("credential", "required"),
                "Bachelor degree required.": ("education", "required"),
                f"5 years {specialty} experience required.": ("experience", "required"),
                "Use Quuxware software.": ("tool", "required"),
                "Supervisory experience is an asset.": ("responsibility", "optional"),
            }
            for source, expected in expectations.items():
                classification_total += 1
                actual = (by_source[source]["type"], by_source[source]["importance"])
                classification_correct += actual == expected
            self.assertTrue(by_source["Diploma or equivalent experience required."]["uncertain"])

            delivered = duty.replace("Coordinate", "Coordinated").replace("Plan", "Planned")
            delivered = delivered.replace("Prepare", "Prepared").replace("Schedule", "Scheduled")
            delivered = delivered.replace("Repair", "Repaired").replace("Track", "Tracked")
            resume = (f"Experience\n{delivered}.\nUsed Quuxware software.\n"
                      f"7 years {specialty} experience.\nSkills\nStrong communication skills.\n"
                      f"Education\nBachelor degree.\nCertifications\n{credential}.")
            result = local_recommendation(job, [("Candidate.txt", resume)], job_title=role)
            self.assertEqual(result["state"], "provisional", sector)
            self.assertNotEqual(result["recommendation"], "Apply", sector)
            for item in result["candidates"][0]["requirements"]:
                self.assertTrue(item["source"].strip())
                if item["coverage"]:
                    self.assertTrue(item["evidence"].strip(), (sector, item))
        self.assertGreaterEqual(classification_correct / classification_total, .95)

    def test_negative_aspirational_unknown_and_low_quality_inputs(self):
        for sector, role, duty, _, _ in SECTORS:
            job = f"{role}\nResponsibilities\n{duty} using Quuxware."
            past = duty.replace("Coordinate", "Coordinated").replace("Plan", "Planned")
            past = past.replace("Prepare", "Prepared").replace("Schedule", "Scheduled")
            past = past.replace("Repair", "Repaired").replace("Track", "Tracked")
            matched = local_recommendation(job, [("A.txt", f"Experience\n{past} using Quuxware.")])
            self.assertNotEqual(matched["recommendation"], "Skip", sector)
            for prefix in ("I have not", "I would like to"):
                result = local_recommendation(job, [("A.txt", f"{prefix} {duty.casefold()} using Quuxware.")])
                self.assertNotEqual(result["state"], "recommended", (sector, prefix))
                self.assertNotEqual(result["recommendation"], "Skip")

            for incomplete in ("", "Responsibilities\nTBD", "职责\n照顾病人"):
                result = local_recommendation(incomplete, [("A.txt", past)])
                self.assertEqual(result["state"], "insufficient", (sector, incomplete))
                self.assertNotEqual(result["recommendation"], "Skip")

    def test_unreadable_resume_never_produces_skip(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder, "Unreadable.pdf")
            bad.write_bytes(b"not a PDF")
            result, errors = recommend(
                "Coordinator\nResponsibilities\nTrack project schedules.", [bad])
        self.assertIsNone(result)
        self.assertTrue(errors)
        self.assertNotIn("Skip", " ".join(errors))


if __name__ == "__main__":
    unittest.main()
