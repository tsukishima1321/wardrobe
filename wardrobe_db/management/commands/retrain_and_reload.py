import json
import os
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from wardrobe_db.nlp.model import WardrobeNLP
from wardrobe_db.models import Pictures, Keywords, Properties

class Command(BaseCommand):
    help = 'Retrain the NLP model and notify running server to reload'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-reload',
            action='store_true',
            help='Do not notify server to reload (train only)',
        )
        parser.add_argument(
            '--api-url',
            type=str,
            default='http://localhost:8000/metadata/reload/',
            help='URL to trigger model reload'
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting NLP model retraining...")
        
        # 1. Export Data (Memory-efficient way, no need to write to JSON file)
        self.stdout.write("Fetching data from database...")
        items = Pictures.objects.exclude(description__isnull=True).exclude(description__exact='')
        data = []
        for item in items:
            keywords = list(Keywords.objects.filter(href=item).values_list('keyword', flat=True))
            props = Properties.objects.filter(href=item)
            prop_dict = {}
            for p in props:
                if p.property_name not in prop_dict:
                    prop_dict[p.property_name] = []
                prop_dict[p.property_name].append(p.value)
            
            data.append({
                'text': item.description,
                'keywords': keywords, 
                'properties': prop_dict 
            })
            
        if not data:
            self.stdout.write(self.style.WARNING("No training data found."))
            return

        # 2. Train Model
        self.stdout.write(f"Training on {len(data)} samples...")
        nlp = WardrobeNLP()
        nlp.load_user_dict() # Ensure dict is fresh
        nlp.train(data)
        nlp.save()
        self.stdout.write(self.style.SUCCESS("Model trained and saved to disk."))

        # 3. Notify Server to Reload
        if not options['no_reload']:
            url = options['api_url']
            try:
                self.stdout.write(f"Notifying server at {url}...")
                # Assuming you set up some internal simple auth or allow localhost
                resp = requests.post(url, timeout=5)
                if resp.status_code == 200:
                    self.stdout.write(self.style.SUCCESS("Server successfully reloaded the model."))
                else:
                    self.stdout.write(self.style.ERROR(f"Server returned error: {resp.status_code} {resp.text}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to notify server: {e}"))
                self.stdout.write(self.style.WARNING("Tip: Make sure API server is running and URL is correct."))
