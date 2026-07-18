import unittest

from layout_work_graphs import (
    layout_edges,
    merge_loci,
    normalize_positions,
    work_edges,
)


class WorkLayoutTests(unittest.TestCase):
    def test_locus_edges_match_source_normalization(self):
        books = ["Genesis"] * 8 + ["Exodus"] * 2
        work = {"sources": [[0, [0, 1, 4]], [1, [4, 8]]]}
        edges = work_edges(work, books)
        self.assertAlmostEqual(sum(edges.values()), 2.0)
        self.assertNotIn((0, 1), edges)
        self.assertIn((0, 4), edges)
        self.assertIn((4, 8), edges)

    def test_position_normalization_is_bounded_and_deterministic(self):
        raw = {3: (10, -2), 1: (0, 8), 2: (5, 3)}
        first = normalize_positions(raw)
        second = normalize_positions(dict(reversed(list(raw.items()))))
        self.assertEqual(first, second)
        self.assertEqual([row[0] for row in first], [1, 2, 3])
        self.assertTrue(all(0 <= value <= 1 for row in first for value in row[1:]))

    def test_adjacent_targets_form_one_locus(self):
        books = ["Genesis"] * 5
        self.assertEqual(merge_loci([0, 2, 4], books), [[0, 2, 4]])

    def test_raw_only_nodes_receive_layout_positions(self):
        books = ["Genesis"] * 8
        work = {"sources": [[0, [0, 1]], [1, [4, 7]]]}
        edges = layout_edges(work, books)
        self.assertEqual({node for edge in edges for node in edge}, {0, 1, 4, 7})


if __name__ == "__main__":
    unittest.main()
