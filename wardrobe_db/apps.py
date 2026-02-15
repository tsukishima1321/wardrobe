import sys
from django.apps import AppConfig


class WardrobeDbConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wardrobe_db'

    def ready(self):
        # Only load NLP model when running server, not during migrations or other commands
        # Check for 'runserver' command or if 'daphne' is the executable/command
        is_server = 'runserver' in sys.argv or any('daphne' in arg for arg in sys.argv)
        
        if is_server:
            # Load NLP Model
            try:
                from .nlp.model import nlp_engine
                # Load trained model if exists, it will also load user dictionary
                if nlp_engine.load():
                    print("NLP Model loaded successfully.")
                else:
                    print("NLP Model not found, please run 'python manage.py train_nlp' first.")
            except Exception as e:
                print(f"Warning: Failed to initialize NLP model: {e}")

            # Load OCR Model
            try:
                from .ocr import load_model
                load_model()
                print("OCR Model loaded successfully.")
            except Exception as e:
                print(f"Warning: Failed to initialize OCR model: {e}")
