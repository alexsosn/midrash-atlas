import unittest

from export_atlas import edges_from_sources, merge_loci


class CitationLocusTests(unittest.TestCase):
    def test_merges_nearby_targets_without_crossing_books(self):
        loci = merge_loci({
            "Genesis 1:1", "Genesis 1:2", "Genesis 1:4",
            "Genesis 1:7", "Exodus 1:1",
        })
        self.assertEqual(loci, [
            ["Genesis 1:1", "Genesis 1:2", "Genesis 1:4"],
            ["Genesis 1:7"],
            ["Exodus 1:1"],
        ])

    def test_suppresses_within_locus_pairs(self):
        edges, evidence, audit = edges_from_sources(
            {"Source 1": {"Genesis 1:1", "Genesis 1:2"}}, "loci"
        )
        self.assertFalse(edges)
        self.assertFalse(evidence)
        self.assertEqual(audit["eligible_sources"], 0)

    def test_normalizes_each_source_to_total_weight_one(self):
        verses = {
            "Genesis 1:1", "Genesis 1:2", "Genesis 1:7", "Exodus 1:1"
        }
        edges, evidence, audit = edges_from_sources(
            {"Source 1": verses}, "loci"
        )
        self.assertAlmostEqual(sum(edges.values()), 1.0)
        self.assertNotIn(("Genesis 1:1", "Genesis 1:2"), edges)
        self.assertEqual(audit["eligible_sources"], 1)
        self.assertTrue(all(refs == {"Source 1"} for refs in evidence.values()))

    def test_raw_mode_retains_all_pairs(self):
        edges, _evidence, audit = edges_from_sources(
            {"Source 1": {"Genesis 1:1", "Genesis 1:2", "Genesis 1:7"}},
            "raw",
        )
        self.assertEqual(sum(edges.values()), 3)
        self.assertEqual(audit["eligible_sources"], 1)


if __name__ == "__main__":
    unittest.main()
