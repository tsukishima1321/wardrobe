import os
from typing import Any
from django.core.management.base import BaseCommand
from wardrobe_db.models import Pictures, Keywords, Properties

class Command(BaseCommand):

    def handle(self, *args: Any, **options: Any) -> None:
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
                'href': item.href,
                'text': item.description,
                'keywords': keywords,
                'properties': prop_dict
            })

        self.stdout.write(f"Exported {len(data)} items.")
        
        import json
        with open('training_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)