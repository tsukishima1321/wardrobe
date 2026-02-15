import jieba
import pickle
import os
from collections import defaultdict, Counter
from django.conf import settings
from wardrobe_db.models import Keywords, Properties


def nested_defaultdict():
    return defaultdict(Counter)

class WardrobeNLP:
    def __init__(self):
        self.keyword_probs = defaultdict(Counter) # {word: {keyword: count}}
        self.property_probs = defaultdict(nested_defaultdict) # {prop_name: {word: {value: count}}}
        self.keyword_totals = Counter()
        self.property_totals = defaultdict(Counter)

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
        
        count = 0
        for word in set(keywords) | set(properties):
            if word and len(word) > 1:
                jieba.add_word(word, freq=20000)
                count += 1
        print(f"Loaded {count} words into user dictionary.")
        self.vocab_loaded = True

    def train(self, data):
        """
        训练模型
        data: list of dict {'text': str, 'keywords': list, 'properties': dict}
        """
        self.keyword_probs = defaultdict(Counter)
        self.property_probs = defaultdict(nested_defaultdict)
        self.keyword_totals = Counter()
        self.property_totals = defaultdict(Counter)

        print(f"Training on {len(data)} items...")
        
        for item in data:
            text = item.get('text', '')
            if not text:
                continue
                
            words = list(set(jieba.lcut(text))) # 使用 set 去重，一个词在一句话里出现多次只算一次关联
            
            # 训练 Keywords
            for kw in item.get('keywords', []):
                self.keyword_totals[kw] += 1
                for word in words:
                    if len(word) > 1: # 忽略单字
                        self.keyword_probs[word][kw] += 1
            
            # 训练 Properties
            # value是一个列表
            for name, values_list in item.get('properties', {}).items():
                if not isinstance(values_list, list):
                    values_list = [values_list]
                
                for value in values_list:
                    self.property_totals[name][value] += 1
                    for word in words:
                        if len(word) > 1:
                            self.property_probs[name][word][value] += 1
                        

    def update(self, text, keywords=None, properties=None, mode='add'):
        """
        实时更新模型的单条记录
        mode: 'add' | 'remove'
        """
        if not text:
            return

        words = list(set(jieba.lcut(text)))
        factor = 1 if mode == 'add' else -1

        # 更新 Keywords
        if keywords:
            for kw in keywords:
                self.keyword_totals[kw] += factor
                # 防止计数变为负数（理论上数据一致时不应该发生，但为了安全）
                if self.keyword_totals[kw] < 0: self.keyword_totals[kw] = 0
                
                for word in words:
                    if len(word) > 1:
                        self.keyword_probs[word][kw] += factor
                        if self.keyword_probs[word][kw] <= 0:
                            if kw in self.keyword_probs[word]:
                                del self.keyword_probs[word][kw]
        
                # 如果某个词的映射现在为空，清理掉
                for word in words:
                    if len(word) > 1 and word in self.keyword_probs and not self.keyword_probs[word]:
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
                        if len(word) > 1:
                            self.property_probs[name][word][value] += factor
                            if self.property_probs[name][word][value] <= 0:
                                if value in self.property_probs[name][word]:
                                    del self.property_probs[name][word][value]
                    
                    # 清理空的映射
                    for word in words:
                        if len(word) > 1 and word in self.property_probs[name] and not self.property_probs[name][word]:
                            del self.property_probs[name][word]
        
        # 实时更新不需要立即保存到磁盘，可以依赖定期任务或手动保存，避免IO瓶颈
        # self.save()

    def predict(self, text, threshold=0.3):
        """
        预测
        """ 

        if not text:
            return {'keywords': [], 'properties': {}}

        words = set(jieba.lcut(text))
        
        # 预测 Keywords
        kw_scores = defaultdict(float)
        for word in words:
            if word in self.keyword_probs:
                for kw, count in self.keyword_probs[word].items():
                    # P(Kw|Word) = Count(Word, Kw) / Total(Kw) * IDF_Like_Weight?
                    # 简化版：直接累加关联度
                    # 使用稍微平滑一点的概率: count / (total_kw_occurrence + 10)
                    # 或者更简单的：如果这个词出现，包含这个keyword的概率是多少？
                    # P(Kw | Word) = Count(Word & Kw) / Count(Word)
                    # 这里我们没存 Count(Word)，暂时用 Count(Word & Kw) 代替作为得分
                    kw_scores[kw] += count
        
        # 归一化并排序
        # 简单的阈值切分
        sorted_kws = sorted(kw_scores.items(), key=lambda x: x[1], reverse=True)
        final_keywords = [k for k, s in sorted_kws if s > 5] # 这里的 5 是硬编码的魔法数字，表示至少只要有几个强关联词或者多次共现

        # 预测 Properties
        # 支持多值预测，返回格式 {prop_name: [val1, val2]}
        final_props = defaultdict(list)
        for prop_name, word_map in self.property_probs.items():
            prop_scores = defaultdict(float)
            for word in words:
                if word in word_map:
                    for val, count in word_map[word].items():
                        prop_scores[val] += count
            
            if prop_scores:
                # 不再只取 max，而是取所有高分值
                # 动态阈值：比如最高分的 50% 以上
                max_score = max(prop_scores.values())
                threshold_score = max(3, max_score * 0.5)
                
                valid_vals = [val for val, score in prop_scores.items() if score >= threshold_score]
                if valid_vals:
                    final_props[prop_name] = valid_vals

        return {
            'keywords': final_keywords[:10], # 限制数量
            'properties': dict(final_props)
        }

    def save(self):
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'keyword_probs': self.keyword_probs,
                    'property_probs': self.property_probs,
                    'keyword_totals': self.keyword_totals,
                    'property_totals': self.property_totals
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
                print("Model loaded successfully.")
                self.load_user_dict() # 加载完模型顺便加载词典
                return True
            except Exception as e:
                print(f"Error loading model: {e}")
        return False

# 单例
nlp_engine = WardrobeNLP()
