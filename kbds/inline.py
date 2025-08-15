from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Кнопка старта
start_kbd = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Так ✅', callback_data='start_yes')],
    [InlineKeyboardButton(text='Ні ⛔', callback_data='start_no')],
])

# Кнопка "назад"
back_kbds = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Повернутися', callback_data='previous_start_message')],
])

# Кнопки администратора
def admin_choices_kbd(chat_id: int, username: str) -> InlineKeyboardMarkup:
    safe_username = username.replace('_', '__')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Прийняти", callback_data=f"admin_accept_{chat_id}_{safe_username}")],
        [InlineKeyboardButton(text="❌ Відхилити 'Сценарій'", callback_data=f"admin_reject_1_{chat_id}_{safe_username}")],
        [InlineKeyboardButton(text="❌ Відхилити 'Не всі кроки'", callback_data=f"admin_reject_2_{chat_id}_{safe_username}")],
        [InlineKeyboardButton(text="❌ Відхилити 'Підпіска на соц. мереж.'", callback_data=f"admin_reject_3_{chat_id}_{safe_username}")],
        [InlineKeyboardButton(text="❌ Відхилити 'Макс. кількість'", callback_data=f"admin_reject_4_{chat_id}_{safe_username}")],

    ])

admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Адмін панель", url="https://249d19e4fad4.ngrok-free.app")],
    [InlineKeyboardButton(text="Добавити Адміністратора", callback_data="add_new_admin")],
])


# Кнопка "нет соцсети"
social_no_kbd = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Немає аккаунту ❌", callback_data="no_social_account")]
])

subscribe_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Подписаться на Instagram", url="https://instagram.com/proove_gaming_ua")],
    [InlineKeyboardButton(text="Подписаться на TikTok", url="https://tiktok.com/@proove_gaming_ua")],
    [InlineKeyboardButton(text="Я подписался", callback_data="check_subscription")]
])
