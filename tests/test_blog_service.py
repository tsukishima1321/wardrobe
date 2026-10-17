import datetime
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wardrobe.settings")
os.environ.setdefault("django_secret_key", "test")
os.environ.setdefault("wardrobe_db_password", "test")
os.environ.setdefault("wardrobe_localhost", "http://127.0.0.1:8000")
os.environ.setdefault("wardrobe_backupdir", "/tmp/opencode/backups")

import django

django.setup()

from wardrobe_db import blog_service


class BlogServicePureTests(unittest.TestCase):
    def test_normalize_tags(self):
        self.assertEqual(blog_service.normalize_tags(" 旅行，日常,旅行 "), ["旅行", "日常"])
        self.assertEqual(blog_service.normalize_tags(["a", "A", "b"]), ["a", "b"])
        self.assertEqual(len(blog_service.normalize_tags([str(i) for i in range(30)])), 20)

    def test_parse_date(self):
        self.assertEqual(blog_service.parse_date("2026-10-17"), datetime.date(2026, 10, 17))
        with self.assertRaises(ValueError):
            blog_service.parse_date("not-a-date")


class BlogImageSyncTests(unittest.TestCase):
    def make_post(self):
        post = MagicMock()
        post.title = "标题"
        post.date = datetime.date(2026, 10, 17)
        post.cover_image_href = None
        post.tags.all.return_value = []
        post.image_links.exclude.return_value.delete.return_value = None
        return post

    def doc(self, href):
        return {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "正文"}]},
            {"type": "image", "attrs": {"href": href, "alt": "图"}},
        ]}

    @patch("wardrobe_db.blog_service.BlogPostImage")
    @patch("wardrobe_db.blog_service.CollectionItems")
    @patch("wardrobe_db.blog_service.Pictures")
    def test_existing_picture_links_without_creating(self, pictures, collection_items, image_links):
        href = "a" * 32 + ".jpg"
        pictures.objects.filter.return_value.first.return_value = MagicMock()
        collection_items.objects.filter.return_value.select_related.return_value.first.return_value = None
        post = self.make_post()

        warnings = blog_service.sync_post_images(post, self.doc(href))

        self.assertEqual(warnings, [])
        pictures.objects.create.assert_not_called()
        image_links.objects.update_or_create.assert_called_once()
        kwargs = image_links.objects.update_or_create.call_args.kwargs
        self.assertEqual(kwargs["post"], post)
        self.assertEqual(kwargs["image_href"], href)
        self.assertEqual(kwargs["defaults"]["role"], "inline")
        self.assertEqual(kwargs["defaults"]["collection_href"], None)

    @patch("wardrobe_db.blog_service._image_file_exists", return_value=True)
    @patch("wardrobe_db.blog_service.Keywords")
    @patch("wardrobe_db.blog_service.PicturesOcr")
    @patch("wardrobe_db.blog_service.BlankPictures")
    @patch("wardrobe_db.blog_service.BlogPostImage")
    @patch("wardrobe_db.blog_service.CollectionItems")
    @patch("wardrobe_db.blog_service.Pictures")
    def test_missing_picture_is_created(self, pictures, collection_items, image_links, blanks, ocr, keywords, _exists):
        href = "b" * 32 + ".png"
        pictures.objects.filter.return_value.first.return_value = None
        collection_items.objects.filter.return_value.select_related.return_value.first.return_value = None
        post = self.make_post()

        blog_service.sync_post_images(post, self.doc(href))

        pictures.objects.create.assert_called_once()
        self.assertEqual(pictures.objects.create.call_args.kwargs["href"], href)
        blanks.objects.filter.assert_called_once_with(href=href)
        ocr.objects.get_or_create.assert_called_once()
        image_links.objects.update_or_create.assert_called_once()
        kwargs = image_links.objects.update_or_create.call_args.kwargs
        self.assertEqual(kwargs["defaults"]["origin"], "auto")

    @patch("wardrobe_db.blog_service.BlogPostImage")
    @patch("wardrobe_db.blog_service.CollectionItems")
    @patch("wardrobe_db.blog_service.Pictures")
    def test_collection_item_resolves_parent_collection(self, pictures, collection_items, image_links):
        href = "c" * 32 + ".webp"
        pictures.objects.filter.return_value.first.return_value = None
        item = MagicMock()
        item.collection_id = "collection-hash"
        collection_items.objects.filter.return_value.select_related.return_value.first.return_value = item
        post = self.make_post()

        blog_service.sync_post_images(post, self.doc(href))

        pictures.objects.create.assert_not_called()
        kwargs = image_links.objects.update_or_create.call_args.kwargs
        self.assertEqual(kwargs["defaults"]["collection_href"], "collection-hash")


if __name__ == "__main__":
    unittest.main()
