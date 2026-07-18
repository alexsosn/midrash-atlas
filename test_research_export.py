import csv
import json
import os
import tempfile
import unittest

from research_export import export_bundle


HERE = os.path.dirname(os.path.abspath(__file__))


class ResearchExportTests(unittest.TestCase):
    def test_work_bundle_has_long_form_exact_source_evidence(self):
        with tempfile.TemporaryDirectory() as output:
            manifest = export_bundle(
                os.path.join(HERE, "atlas_data.json"),
                output,
                category="Kabbalah",
                work_name="Maaseh Rokeach on Mishnah",
                mode="loci",
                min_support=1,
            )
            with open(os.path.join(output, "edge-evidence.csv"), encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            with open(os.path.join(output, "nodes.csv"), encoding="utf-8") as handle:
                nodes = list(csv.DictReader(handle))
            with open(os.path.join(output, "manifest.json"), encoding="utf-8") as handle:
                saved_manifest = json.load(handle)

        self.assertEqual(saved_manifest["atlas"]["sha256"], manifest["atlas"]["sha256"])
        self.assertEqual(manifest["selection"]["min_support"], 1)
        self.assertIn("not limited", manifest["scope"])
        self.assertEqual(len(nodes), manifest["counts"]["nodes"])
        self.assertEqual(len(rows), manifest["counts"]["evidence_rows"])
        self.assertGreater(manifest["counts"]["edges"], 0)
        self.assertTrue(all(row["source_ref"] for row in rows))
        self.assertTrue(all(row["source_url"].startswith("https://www.sefaria.org/") for row in rows))
        self.assertTrue(all(int(row["source_support"]) >= 1 for row in rows))

    def test_unknown_work_is_rejected(self):
        with tempfile.TemporaryDirectory() as output:
            with self.assertRaisesRegex(ValueError, "unknown work"):
                export_bundle(
                    os.path.join(HERE, "atlas_data.json"),
                    output,
                    category="Musar",
                    work_name="Not a Sefaria work",
                )

    def test_empty_filter_is_reported_as_researcher_error(self):
        with tempfile.TemporaryDirectory() as output:
            with self.assertRaisesRegex(ValueError, "leave no evidence edges"):
                export_bundle(
                    os.path.join(HERE, "atlas_data.json"),
                    output,
                    category="Kabbalah",
                    work_name="Maaseh Rokeach on Mishnah",
                    min_support=10_000,
                )


if __name__ == "__main__":
    unittest.main()
