from typing import Optional, Any

from django.db.models import Model


class BusinessDBRouter:

    def db_for_read(self, model: Model, **hints: Any) -> Optional[str]:
        if model._meta.app_label == 'wardrobe_db':
            return 'business'
        return 'default'

    def db_for_write(self, model: Model, **hints: Any) -> Optional[str]:
        if model._meta.app_label == 'wardrobe_db':
            return 'business'
        return 'default'

    def allow_relation(self, obj1: Model, obj2: Model, **hints: Any) -> Optional[bool]:
        db_obj1 = self.db_for_read(obj1)
        db_obj2 = self.db_for_read(obj2)
        if db_obj1 and db_obj2:
            return db_obj1 == db_obj2
        return None

    def allow_migrate(self, db: str, app_label: str, model_name: Optional[str] = None, **hints: Any) -> bool:
        if app_label == 'wardrobe_db':
            return db == 'business'
        else:
            return db == 'default'