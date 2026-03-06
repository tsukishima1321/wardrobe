import json
import pickle
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from collections import defaultdict, Counter

def convert_to_dict(obj):
    """
    Recursively convert defaultdict and Counter to standard dicts for JSON serialization.
    """
    if isinstance(obj, (defaultdict, Counter)):
        return {k: convert_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, dict):
        return {k: convert_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_dict(i) for i in obj]
    else:
        return obj

class Command(BaseCommand):
    help = 'Export the NLP model pickle file to JSON for inspection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'wardrobe_db', 'nlp', 'data', 'model.json'),
            help='Output JSON file path'
        )

    def handle(self, *args, **options):
        pkl_path = os.path.join(settings.BASE_DIR, 'wardrobe_db', 'nlp', 'data', 'model.pkl')
        json_path = options['output']

        if not os.path.exists(pkl_path):
            self.stdout.write(self.style.ERROR(f"Model file not found at: {pkl_path}"))
            return

        self.stdout.write(f"Loading pickle from {pkl_path}...")
        try:
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to load pickle: {e}"))
            return

        self.stdout.write("Converting data structures to JSON-compatible format...")
        json_data = convert_to_dict(data)

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Successfully exported model to {json_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to write JSON: {e}"))
