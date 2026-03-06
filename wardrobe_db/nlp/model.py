import jieba
import pickle
import os
import logging
from collections import defaultdict, Counter
from django.conf import settings
from wardrobe_db.models import Keywords, Properties, UserDictionary

logger = logging.getLogger('nlp')


def nested_defaultdict():
    return defaultdict(Counter)

class WardrobeNLP:
    def __init__(self):
        self.keyword_probs = defaultdict(Counter) # {word: {keyword: count}}
        self.property_probs = defaultdict(nested_defaultdict) # {prop_name: {word: {value: count}}}
        self.keyword_totals = Counter()
        self.property_totals = defaultdict(Counter)
        self.word_totals = Counter()
        self.allowed_single_char_words = set()

        self.model_path = os.path.join(settings.BASE_DIR, 'wardrobe_db', 'nlp', 'data', 'model.pkl')
        self.vocab_loaded = False

    def load_user_dict(self):
        """
        从数据库加载自定义词典，增强分词效果
        """
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

    def refresh_user_dict(self):
        self.vocab_loaded = False
        self.load_user_dict()

    def _is_model_token(self, word):
        if not word:
            return False
        if len(word) > 1:
            return True
        return word in self.allowed_single_char_words

    def _tokenize_for_model(self, text):
        return {word for word in jieba.lcut(text) if self._is_model_token(word)}

    def train(self, data):
        """
        训练模型
        data: list of dict {'text': str, 'keywords': list, 'properties': dict}
        """
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
                        

    def update(self, text, keywords=None, properties=None, mode='add', update_word_counts=False):
        """
        实时更新模型的单条记录
        mode: 'add' | 'remove'
        """
        if not text:
            return

        words = list(self._tokenize_for_model(text))
        factor = 1 if mode == 'add' else -1
        
        if update_word_counts:
            for word in words:
                self.word_totals[word] += factor
                if self.word_totals[word] <= 0:
                    del self.word_totals[word]

        # 更新 Keywords
        if keywords:
            for kw in keywords:
                self.keyword_totals[kw] += factor
                # 防止计数变为负数（理论上数据一致时不应该发生，但为了安全）
                if self.keyword_totals[kw] < 0: self.keyword_totals[kw] = 0
                
                for word in words:
                    self.keyword_probs[word][kw] += factor
                    if self.keyword_probs[word][kw] <= 0:
                        if kw in self.keyword_probs[word]:
                            del self.keyword_probs[word][kw]
        
                # 如果某个词的映射现在为空，清理掉
                for word in words:
                    if word in self.keyword_probs and not self.keyword_probs[word]:
                        del self.keyword_probs[word]

        # 更新 Properties
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
                    
                    # 清理空的映射
                    for word in words:
                        if word in self.property_probs[name] and not self.property_probs[name][word]:
                            del self.property_probs[name][word]
        
        # 实时更新不需要立即保存到磁盘，可以依赖定期任务或手动保存，避免IO瓶颈
        # self.save()

    def predict(self, text, threshold=0.5):
        """
        预测
        """ 

        if not text:
            return {'keywords': [], 'properties': {}}

        if not self.vocab_loaded:
            self.load_user_dict()

        words = self._tokenize_for_model(text)
        
        kw_scores = defaultdict(float)
        for word in words:
            if word in self.keyword_probs:
                # P(Kw | Word) = Count(Word & Kw) / Count(Word)，在此基础上除以 P(Kw) 来降低高频关键词的影响，同时计算时加上平滑项避免低频关键词过度影响结果
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

        final_props = list() # [(prop_name, value, score)]
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

    def save(self):
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

    def load(self):
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
                self.load_user_dict() # 加载完模型顺便加载词典
                return True
            except Exception as e:
                print(f"Error loading model: {e}")
        return False

# 单例
nlp_engine = WardrobeNLP()
