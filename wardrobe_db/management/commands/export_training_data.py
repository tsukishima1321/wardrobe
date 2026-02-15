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
            # 将属性转换为 key:[values] 格式，一个propertyName可能对应多个values
            props = Properties.objects.filter(href=item)
            prop_dict = {}
            for p in props:
                if p.property_name not in prop_dict:
                    prop_dict[p.property_name] = []
                prop_dict[p.property_name].append(p.value)
            
            data.append({
                'href': item.href,
                'text': item.description,
                'keywords': keywords, # List of strings
                'properties': prop_dict # Dictionary with list values
            })

        self.stdout.write(f"Exported {len(data)} items.")
        
        # 这里你可以选择保存为 JSON 或 CSV，建议保存为 JSON 方便处理嵌套结构
        import json
        with open('training_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)