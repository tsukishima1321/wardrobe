class BusinessDBRouter:
    """
    A router to control operations on models in the business application.
    """

    def db_for_read(self, model, **hints):
        """Directs read operations for business app models to 'business'."""
        if model._meta.app_label == 'wardrobe_db':
            return 'business'
        return 'default'

    def db_for_write(self, model, **hints):
        """Directs write operations for business app models to 'business'."""
        if model._meta.app_label == 'wardrobe_db':
            return 'business'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allows relations if both models are in the same database."""
        db_obj1 = self.db_for_read(obj1)
        db_obj2 = self.db_for_read(obj2)
        if db_obj1 and db_obj2:
            return db_obj1 == db_obj2
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensures that the business app's models get created on the right database."""
        if app_label == 'wardrobe_db':
            return db == 'business'
        else:
            return db == 'default'