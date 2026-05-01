import os
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


@app.route("/", methods=["GET"])
def home():
    return "Interlink AI server is running"


def extract_phone(text):
    match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)
    return match.group(1) if match else None


def save_chat(user_message, ai_reply, page_url):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase env missing")
        return

    phone = extract_phone(user_message)
    status = "lead" if phone else "new"

    try:
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/chat_logs",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={
                "user_message": user_message,
                "ai_reply": ai_reply,
                "page_url": page_url,
                "phone": phone,
                "status": status,
            },
            timeout=10,
        )

        print("✅ Supabase:", res.status_code)

    except Exception as e:
        print("❌ Supabase error:", e)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user_message = data.get("message", "")
    page_url = data.get("page_url") or request.headers.get("Origin")

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

    ai_reply = response.output_text

    # 💥 СОХРАНЕНИЕ В БАЗУ
    save_chat(user_message, ai_reply, page_url)

    return jsonify({"reply": ai_reply})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)