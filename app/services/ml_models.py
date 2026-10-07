# app/services/ml_models.py
from sentence_transformers import SentenceTransformer
from transformers import pipeline

class MLModels:
    def __init__(self):
        print("ML Modelleri: SentenceTransformer yükleniyor...")
        try:
            self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            print("ML Modelleri: SentenceTransformer yüklendi.")
        except Exception as e:
            print(f"KRİTİK HATA: SentenceTransformer modeli yüklenemedi: {e}")
            self.embedding_model = None

        print("ML Modelleri: Duygu analizi modeli yükleniyor...")
        try:
            self.sentiment_pipeline = pipeline("sentiment-analysis", model="savasy/bert-base-turkish-sentiment-cased")
            print("ML Modelleri: Duygu analizi modeli yüklendi.")
        except Exception as e:
            print(f"KRİTİK HATA: Duygu analizi modeli yüklenemedi: {e}")
            self.sentiment_pipeline = None

       
