"""Regression checks against prices cached in the released workbook."""

import unittest

from pricing_rule_engine import DEFAULT_WORKBOOK, PricingEngine, RUNTIME


class PricingParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = PricingEngine(DEFAULT_WORKBOOK, RUNTIME)

    def test_belt_drive_part_matches_workbook(self):
        result = self.engine.calculate("39MBHHGTB10674MHDK")
        self.assertTrue(result.ok, result.errors)
        self.assertAlmostEqual(result.total_price, 2333.811990811239, places=4)
        check = result.reconciliation
        self.assertEqual(check["price_tolerance"], 0.01)
        self.assertTrue(check["matches_total_price"])
        self.assertAlmostEqual(check["raw_sums"]["sled"], 1382.894, places=3)
        self.assertAlmostEqual(check["raw_sums"]["motor"], 499.94, places=2)
        self.assertAlmostEqual(check["raw_sums"]["drive"], 87.0470588235, places=6)
        self.assertEqual(check["unclassified_price_hits"], [])
        self.assertAlmostEqual(check["difference_total_minus_three_buckets"], 0, places=4)
        self.assertIsNotNone(result.selected_drive)
        self.assertAlmostEqual(result.selected_drive.cost, 73.99, places=2)

    def test_direct_drive_part_matches_workbook(self):
        result = self.engine.calculate("39MBS9PRB13210PCCK")
        self.assertTrue(result.ok, result.errors)
        self.assertAlmostEqual(result.total_price, 4075.62177873415, places=4)
        self.assertTrue(result.reconciliation["matches_total_price"])
        self.assertEqual(result.reconciliation["unclassified_price_hits"], [])
        self.assertIsNone(result.selected_drive)


if __name__ == "__main__":
    unittest.main()
