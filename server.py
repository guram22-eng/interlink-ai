import os
import re
import requests
import smtplib
import threading
from email.mime.text import MIMEText

from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


app = Flask(__name__)
CORS(app)

limiter = Limiter(get_remote_address, app=app, default_limits=["30 per minute"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

EMAIL_USER = "interlink.ai.leads@gmail.com"
EMAIL_PASS = "qucnhztnolhyunqa"

PRODUCTS_KNOWLEDGE = """
Если клиент не ограничен бюджетом — предлагай MSZ-LN в первую очередь.

Серии:
- MSZ-LN — премиум, тихий, лучший выбор
- MSZ-EF — дизайнерский
- MSZ-AP — универсальный
- MSZ-HR — бюджет

Цены (оборудование):
MSZ-LN 25 — от 1700$
MSZ-LN 35 — от 1900$
MSZ-LN 50 — от 2300$

MSZ-EF 25 — от 1300$
MSZ-EF 35 — от 1400$
MSZ-EF 50 — от 2000$

MSZ-AP 25 — от 1200$
MSZ-AP 35 — от 1300$
MSZ-AP 50 — от 1700$

Важно:
цены только за оборудование, монтаж отдельно
"""


@app.route("/")
def home():
    return "OK"


def extract_phone(text):
    match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)
    return match.group(1) if match else None


def send_email(subject, body):
    if not EMAIL_USER or not EMAIL_PASS:
        return

    def _send():
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = EMAIL_USER
            msg["To"] = EMAIL_USER

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as server:
                server.login(EMAIL_USER, EMAIL_PASS)
                server.send_message(msg)

        except Exception as e:
            print("email error:", e)

    threading.Thread(target=_send, daemon=True).start()


def save_chat(user_message, ai_reply, page_url):
    phone = extract_phone(user_message)
    status = "lead" if phone else "new"

    if status == "lead":
        send_email(
            "Новый лид",
            f"{user_message}\nТелефон: {phone}\n{page_url}"
        )

    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/chat_logs",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "user_message": user_message,
                "ai_reply": ai_reply,
                "page_url": page_url,
                "phone": phone,
                "status": status,
            },
            timeout=5,
        )
    except:
        pass


@app.route("/chat", methods=["POST"])
@limiter.limit("5 per 10 seconds")
def chat():
    data = request.json or {}
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"reply": "Напишите вопрос"})

    try:
        response = client.responses.create(
            model="gpt-5.4-mini",
            input=f"""
{PRODUCTS_KNOWLEDGE}

Ты эксперт Interlink. Отвечай коротко, 2-3 предложения.

Вопрос: {user_message}
"""
        )

        ai_reply = response.output_text

    except Exception as e:
        print("AI error:", e)
        return jsonify({"reply": "Ошибка, попробуйте позже"})

    save_chat(user_message, ai_reply, "")

    return jsonify({"reply": ai_reply})


if __name__ == "__main__":
    app.run()
