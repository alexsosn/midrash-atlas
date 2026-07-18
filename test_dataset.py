import json
import os
import tempfile
import unittest

from dataset import VERSE_COUNTS, iter_records, parse_verse, sefaria_url


class DatasetExtractionTests(unittest.TestCase):
    def test_validates_chapter_and_verse(self):
        self.assertEqual(parse_verse("Genesis 1:31"), ("Genesis", 1, 31))
        self.assertIsNone(parse_verse("Genesis 1:32"))
        self.assertIsNone(parse_verse("Genesis 51:1"))
        self.assertEqual(parse_verse("Isaiah 66:24"), ("Isaiah", 66, 24))
        self.assertEqual(parse_verse("Psalms 119:176"), ("Psalms", 119, 176))
        self.assertEqual(
            parse_verse("II Chronicles 36:23"),
            ("II Chronicles", 36, 23),
        )
        self.assertIsNone(parse_verse("Psalms 119:177"))
        self.assertIsNone(parse_verse("Zohar 1:1"))

    def test_covers_complete_sefaria_tanakh_shape(self):
        self.assertEqual(len(VERSE_COUNTS), 39)
        self.assertEqual(sum(map(len, VERSE_COUNTS.values())), 929)
        self.assertEqual(sum(sum(chapters) for chapters in VERSE_COUNTS.values()), 23206)

    def test_clips_expanded_range_to_requested_chapter(self):
        link = {
            "anchorRef": "Genesis 1:31-2:2",
            "anchorRefExpanded": [
                "Genesis 1:31", "Genesis 1:32", "Genesis 2:1", "Genesis 2:2"
            ],
            "category": "Midrash",
            "index_title": "Example",
            "sourceRef": "Example 1:2:3",
            "type": "quotation",
        }
        with tempfile.TemporaryDirectory() as cache:
            for chapter in (1, 2):
                with open(os.path.join(cache, f"Genesis.{chapter}.json"), "w") as handle:
                    json.dump([link], handle)
            records = list(iter_records(cache))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["verses"], ["Genesis 1:31"])
        self.assertEqual(records[1]["verses"], ["Genesis 2:1", "Genesis 2:2"])
        self.assertEqual(records[0]["anchor_span"], 3)

    def test_builds_documented_url_form(self):
        self.assertEqual(
            sefaria_url("Rashi on Genesis 1:2:1"),
            "https://www.sefaria.org/Rashi_on_Genesis_1.2.1",
        )
        self.assertEqual(
            sefaria_url("II Samuel 1:1"),
            "https://www.sefaria.org/II_Samuel_1.1",
        )


if __name__ == "__main__":
    unittest.main()
