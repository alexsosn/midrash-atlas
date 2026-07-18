import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def read_template():
    with open(os.path.join(HERE, "atlas_template.html"), encoding="utf-8") as handle:
        return handle.read()


def dict_keys(source, block_start):
    """Extract top-level keys of a JS object literal starting at block_start."""
    depth = 0
    keys = []
    for index, line in enumerate(source[block_start:].splitlines()):
        depth += line.count("{") - line.count("}")
        if depth <= 0 and keys:
            break
        if index == 0:
            continue  # the block opener itself ("en: {") is not a key
        match = re.match(r'\s*"?([A-Za-z0-9_.]+)"?\s*:', line)
        if match and depth == 1:
            keys.append(match.group(1))
    return keys


class LocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = read_template()

    def test_every_static_key_has_an_english_translation(self):
        en_block = self.template.index("const L10N_EN = {")
        en_keys = set(dict_keys(self.template, en_block))
        used = set(re.findall(r'data-i18n(?:-aria)?="([^"]+)"', self.template))
        self.assertTrue(used)
        missing = used - en_keys
        self.assertFalse(missing, f"data-i18n keys without an English string: {sorted(missing)}")

    def test_dynamic_message_dictionaries_are_parallel(self):
        uk_start = self.template.index("uk: {", self.template.index("const MSG = {"))
        en_start = self.template.index("en: {", self.template.index("const MSG = {"))
        uk_keys = dict_keys(self.template, uk_start)
        en_keys = dict_keys(self.template, en_start)
        self.assertTrue(uk_keys)
        self.assertEqual(sorted(uk_keys), sorted(en_keys))

    def test_language_plumbing_is_present(self):
        for fragment in (
            'id="lang-toggle"',
            "function detectLang()",
            "function captureUk()",
            "function applyStatic()",
            "function setLang(",
            'localStorage.getItem("atlas-lang")',
        ):
            self.assertIn(fragment, self.template)


if __name__ == "__main__":
    unittest.main()
