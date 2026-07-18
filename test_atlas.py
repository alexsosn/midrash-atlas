import json
import os
import unittest

from dataset import BOOK_SECTIONS, VERSE_COUNTS, parse_verse
from layout_collection_graphs import collection_edges
from layout_work_graphs import book_lookup, layout_edges


HERE = os.path.dirname(os.path.abspath(__file__))


class AtlasDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "atlas_data.json"), encoding="utf-8") as handle:
            cls.data = json.load(handle)

    def test_reports_complete_tanakh_corpus(self):
        summary = self.data["summary"]
        self.assertEqual(
            self.data["meta"]["method_version"],
            "8.0-full-collection-graphs",
        )
        self.assertEqual(summary["tanakh_books"], 39)
        self.assertEqual(summary["tanakh_chapters"], 929)
        self.assertEqual(summary["tanakh_verses"], 23206)
        self.assertEqual(self.data["meta"]["cache"]["files"], 929)

    def test_report_footer_uses_dataset_method_version(self):
        template_path = os.path.join(HERE, "atlas_template.html")
        with open(template_path, encoding="utf-8") as handle:
            template = handle.read()
        self.assertIn('id="method-version"', template)
        self.assertIn("DATA.meta.method_version", template)
        self.assertNotIn("метод 3.0", template)

    def test_work_graphs_are_not_centrality_truncated(self):
        template_path = os.path.join(HERE, "atlas_template.html")
        with open(template_path, encoding="utf-8") as handle:
            template = handle.read()
        self.assertNotIn(".slice(0, 120)", template)
        self.assertIn("completeWorkLayout", template)
        self.assertIn("Показати підграф джерела", template)
        self.assertIn("function buildCollectionGraph", template)
        self.assertNotIn("DATA.graphs[category]", template)

    def test_labels_follow_the_active_research_focus(self):
        template_path = os.path.join(HERE, "atlas_template.html")
        with open(template_path, encoding="utf-8") as handle:
            template = handle.read()
        self.assertIn("function focusedNeighborRows", template)
        self.assertIn("function labelCandidates", template)
        self.assertIn("function drawLabels", template)
        self.assertNotIn("if (index > 15", template)

    def test_bereshit_rabbah_source_is_complete_and_laid_out(self):
        source = "Bereshit Rabbah 44:12"
        source_id = self.data["source_index"].index(source)
        work = next(
            item
            for item in self.data["work_graphs"]["Midrash"]
            if item["name"] == "Bereshit Rabbah"
        )
        source_entry = next(entry for entry in work["sources"] if entry[0] == source_id)
        refs = {self.data["verse_index"][verse_id] for verse_id in source_entry[1]}
        self.assertEqual(
            refs,
            {
                "Genesis 12:1", "Genesis 15:5", "Genesis 17:5",
                "Genesis 20:7", "Genesis 20:17", "Jeremiah 10:2",
                "Jonah 3:10", "Psalms 17:15", "Psalms 20:2",
                "Proverbs 8:26", "II Chronicles 7:14",
            },
        )
        laid_out = {
            verse_id
            for verse_id, _x, _y in self.data["work_layouts"]["Midrash"]["Bereshit Rabbah"]
        }
        self.assertTrue(set(source_entry[1]).issubset(laid_out))

    def test_every_large_work_has_complete_dual_model_layout(self):
        books = book_lookup(self.data)
        expected = {}
        for category, works in self.data["work_graphs"].items():
            for work in works:
                nodes = {
                    node
                    for edge in layout_edges(work, books)
                    for node in edge
                }
                if len(nodes) > 120:
                    expected[(category, work["name"])] = nodes
        actual = {
            (category, name): {row[0] for row in positions}
            for category, works in self.data["work_layouts"].items()
            for name, positions in works.items()
        }
        self.assertEqual(actual, expected)
        self.assertEqual(self.data["meta"]["work_layouts"]["format_version"], 2)

    def test_every_collection_layout_covers_the_complete_graph(self):
        books = book_lookup(self.data)
        for category, works in self.data["work_graphs"].items():
            for mode in ("loci", "raw"):
                edges = collection_edges(works, books, mode)
                expected = {node for edge in edges for node in edge}
                layout = self.data["collection_layouts"][category][mode]
                actual = {row[0] for row in layout["nodes"]}
                self.assertEqual(actual, expected, (category, mode))
                self.assertEqual(layout["edge_count"], len(edges), (category, mode))
        self.assertNotIn("graphs", self.data)
        self.assertTrue(all(
            len(graph["nodes"]) <= 240
            for modes in self.data["collection_previews"].values()
            for graph in modes.values()
        ))

    def test_profiles_reach_all_three_tanakh_sections(self):
        sections = set()
        for profile in self.data["profiles"].values():
            for ref, _weight in profile:
                parsed = parse_verse(ref)
                self.assertIsNotNone(parsed, ref)
                sections.add(BOOK_SECTIONS[parsed[0]])
        self.assertEqual(sections, {"Torah", "Prophets", "Writings"})

    def test_graph_evidence_resolves_to_exact_source_refs(self):
        source_count = len(self.data["source_index"])
        self.assertGreater(source_count, 0)
        for modes in self.data["collection_previews"].values():
            self.assertEqual(set(modes), {"loci", "raw"})
            for graph in modes.values():
                self.assertTrue(graph["nodes"])
                self.assertTrue(graph["edges"])
                self.assertEqual(graph["min_support"], 1)
                self.assertTrue(any(edge[3] == 1 for edge in graph["edges"]))
                for node in graph["nodes"]:
                    self.assertIsNotNone(parse_verse(node["id"]), node["id"])
                    for _neighbor, _weight, support, sources, _surprise in node["nb"]:
                        self.assertEqual(support, len(sources))
                        for source_id in sources:
                            self.assertTrue(0 <= source_id < source_count)
        for works in self.data["work_graphs"].values():
            for work in works:
                for source_id, verse_ids in work["sources"]:
                    self.assertTrue(0 <= source_id < source_count)
                    self.assertTrue(verse_ids)

    def test_requested_drilldowns_remain_available(self):
        self.assertIn("Musar", self.data["collection_layouts"])
        names = {work["name"] for work in self.data["work_graphs"]["Kabbalah"]}
        self.assertIn("Maaseh Rokeach on Mishnah", names)

    def test_locus_sources_have_total_weight_one(self):
        for category, modes in self.data["collection_previews"].items():
            locus = modes["loci"]
            self.assertAlmostEqual(
                locus["full"]["total_weight"],
                locus["full"]["supporting_sources"],
                places=1,
                msg=category,
            )


if __name__ == "__main__":
    unittest.main()
