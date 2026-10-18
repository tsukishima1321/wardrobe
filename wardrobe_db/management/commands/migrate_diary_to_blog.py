"""Migrate legacy DiaryTexts rows into BlogPost.

Run after applying django/sql/20261017_blog.sql.
"""

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from wardrobe_db.blog_content import (
    count_words,
    make_excerpt,
    plain_text_to_doc,
    plain_text_to_html,
    sanitize_html,
)
from wardrobe_db.models import BlogPost, DiaryTexts


class Command(BaseCommand):
    help = "Migrate legacy diary_texts into blog_posts (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report what would be migrated.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of rows to migrate.")
        parser.add_argument("--batch-size", type=int, default=100, help="Batch size for reporting.")
        parser.add_argument("--refresh-existing", action="store_true",
                            help="Rebuild content for already migrated rows (keeps title/date/tags).")
        parser.add_argument("--force", action="store_true",
                            help="With --refresh-existing, overwrite rows whose content_text was edited.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        batch_size = max(1, options["batch_size"])
        refresh_existing = options["refresh_existing"]
        force = options["force"]

        legacy_rows = DiaryTexts.objects.order_by("date", "id")
        if limit:
            legacy_rows = legacy_rows[:limit]

        total = 0
        created = 0
        refreshed = 0
        skipped = 0
        for diary in legacy_rows.iterator(chunk_size=batch_size):
            total += 1
            existing = BlogPost.objects.filter(legacy_diary_id=diary.id).first()

            text = (diary.text or "").strip()
            if not text:
                skipped += 1
                continue

            date_str = diary.date.strftime("%Y-%m-%d")
            doc = plain_text_to_doc(text)
            html = sanitize_html(plain_text_to_html(text))
            excerpt = make_excerpt(text, 500)
            word_count = count_words(text)

            if existing is not None:
                if not refresh_existing:
                    skipped += 1
                    continue
                if not force and existing.content_text != text:
                    skipped += 1
                    continue
                if dry_run:
                    refreshed += 1
                    if refreshed <= 3:
                        self.stdout.write(f"[dry-run] refresh #{existing.id} from diary #{diary.id}")
                    continue
                with transaction.atomic():
                    BlogPost.objects.filter(pk=existing.pk).update(
                        content_json=doc,
                        content_html=html,
                        content_text=text,
                        excerpt=excerpt,
                        word_count=word_count,
                        updated_at=timezone.now(),
                    )
                refreshed += 1
                if refreshed % batch_size == 0:
                    self.stdout.write(f"refreshed {refreshed} rows...")
                continue

            created_at = datetime.datetime.combine(diary.date, datetime.time.min)
            if dry_run:
                created += 1
                if created <= 3:
                    self.stdout.write(f"[dry-run] diary #{diary.id} -> {date_str!r}")
                continue

            with transaction.atomic():
                post = BlogPost.objects.create(
                    title=date_str,
                    kind="note",
                    status="published",
                    date=diary.date,
                    content_json=doc,
                    content_html=html,
                    content_text=text,
                    excerpt=excerpt,
                    word_count=word_count,
                    legacy_diary_id=diary.id,
                    published_at=created_at,
                )
                BlogPost.objects.filter(pk=post.pk).update(
                    created_at=created_at,
                    updated_at=created_at,
                )
            created += 1
            if created % batch_size == 0:
                self.stdout.write(f"migrated {created} rows...")

        mode = "dry-run" if dry_run else "migrated"
        self.stdout.write(self.style.SUCCESS(
            f"{mode}: total={total}, created={created}, refreshed={refreshed}, skipped={skipped}"
        ))
