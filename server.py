import os
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
CORS(app)

# Rate limit
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["30 per minute"]
)

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


# 🔥 НОВОЕ — получение истории
def get_history():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return ""

    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_logs?select=user_message,ai_reply&order=id.desc&limit=5",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            timeout=5,
        )

        data = res.json()

        history_text = ""
        for row in reversed(data):
            history_text += f"Клиент: {row['user_message']}\nAI: {row['ai_reply']}\n"

        return history_text

    except Exception as e:
        print("history error:", e)
        return ""


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "reply": "Слишком много запросов. Подождите несколько секунд и попробуйте снова."
    }), 429


@app.route("/chat", methods=["POST"])
@limiter.limit("5 per 10 seconds")
def chat():
    data = request.json or {}
    user_message = data.get("message", "")
    page_url = data.get("page_url") or request.headers.get("Origin")

    if not user_message:
        return jsonify({"reply": "Напишите вопрос, и я помогу вам."})

    # 🔥 НОВОЕ — берём историю
    history = get_history()

    response = client.responses.create(
        model="gpt-5.4-mini",
        input=f"""
{history}

Ты профессиональный AI-консультант компании Interlink (Грузия).

О компании:
- Официальный дистрибьютор Mitsubishi Electric в Грузии
- Работаем с 2014 года
- 150+ реализованных проектов

Правила:
- отвечай коротко (2-4 предложения)
- не выдумывай цены
- веди к контакту

Вопрос клиента: {user_message}
"""
    )

    ai_reply = response.output_text

    save_chat(user_message, ai_reply, page_url)

    return jsonify({"reply": ai_reply})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
