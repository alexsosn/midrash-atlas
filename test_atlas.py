import json
import os
import unittest

from dataset import BOOK_SECTIONS, VERSE_COUNTS, parse_verse


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
            "6.2-most-specific-link-dedup",
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
        for modes in self.data["graphs"].values():
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
        self.assertIn("Musar", self.data["graphs"])
        names = {work["name"] for work in self.data["work_graphs"]["Kabbalah"]}
        self.assertIn("Maaseh Rokeach on Mishnah", names)

    def test_locus_sources_have_total_weight_one(self):
        for category, modes in self.data["graphs"].items():
            locus = modes["loci"]
            self.assertAlmostEqual(
                locus["full"]["total_weight"],
                locus["full"]["supporting_sources"],
                places=1,
                msg=category,
            )


if __name__ == "__main__":
    unittest.main()
