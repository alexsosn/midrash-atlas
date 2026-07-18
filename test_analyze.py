import unittest
from unittest.mock import patch

from analyze import load_bundle


class ProfileDeduplicationTests(unittest.TestCase):
    def test_most_specific_duplicate_wins_independent_of_record_order(self):
        broad = {
            "category": "Halakhah",
            "sourceRef": "Example Work 1",
            "index_title": "Example Work",
            "anchor_span": 19,
            "verses": ["Amos 2:6"],
        }
        specific = {
            "category": "Halakhah",
            "sourceRef": "Example Work 1",
            "index_title": "Example Work",
            "anchor_span": 1,
            "verses": ["Amos 2:6"],
        }

        bundles = []
        for records in ([broad, specific], [specific, broad]):
            with patch("analyze.iter_records", return_value=iter(records)):
                bundles.append(load_bundle())

        for counts, works, sources, graph_sources in bundles:
            self.assertEqual(counts["Halakhah"]["Amos 2:6"], 1.0)
            self.assertEqual(
                works["Halakhah"]["Example Work"]["Amos 2:6"], 1.0
            )
            self.assertEqual(sources["Halakhah"], {"Example Work 1"})
            self.assertEqual(
                graph_sources["Halakhah"]["Example Work"]["Example Work 1"],
                {"Amos 2:6"},
            )
        self.assertEqual(bundles[0][0], bundles[1][0])
        self.assertEqual(bundles[0][1], bundles[1][1])

    def test_equal_span_tie_break_is_content_deterministic(self):
        records = [
            {
                "category": "Midrash",
                "sourceRef": "Example Source 2",
                "index_title": work,
                "anchor_span": 2,
                "verses": ["Genesis 1:1"],
            }
            for work in ("Work B", "Work A")
        ]
        results = []
        for ordered in (records, list(reversed(records))):
            with patch("analyze.iter_records", return_value=iter(ordered)):
                results.append(load_bundle()[1])
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0]["Midrash"]["Work A"]["Genesis 1:1"], 0.5)
        self.assertNotIn("Work B", results[0]["Midrash"])


if __name__ == "__main__":
    unittest.main()
