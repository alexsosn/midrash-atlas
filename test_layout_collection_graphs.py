import unittest

from layout_collection_graphs import collection_edges


class CollectionLayoutTests(unittest.TestCase):
    def test_duplicate_source_ids_are_unioned_before_edge_construction(self):
        books = ["Genesis"] * 10
        works = [
            {"sources": [[0, [0, 4]]]},
            {"sources": [[0, [4, 8]]]},
        ]
        locus = collection_edges(works, books, "loci")
        raw = collection_edges(works, books, "raw")
        self.assertEqual(set(locus), {(0, 4), (0, 8), (4, 8)})
        self.assertAlmostEqual(sum(locus.values()), 1)
        self.assertEqual(set(raw), {(0, 4), (0, 8), (4, 8)})
        self.assertEqual(sum(raw.values()), 3)


if __name__ == "__main__":
    unittest.main()
