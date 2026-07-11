"""
gdebenz_core.py — общая логика бота ГдеБЕНЗ.

Используется и консольным скриптом (notify_gdebenz.py), и графическим
окном настроек (gdebenz_gui.py), чтобы не дублировать код.
"""

import html
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")

API_URL = "https://gdebenz.ru/api/nearby"

DEFAULT_CONFIG = {
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "lat": 58.0116,
    "lon": 56.2493,
    "radius_km": 20,
    "favorites": [],           # список osm_id; пусто = следим за всеми в радиусе
    "notify_statuses": ["yes", "queue", "low"],
    "check_interval_seconds": 60,
    "disable_ssl_verify": False,
}

STATUS_LABELS = {
    "yes": "✅ Есть топливо",
    "queue": "🚗 Есть, но очередь",
    "low": "⚠️ Мало, скоро может кончиться",
    "limit": "⛔ Лимит на выдачу",
    "no": "❌ Нет топлива",
}

# Несколько городов для быстрого выбора в GUI (координаты центра).
CITY_PRESETS = {
    "Пермь": (58.0116, 56.2493),
    "Москва": (55.7558, 37.6173),
    "Санкт-Петербург": (59.9311, 30.3609),
    "Новосибирск": (55.0084, 82.9357),
    "Екатеринбург": (56.8389, 60.6057),
    "Казань": (55.7963, 49.1088),
    "Нижний Новгород": (56.2965, 43.9361),
    "Челябинск": (55.1644, 61.4368),
    "Самара": (53.2001, 50.15),
    "Ростов-на-Дону": (47.2357, 39.7015),
    "Уфа": (54.7388, 55.9721),
    "Краснодар": (45.0355, 38.9753),
}


# ---------------------------------------------------------------------------
# Конфиг
# ---------------------------------------------------------------------------

def load_config():
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
        except (json.JSONDecodeError, OSError):
            pass

    # Переменные окружения (например, GitHub Actions secrets) имеют приоритет
    # над config.json, если заданы.
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["telegram_bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        config["telegram_chat_id"] = os.environ["TELEGRAM_CHAT_ID"]

    return config


def save_config(config):
    to_save = {k: config[k] for k in DEFAULT_CONFIG if k in config}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Состояние (чтобы не слать повторные уведомления)
# ---------------------------------------------------------------------------

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Сеть
# ---------------------------------------------------------------------------

def _ssl_context(config):
    if config.get("disable_ssl_verify"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def fetch_stations(config):
    params = urllib.parse.urlencode({
        "lat": config["lat"],
        "lon": config["lon"],
        "radius_km": config["radius_km"],
    })
    url = f"{API_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; gdebenz-notify-bot/1.0)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20, context=_ssl_context(config)) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("stations", [])


def format_message(station):
    label = STATUS_LABELS.get(station.get("status"), station.get("status", "?"))
    brand = html.escape(station.get("brand") or "")
    addr = html.escape(station.get("addr") or "адрес не указан")
    fuels = html.escape(station.get("fuels_now") or "не указано")
    last_at = html.escape(station.get("last_at") or "?")
    maps_link = f"https://yandex.ru/maps/?pt={station['lon']},{station['lat']}&z=17"
    return (
        f"<b>{label}</b>\n"
        f"{brand} — {addr}\n"
        f"Марки: {fuels}\n"
        f"Отметка: {last_at}\n"
        f"Уверенность: {round(station.get('confidence_base', 0) * 100)}% "
        f"({station.get('confirmations', 0)} подтв.)\n"
        f"<a href=\"{maps_link}\">Маршрут на карте</a>"
    )


def send_telegram(config, text):
    """Возвращает (успех: bool, сообщение: str)."""
    token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")
    if not token or not chat_id:
        return False, "Не заданы токен бота или chat_id."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context(config)) as resp:
            resp.read()
        return True, "Отправлено."
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return False, f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, str(e)


def send_test_message(config):
    text = (
        "🧪 <b>Тестовое сообщение от бота ГдеБЕНЗ</b>\n"
        "Если вы видите это в Telegram — токен и chat_id настроены правильно."
    )
    return send_telegram(config, text)


# ---------------------------------------------------------------------------
# Основная проверка
# ---------------------------------------------------------------------------

def check_once(config):
    """Одна проверка карты. Возвращает (checked_count, notified_count, log_lines)."""
    log_lines = []
    stations = fetch_stations(config)
    state = load_state()
    new_state = {}
    notified = 0
    favorites = set(config.get("favorites") or [])
    notify_statuses = set(config.get("notify_statuses") or [])

    for st in stations:
        osm_id = st.get("osm_id")
        if not osm_id:
            continue

        if favorites and osm_id not in favorites:
            continue

        status = st.get("status")
        fingerprint = status
        new_state[osm_id] = fingerprint

        if status in notify_statuses and state.get(osm_id) != fingerprint:
            ok, msg = send_telegram(config, format_message(st))
            if ok:
                notified += 1
                log_lines.append(f"→ Уведомление: {st.get('brand')} {st.get('addr')}")
            else:
                log_lines.append(f"[!] Ошибка отправки: {msg}")

    save_state(new_state)
    return len(stations), notified, log_lines
