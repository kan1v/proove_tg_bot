# admin.py
import logging
import asyncio
import time
import csv
from flask import Flask, render_template, redirect, url_for, request
from flask_basicauth import BasicAuth
from tg_bot import bot, bot_loop, bot_loop_ready, ADMIN_CHAT_IDS, CSV_FILE  # Импорт из бота


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
    """Читаем таблицу заявок"""
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))



def _send_message(chat_id: int, text: str) -> bool:
    max_wait = 5  # секунд
    waited = 0
    while bot_loop is None and waited < max_wait:
        time.sleep(0.1)
        waited += 0.1

    if bot_loop is None:
        logger.error(f"❌ bot_loop так и не готов, сообщение не отправлено chat_id={chat_id}")
        return False

    try:
        future = asyncio.run_coroutine_threadsafe(bot.send_message(chat_id, text), bot_loop)
        future.result(timeout=15)
        logger.info(f"📩 Сообщение отправлено chat_id={chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке chat_id={chat_id}: {e}")
        return False




def notify_admins(text: str):
    """Уведомляем всех админов"""
    sent = sum(_send_message(admin_id, text) for admin_id in ADMIN_CHAT_IDS)
    logger.info(f"👑 Уведомления админам отправлены {sent}/{len(ADMIN_CHAT_IDS)}")

def update_status_and_notify(chat_id: str, status: str, username: str, reason_key: str | None = None):
    """Меняем статус заявки и шлём уведомления"""
    rows = []
    pib = ""
    updated = False

    # Читаем и меняем статус
    with open(CSV_FILE, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("chat_id")) == str(chat_id):
                if status == "Відхилено" and reason_key:
                    row["Статус"] = f"Відхилено ({reason_key})"
                else:
                    row["Статус"] = status
                updated = True
                pib = row.get("ПІБ", "")
            rows.append(row)

    if not updated:
        logger.warning(f"⚠ Заявка с chat_id={chat_id} не найдена")
        return

    # Записываем обновлённые данные
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    # Отправка пользователю
    if status == "Прийнято":
        _send_message(int(chat_id), ACCEPT_TEXT)
    elif status == "Відхилено":
        _send_message(int(chat_id), REJECT_REASONS.get(reason_key, "❌ Ваша заявка відхилена."))

    # Уведомление админам
    notify_admins(
        f"✏️ Статус заявки змінено через адмін-панель:\n"
        f"👤 {pib}\n"
        f"@{username} ({chat_id})\n"
        f"Статус: {('Відхилено (' + reason_key + ')') if status=='Відхилено' and reason_key else status}"
    )

# ---------------- ROUTES ----------------
@app.route("/")
@basic_auth.required
def index():
    return render_template("admin_table.html", rows=read_csv())

@app.route("/action/<chat_id>/<action>", methods=["POST"])
@basic_auth.required
def action(chat_id, action):
    username = next((r["Telegram username"] for r in read_csv() if str(r["chat_id"]) == str(chat_id)), "")
    if action == "accept":
        update_status_and_notify(chat_id, "Прийнято", username)
    elif action.startswith("reject_"):
        reason_key = action.split("_", 1)[1]
        update_status_and_notify(chat_id, "Відхилено", username, reason_key)
    return redirect(url_for('index'))

@app.route("/delete/<chat_id>", methods=["POST"])
@basic_auth.required
def delete(chat_id):
    rows = read_csv()
    target = next((r for r in rows if str(r["chat_id"]) == str(chat_id)), None)
    if target:
        notify_admins(
            f"🗑 Заявку видалено через адмін-панель:\n"
            f"👤 {target.get('ПІБ', '')}\n"
            f"@{target.get('Telegram username', '')} ({chat_id})\n"
            f"Статус: {target.get('Статус', '')}"
        )
    # Удаляем запись
    rows = [r for r in rows if str(r["chat_id"]) != str(chat_id)]
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return redirect(url_for('index'))

@app.route("/delete_all", methods=["POST"])
@basic_auth.required
def delete_all():
    rows = read_csv()
    count = len(rows)
    if count > 0:
        notify_admins(
            f"🔥 Всі заявки ({count}) були видалені через адмін-панель!\n"
            f"Останній запис:\n"
            f"👤 {rows[-1].get('ПІБ', '')}\n"
            f"@{rows[-1].get('Telegram username', '')} ({rows[-1].get('chat_id', '')})"
        )
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDNAMES)
    return redirect(url_for('index'))

# ---------------- ЗАПУСК ----------------
def run_flask():
    logger.info("🚀 Запуск Flask сервера...")
    app.run(host="0.0.0.0", port=5002, debug=False, use_reloader=False)
