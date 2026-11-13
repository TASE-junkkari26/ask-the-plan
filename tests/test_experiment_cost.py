"""Check nominal token-price arithmetic independently of any live API."""
from decimal import Decimal
import unittest

from experiments.door_labeling.reporting import estimate_cost


class CostEstimateTests(unittest.TestCase):
    def test_saved_example_uses_exact_decimal_currency_arithmetic(self):
        result = estimate_cost({"prompt_tokens": 4009, "completion_tokens": 459})
        self.assertEqual(result["nominal_input_cost_usd"], "0.00060135")
        self.assertEqual(result["nominal_output_cost_usd"], "0.00022950")
        self.assertEqual(result["nominal_total_cost_usd"], "0.00083085")
        self.assertEqual(Decimal(result["nominal_cost_per_1000_equal_usage_requests_usd"]), Decimal("0.83085"))
        self.assertEqual(Decimal(result["effective_project_cost_usd"]), Decimal(0))

    def test_missing_usage_stays_unknown_instead_of_becoming_zero(self):
        for usage in (None, {}, {"prompt_tokens": 100}):
            with self.subTest(usage=usage):
                result = estimate_cost(usage)
                self.assertEqual(result["status"], "unavailable")
                self.assertIsNone(result["nominal_total_cost_usd"])

    def test_invalid_counts_fail_and_reasoning_is_not_double_counted(self):
        for value in (-1, "100", 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    estimate_cost({"prompt_tokens": value, "completion_tokens": 1})
        plain = estimate_cost({"prompt_tokens": 4009, "completion_tokens": 459})
        detailed = estimate_cost({"prompt_tokens": 4009, "completion_tokens": 459,
                                 "completion_tokens_details": {"reasoning_tokens": 100}})
        self.assertEqual(plain["nominal_total_cost_usd"], detailed["nominal_total_cost_usd"])


if __name__ == "__main__":
    unittest.main()
