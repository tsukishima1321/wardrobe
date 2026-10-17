"""Retitle entries migrated from legacy DiaryTexts to plain date strings.

Run after migrate_diary_to_blog. Idempotent.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from wardrobe_db.models import BlogPost


class Command(BaseCommand):
    help = "Set migrated diary titles to YYYY-MM-DD (only rows with legacy_diary_id)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report changes.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of rows to update.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        posts = BlogPost.objects.filter(legacy_diary_id__isnull=False).order_by("id")
        if limit:
            posts = posts[:limit]

        total = 0
        changed = 0
        skipped = 0
        for post in posts.iterator(chunk_size=200):
            total += 1
            new_title = post.date.strftime("%Y-%m-%d") if post.date else ""
            if not new_title or post.title == new_title:
                skipped += 1
                continue
            if dry_run:
                changed += 1
                if changed <= 3:
                    self.stdout.write(f"[dry-run] #{post.id}: {post.title!r} -> {new_title!r}")
                continue
            with transaction.atomic():
                post.title = new_title
                post.save(update_fields=["title", "updated_at"])
            changed += 1

        mode = "dry-run" if dry_run else "updated"
        self.stdout.write(self.style.SUCCESS(
            f"{mode}: total={total}, changed={changed}, skipped={skipped}"
        ))
