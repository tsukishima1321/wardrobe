from django.core.management.base import BaseCommand
from wardrobe_db.models import Pictures
from wardrobe_db.views.collection_views import _generate_collection_thumbnail


class Command(BaseCommand):
    help = 'Regenerate thumbnails for all collections'

    def add_arguments(self, parser):
        parser.add_argument('--href', type=str, help='Only regenerate for a specific collection href')

    def handle(self, *args, **options):
        href = options.get('href')
        if href:
            collections = Pictures.objects.filter(href=href, is_collection=True)
        else:
            collections = Pictures.objects.filter(is_collection=True)

        total = collections.count()
        self.stdout.write(f'Found {total} collection(s) to regenerate.')

        for i, col in enumerate(collections, 1):
            self.stdout.write(f'[{i}/{total}] {col.href} — {col.description or "(no title)"}')
            try:
                _generate_collection_thumbnail(col.href)
                self.stdout.write(self.style.SUCCESS(f'  ✓ done'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {e}'))

        self.stdout.write(self.style.SUCCESS(f'Finished. {total} collection(s) processed.'))
