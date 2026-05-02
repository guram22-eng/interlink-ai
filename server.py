import os
import re
import requests
import smtplib
from email.mime.text import MIMEText

from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


app = Flask(__name__)
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["30 per minute"]
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")


PRODUCTS_KNOWLEDGE = """
БАЗА ЗНАНИЙ INTERLINK / MITSUBISHI ELECTRIC

Бытовые кондиционеры:

Если клиент не ограничен бюджетом — всегда начинай с MSZ-LN.

Приоритет рекомендаций:
1. MSZ-LN — предлагать в первую очередь
2. MSZ-EF — если важен дизайн или LN не подходит
3. MSZ-AP — как универсальный вариант
4. MSZ-HR — как бюджетный вариант

MSZ-LN (Premium):
- премиальная серия Mitsubishi Electric
- дизайн: 4 цвета (красный, черный, перламутровый белый, белый)
- очень тихий: от 19 дБ
- энергоэффективность A+++ (SEER до 10.5, R32)
- встроенный Wi-Fi
- 3D I-SEE датчик: определяет людей и регулирует поток воздуха
- Plasma Quad Plus: очистка от вирусов, бактерий, аллергенов, PM2.5
- подходит для премиум квартир, домов, спален, гостиных

MSZ-EF (Design Inverter):
- дизайнерская серия
- 3 цвета: белый, серебристый, черный
- тихая работа: от 19 дБ
- энергоэффективность A+++ (SEER до 9.1)
- встроенный Wi-Fi
- антивирусный фильтр V Blocking с ионами серебра
- подходит для современных квартир, спален, гостиных, дизайнерских интерьеров

MSZ-AP (Standard Inverter):
- универсальная и компактная серия
- хороший баланс цена / качество
- тихая работа: от 19 дБ
- высокая энергоэффективность
- встроенный Wi-Fi
- работает в мульти-сплит системах
- подходит для квартир, офисов, спален, гостиных

MSZ-HR (Classic Inverter):
- доступная серия Mitsubishi Electric
- надежность и инверторная технология
- энергоэффективность A++ охлаждение / A+ обогрев
- ECONO COOL
- авторестарт после отключения питания
- Wi-Fi как опция
- подходит для клиентов с ограниченным бюджетом, квартир и офисов

Цены (ориентир по мощности, только оборудование):

MSZ-LN:
- 25 (до 25 м²) — от 1700$
- 35 (до 35 м²) — от 1900$
- 50 (до 50 м²) — от 2300$

MSZ-EF:
- 25 (до 25 м²) — от 1300$
- 35 (до 35 м²) — от 1400$
- 50 (до 50 м²) — от 2000$

MSZ-AP:
- 25 (до 25 м²) — от 1200$
- 35 (до 35 м²) — от 1300$
- 50 (до 50 м²) — от 1700$

Важно по ценам:
- цены указаны только за оборудование
- монтаж, трасса и дополнительные материалы рассчитываются отдельно
- точную цену подтверждать после подбора модели

Мульти-сплит:

MXZ:
- подключение 2–6 внутренних блоков к одному наружному
- можно комбинировать разные внутренние блоки
- высокая энергоэффективность A++ / A+++
- низкий шум и вибрации
- подходит для квартир, домов и объектов с несколькими комнатами
- хороший выбор, когда нужно меньше наружных блоков на фасаде

Кассетный блок:

MLZ-KP (кассетный 1 поток):
- компактный потолочный блок
- высота около 185 мм
- скрытый монтаж
- равномерный поток воздуха
- управление потоком в 4 направлениях
- подходит для квартир, домов, офисов с подвесным потолком
- рекомендовать, когда нельзя или нежелательно ставить настенный блок

VRF:

CITY MULTI / VRF:
- система для больших объектов
- одно решение для здания с большим количеством помещений
- точный контроль температуры по зонам
- высокая энергоэффективность
- подходит для офисов, гостиниц, торговых объектов, больших домов, коммерческих зданий
- рекомендовать, если объект большой, много комнат, этажей или нужна централизованная система

Правила подбора:
- если клиент спрашивает “что лучше” — сначала уточни площадь, тип объекта, количество комнат и бюджет
- если клиент спрашивает цену — называй ориентир по мощности и уточняй, что это только оборудование
- если нужен премиум — предлагай MSZ-LN
- если важен дизайн — MSZ-EF
- если нужен оптимальный вариант — MSZ-AP
- если нужен доступный вариант — MSZ-HR
- если несколько комнат — MXZ
- если скрытый потолочный монтаж — MLZ-KP
- если большой объект — VRF / CITY MULTI
"""


@app.route("/", methods=["GET"])
def home():
    return "Interlink AI server is running"


def extract_phone(text):
    match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)
    return match.group(1) if match else None


def send_email(subject, body):
    if not EMAIL_USER or not EMAIL_PASS:
        print("❌ Email env missing")
        return

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_USER

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)

        print("📧 Email sent")

    except Exception as e:
        print("❌ Email error:", e)


def save_chat(user_message, ai_reply, page_url):
    phone = extract_phone(user_message)
    status = "lead" if phone else "new"

    if status == "lead":
        send_email(
            "🔥 Новый лид с сайта Interlink",
            f"Сообщение клиента:\n{user_message}\n\nТелефон: {phone}\n\nСтраница: {page_url}\n\nОтвет AI:\n{ai_reply}"
        )

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase env missing")
        return

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
    user_message = data.get("message", "").strip()
    page_url = data.get("page_url") or request.headers.get("Origin")

    if not user_message:
        return jsonify({"reply": "Напишите вопрос, и я помогу вам."})

    try:
        
        response = client.responses.create(
            model="gpt-5.4-mini",
            input=f"""
{history}

{PRODUCTS_KNOWLEDGE}

Ты профессиональный AI-консультант компании Interlink (Грузия).

О компании:
- Официальный дистрибьютор Mitsubishi Electric в Грузии
- Работаем с 2014 года
- 150+ реализованных проектов
- Подбираем кондиционеры, мульти-сплит, VRF, вентиляцию и рекуперацию

Правила ответа:
- отвечай на языке клиента
- отвечай коротко: 2–4 предложения
- не используй markdown и символы **
- говори как эксперт, но простыми словами
- не выдумывай цены
- не перегружай клиента техническими деталями
- если данных мало — задай 1–2 уточняющих вопроса
- мягко веди к консультации, WhatsApp, Telegram или телефону

Вопрос клиента: {user_message}
"""
        )

        ai_reply = response.output_text

    except Exception as e:
        print("❌ OpenAI error:", e)
        return jsonify({
            "reply": "Сейчас есть временная ошибка связи с AI. Пожалуйста, попробуйте ещё раз через минуту."
        }), 500

    save_chat(user_message, ai_reply, page_url)

    return jsonify({"reply": ai_reply})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
