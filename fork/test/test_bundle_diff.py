"""Unit tests for fork/bin/bundle_diff.py: pairing, noise filtering, output,
and the size-limited PR comment.

They need neither git nor node. Run from the repository root:
    python3 -I -m unittest discover -s fork/test -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

from bundle_diff import (
    COMMENT_MARKER,
    BundleFile,
    FileChange,
    pair_changes,
    readable_diff,
    render,
    render_comment,
)

JS = "web-app/build/static/js/"


class BundleFileTest(unittest.TestCase):
    def test_key_drops_content_hash(self):
        self.assertEqual(BundleFile(JS + "main.45669c2e.js").key, "js/main.js")
        self.assertEqual(BundleFile(JS + "182.6e133743.chunk.js").key, "js/182.chunk.js")
        self.assertEqual(
            BundleFile("web-app/build/static/css/main.e60e4760.css").key, "css/main.css"
        )

    def test_key_keeps_unhashed_name(self):
        self.assertEqual(BundleFile(JS + "vendor.js").key, "js/vendor.js")

    def test_parser_by_extension(self):
        self.assertEqual(BundleFile(JS + "main.45669c2e.js").parser, "babel")
        self.assertEqual(BundleFile("web-app/build/static/css/main.e60e4760.css").parser, "css")


class PairChangesTest(unittest.TestCase):
    def test_same_hash_is_unchanged(self):
        same = [BundleFile(JS + "8104.047c0527.chunk.js")]
        self.assertEqual(pair_changes(same, same), [])

    def test_changed_added_removed(self):
        old = [BundleFile(JS + "main.45669c2e.js"), BundleFile(JS + "99.aaaaaaaa.chunk.js")]
        new = [BundleFile(JS + "main.8f3a6a8e.js"), BundleFile(JS + "77.bbbbbbbb.chunk.js")]
        self.assertEqual(
            pair_changes(old, new),
            [
                FileChange("js/77.chunk.js", None, new[1]),
                FileChange("js/99.chunk.js", old[1], None),
                FileChange("js/main.js", old[0], new[0]),
            ],
        )


class ReadableDiffTest(unittest.TestCase):
    def test_real_change_kept_noise_dropped(self):
        old = 'a: "x",\n182: "6e133743",\n//# sourceMappingURL=main.45669c2e.js.map\n'
        new = 'a: "y",\n182: "7256c0d0",\n//# sourceMappingURL=main.8f3a6a8e.js.map\n'
        lines = readable_diff(old, new, "old", "new")
        changed = [line for line in lines if line[:1] in "+-" and not line.startswith(("---", "+++"))]
        self.assertEqual(changed, ['-a: "x",', '+a: "y",'])

    def test_noise_only_change_gives_no_diff(self):
        old = "code();\n" * 20 + "//# sourceMappingURL=a.11111111.js.map\n"
        new = "code();\n" * 20 + "//# sourceMappingURL=a.22222222.js.map\n"
        self.assertEqual(readable_diff(old, new, "old", "new"), [])

    def test_noise_only_hunk_dropped_real_hunk_kept(self):
        old = "real_old();\n" + "same();\n" * 20 + "//# sourceMappingURL=a.11111111.js.map\n"
        new = "real_new();\n" + "same();\n" * 20 + "//# sourceMappingURL=a.22222222.js.map\n"
        lines = readable_diff(old, new, "old", "new")
        self.assertEqual(sum(1 for line in lines if line.startswith("@@")), 1)
        self.assertIn("+real_new();", lines)


class RenderTest(unittest.TestCase):
    def test_unchanged(self):
        self.assertIn("bundle unchanged", render([], {}, "a", "b", markdown=False))

    def test_markdown_sections(self):
        change = FileChange(
            "js/main.js", BundleFile(JS + "main.45669c2e.js"), BundleFile(JS + "main.8f3a6a8e.js")
        )
        text = render([change], {"js/main.js": ["@@ -1 +1 @@", "-a", "+b"]}, "a", "b", True)
        self.assertIn("<details><summary><code>js/main.js</code></summary>", text)
        self.assertIn("```diff\n@@ -1 +1 @@\n-a\n+b\n```", text)

    def test_added_and_removed_listed(self):
        added = FileChange("js/7.chunk.js", None, BundleFile(JS + "7.aaaaaaaa.chunk.js"))
        removed = FileChange("js/9.chunk.js", BundleFile(JS + "9.bbbbbbbb.chunk.js"), None)
        text = render([added, removed], {}, "a", "b", markdown=False)
        self.assertIn("added: " + JS + "7.aaaaaaaa.chunk.js", text)
        self.assertIn("removed: " + JS + "9.bbbbbbbb.chunk.js", text)

    def test_markdown_added_removed_are_list_items(self):
        added = FileChange("js/7.chunk.js", None, BundleFile(JS + "7.aaaaaaaa.chunk.js"))
        text = render([added], {}, "a", "b", markdown=True)
        self.assertIn("- added: `" + JS + "7.aaaaaaaa.chunk.js`", text)


def _changed(key: str, lines: int) -> tuple[FileChange, list[str]]:
    """A changed file whose diff has `lines` lines of 10 characters."""
    name = key.removeprefix("js/").removesuffix(".js")
    change = FileChange(key, BundleFile(f"{JS}{name}.11111111.js"), BundleFile(f"{JS}{name}.22222222.js"))
    return change, ["+123456789"] * lines


class RenderCommentTest(unittest.TestCase):
    URL = "https://github.com/aursu/console/actions/runs/1"

    def test_marker_first_run_url_last(self):
        change, diff = _changed("js/main.js", 3)
        text = render_comment([change], {change.key: diff}, "a", "b", self.URL, 60000)
        self.assertTrue(text.startswith(COMMENT_MARKER + "\n"))
        self.assertTrue(text.rstrip().endswith(self.URL))
        self.assertNotIn("Too long", text)

    def test_unchanged(self):
        text = render_comment([], {}, "a", "b", self.URL, 60000)
        self.assertIn("bundle unchanged", text)
        self.assertIn(self.URL, text)

    def test_files_that_do_not_fit_are_named(self):
        small, small_diff = _changed("js/main.js", 3)
        big, big_diff = _changed("js/182.chunk.js", 1000)  # about 11 000 characters
        diffs = {small.key: small_diff, big.key: big_diff}
        text = render_comment([small, big], diffs, "a", "b", self.URL, 2000)
        self.assertLessEqual(len(text), 2000)
        self.assertIn("<code>js/main.js</code>", text)
        self.assertNotIn("<code>js/182.chunk.js</code>", text)
        self.assertIn("see the run summary:** `js/182.chunk.js`", text)

    def test_smaller_file_after_one_that_does_not_fit_is_shown(self):
        big, big_diff = _changed("js/182.chunk.js", 1000)
        small, small_diff = _changed("js/main.js", 3)
        diffs = {small.key: small_diff, big.key: big_diff}
        text = render_comment([big, small], diffs, "a", "b", self.URL, 2000)
        self.assertLessEqual(len(text), 2000)
        self.assertIn("<code>js/main.js</code>", text)
        self.assertIn("see the run summary:** `js/182.chunk.js`\n", text)


if __name__ == "__main__":
    unittest.main()
