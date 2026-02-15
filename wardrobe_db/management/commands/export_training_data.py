import csv
import os
from django.core.management.base import BaseCommand
from wardrobe_db.models import Pictures, Keywords, Properties

class Command(BaseCommand):
    help = 'Export description, keywords, and properties for ML training'

    def handle(self, *args, **options):
        # 获取所有有描述的图片
        items = Pictures.objects.exclude(description__isnull=True).exclude(description__exact='')
        
        data = []
        for item in items:
            # 获取关联的 keywords
            keywords = list(Keywords.objects.filter(href=item).values_list('keyword', flat=True))
            
            # 获取关联的 properties
            # 将属性转换为 key:value 格式，或者分别存储
            props = Properties.objects.filter(href=item)
            prop_dict = {p.property_name: p.value for p in props}
            
            data.append({
                'href': item.href,
                'text': item.description,
                'keywords': keywords, # List of strings
                'properties': prop_dict # Dictionary
            })

        self.stdout.write(f"Exported {len(data)} items.")
        
        # 这里你可以选择保存为 JSON 或 CSV，建议保存为 JSON 方便处理嵌套结构
        import json
        with open('training_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)