import unittest

from wardrobe_db.blog_content import (
    auto_title,
    collect_image_refs,
    count_words,
    extract_text_from_tiptap,
    highlight_snippet,
    make_excerpt,
    normalize_image_href,
    plain_text_to_doc,
    plain_text_to_html,
    sanitize_html,
)


class BlogContentTests(unittest.TestCase):
    def test_extract_text(self):
        doc = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "第一段"}]},
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "图片说明"},
                    {"type": "image", "attrs": {"href": "a" * 32 + ".jpg", "alt": "海边"}},
                ]},
                {"type": "bulletList", "content": [
                    {"type": "listItem", "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "列表项"}]}
                    ]}
                ]},
            ],
        }
        text = extract_text_from_tiptap(doc)
        self.assertIn("第一段", text)
        self.assertIn("海边", text)
        self.assertIn("列表项", text)

    def test_plain_text_roundtrip(self):
        doc = plain_text_to_doc("第一行\n\n第二行")
        self.assertEqual(doc["type"], "doc")
        self.assertEqual(len(doc["content"]), 3)
        html = plain_text_to_html("第一行\n\n第二行")
        self.assertIn("<p>第一行</p>", html)
        self.assertIn("<p><br></p>", html)
        self.assertIn("<p>第二行</p>", html)

    def test_sanitize_blocks_xss(self):
        dirty = (
            '<p onclick="alert(1)">hello</p>'
            '<script>alert(2)</script>'
            '<a href="javascript:alert(3)">bad</a>'
            '<img src="https://evil.example/a.jpg" onerror="alert(4)">'
        )
        clean = sanitize_html(dirty)
        self.assertNotIn("onclick", clean)
        self.assertNotIn("<script", clean)
        self.assertNotIn("javascript:", clean)
        self.assertNotIn("evil.example", clean)
        self.assertNotIn("onerror", clean)

    def test_sanitize_allows_internal_image(self):
        href = "a" * 32 + ".jpg"
        clean = sanitize_html(f'<img src="/imagebed/{href}" data-image-href="{href}" alt="图">')
        self.assertIn(f'/imagebed/{href}', clean)
        self.assertIn(f'data-image-href="{href}"', clean)

    def test_sanitize_image_ref_and_text_align(self):
        href = "d" * 32 + ".jpg"
        clean = sanitize_html(
            f'<a href="#/detail/{href}" data-image-ref="{href}" class="blog-image-ref">引用</a>'
            '<p style="text-align:center;color:red;position:fixed">居中</p>'
        )
        self.assertIn(f'data-image-ref="{href}"', clean)
        self.assertIn("text-align:center", clean)
        self.assertNotIn("color:red", clean)
        self.assertNotIn("position:fixed", clean)

    def test_collect_image_refs(self):
        href = "b" * 32 + ".png"
        doc = {
            "type": "doc",
            "content": [
                {"type": "image", "attrs": {"href": href, "alt": "alt", "caption": "caption"}},
                {"type": "gallery", "attrs": {"items": [{"href": href}, {"href": "bad/../x"}]}},
                {"type": "imageRef", "attrs": {"href": href, "label": "引用"}},
            ],
        }
        refs = collect_image_refs(doc)
        self.assertEqual(len(refs), 3)
        self.assertEqual(refs[0]["role"], "inline")
        self.assertEqual(refs[1]["role"], "gallery")
        self.assertEqual(refs[2]["role"], "reference")

    def test_normalize_href(self):
        href = "c" * 32 + ".webp"
        self.assertEqual(normalize_image_href(f"/imagebed/{href}"), href)
        self.assertEqual(normalize_image_href(f"/imagebed/thumbnails/large/{href}"), href)
        self.assertIsNone(normalize_image_href("https://example.com/a.jpg"))
        self.assertIsNone(normalize_image_href("../secret.jpg"))

    def test_highlight_snippet(self):
        text = "今天去了海边，海边的风很大。"
        result = highlight_snippet(text, ["海边"])
        self.assertIn("海边", result["text"])
        self.assertTrue(result["highlights"])
        start, end = result["highlights"][0]
        self.assertEqual(result["text"][start:end], "海边")

    def test_title_excerpt_words(self):
        self.assertEqual(auto_title("短句", "2026-10-17"), "2026-10-17")
        self.assertEqual(auto_title("", "2026-10-17"), "2026-10-17")
        self.assertLessEqual(len(make_excerpt("a" * 300, 20)), 20)
        self.assertGreater(count_words("hello 世界"), 0)


if __name__ == "__main__":
    unittest.main()
