"""Offline checks for answer-blind selection and count-proxy scoring."""
import unittest

from experiments.image_questions.benchmark import balanced_sample, compare_count, reference_count


class ImageBenchmarkTests(unittest.TestCase):
    def test_sample_is_reproducible_distinct_and_balances_families(self):
        rows = [{"source": source, "family": family, "path": f"{source}/{index}.png", "question": f"{family}?"}
                for source in ("a", "b") for family in ("doors", "windows") for index in range(12)]
        sample = balanced_sample(rows, {"a": 6, "b": 4}, 42)
        self.assertEqual(sample, balanced_sample(rows, {"a": 6, "b": 4}, 42))
        self.assertEqual(len({row["path"] for row in sample}), 10)
        for source, count in (("a", 3), ("b", 2)):
            for family in ("doors", "windows"):
                self.assertEqual(sum(row["source"] == source and row["family"] == family for row in sample), count)
        self.assertTrue(all("answer" not in row for row in sample))

    def test_insufficient_unique_images_fail_instead_of_resampling(self):
        with self.assertRaises(ValueError):
            balanced_sample([{"source": "a", "family": "doors", "path": "a.png"}], {"a": 2}, 1)

    def test_valid_reference_zero_stays_distinct_from_missing_or_noninteger(self):
        for value in (0, "0", 0.0):
            self.assertEqual(reference_count(value), 0)
        for value in (None, True, "unknown", -1, 1.5, float("nan"), float("inf")):
            self.assertIsNone(reference_count(value))

    def test_abstention_or_failure_cannot_match_a_zero_reference(self):
        for status in ("unsupported", "unreadable", "provider_unavailable", None):
            result = compare_count({"status": status, "candidates": []}, 0)
            self.assertFalse(result["exact_count_match"])
            self.assertIsNone(result["predicted_candidate_count"])
        self.assertTrue(compare_count({"status": "ok", "candidates": []}, 0)["exact_count_match"])

    def test_partial_match_is_only_count_agreement(self):
        result = compare_count({"status": "partial", "candidates": [{}, {}]}, "2")
        self.assertTrue(result["exact_count_match"])
        self.assertEqual(result["absolute_error"], 0)
        self.assertFalse(compare_count({"status": "ok", "candidates": [{}]}, 2)["exact_count_match"])


if __name__ == "__main__":
    unittest.main()
