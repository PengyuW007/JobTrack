import tempfile
import unittest
from pathlib import Path

from business.ResumeAdvisor import recommend


class ResumeAdvisorTests(unittest.TestCase):
    def test_local_resume_recommendation(self):
        with tempfile.TemporaryDirectory() as folder:
            backend = Path(folder, 'backend.txt')
            analyst = Path(folder, 'analyst.txt')
            backend.write_text('Python AWS Docker SQL', encoding='utf-8')
            analyst.write_text('Excel Tableau data analysis', encoding='utf-8')
            result, errors = recommend('Build Python services using AWS and Docker', [backend, analyst])
            self.assertEqual(result['file'], 'backend.txt')
            self.assertEqual(result['source'], 'Local match')
            self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
