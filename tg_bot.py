# tg_bot.py
import asyncio
import os
import csv
import logging
import datetime
import re
import json

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from kbds.inline import start_kbd, back_kbds, social_no_kbd, admin_panel, admin_choices_kbd

from dotenv import load_dotenv
load_dotenv()

import config
from check_subscriptions import check_instagram_follow, check_tiktok_follow

bot_loop = asyncio.get_event_loop()


# Настройки
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tg_bot")

BOT_TOKEN = os.getenv("TOKEN") or config.BOT_TOKEN

ADMINS_FILE = "admins.json"

def load_admins():
    if not os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(ADMINS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def add_admin(chat_id: int):
    admins = load_admins()
    if chat_id not in admins:
        admins.append(chat_id)
        with open(ADMINS_FILE, "w", encoding="utf-8") as f:
            json.dump(admins, f)
    return admins

ADMIN_CHAT_IDS = load_admins()

CSV_FILE = "data.csv"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Клавиатура для подписки (юзер будет подписываться на эти аккаунты)
subscribe_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Підписатися на Instagram", url="https://instagram.com/proove_gaming_ua")],
    [types.InlineKeyboardButton(text="Підписатися на TikTok", url="https://tiktok.com/@proove_gaming_ua")],
    [types.InlineKeyboardButton(text="Я підписався", callback_data="check_subscription")]
])

# Создание файла с заголовками, если нет
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "ПІБ",
                "Телефон",
                "Instagram",
                "TikTok",
                "YouTube Shorts",
                "Підписники / Перегляди",
                "Ідея",
                "Telegram username",
                "Дата",
                "Статус",
                "chat_id",
            ]
        )

# Команды телеграмм бота 
async def set_commands():
    commands = [
        types.BotCommand(command="start", description="Запуск бота"),
    ]
    
    await bot.set_my_commands(commands)

# ------------------ FSM ------------------
class Form(StatesGroup):
    pib = State()
    phone = State()
    instagram = State()
    tiktok = State()
    # youtube = State()
    followers = State()
    idea = State()
    check_subscription = State()

# ------------------ Утилиты ------------------
def extract_username_from_link(url: str) -> str:
    """
    Extract username from instagram or tiktok url.
    Returns username or None.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip().rstrip("/")
    # Instagram patterns
    m = re.search(r"(?:instagram\.com/)(?:@?)([A-Za-z0-9._]+)", url, re.IGNORECASE)
    if m:
        return m.group(1)
    # TikTok patterns
    m = re.search(r"(?:tiktok\.com/@)([A-Za-z0-9._]+)", url, re.IGNORECASE)
    if m:
        return m.group(1)
    # fallback: last path part
    parts = url.split("/")
    if parts:
        return parts[-1]
    return None

def update_status_in_csv(chat_id: int, status: str, csv_file: str = CSV_FILE):
    rows = []
    updated = False
    with open(csv_file, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("chat_id")) == str(chat_id):
                row["Статус"] = status
                updated = True
            rows.append(row)
    if updated:
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "ПІБ",
                "Телефон",
                "Instagram",
                "TikTok",
                "YouTube Shorts",
                "Підписники / Перегляди",
                "Ідея",
                "Telegram username",
                "Дата",
                "Статус",
                "chat_id",
            ])
            writer.writeheader()
            writer.writerows(rows)

# ------------------ Команды ------------------
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Привіт! Це бот акції Proove Gaming Challenge! Тобі вже є 18 років?",
        reply_markup=start_kbd,
    )

@dp.message(Command("id"))
async def get_admin_id(message: types.Message):
    await message.answer(f"Ваш Chat_ID: {message.chat.id}")

@dp.message(Command("admin"))
async def get_admin_panel(message:types.Message):
    if message.chat.id in ADMIN_CHAT_IDS:
        await message.answer("TELEGRAM Адмін панель", reply_markup=admin_panel)
    else:
        await message.answer("У вас немає доступу до цієї команди")

# ------------------ Кнопки возраст ------------------
@dp.callback_query(lambda c: c.data == "start_yes")
async def user_info(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔤 Напиши своє ПІБ:")
    await state.set_state(Form.pib)

@dp.callback_query(lambda c: c.data == "start_no")
async def start_age_no(callback: types.CallbackQuery):
    await callback.message.answer(
        "Це погано, потрібно щоб вам було від 18 років", reply_markup=back_kbds
    )

@dp.callback_query(lambda c: c.data == "previous_start_message")
async def previous_start_message(callback: types.CallbackQuery):
    await callback.message.answer(
        "👋 Привіт! Це бот акції Proove Gaming Challenge! Тобі вже є 18 років?",
        reply_markup=start_kbd,
    )

# ------------------ Анкета ------------------
@dp.message(Form.pib)
async def get_pib(message: types.Message, state: FSMContext):
    await state.update_data(pib=message.text)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Надіслати номер телефону", request_contact=True)]],
        resize_keyboard=True,
    )
    await message.answer("📞 Надішли свій номер телефону:", reply_markup=kb)
    await state.set_state(Form.phone)

import csv

@dp.message(Form.phone)
async def get_phone(message: types.Message, state: FSMContext):
    if not message.contact or not message.contact.phone_number:
        await message.answer("❗ Надішліть номер телефону через кнопку нижче!")
        return

    phone = message.contact.phone_number

    # Проверяем, есть ли уже такой номер в CSV
    already_registered = False
    try:
        with open(CSV_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Телефон") == phone:
                    already_registered = True
                    break
    except FileNotFoundError:
        # Файл может еще не существовать, тогда регистрация возможна
        pass

    if already_registered:
        await message.answer("❌ Цей номер телефону вже зареєстрований. Повторна реєстрація не дозволена.")
        await state.clear()  # Завершаем состояние, чтобы пользователь мог начать заново или остановить
        return

    # Если номер уникален — продолжаем
    await state.update_data(phone=phone)

    await message.answer("🔗 Введи посилання на свій Instagram профіль:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.instagram)


@dp.message(Form.instagram)
async def get_instagram(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() == "немає" or text == "Немає":
        await state.update_data(instagram="Немає")
        await message.answer("🔗 Введи посилання на свій TikTok профіль:")
        await state.set_state(Form.tiktok)
        return

    if "instagram.com" not in text:
        await message.answer(
            "❗ Це не схоже на Instagram посилання. Спробуй ще раз",
        )
        return

    # extract username and check subscription to target
    user_username = extract_username_from_link(text)
    if not user_username:
        await message.answer("❗ Не вдалося витягти username з посилання. Спробуйте ще раз.")
        return

    # Save link
    await state.update_data(instagram=text)

    # Run check against our target account(s) — example "proove_gaming"
    target_instagram = "proove_gaming_ua"  # change if needed

    await message.answer("⏳ Перевіряю підписку в Instagram... Будь ласка, зачекай.")
    try:
        ok = await asyncio.wait_for(check_instagram_follow(target_instagram, user_username), timeout=120)
    except asyncio.TimeoutError:
        await message.answer("❌ Перевірка зайняла забагато часу. Спробуйте пізніше.")
        return
    except Exception as e:
        await message.answer(f"❌ Помилка перевірки: {e}")
        return

    if ok:
        await message.answer("✅ Ви підписані на Instagram! Продовжуємо анкету.")
        await message.answer("🔗 Введи посилання на свій TikTok профіль:")
        await state.set_state(Form.tiktok)
    else:
        await message.answer(
            "❌ Ми не знайшли вашу підписку на Instagram. Підпишіться на proove_gaming_ua і натисніть 'Я підписався'.",
            reply_markup=subscribe_keyboard
        )
        await state.set_state(Form.check_subscription)

@dp.message(Form.tiktok)
async def get_tiktok(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() in ("немає", "не має", "Немає"):
        await state.update_data(tiktok="Немає")
        # Переходим сразу к followers, пропускаем youtube
        await message.answer("👥 Введи кількість підписників або середні перегляди:")
        await state.set_state(Form.followers)
        return

    if "tiktok.com" not in text:
        await message.answer(
            "❗ Це не схоже на TikTok посилання. Спробуй ще раз"
        )
        return

    user_username = extract_username_from_link(text)
    if not user_username:
        await message.answer("❗ Не вдалося витягти username з посилання. Спробуйте ще раз.")
        return

    await state.update_data(tiktok=text)

    target_tiktok = "proove_gaming_ua"
    await message.answer("⏳ Перевіряю підписку в TikTok... Будь ласка, зачекай.")
    try:
        ok = await asyncio.wait_for(check_tiktok_follow(target_tiktok, user_username), timeout=380)
    except asyncio.TimeoutError:
        await message.answer("❌ Перевірка зайняла забагато часу. Спробуйте пізніше.", reply_markup=back_kbds)
        return
    except Exception as e:
        await message.answer(f"❌ Помилка перевірки: {e}")
        return

    if ok:
        await message.answer("✅ Ви підписані на TikTok! Продовжуємо анкету.")
        # Вместо youtube — сразу followers
        await message.answer("👥 Введи кількість підписників або середні перегляди:")
        await state.set_state(Form.followers)
    else:
        await message.answer(
            "❌ Ми не знайшли вашу підписку на TikTok. Підпишіться на proove_gaming_ua і натисніть 'Я підписався'.",
            reply_markup=subscribe_keyboard
        )
        await state.set_state(Form.check_subscription)

@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_again(callback: types.CallbackQuery, state: FSMContext):
    # Отвечаем сразу, чтобы не получить ошибку из-за таймаута
    await callback.answer("Перевірка триває, зачекайте...", show_alert=False)

    data = await state.get_data()
    ig_link = data.get("instagram")
    tt_link = data.get("tiktok")

    if ig_link and ig_link != "Немає":
        username = extract_username_from_link(ig_link)
        if username:
            await callback.message.answer("⏳ Перевіряю Instagram...")
            try:
                ok = await asyncio.wait_for(check_instagram_follow("proove_gaming_ua", username), timeout=120)
            except Exception as e:
                await callback.message.answer(f"❌ Помилка при перевірці: {e}")
                return
            if ok:
                await callback.message.answer("✅ Підписка на Instagram підтверджена. Продовжуємо.")
                if not tt_link or tt_link == "Немає":
                    await callback.message.answer("🔗 Введи посилання на свій TikTok профіль:")
                    await state.set_state(Form.tiktok)
                    return
            else:
                await callback.message.answer("❌ Все ще не бачимо підписки в Instagram. Перевірте та спробуйте ще.")
                return

    if tt_link and tt_link != "Немає":
        username = extract_username_from_link(tt_link)
        if username:
            await callback.message.answer("⏳ Перевіряю TikTok...")
            try:
                ok = await asyncio.wait_for(check_tiktok_follow("proove_gaming_ua", username), timeout=120)
            except Exception as e:
                await callback.message.answer(f"❌ Помилка при перевірці: {e}")
                return
            if ok:
                await callback.message.answer("✅ Підписка на TikTok підтверджена. Продовжуємо.")
                await callback.message.answer("👥 Введи кількість підписників або середні перегляди:")
                await state.set_state(Form.followers)
                return
            else:
                await callback.message.answer("❌ Все ще не бачимо підписки в TikTok. Перевірте та спробуйте ще.")
                return

    # Если ни по Instagram, ни по TikTok подписка не найдена:
    await callback.message.answer(
        "❗ Не вдалося підтвердити підписки. Перевірте, будь ласка, чи ви підписані та натисніть 'Я підписався' ще раз.",
        reply_markup=subscribe_keyboard,
    )

# @dp.message(Form.youtube)
# async def get_youtube(message: types.Message, state: FSMContext):
#     text = message.text.strip()
#     if text.lower() in ("немає", "не має", "Немає"):
#         await state.update_data(youtube="Немає")
#         await message.answer("👥 Введи кількість підписників або середні перегляди:")
#         await state.set_state(Form.followers)
#         return

#     if "youtube.com" not in text:
#         await message.answer(
#             "❗ Це не схоже на YouTube посилання. Спробуй ще раз або натисни, якщо немає акаунту:",
#             reply_markup=social_no_kbd,
#         )
#         return

#     await state.update_data(youtube=text)
#     await message.answer("👥 Введи кількість підписників або середні перегляди:")
#     await state.set_state(Form.followers)

@dp.message(Form.followers)
async def get_followers(message: types.Message, state: FSMContext):
    await state.update_data(followers=message.text)
    await message.answer("💡 Опиши ідею для безпечного та креативного знищення старої клавіатури:")
    await state.set_state(Form.idea)

@dp.callback_query(lambda c: c.data == "no_social_account")
async def no_social_account(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == Form.instagram.state:
        await state.update_data(instagram="Немає")
        await callback.message.answer("🔗 Введи посилання на свій TikTok профіль:")
        await state.set_state(Form.tiktok)
    elif current_state == Form.tiktok.state:
        await state.update_data(tiktok="Немає")
        await callback.message.answer("👥 Введи кількість підписників або середні перегляди:")
        await state.set_state(Form.followers)
    await callback.answer()

@dp.message(Form.idea)
async def get_idea(message: types.Message, state: FSMContext):
    await state.update_data(idea=message.text)
    data = await state.get_data()

    username = message.from_user.username or "немає"
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    chat_id = message.chat.id

    row = [
        data.get("pib", ""),
        data.get("phone", ""),
        data.get("instagram", ""),
        data.get("tiktok", ""),
        data.get("youtube", ""),
        data.get("followers", ""),
        data.get("idea", ""),
        username,
        date,
        "Очікує",
        chat_id,
    ]

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    for admin_id in ADMIN_CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"📥 Нова заявка:\n\n"
                    f"👤 ПІБ: {data.get('pib','')}\n"
                    f"📱 Телефон: {data.get('phone','')}\n"
                    f"📷 Instagram: {data.get('instagram','')}\n"
                    f"🎵 TikTok: {data.get('tiktok','')}\n"
                    f"▶️ YouTube Shorts: {data.get('youtube','')}\n"
                    f"👥 Підписники / Перегляди: {data.get('followers','')}\n"
                    f"💡 Ідея: {data.get('idea','')}\n"
                    f"📅 Дата: {date}\n"
                    f"👤 Telegram: @{username}\n"
                    f"🧾 Статус: Очікує",
                parse_mode=ParseMode.HTML,
                reply_markup=admin_choices_kbd(chat_id, username)
            )
        except Exception as e:
            log.error(f"Не вдалося надіслати повідомлення адміну {admin_id}: {e}")


    await message.answer("✅ Дякуємо! Твою заявку прийнято. Ми зв’яжемося з тобою найближчим часом!")
    await state.clear()

# --------------- Admin decisions ---------------
reject_reasons = {
    "1": "❌Ваша заявка відхилена\nСценарій не відповідає вимогам челенджу. (Ознайомтесь із правилами та спробуйте знову.)",
    "2": "❌ Ваша заявка відхилена\nВи виконали не всі кроки для участі. (Перевірте умови та спробуйте знову.).",
    "3": "❌ Ваша заявка відхилена\nПідписка на соцмережу — обов’язкова умова. (Додайте підписку та спробуйте знову.)",
    "4": "❌ Ваша заявка відхилена\nМаксимальна кількість учасників досягнута. Дякуємо, що ви є частиною Proove Gaming👾",
}

@dp.callback_query(lambda c: c.data and c.data.startswith("admin_accept_"))
async def handle_accept(callback: types.CallbackQuery):
    parts = callback.data.split("_", 3)
    if len(parts) < 4:
        await callback.answer("Невірні дані.", show_alert=True)
        return
    user_id_str = parts[2]
    safe_username = parts[3]
    try:
        user_id = int(user_id_str)
    except ValueError:
        await callback.answer("Невірний chat_id.", show_alert=True)
        return
    username = safe_username.replace("__", "_")

    update_status_in_csv(user_id, "Прийнято")

    try:
        await bot.send_message(user_id, (
            "✅Ваша заявка на участь у розіграші прийнята! \n\n"
            "Наступні кроки:\n"
            "1. Зніміть відео та опублікуйте його у своїх соцмережах Instagram або TikTok до 30.08.\n"
            "2. Обов’язково відмітьте акаунти Proove Gaming та додайте хештег #ProoveGamingChallenge.\n"
            "3. Надішліть посилання на ваше відео у Telegram @pgchallenge.\n\n"
            "Результати розіграшу та імена переможців (Топ-3) будуть оголошені 04.09 на наших офіційних сторінках:\n"
            "Instagram\n"
            "TikTok\n\n"
            "Бажаємо успіху!\n"
            "https://www.tiktok.com/@proove_gaming_ua?_t=ZM-8yohKjOALuI"
        ))
        await callback.message.edit_text(f"Рішення 'прийнято' застосовано для користувача @{username} ({user_id}).")
    except Exception as e:
        await callback.message.edit_text(f"❌ Не вдалося надіслати повідомлення користувачу: {e}")

    await callback.answer("Заявка прийнята!")


@dp.callback_query(lambda c: c.data and c.data.startswith("admin_reject_"))
async def handle_reject(callback: types.CallbackQuery):
    parts = callback.data.split("_", 4)
    if len(parts) < 5:
        await callback.answer("Невірні дані.", show_alert=True)
        return
    reason_key = parts[2]  # reject reason number: "1", "2", ...
    user_id_str = parts[3]
    safe_username = parts[4]

    try:
        user_id = int(user_id_str)
    except ValueError:
        await callback.answer("Невірний chat_id.", show_alert=True)
        return

    username = safe_username.replace("__", "_")
    update_status_in_csv(user_id, f"Відхилено ({reason_key})")

    reason_text = reject_reasons.get(reason_key, "❌ Ваша заявка відхилена.")

    try:
        await bot.send_message(user_id, reason_text)
        await callback.message.edit_text(f"Рішення 'відхилено' (причина {reason_key}) застосовано для користувача @{username} ({user_id}).")
    except Exception as e:
        await callback.message.edit_text(f"❌ Не вдалося надіслати повідомлення користувачу: {e}")

    await callback.answer(f"Заявка відхилена з причиною {reason_key}!")


# FSM для добавления нового админа
class AdminFSM(StatesGroup):
    waiting_chat_id = State()

# Обработчик кнопки "Добавить нового админа"
@dp.callback_query(lambda c: c.data == "add_new_admin")
async def add_new_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    # Проверяем, что это админ
    admins = load_admins()
    if callback.from_user.id not in admins:
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    await callback.message.answer("Введи chat_id пользователя, которого хочешь сделать админом:")
    await state.set_state(AdminFSM.waiting_chat_id)
    await callback.answer()

@dp.message(AdminFSM.waiting_chat_id)
async def receive_new_admin(message: types.Message, state: FSMContext):
    try:
        new_admin_id = int(message.text)
    except ValueError:
        await message.answer("❌ Некорректный chat_id. Введите число.")
        return

    admins = add_admin(new_admin_id)
    await message.answer(f"✅ Пользователь {new_admin_id} добавлен в админы!\nТекущие админы: {admins}")
    await state.clear()



# ------------------ Запуск ------------------
async def run_bot():
    
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands()

    try:
        me = await bot.get_me()
        log.info(f"Бот @{me.username} успешно подключен!")
    except Exception as e:
        log.error(f"Ошибка подключения бота: {e}")
        raise

    await dp.start_polling(bot)

# if __name__ == "__main__":
#     try:
#         asyncio.run(run_bot())
#     except (KeyboardInterrupt, SystemExit):
#         log.info("Бот зупинений вручну")
