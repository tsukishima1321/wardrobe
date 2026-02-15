import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from wardrobe_db.nlp.model import WardrobeNLP

class Command(BaseCommand):
    help = 'Train the NLP model based on exported training data'

    def handle(self, *args, **options):
        data_path = os.path.join(settings.BASE_DIR, 'training_data.json')
        
        if not os.path.exists(data_path):
            self.stdout.write(self.style.ERROR(f"Data file not found: {data_path}"))
            return

        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not data:
            self.stdout.write(self.style.WARNING("No data found in training_data.json"))
            return

        nlp = WardrobeNLP()
        # Ensure user dict is loaded
        nlp.load_user_dict()
        
        self.stdout.write(f"Start training with {len(data)} samples...")
        nlp.train(data)
        nlp.save()
        
        self.stdout.write(self.style.SUCCESS("NLP model trained and saved successfully."))
