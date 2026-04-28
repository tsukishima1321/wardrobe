import sys
from django.apps import AppConfig


class WardrobeDbConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wardrobe_db'

    def ready(self) -> None:
        is_server = 'runserver' in sys.argv or any('daphne' in arg for arg in sys.argv)

        if is_server:
            try:
                from .nlp.model import nlp_engine
                if nlp_engine.load():
                    print("NLP Model loaded successfully.")
                else:
                    print("NLP Model not found, please run 'python manage.py train_nlp' first.")
            except Exception as e:
                print(f"Warning: Failed to initialize NLP model: {e}")

            try:
                from .ocr import load_model
                load_model()
                print("OCR Model loaded successfully.")
            except Exception as e:
                print(f"Warning: Failed to initialize OCR model: {e}")
