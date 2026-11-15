# app/services/nlu_service.py
import numpy as np
from sentence_transformers import util
from app.services.utils import normalize_text

class NLU_Service:
    def __init__(self, data_manager, ml_models, threshold=0.7):
        self.data_manager = data_manager
        self.ml_models = ml_models
        self.threshold = threshold
        self._customer_vectors = {}
        self.library_keys = []
        self.library_vectors = np.array([])
        self.update_library_vectors()

    def update_library_vectors(self):
        if not self.ml_models.embedding_model: return
        library = self.data_manager.get_library()
        keys_to_encode = list(library.keys())
        if keys_to_encode:
            self.library_vectors = self.ml_models.embedding_model.encode(keys_to_encode)
            self.library_keys = keys_to_encode
        else:
            self.library_vectors, self.library_keys = np.array([]), []
        print(f"NLU Servisi: Kütüphane vektörleri güncellendi. {len(self.library_keys)} adet niyet mevcut.")

    def get_intent(self, user_text):
        if self.data_manager.current_group() not in self._customer_vectors:
            self.update_library_vectors()
        if not self.ml_models.embedding_model or self.library_vectors.shape[0] == 0:
            return None, 0.0

        normalized_user_text = normalize_text(user_text)
        user_vector = self.ml_models.embedding_model.encode([normalized_user_text])

        similarities = util.cos_sim(user_vector, self.library_vectors)
        if similarities.shape[1] == 0: return None, 0.0
        best_match_index = np.argmax(similarities)
        best_match_score = similarities[0][best_match_index].item()
        if best_match_score >= self.threshold:
            return self.library_keys[best_match_index], best_match_score
        return None, best_match_score


    @property
    def library_keys(self):
        return self._customer_vectors.setdefault(self.data_manager.current_group(), {'keys': [], 'vectors': np.array([])})['keys']

    @library_keys.setter
    def library_keys(self, value):
        self._customer_vectors.setdefault(self.data_manager.current_group(), {'keys': [], 'vectors': np.array([])})['keys'] = value

    @property
    def library_vectors(self):
        return self._customer_vectors.setdefault(self.data_manager.current_group(), {'keys': [], 'vectors': np.array([])})['vectors']

    @library_vectors.setter
    def library_vectors(self, value):
        self._customer_vectors.setdefault(self.data_manager.current_group(), {'keys': [], 'vectors': np.array([])})['vectors'] = value
