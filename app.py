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


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def save_client(phone, user_message, page_url):
    if not phone or not SUPABASE_URL or not SUPABASE_KEY:
        return

    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/clients",
            headers=supabase_headers(),
            json={
                "phone": phone,
                "source": "site_chat",
                "notes": f"{user_message}\nСтраница: {page_url}",
                "status": "new",
            },
            timeout=5,
        )
    except Exception as e:
        print("save client error:", e)


def save_chat(user_message, ai_reply, page_url):
    phone = extract_phone(user_message)
    status = "lead" if phone else "new"

    if status == "lead":
        send_email(
            "Новый лид Interlink",
            f"Сообщение: {user_message}\nТелефон: {phone}\nСтраница: {page_url}"
        )

    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/chat_logs",
            headers=supabase_headers(),
            json={
                "user_message": user_message,
                "ai_reply": ai_reply,
                "page_url": page_url,
                "phone": phone,
                "status": status,
            },
            timeout=5,
        )
    except Exception as e:
        print("save chat error:", e)

    if phone:
        save_client(phone, user_message, page_url)


def search_products(user_message):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []

    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/products",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            params={
                "select": "brand,series,model,type,power,area_m2,price,description",
                "is_active": "eq.true",
                "limit": "20",
            },
            timeout=5,
        )

        if response.status_code != 200:
            print("products error:", response.status_code, response.text)
            return []

        return response.json()

    except Exception as e:
        print("products search error:", e)
        return []


def build_products_context(products):
    if not products:
        return "Товары из базы не найдены."

    lines = []

    for p in products:
        brand = p.get("brand") or ""
        series = p.get("series") or ""
        model = p.get("model") or ""
        product_type = p.get("type") or ""
        power = p.get("power") or ""
        area_m2 = p.get("area_m2") or ""
        price = p.get("price") or ""
        description = p.get("description") or ""

        price_text = f"{price}$" if price != "" else "цена не указана"

        lines.append(
            f"- {brand} {model}, серия {series}, {product_type}, "
            f"мощность {power}, площадь {area_m2} м², "
            f"цена {price_text}, {description}"
        )

    return "\n".join(lines)


@app.route("/chat", methods=["POST"])
@limiter.limit("5 per 10 seconds")
def chat():
    data = request.json or {}
    user_message = data.get("message", "")
    page_url = data.get("page_url", "")

    if not user_message:
        return jsonify({"reply": "Напишите вопрос"})

    products = search_products(user_message)
    products_context = build_products_context(products)

    try:
        response = client.responses.create(
            model="gpt-5.4-mini",
            input=f"""
Ты эксперт Interlink. Отвечай коротко, 2-3 предложения.

Правила:
- Подбирай модель по площади, бюджету и типу помещения.
- Если клиент не ограничен бюджетом — предлагай MSZ-LN в первую очередь.
- Если клиент ищет дешевле — предложи AP или HR, если они есть в базе.
- Цены указываются только за оборудование.
- Монтаж считается отдельно.
- Не выдумывай модели и цены.
- Используй товары только из базы ниже.
- Если клиент оставил телефон — поблагодари и скажи, что менеджер свяжется.
- Если точного товара нет, скажи что лучше уточнить площадь, тип помещения и бюджет.

Товары из базы:
{products_context}

Вопрос клиента:
{user_message}
"""
        )

        ai_reply = response.output_text

    except Exception as e:
        print("AI error:", e)
        return jsonify({"reply": "Ошибка, попробуйте позже"})

    save_chat(user_message, ai_reply, page_url)

    return jsonify({"reply": ai_reply})


if __name__ == "__main__":
    app.run()
