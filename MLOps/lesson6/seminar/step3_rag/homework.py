import json
import base64
import io
from pathlib import Path

import requests
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Предполагается, что OllamaClient находится в ../step1_vllm_inference/src/llm_client.py
# Для простоты, я скопирую необходимый код сюда, но в реальном проекте лучше настроить PYTHONPATH
import sys
sys.path.append(str(Path(__file__).parent.parent / 'step1_vllm_inference'))
from src.llm_client import OllamaClient

class PoseRetriever:
    def __init__(self, database_path):
        with open(database_path, 'r', encoding='utf-8') as f:
            self.database = json.load(f)
        self.descriptions = [item['description'] for item in self.database]
        self.vectorizer = TfidfVectorizer()
        self.tfidf_matrix = self.vectorizer.fit_transform(self.descriptions)

    def find_closest_pose(self, description):
        query_vector = self.vectorizer.transform([description])
        similarities = cosine_similarity(query_vector, self.tfidf_matrix)
        closest_index = similarities.argmax()
        return self.database[closest_index]['pose']

def generate_animation(query):
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # 1. Получаем описания движений от LLM
    llm_client = OllamaClient()
    prompt = f"Создай текстовое описание 12 движений для танца '{query}'. Каждое движение на новой строке."
    messages = [{"role": "user", "content": prompt}]
    try:
        response = llm_client.chat_completion(messages=messages, temperature=0.5, max_tokens=500)
        dance_moves = response.strip().split('\n')
        print(f"🤖 LLM сгенерировал {len(dance_moves)} движений.")
    except Exception as e:
        print(f"❌ Ошибка при обращении к LLM: {e}")
        return

    # 2. RAG: Находим позы для каждого движения
    retriever = PoseRetriever('poses_database.json')
    poses = [retriever.find_closest_pose(move) for move in dance_moves]
    print(f"🔍 Найдено {len(poses)} поз в базе данных.")

    # 3. Генерируем кадры через Pose API
    frames = []
    for i, pose in enumerate(poses):
        try:
            response = requests.post("http://localhost:8001/visualize", json={"pose": pose}, timeout=10)
            result = response.json()
            if result.get("success") and result.get("image"):
                img_data = base64.b64decode(result["image"])
                img = Image.open(io.BytesIO(img_data))
                frames.append(img)
                print(f"  ✓ Кадр {i+1}/{len(poses)}")
            else:
                print(f"  ✗ Ошибка при генерации кадра {i+1}")
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Ошибка API для кадра {i+1}: {e}")

    # 4. Сохраняем GIF
    if frames:
        gif_path = output_dir / f"{query.replace(' ', '_')}.gif"
        frames[0].save(
            gif_path,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=500,
            loop=0,
        )
        print(f"✅ Анимация сохранена: {gif_path}")
    else:
        print("❌ Не удалось создать кадры для анимации.")

if __name__ == "__main__":
    generate_animation("танец макарена")
