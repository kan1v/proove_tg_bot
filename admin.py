# admin.py
import logging
import asyncio
import csv
from flask import Flask, render_template, redirect, url_for, request
from flask_basicauth import BasicAuth
from tg_bot import bot, ADMIN_CHAT_IDS, CSV_FILE, bot_loop  # loop бота

# ---------------- ЛОГИ ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- FLASK ----------------
app = Flask(__name__)
app.config['BASIC_AUTH_USERNAME'] = 'admin'
app.config['BASIC_AUTH_PASSWORD'] = 'admin'
app.config['BASIC_AUTH_FORCE'] = True
basic_auth = BasicAuth(app)

# ---------------- КОНСТАНТЫ ----------------
FIELDNAMES = [
    "ПІБ", "Телефон", "Instagram", "TikTok", "YouTube Shorts",
    "Підписники / Перегляди", "Ідея", "Telegram username",
    "Дата", "Статус", "chat_id",
]

ACCEPT_TEXT = (
    "✅Ваша заявка на участь у розіграші прийнята! \n\n"
    "Наступні кроки:\n"
    "1. Зніміть відео та опублікуйте його у своїх соцмережах Instagram або TikTok до 30.08.\n"
    "2. Обов’язково відмітьте акаунти Proove Gaming та додайте хештег #ProoveGamingChallenge.\n"
    "3. Надішліть посилання на ваше відео у Telegram @pgchallenge.\n\n"
    "Результати розіграшу та імена переможців (Топ-3) будуть оголошені 04.09 на наших офіційних сторінках:\n"
    "Instagram\nTikTok\n\nБажаємо успіху!\n"
    "https://www.tiktok.com/@proove_gaming_ua?_t=ZM-8yohKjOALuI"
)

REJECT_REASONS = {
    "1": "❌Ваша заявка відхилена\nСценарій не відповідає вимогам челенджу. (Ознайомтесь із правилами та спробуйте знову.)",
    "2": "❌ Ваша заявка відхилена\nВи виконали не всі кроки для участі. (Перевірте умови та спробуйте знову.).",
    "3": "❌ Ваша заявка відхилена\nПідписка на соцмережу — обов’язкова умова. (Додайте підписку та спробуйте знову.)",
    "4": "❌ Ваша заявка відхилена\nМаксимальна кількість учасників досягнута. Дякуємо, що ви є частиною Proove Gaming👾",
}

# ---------------- ВСПОМОГАТЕЛЬНЫЕ ----------------
def read_csv():
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_csv(rows):
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

def send_async_message(chat_id: int, text: str):
    """Отправка сообщений через Aiogram из синхронного Flask."""
    try:
        asyncio.run_coroutine_threadsafe(bot.send_message(chat_id, text), bot_loop)
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")

def update_status_and_notify(chat_id: str, status: str, reason_key: str = None):
    """Обновление статуса заявки и отправка сообщений пользователю."""
    rows = read_csv()
    updated = False

    for row in rows:
        if str(row.get("chat_id")) == str(chat_id):
            if status == "Відхилено" and reason_key:
                row["Статус"] = f"Відхилено ({reason_key})"
            else:
                row["Статус"] = status
            updated = True

    if not updated:
        logger.warning(f"⚠ Заявка с chat_id={chat_id} не найдена")
        return

    write_csv(rows)

    # Отправка уведомления пользователю
    if status == "Прийнято":
        send_async_message(int(chat_id), ACCEPT_TEXT)
    elif status == "Відхилено":
        send_async_message(int(chat_id), REJECT_REASONS.get(reason_key, "❌ Ваша заявка відхилена."))

# ---------------- ROUTES ----------------
@app.route("/")
@basic_auth.required
def index():
    return render_template("admin_table.html", rows=read_csv())

@app.route("/action/<chat_id>/<action>", methods=["POST"])
@basic_auth.required
def action(chat_id, action):
    if action == "accept":
        update_status_and_notify(chat_id, "Прийнято")
    elif action.startswith("reject_"):
        reason_key = action.split("_", 1)[1]
        update_status_and_notify(chat_id, "Відхилено", reason_key)
    return redirect(url_for('index'))

@app.route("/delete/<chat_id>", methods=["POST"])
@basic_auth.required
def delete(chat_id):
    rows = read_csv()
    target = next((r for r in rows if str(r["chat_id"]) == str(chat_id)), None)
    if target:
        notify_admin = (
            f"🗑 Заявку видалено через адмін-панель:\n"
            f"👤 {target.get('ПІБ', '')}\n"
            f"@{target.get('Telegram username', '')} ({chat_id})\n"
            f"Статус: {target.get('Статус', '')}"
        )
        for admin in ADMIN_CHAT_IDS:
            send_async_message(admin, notify_admin)

        # Удаление заявки из CSV
        rows = [r for r in rows if str(r["chat_id"]) != str(chat_id)]
        write_csv(rows)

    return redirect(url_for('index'))

@app.route("/delete_all", methods=["POST"])
@basic_auth.required
def delete_all():
    rows = read_csv()
    count = len(rows)
    if count > 0:
        text_admin_message = (
            f"🔥 Всі заявки ({count}) були видалені через адмін-панель!\n"
            f"Останній запис:\n"
            f"👤 {rows[-1].get('ПІБ', '')}\n"
            f"@{rows[-1].get('Telegram username', '')} ({rows[-1].get('chat_id', '')})"
        )
        for admin in ADMIN_CHAT_IDS:
            send_async_message(admin, text_admin_message)

    # Очистка CSV
    write_csv([])

    return redirect(url_for('index'))

# ---------------- ЗАПУСК ----------------
def run_flask():
    logger.info("🚀 Запуск Flask сервера...")
    app.run(host="0.0.0.0", port=5002, debug=False, use_reloader=False)
