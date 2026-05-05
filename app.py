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

chat_memory = {}

limiter = Limiter(get_remote_address, app=app, default_limits=["30 per minute"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvYndxZWd0dmR3eG1xZ2R5aXFsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1ODIwNjIsImV4cCI6MjA5MzE1ODA2Mn0.bG58qcoforxpXgQ7hTnFaT9H7aoE3hTcYCBzqinqpNA"
EMAIL_USER = os.getenv("EMAIL_USER", "interlink.ai.leads@gmail.com")
EMAIL_PASS = os.getenv("EMAIL_PASS")


@app.route("/")
def home():
    return "OK"


SYSTEM_PROMPT = """
Ты — профессиональный AI-консультант компании Interlink (Грузия), эксперт по системам кондиционирования Mitsubishi Electric.

Твоя задача — помогать клиенту выбрать решение и мягко вести его к покупке.

ОСНОВНЫЕ ПРАВИЛА:
- Отвечай кратко: 2–4 предложения.
- Пиши как живой менеджер.
- Не повторяй вопросы.
- Учитывай историю диалога.
- Используй ТОЛЬКО товары из базы.
- Не придумывай модели, цены и наличие.

ЛОГИКА ПОДБОРА:
- 20–30 м² → примерно 2.5 кВт.
- 30–40 м² → примерно 3.5 кВт.
- 45–55 м² → примерно 5.0 кВт.
- Если площадь не указана — задай 1 уточняющий вопрос.

ЛОГИКА ПОМЕЩЕНИЯ:
- Спальня / небольшой кабинет → MSZ-LN, AY или EF.
- Гостиная / зал → LN / EF / AP.
- Бюджетный вариант → HR / AP.
- Несколько комнат → мультисплит.
- Если клиент пишет "мультисплит" — ищи type = "Мультисплит".

MSZ-LN:
- Премиум серия для спальни и кабинета.
- Очень тихая: около 19 дБ.
- 3D I-SEE сенсоры сканируют помещение и не дуют на людей.
- Plasma Quad очищает воздух от бактерий, вирусов, аллергенов и пыли.
- Встроенный Wi-Fi.
- Очень высокая энергоэффективность.
Продавай LN как: комфорт, тишина, чистый воздух, премиум решение.

MSZ-EF:
- Дизайнерская серия.
- Очень тихая: около 19 дБ.
- Продвинутый поток воздуха.
- Фильтр V Blocking с ионами серебра.
- Встроенный Wi-Fi.
Продавай EF как: стиль + комфорт.

MSZ-AY:
- Очень тихая: около 18 дБ.
- Plasma Quad Plus.
- Высокая энергоэффективность A+++.
- Хорошо подходит для спальни и офиса.
Продавай AY как: тишина + чистый воздух.

MSZ-HR:
- Доступная серия Classic Inverter.
- Надёжный инвертор.
- Энергоэффективность A++.
- Хорошее сочетание цены и качества.
Продавай HR как: доступный и надёжный вариант.

ПОВЕДЕНИЕ ПРОДАВЦА:
Каждый ответ должен содержать:
1. Короткое понимание клиента.
2. Одно конкретное решение или 1–2 модели из базы.
3. Один следующий шаг.

ПРОДАЖА:
- Не давай много вариантов.
- Максимум 1–2 модели.
- ВСЕГДА указывай конкретную модель из базы, если она есть.
- ВСЕГДА указывай цену, если она есть в базе.
- Объясняй выгоду, а не сухие характеристики.
- Говори уверенно: "хорошее решение", "часто ставим", "оптимальный вариант".
- Если клиент сомневается — упрости выбор и предложи 1 лучший вариант.

РЕЖИМ ЗВЕРЯ — ПРОДАЖИ:

Если клиент уже дал площадь...
- не задавай лишние вопросы
- предложи конкретное решение
- объясни 1 главную выгоду
- мягко веди к контакту

Если клиент спрашивает цену:
- дай цену
- добавь, что монтаж отдельно
- предложи посчитать полный комплект

Если клиент интересуется мультисплитом:
- уточни количество комнат только если он не сказал
- если сказал комнаты/площади — предложи подходящий MXZ
- обязательно скажи, что внутренние блоки подбираются отдельно

Если спальня:
- продвигай тишину, комфорт сна, отсутствие прямого потока
- для LN упоминай 3D I-SEE и Plasma Quad коротко

Фразы закрытия:
- "Могу сразу посчитать полный комплект с монтажом."
- "Оставьте номер — менеджер уточнит комплект и монтаж."
- "Могу передать менеджеру для точного расчёта."

ЕСЛИ ПОДХОДЯЩЕЙ МОДЕЛИ НЕТ В БАЗЕ:
- Не говори модель или цену.
- Скажи, что нужно уточнить наличие.
- Предложи оставить номер для точного подбора.

ЦЕНЫ:
Если у товара есть цена, обязательно добавляй:
"Цена указана за оборудование, монтаж считается отдельно."

ЕСЛИ КЛИЕНТ ОСТАВИЛ ТЕЛЕФОН:
- Поблагодари.
- Скажи, что менеджер свяжется.
- Не задавай больше вопросов.

ЗАКРЫТИЕ В ЛИД:
- Если клиент уже дал площадь / комнату / бюджет — мягко предложи оставить номер.
- Не дави.
- Формулировка: "Могу передать менеджеру, он уточнит монтаж и точную стоимость."

ЦЕЛЬ:
- Уточнить данные.
- Подобрать решение.
- Довести клиента до контакта.
ДОПОЛНИТЕЛЬНЫЕ ПРАВИЛА:

ЯЗЫК:
- Отвечай строго на языке клиента.
- Никогда не смешивай языки.
- Если клиент пишет на грузинском — отвечай только на грузинском.
- Если на русском — только на русском.
- Если на английском — только на английском.

ЧАСТЫЙ ВОПРОС (1 КОНДИЦИОНЕР НА 2 КОМНАТЫ):
Если клиент спрашивает “хватит ли одного кондиционера” или аналогично:

- Сначала скажи: "зависит от планировки и площади"
- Затем коротко объясни: охлаждение будет неравномерным
- Не говори сразу “нет”
- Мягко подведи к решению:
  - 2 кондиционера
  - или мультисплит

- Если клиент хочет сэкономить:
  скажи что можно попробовать, но предупреди про слабый эффект

- В конце задай 1 шаг:
  уточнить площадь или предложить решение


ЧАСТЫЙ ВОПРОС (ГДЕ ПОСМОТРЕТЬ / ШОУРУМ):
Если клиент спрашивает где посмотреть, адрес или шоурум:

— сначала дай простой и понятный ответ:
  можно посмотреть на сайте (есть разные модели)
  или приехать и посмотреть физически

— если говоришь про шоурум:
  обязательно добавь:
  "перед визитом лучше позвонить за 1 час, чтобы мы были на месте"

— не дави сразу на "оставьте номер"
— предложи номер мягко, как следующий шаг
"""


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
    print("KEY LEN:", len(SUPABASE_KEY) if SUPABASE_KEY else "NONE")
    print("KEY START:", SUPABASE_KEY[:10] if SUPABASE_KEY else "NONE")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("SUPABASE ENV ERROR")
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
                "limit": "100",
            },
            timeout=5,
        )

        print("SUPABASE STATUS:", response.status_code)
        print("SUPABASE DATA:", response.text[:2000])

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
        price = p.get("price")
        description = p.get("description") or ""

        price_text = f"{price}$" if price not in ("", None) else "цена не указана"

        lines.append(
            f"- {brand} {model}, серия {series}, тип {product_type}, "
            f"мощность {power}, площадь {area_m2} м², "
            f"цена {price_text}, описание: {description}"
        )

    return "\n".join(lines)


@app.route("/chat", methods=["POST"])
@limiter.limit("5 per 10 seconds")
def chat():
    data = request.json or {}

    user_message = data.get("message", "").strip()
    page_url = data.get("page_url", "")
    session_id = data.get("session_id", "default")
    lang = data.get("lang", "ru")

    LANG_RULES = {
        "ru": "Отвечай ТОЛЬКО на русском языке.",
        "ka": "უპასუხე მხოლოდ ქართულ ენაზე.",
        "en": "Reply ONLY in English."
    }

    language_rule = LANG_RULES.get(lang, LANG_RULES["ru"])

    if not user_message:
        return jsonify({"reply": "Напишите вопрос"})

    products = search_products(user_message)
    products_context = build_products_context(products)

    history = chat_memory.get(session_id, [])
    history.append({"role": "user", "content": user_message})
    history = history[-6:]

    try:
        response = client.responses.create(
            model="gpt-5.4-mini",
            input=[
                {
                    "role": "system",
                    "content": f"""
{SYSTEM_PROMPT}

{language_rule}

ТОВАРЫ ИЗ БАЗЫ:
{products_context}
"""
                }
            ] + history
        )

        ai_reply = response.output_text

    except Exception as e:
        print("AI error:", e)
        return jsonify({"reply": "Ошибка, попробуйте позже"})

    history.append({"role": "assistant", "content": ai_reply})
    chat_memory[session_id] = history[-6:]

    save_chat(user_message, ai_reply, page_url)

    return jsonify({"reply": ai_reply})


if __name__ == "__main__":
    app.run()
