import jieba
import pickle
import os
import logging
from collections import defaultdict, Counter
from typing import Dict, Any, Optional, List, Set, Counter as CounterType, DefaultDict, Tuple, Union
from django.conf import settings
from wardrobe_db.models import Keywords, Properties, UserDictionary

logger = logging.getLogger('nlp')


def nested_defaultdict():
    return defaultdict(Counter)

class WardrobeNLP:
    def __init__(self) -> None:
        self.keyword_probs: DefaultDict[str, CounterType] = defaultdict(Counter)
        self.property_probs: DefaultDict[str, DefaultDict[str, CounterType]] = defaultdict(nested_defaultdict)
        self.keyword_totals: CounterType = Counter()
        self.property_totals: DefaultDict[str, CounterType] = defaultdict(Counter)
        self.word_totals: CounterType = Counter()
        self.allowed_single_char_words: Set[str] = set()
        self.model_path: str = os.path.join(settings.BASE_DIR, 'wardrobe_db', 'nlp', 'data', 'model.pkl')
        self.vocab_loaded: bool = False

    def load_user_dict(self) -> None:
        if self.vocab_loaded:
            return

        print("Loading user dictionary for segmentation...")
        keywords = Keywords.objects.values_list('keyword', flat=True).distinct()
        properties = Properties.objects.values_list('value', flat=True).distinct()
        user_words = UserDictionary.objects.values_list('word', flat=True).distinct()
        print(f"Loaded {len(keywords)} unique keywords, {len(properties)} unique property values, and {len(user_words)} user dictionary words from the database.")

        self.allowed_single_char_words = {w for w in user_words if w and len(w) == 1}
        
        count = 0
        for word in set(keywords) | set(properties) | set(user_words):
            if word:
                jieba.add_word(word, freq=20000)
                count += 1
        print(f"Loaded {count} words into user dictionary.")
        self.vocab_loaded = True

    def refresh_user_dict(self) -> None:
        self.vocab_loaded = False
        self.load_user_dict()

    def _is_model_token(self, word: str) -> bool:
        if not word:
            return False
        if len(word) > 1:
            return True
        return word in self.allowed_single_char_words

    def _tokenize_for_model(self, text: str) -> Set[str]:
        return {word for word in jieba.lcut(text) if self._is_model_token(word)}

    def train(self, data: List[Dict[str, Any]]) -> None:
        self.keyword_probs = defaultdict(Counter)
        self.property_probs = defaultdict(nested_defaultdict)
        self.keyword_totals = Counter()
        self.property_totals = defaultdict(Counter)
        self.word_totals = Counter()

        print(f"Training on {len(data)} items...")
        
        for item in data:
            text = item.get('text', '')
            if not text:
                continue
                
            words = list(self._tokenize_for_model(text))
            
            for word in words:
                self.word_totals[word] += 1

            for kw in item.get('keywords', []):
                self.keyword_totals[kw] += 1
                for word in words:
                    self.keyword_probs[word][kw] += 1
            
            for name, values_list in item.get('properties', {}).items():
                if not isinstance(values_list, list):
                    values_list = [values_list]
                
                for value in values_list:
                    self.property_totals[name][value] += 1
                    for word in words:
                        self.property_probs[name][word][value] += 1
                        

    def update(self, text: str, keywords: Optional[List[str]] = None, properties: Optional[Dict[str, Any]] = None, mode: str = 'add', update_word_counts: bool = False) -> None:
        if not text:
            return

        words = list(self._tokenize_for_model(text))
        factor = 1 if mode == 'add' else -1
        
        if update_word_counts:
            for word in words:
                self.word_totals[word] += factor
                if self.word_totals[word] <= 0:
                    del self.word_totals[word]


        if keywords:
            for kw in keywords:
                self.keyword_totals[kw] += factor

                if self.keyword_totals[kw] < 0: self.keyword_totals[kw] = 0
                
                for word in words:
                    self.keyword_probs[word][kw] += factor
                    if self.keyword_probs[word][kw] <= 0:
                        if kw in self.keyword_probs[word]:
                            del self.keyword_probs[word][kw]
        

                for word in words:
                    if word in self.keyword_probs and not self.keyword_probs[word]:
                        del self.keyword_probs[word]


        if properties:
            for name, values_list in properties.items():
                if not isinstance(values_list, list):
                    values_list = [values_list]
                
                for value in values_list:
                    self.property_totals[name][value] += factor
                    if self.property_totals[name][value] < 0: self.property_totals[name][value] = 0

                    for word in words:
                        self.property_probs[name][word][value] += factor
                        if self.property_probs[name][word][value] <= 0:
                            if value in self.property_probs[name][word]:
                                del self.property_probs[name][word][value]
                    

                    for word in words:
                        if word in self.property_probs[name] and not self.property_probs[name][word]:
                            del self.property_probs[name][word]
        


    def predict(self, text: str, threshold: float = 0.5) -> Dict[str, Any]:


        if not text:
            return {'keywords': [], 'properties': {}}

        if not self.vocab_loaded:
            self.load_user_dict()

        words = self._tokenize_for_model(text)
        
        kw_scores = defaultdict(float)
        for word in words:
            if word in self.keyword_probs:

                word_total = self.word_totals[word]
                if word_total > 0:
                    for kw, count in self.keyword_probs[word].items():
                        keyword_totals_sum = sum(self.keyword_totals.values())
                        prob = count / word_total / ((self.keyword_totals[kw] + keyword_totals_sum / len(self.keyword_totals) * 2) / keyword_totals_sum)
                        kw_scores[kw] += prob

        max_kw_score = max(kw_scores.values(), default=0)
        threshold_score = max(5, max_kw_score * threshold)

        sorted_kws = sorted(kw_scores.items(), key=lambda x: x[1], reverse=True)

        final_keywords = [k for k, s in sorted_kws if s > threshold_score][:4]

        final_props = list()
        for prop_name, word_map in self.property_probs.items():
            prop_scores = defaultdict(float)
            for word in words:
                if word in word_map:
                    word_total = self.word_totals[word]
                    if word_total > 0:
                        for val, count in word_map[word].items():
                            s = sum(self.property_totals[prop_name].values())
                            prob = count / word_total / ((self.property_totals[prop_name][val] + s / len(self.property_totals[prop_name]) * 2) / s)
                            prop_scores[val] += prob
            
            if prop_scores:
                final_props.extend([(prop_name, val, score) for val, score in prop_scores.items()])

        max_score = max((score for _, _, score in final_props), default=0)
        threshold_score = max(5, max_score * threshold)
        final_props = [(p, v, s) for p, v, s in final_props if s >= threshold_score]
        
        final_props = sorted(final_props, key=lambda x: x[2], reverse=True)[:4]

        formatted_props = [{'name': p[0], 'value': p[1], 'score': p[2]} for p in final_props]

        return {
            'keywords': final_keywords,
            'properties': formatted_props
        }

    def save(self) -> None:
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'keyword_probs': self.keyword_probs,
                    'property_probs': self.property_probs,
                    'keyword_totals': self.keyword_totals,
                    'property_totals': self.property_totals,
                    'word_totals': self.word_totals
                }, f)
            print(f"Model saved to {self.model_path}")
        except Exception as e:
            print(f"Error saving model: {e}")

    def load(self) -> bool:
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.keyword_probs = data['keyword_probs']
                    self.property_probs = data['property_probs']
                    self.keyword_totals = data.get('keyword_totals', Counter())
                    self.property_totals = data.get('property_totals', defaultdict(Counter))
                    self.word_totals = data.get('word_totals', Counter())
                print("Model loaded successfully.")
                self.load_user_dict()
                return True
            except Exception as e:
                print(f"Error loading model: {e}")
        return False

nlp_engine = WardrobeNLP()
