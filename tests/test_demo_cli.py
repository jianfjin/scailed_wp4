import unittest

from pathfinder.demo import run_demo


class DemoCliTests(unittest.TestCase):
    def test_run_demo_returns_report(self) -> None:
        report = run_demo()

        self.assertTrue(report["audit_chain_valid"])
        self.assertIn("recommended_path", report)
        self.assertIn("mock data mode", " ".join(report["missing_data_warnings"]))


if __name__ == "__main__":
    unittest.main()
