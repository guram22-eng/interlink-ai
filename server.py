import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# 🔑 ключ берётся из Render (Environment)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.route("/", methods=["GET"])
def home():
    return "Interlink AI server is running"


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"reply": "Напишите вопрос, и я помогу вам."})

    response = client.responses.create(
        model="gpt-5.4-mini",
        input=f"""
Ты профессиональный AI-консультант компании Interlink (Грузия).

О компании:
- Официальный дистрибьютор Mitsubishi Electric в Грузии
- Работаем с 2014 года
- 150+ реализованных проектов
- Даем гарантию на оборудование и монтаж

Чем занимаемся:
- кондиционирование
- VRF системы
- вентиляция и рекуперация
- решения для квартир, домов, офисов, гостиниц и бизнеса

Твоя задача:
1. Помочь выбрать решение
2. Объяснить простым языком
3. Дать уверенность клиенту
4. Подвести к контакту

Правила:
- отвечай коротко (2-4 предложения)
- говори как эксперт
- не выдумывай цены
- если клиент хочет подбор — предложи бесплатную консультацию
- мягко предложи оставить телефон или написать в WhatsApp / Telegram

Вопрос клиента: {user_message}
"""
    )

    return jsonify({"reply": response.output_text})


# 🔥 важно для Render
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)