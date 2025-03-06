import operator
import nest_asyncio
nest_asyncio.apply()

import asyncio
import logging
import configparser
import os
import shutil
import string
import random
import time
import httpx
import locale  # Импорт библиотеки locale
import locale  # Импорт библиотеки locale
locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')  # Установка локали для корректного форматирования чисел
from datetime import datetime  
from uuid import uuid4

# Removed requests, csv, StringIO imports
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
        
# Файл .ini для хранения всех данных бота

ACCOUNTS_FILE = "accounts.ini"
REPORTS_FILE = "reports.ini"
WITHDRAWALS_FILE = "withdrawals.ini"
REGISTRATIONS_FILE = "registrations.ini"
admin_ids = [737010714]
REG_NAME, REG_REALNAME, REG_BIRTHDATE = range(3)

async def unknown_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Пожалуйста, используйте доступные команды или введите корректные данные.")

# Функция загрузки данных из .ini-файла (с отключенной интерполяцией для символа '%')
def load_accounts():
    config = configparser.ConfigParser(interpolation=None)
    config.read(ACCOUNTS_FILE, encoding="utf-8")
    return config

def save_accounts(config):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as configfile:
        config.write(configfile)
        
def load_reports():
    config = configparser.ConfigParser(interpolation=None)
    config.read(REPORTS_FILE, encoding="utf-8")
    return config

def load_withdrawals():
    config = configparser.ConfigParser(interpolation=None)
    config.read(WITHDRAWALS_FILE, encoding="utf-8")
    return config

def load_registrations():
    config = configparser.ConfigParser(interpolation=None)
    config.read(REGISTRATIONS_FILE, encoding="utf-8")
    return config

# Система плана (получение пользователей)
def get_top_players():
    config = load_accounts()
    players = []
    for section in config.sections():
        if section.isdigit():  # Проверяем, что это ID пользователя
            try:
                ball = int(config[section].get('ball', 0))
                nick = config[section].get('nick', 'Неизвестный')
                players.append((nick, ball))
            except ValueError:
                continue  # Пропустить пользователя, если значение ball некорректное
    top_players = sorted(players, key=operator.itemgetter(1), reverse=True)[:3]
    return top_players

# Генерация случайного ID из заданного числа символов (для идентификаторов отчётов)
def generate_random_id(length=5):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# Обработчик колбэков (не используется напрямую, оставлен для совместимости)
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query  # Заглушка

# Токен бота (замените на актуальный перед запуском)
TOKEN = '8108534662:AAGITJNoOW2VQotLETnJAuJjVoOkpX2VzHA'  # ПЕРЕД запуском бота ОБНОВИТЬ токен

# Получение информации о пользователе по Telegram ID из .ini-файла
def get_user_info(user_id):
    config = load_accounts()
    sec_name = str(user_id)
    if config.has_section(sec_name):
        sec = config[sec_name]
        rank = int(sec.get('rank', '-1'))  
        daily_rate = get_daily_rate(rank)  
        ball = int(sec.get('ball', '0')) if 'ball' in sec else 0
        warnings = int(sec.get('warnings', '0'))
        predicted_payment = calculate_predicted_payment(ball=ball, daily_rate=daily_rate, warnings=warnings)
        return {
            'nick': sec.get('nick', ''), 
            'position': sec.get('position', ''), 
            'rank': rank, 
            'daily_rate': daily_rate, 
            'warnings': sec.get('warnings', '0'), 
            'predicted_payment': predicted_payment, 
            'personal_account': sec.get('personal_account', '0'), 
            'rating': sec.get('rating', '0'), 
            'ball': ball, 
            'is_admin': sec.get('is_admin', '-1'),
            'realname': sec.get('realname', ''), 
            'daterod': sec.get('daterod', ''), 
        }
    return None

# Функция для получения ставки в зависимости от разряда
def get_daily_rate(rank):
    rates = {
        -1: 0,  # Отсутствие разряда
        0: 150000,
        1: 175000,
        2: 200000,
        3: 225000,
        4: 250000,
        5: 275000,
        6: 300000,
        7: 325000,
        8: 350000,
        9: 375000,
        10: 400000
    }
    return rates.get(rank, 0)

# Функция для расчета predicted_payment
def calculate_predicted_payment(ball, daily_rate, warnings):
    reduction_factor = 1 - (0.25 * warnings)
    return ball * daily_rate * reduction_factor

def update_balls():
    config = load_accounts()
    updated = False
    for section in config.sections():
        if section.isdigit():  
            ball = int(config[section].get('ball', 0))
            
            if config[section].get('ball') != str(ball):
                config[section]['ball'] = str(ball)
                updated = True
                logging.info(f"Updated ball for user {section}: ball={ball}")
    
    if updated:
        save_accounts(config)
        logging.info("All updates saved to accounts.ini")
    else:
        logging.info("No updates needed")

# Клавиатура главного меню
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("Личный кабинет"), KeyboardButton("Рейтинг")],
        [KeyboardButton("Отчёт"), KeyboardButton("Активность")],
        [KeyboardButton("Вывод средств")],
        [KeyboardButton("Панель администратора")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# Клавиатура для кнопки "Назад"
def get_back_keyboard():
    keyboard = [[KeyboardButton("Назад")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# Стартовое приветствие (/start)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Для входа в систему нажмите кнопку ниже.",
        reply_markup=get_login_keyboard()
    )

# Обработчик кнопки "Войти"
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Авторизация":
        await login(update, context)

# Вход в систему (по нажатию "Войти" или сообщению "войти")
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    
    if not user_info:
        await update.message.reply_text("Ваш Telegram ID не найден в базе данных. Обратитесь к администратору бота.")
        return
    
    admin_level = int(user_info.get('is_admin', 0))
    nick = user_info['nick']
    rank = user_info['rank']

    if admin_level == -1:
        await update.message.reply_text(
            f"🐻 Рады приветствовать снова *{nick}*!\n"
            f"⚪ Вы авторизовались как Гость. Для выдачи прав обратитесь к администратору бота.",
            parse_mode="Markdown"
        )
    if admin_level == 0:
        await update.message.reply_text(
            f"🐻 Рады приветствовать снова *{nick}*!\n"
            f"🔵 Вы авторизовались как Заместитель *{rank}* разряда.",
            parse_mode="Markdown"
        )
    elif admin_level == 1:
        await update.message.reply_text(
            f"🐻 Рады приветствовать снова *{nick}*!\n"
            f"🟡 Вы авторизовались как Почётный заместитель.",
            parse_mode="Markdown"
        )
    elif admin_level == 2:
        await update.message.reply_text(
            f"🐻 Рады приветствовать снова *{nick}*!\n"
            f"🟠 Вы авторизовались как Старший заместитель.",
            parse_mode="Markdown"
        )
    elif admin_level == 3:
        await update.message.reply_text(
            f"🐻 Рады приветствовать снова *{nick}*!\n"
            f"🔴 Вы авторизовались как Лидер семьи.",
            parse_mode="Markdown"
        )
    
    await update.message.reply_text("Ниже представлено главное меню. Выберите нужный вариант.", reply_markup=get_main_keyboard())


# Клавиатура для входа (кнопка "Войти")
def get_login_keyboard():
    keyboard = [
        [KeyboardButton("Авторизация"), KeyboardButton("Регистрация")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# Возврат в главное меню (/menu)
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    admin_level = int(user_info.get('is_admin', 0)) if user_info else 0
    await update.message.reply_text(
        "Ниже представлено главное меню. Выберите нужный вариант.",
        reply_markup=get_main_keyboard()
    )

# Личный кабинет (команда "Личный кабинет")
async def personal_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    if user_info:
        predicted_payment_formatted = locale.format_string("%d", user_info['predicted_payment'], grouping=True).replace(' ', '.')
        daily_rate_formatted = locale.format_string("%d", user_info['daily_rate'], grouping=True).replace(' ', '.')
        personal_account_formatted = locale.format_string("%d", int(user_info['personal_account']), grouping=True).replace(' ', '.')
        message = (
            f"📌 Личный кабинет\n\n"
            f"👤 Никнейм: {user_info['nick']}\n"
            f"🔮 Реальное имя: {user_info['realname']}\n"
            f"🎂 Дата рождения: {user_info['daterod']}\n"
            f"💼 Должность: {user_info['position']}\n"
            f"⭐ Разряд: {user_info['rank']}\n"
            f"💰 Ставка в день: {daily_rate_formatted} RUB\n"
            f"⚠️ Предупреждения: {user_info['warnings']}\n"
            f"✴️ Баллы: {user_info['ball']}\n"
            f"💸 Зарплата: {predicted_payment_formatted} RUB\n"
            f"💳 Личный счет: {personal_account_formatted} RUB" 
        )
        await update.message.reply_text(message, reply_markup=get_back_keyboard())
    else:
        await update.message.reply_text("Информация о пользователе не найдена.", reply_markup=get_back_keyboard())
        
# Рейтинг (команда "Рейтинг")
async def rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_players = get_top_players()
    if not top_players:
        await update.message.reply_text("На данный момент нет пользователей в рейтинге.", reply_markup=get_back_keyboard())
        return

    message = "🏆 Рейтинг заместителей по активности за расчётную неделю:\n\n"
    emojis = ["🥇", "🥈", "🥉"]
    for i, (nick, ball) in enumerate(top_players):
        message += f"{emojis[i]} {nick}: {ball} баллов\n"
    
    message += "\nЧто получает Лидер ❓\n"
    message += "🏆 Первое место в рейтинге получает гарантированное повышение в разряде без ограничений при наличии 5 активных заместителей."

    await update.message.reply_text(message, reply_markup=get_back_keyboard())

# План работ (команда "План")
async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_text = (
        "1️⃣ Бальная система — это система выплат заработной платы за расчётную неделю.\n"
        "2️⃣ Баллы начисляются за любую активность согласно существующим системам.\n"
        "3️⃣ Выплачивается относительно вклада каждого члена старшего состава.\n"
        "4️⃣ Действует разрядная система и поощрительные выплаты.\n"
        "5️⃣ Для заместителей установлены нормы активности в неделю.\n"
        "6️⃣ В случае нарушения норм они могут быть понижены или сняты.\n\n"
        "🏆 Активность.\n"
        "🔴 Минимальная активность – от 200 до 299 баллов в неделю.\n"
        "🟢 Средняя активность – от 300 до 399 баллов в неделю.\n"
        "🟡 Максимальная активность – от 400 баллов в неделю.\n\n"
        "🎁 Бонусы.\n"
        "🟢 Средняя активность – 50 баллов и средний шанс повышения.\n"
        "🟡 Максимальная активность – 100 баллов и высокий шанс повышения."
    )
    await update.message.reply_text(f"ℹ️ FAQ по активности.\n\n{plan_text}", reply_markup=get_back_keyboard())

# Панель администратора (команда "Панель администратора")
# Панель администратора (команда "Панель администратора")
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    
    # Проверка наличия информации о пользователе и прав администратора
    if not user_info or int(user_info['is_admin']) == 0:
        await update.message.reply_text("⛔ У вас нет доступа к этому разделу.")
        return

    admin_level = int(user_info.get('is_admin', 0))

    # Инициализация клавиатуры
    keyboard = []

    # Кнопки для администраторов с уровнем 1 и выше
    if admin_level >= 1:
        keyboard.append([InlineKeyboardButton("👥 Управление пользователями", callback_data="manage_users")])
        
    # Кнопки для администраторов с уровнем 2 и выше
    if admin_level >= 2:
        keyboard.append([InlineKeyboardButton("📊 Отчеты", callback_data="reports")])
        keyboard.append([InlineKeyboardButton("📢 Массовая рассылка", callback_data="mass_message")])
        keyboard.append([InlineKeyboardButton("✉ Одиночная рассылка", callback_data="start_single_message")])
        keyboard.append([InlineKeyboardButton("📋 Заявки на регистрацию", callback_data="view_registrations")])

    # Кнопка для администраторов с уровнем 3
    if admin_level >= 3:
        keyboard.append([InlineKeyboardButton("💰 Заявки на вывод", callback_data="admin_withdrawals")])

    # Отправка клавиатуры с кнопками
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("✅ Вы вошли в панель администратора.", reply_markup=reply_markup)

# Команда "Отчёт" (подача нового отчета или проверка статуса существующего)
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        config = load_reports()
    except Exception as e:
        logging.error(f"Error loading report data for user {user_id}: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке данных отчетов.", reply_markup=get_back_keyboard())
        return

    # Отображение списка отчетов на рассмотрении
    pending_reports = []
    for sec in config.sections():
        if sec.startswith("report_") and config[sec].get("user_id") == str(user_id) and config[sec].get("status", "pending") == "pending":
            pending_reports.append(sec)

    if pending_reports:
        reports_message = "📋 Ваши отчеты на рассмотрении:\n\n"
        for report_id in pending_reports:
            reports_message += f"⏳ Отчет ID: {report_id[len('report_'):]}\n"
        await update.message.reply_text(reports_message, reply_markup=get_back_keyboard())

    # Позволить пользователю создавать новый отчет
    context.user_data['report_state'] = 'await_text'
    logging.info(f"User {user_id} is creating a new report.")
    await update.message.reply_text(
        "✏️ Пожалуйста, отправьте текст вашего отчета.",
        reply_markup=get_back_keyboard()
    )

# Обработчик выбора пункта меню (общий для кнопок главного меню)
async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    admin_level = int(user_info.get('is_admin', 0)) if user_info else 0
    
    if admin_level == -1:
        await update.message.reply_text("Для выдачи прав обратитесь к администратору бота.")
        return

    try:
        text = update.message.text.strip()
        logging.info(f"Обработка команды: {text}")
        if text == "Личный кабинет":
            await personal_account(update, context)
        elif text == "Отчёт":
            await report(update, context)
        elif text == "Вывод средств":
            await request_withdrawal(update, context)
        elif text == "Рейтинг":
            await rating(update, context)
        elif text == "Активность":
            await plan(update, context)
        elif text == "Панель администратора":
            await admin(update, context)
        elif text == "Назад":
            await menu(update, context)
        else:
            logging.warning(f"Неизвестная команда: {text}")
    except Exception as e:
        logging.error(f"Ошибка в обработке меню: {e}")

# Сохранение заявки на вывод средств в .ini-файл
async def save_request(request_id: str, nick: str, amount: float, remaining_balance: float, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    config = load_withdrawals()
    config[f"request_{request_id}"] = {
        "nick": nick,
        "amount": str(amount),
        "remaining_balance": str(remaining_balance),
        "user_id": str(user_id),
        "status": "pending"
    }
    with open(WITHDRAWALS_FILE, "w", encoding="utf-8") as configfile:
        config.write(configfile)

# Удаление заявки на вывод средств из .ini-файла
def remove_request(request_id: str):
    config = load_withdrawals()
    sec_name = f"request_{request_id}"
    if config.has_section(sec_name):
        config.remove_section(sec_name)
        with open(WITHDRAWALS_FILE, "w", encoding="utf-8") as configfile:
            config.write(configfile)

# Пользователь выбрал "Вывод средств" (инициация заявки)
async def request_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await update.message.reply_text("Ошибка: Информация о пользователе не найдена.")
        return
    balance = float(user_info['personal_account'])
    if balance <= 0:
        await update.message.reply_text("❌ У вас недостаточно средств для вывода.")
        return
    amounts = {
        25: round(balance * 0.25, 2),
        50: round(balance * 0.50, 2),
        75: round(balance * 0.75, 2),
        100: round(balance * 1.00, 2),
    }
    keyboard = [
        [InlineKeyboardButton(f"Вывести 25% ({amounts[25]})", callback_data="withdraw_25")],
        [InlineKeyboardButton(f"Вывести 50% ({amounts[50]})", callback_data="withdraw_50")],
        [InlineKeyboardButton(f"Вывести 75% ({amounts[75]})", callback_data="withdraw_75")],
        [InlineKeyboardButton(f"Вывести 100% ({amounts[100]})", callback_data="withdraw_100")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите сумму для вывода:", reply_markup=reply_markup)

# Обработчик выбора процента вывода (после кнопок 25%, 50%, 75%, 100%)
async def handle_withdrawal_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_info = get_user_info(user_id)
    if not user_info:
        await query.message.edit_text("Ошибка: Информация о пользователе не найдена.")
        return
    balance = float(user_info['personal_account'])
    percentage = int(query.data.split("_")[1])
    amount = round(balance * (percentage / 100), 2)
    if amount <= 0:
        await query.message.edit_text("Ошибка: Недостаточно средств для вывода.")
        return
    remaining_balance = round(balance - amount, 2)
    request_id = str(uuid4())[:8]
    # Сохраняем данные заявки во временном контексте пользователя (для подтверждения)
    context.user_data[user_id] = {
        "request_id": request_id,
        "amount": amount,
        "remaining_balance": remaining_balance,
        "nick": user_info['nick']
    }
    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data="confirm_withdraw")],
        [InlineKeyboardButton("❌ Нет", callback_data="cancel_withdraw")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        f"🔔 Подтверждение заявки на вывод\n\n"
        f"👤 Ник: {user_info['nick']}\n"
        f"💸 Сумма вывода: {amount} RUB\n"
        f"💳 Остаток после вывода: {remaining_balance}\n\n"
        f"Проверьте, правильно ли указаны данные. Нажмите 'Да', если всё верно, или 'Нет' для отмены."
    )
    # Сохраняем заявку в .ini-файл со статусом "pending"
    await save_request(request_id, user_info['nick'], amount, remaining_balance, user_id, context)
    await query.message.edit_text(message, reply_markup=reply_markup)

# Обработчик подтверждения заявки ("Да")
async def confirm_withdraw_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in context.user_data or "request_id" not in context.user_data[user_id]:
        await query.message.edit_text("❌ Заявка не найдена.")
        return
    req = context.user_data[user_id]
    request_id = req["request_id"]
    amount = req["amount"]
    remaining_balance = req["remaining_balance"]
    nick = req["nick"]
    # Уведомляем администратора о новой заявке
    await notify_admin_about_new_request(nick, amount, request_id, context)
    # Сообщаем пользователю, что заявка отправлена на рассмотрение
    await query.message.edit_text("✅ Заявка отправлена на рассмотрение администрации.")

# Обработчик отмены заявки ("Нет")
async def cancel_withdraw_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id in context.user_data and "request_id" in context.user_data[user_id]:
        req_id = context.user_data[user_id]["request_id"]
        remove_request(req_id)
        context.user_data.pop(user_id, None)
    await query.message.edit_text("❌ Заявка на вывод отменена.")

# Обработчик нажатия "Заявки на вывод" в админ-панели – список активных заявок
async def admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = load_withdrawals()
    # Собираем все заявки со статусом "pending"
    requests = [sec for sec in config.sections() if sec.startswith("request_") and config[sec].get("status", "pending") == "pending"]
    if not requests:
        await query.message.edit_text("📋 Нет заявок, ожидающих подтверждения.")
        return
    text = "📋 Активные заявки на вывод:\n"
    keyboard = []
    for sec in requests:
        nick = config[sec].get("nick", "Неизвестный")
        amount = config[sec].get("amount", "0")
        text += f"\n🔹 {nick} — {amount} RUB"
        req_id = sec[len("request_"):]
        keyboard.append([InlineKeyboardButton(f"ID заявки: {req_id}", callback_data=f"view_{req_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text, reply_markup=reply_markup)

# Обработчик нажатия на конкретную заявку (ID) – просмотр деталей заявки
async def view_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    request_id = query.data.split("_")[1]
    config = load_withdrawals()
    sec_name = f"request_{request_id}"
    if not config.has_section(sec_name):
        await query.message.edit_text("❌ Заявка не найдена.")
        return
    user_id = int(config[sec_name]["user_id"])
    amount = config[sec_name]["amount"]
    nick = config[sec_name]["nick"]
    text = f"Заявка на вывод {amount} RUB для {nick}\nID заявки: {request_id}\nВыберите действие:"
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve_{request_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text, reply_markup=reply_markup)

# Обработчик подтверждения вывода средств (админ нажал "Подтвердить")
async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    request_id = query.data.split("_")[1]
    config = load_withdrawals()
    sec_name = f"request_{request_id}"
    if not config.has_section(sec_name):
        await query.message.edit_text("❌ Заявка не найдена.")
        return
    user_id = int(config[sec_name]["user_id"])
    amount = config[sec_name]["amount"]
    nick = config[sec_name]["nick"]
    # Удаляем заявку из файла
    config.remove_section(sec_name)
    with open(WITHDRAWALS_FILE, "w", encoding="utf-8") as f:
        config.write(f)
    # Уведомляем пользователя об одобрении заявки
    await context.bot.send_message(user_id, f"✅ Ваш вывод {amount} RUB одобрен, не забудьте обязательно заполнить тему - бюджет семьи!")
    await query.message.edit_text(f"✅ Вывод {amount} RUB для {nick} одобрен!")

# Обработчик отклонения заявки ("Отклонить")
async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    request_id = query.data.split("_")[1]
    config = load_withdrawals()
    sec_name = f"request_{request_id}"
    if not config.has_section(sec_name):
        await query.message.edit_text("❌ Заявка не найдена.")
        return
    user_id = int(config[sec_name]["user_id"])
    amount = config[sec_name]["amount"]
    nick = config[sec_name]["nick"]
    # Удаляем заявку из файла
    config.remove_section(sec_name)
    with open(WITHDRAWALS_FILE, "w", encoding="utf-8") as f:
        config.write(f)
    # Логируем отклонение (для отладки)
    print(f"Заявка {request_id} отклонена и удалена.")
    try:
        # Уведомляем пользователя об отклонении
        await context.bot.send_message(user_id, f"❌ Ваша заявка на вывод {amount} RUB отклонена. Пожалуйста, свяжитесь с руководством для уточнений.")
    except Exception as e:
        print(f"Ошибка при отправке сообщения пользователю: {e}")
        await query.message.edit_text("❌ Ошибка при отправке сообщения пользователю.")
        return
    await query.message.edit_text(f"❌ Заявка на вывод {amount} RUB для {nick} отклонена.")

# Уведомление администратора о новой заявке на вывод
async def notify_admin_about_new_request(nick: str, amount: float, request_id: str, context: ContextTypes.DEFAULT_TYPE):
    if not admin_ids:
        return
    admin_id = admin_ids[0]
    message = (
        f"🆕 Новая заявка на вывод\n\n"
        f"👤 Пользователь: {nick}\n"
        f"💸 Сумма вывода: {amount} RUB\n"
        f"🆔 ID заявки: {request_id}\n\n"
        f"Проверьте заявку в админ-панели для окончательного подтверждения или отклонения."
    )
    try:
        await context.bot.send_message(admin_id, message)
        print(f"Уведомление отправлено админу {admin_id}")
    except Exception as e:
        print(f"Ошибка при отправке уведомления админу: {e}")

# Массовая рассылка (инициация)
async def mass_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message_text = "Введите сообщение для массовой рассылки:"
    keyboard = [[InlineKeyboardButton("Отменить", callback_data="cancel_mass_message")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(message_text, reply_markup=reply_markup)
    context.user_data['mass_message'] = True

# Отмена массовой рассылки
async def cancel_mass_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if 'mass_message' in context.user_data:
        del context.user_data['mass_message']
    await query.message.edit_text("❌ Массовая рассылка отменена.")

# Одиночная рассылка (инициация)
async def single_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = load_accounts()
    # Собираем список всех пользователей (ID и никнейм)
    users = [(sec, config[sec].get("nick", "Неизвестный")) for sec in config.sections() if sec.isdigit()]
    if not users:
        await query.message.reply_text("⚠️ Нет пользователей для отправки сообщений.")
        return
    buttons = []
    for user_id, user_name in users:
        buttons.append([InlineKeyboardButton(user_name, callback_data=f"single_user_{user_id}")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.message.reply_text("👤 *Выберите пользователя для отправки сообщения:*", reply_markup=reply_markup, parse_mode="Markdown")

# Обработчик выбора пользователя для одиночной рассылки
async def send_single_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[2])
    context.user_data['single_message_user'] = user_id
    cancel_button = InlineKeyboardButton("Отменить", callback_data="cancel_single_message")
    reply_markup = InlineKeyboardMarkup([[cancel_button]])
    await query.message.reply_text("📝 Введите текст сообщения для отправки выбранному пользователю:", reply_markup=reply_markup)

# Отмена одиночной рассылки
async def cancel_single_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if 'single_message_user' in context.user_data:
        del context.user_data['single_message_user']
    await query.message.reply_text("❌ Одиночная рассылка отменена.")

# Администратор: список отчетов, ожидающих проверки
async def admin_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = load_reports()
    reports = [sec for sec in config.sections() if sec.startswith("report_") and config[sec].get("status", "pending") == "pending"]
    if not reports:
        await query.message.edit_text("📋 Нет отчетов, ожидающих проверки.")
        return
    text = "📋 Активные отчеты:\n"
    keyboard = []
    for sec in reports:
        nick = config[sec].get("nick", "Неизвестный")
        rid = sec[len("report_"):]
        text += f"\n🔹 Отчет от {nick} (ID: {rid})"
        keyboard.append([InlineKeyboardButton(f"ID отчета: {rid}", callback_data=f"viewReport_{rid}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text, reply_markup=reply_markup)

# Администратор: просмотр конкретного отчета (нажатие на кнопку с ID отчета)
async def view_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = query.data[len("viewReport_"):]
    config = load_reports()
    sec_name = f"report_{report_id}"
    if not config.has_section(sec_name):
        await query.message.edit_text("❌ Отчет не найден или уже обработан.")
        return
    sec = config[sec_name]
    user_id = int(sec.get("user_id", 0))
    nick = sec.get("nick", "Неизвестный")
    date = sec.get("date", "")
    folder = f"reports/{report_id}"
    # Загружаем текст отчета из файла
    report_text = ""
    try:
        with open(os.path.join(folder, "text.txt"), "r", encoding="utf-8") as f:
            report_text = f.read()
    except Exception as e:
        logging.error(f"Не удалось прочитать текст отчета {report_id}: {e}")
        report_text = "[Ошибка чтения текста отчета]"
    # Удаляем сообщение со списком отчетов (для чистоты интерфейса)
    try:
        await query.message.delete()
    except Exception as e:
        logging.error(f"Не удалось удалить сообщение списка отчетов: {e}")
    # Отправляем администратору детали отчета
    detail_text = f"Отчёт {report_id} от {nick} (дата: {date}):\n\n{report_text}"
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"approveReport_{report_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"rejectReport_{report_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    admin_chat_id = update.effective_chat.id
    await context.bot.send_message(admin_chat_id, detail_text, reply_markup=reply_markup)
    # Отправляем фотографии отчета (если есть)
    if os.path.isdir(folder):
        files = sorted([f for f in os.listdir(folder) if f.startswith("photo")])
        for fname in files:
            if fname.startswith("photo"):
                try:
                    with open(os.path.join(folder, fname), "rb") as img:
                        await context.bot.send_photo(admin_chat_id, photo=img)
                except Exception as e:
                    logging.error(f"Ошибка отправки фото {fname} отчета {report_id}: {e}")

# Администратор: подтвердить отчет
async def approve_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = query.data[len("approveReport_"):]
    try:
        config = load_reports()
        sec_name = f"report_{report_id}"
        if not config.has_section(sec_name):
            await query.message.edit_text("❌ Отчет не найден.")
            return
        nick = config[sec_name].get("nick", "Неизвестный")
        user_id = int(config[sec_name].get("user_id", 0)) if config[sec_name].get("user_id") else 0

        # Обновляем статус отчета на "approved"
        config[sec_name]["status"] = "approved"
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            config.write(f)

        # Уведомляем администратора и запрашиваем количество принятых человек
        context.user_data['approve_report_id'] = report_id
        context.user_data['approve_user_id'] = user_id
        await query.message.edit_text(
            f"🕓 Отчёт ID {report_id} от {nick} подтверждён частично.\n\n"
            "‼ Пожалуйста, напишите в чат количество баллов для начисления заместителю:"
        )
    except Exception as e:
        logging.error(f"Ошибка при подтверждении отчета {report_id}: {e}")
        await query.message.edit_text("❌ Не удалось подтвердить отчет.")

#Обработчик для ввода количества принятых человек
async def handle_personnel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Проверяем, есть ли данные о подтвержденном отчете и пользователе
        report_id = context.user_data.get('approve_report_id')
        user_id = context.user_data.get('approve_user_id')
        nick = context.user_data.get('approve_report_nick')

        if report_id and user_id:
            # Пытаемся преобразовать сообщение в число
            personnel_count = int(update.message.text.strip())

            # Обновление ball
            config = load_accounts()
            admin_id = update.effective_user.id

            if config.has_section(str(admin_id)):
                admin_ball = int(config[str(admin_id)].get('ball', '0'))
                config[str(admin_id)]['ball'] = str(admin_ball + 3) #выдаем 3 балла админку за принятый отчёт

            if config.has_section(str(user_id)):
                user_ball = int(config[str(user_id)].get('ball', '0'))
                config[str(user_id)]['ball'] = str(user_ball + personnel_count)

            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                config.write(f)

            # Уведомление пользователя о подтверждении отчета и начислении баллов
            try:
                await context.bot.send_message(user_id, f"✅ Ваш отчёт (ID {report_id}) подтверждён. Вам начислено {personnel_count} баллов.")
            except Exception as e:
                logging.error(f"Не удалось уведомить пользователя {user_id} о подтверждении отчета {report_id}: {e}")

            # Уведомление о завершении
            await update.message.reply_text("✅ Отчёт подтвержден! Количество принятых человек сохранено и баллы начислены.")
            update_balls()
            context.user_data.pop('approve_report_id', None)
            context.user_data.pop('approve_user_id', None)
            context.user_data.pop('approve_report_nick', None)
        else:
            # Если нет данных о подтвержденном отчете и пользователе, пропускаем сообщение
            await handle_menu_selection(update, context)
    except ValueError:
        if report_id and user_id:
            await update.message.reply_text("Ошибка: Пожалуйста, введите корректное число.")
        else:
            await handle_menu_selection(update, context)
    except telegram.error.TimedOut:
        logging.error("Ошибка при обработке ввода количества принятых человек: Timed out")
        await update.message.reply_text("❌ Произошла ошибка: запрос к Telegram API истек.")
    except Exception as e:
        logging.error(f"Ошибка при обработке ввода количества принятых человек: {e}")
        if report_id and user_id:
            await update.message.reply_text("❌ Произошла ошибка при обработке ввода.")
        else:
            await handle_menu_selection(update, context)

# Администратор: отклонить отчет (запрос причины отклонения)
async def reject_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = query.data[len("rejectReport_"):]
    try:
        config = load_reports()
        sec_name = f"report_{report_id}"
        if not config.has_section(sec_name):
            await query.message.edit_text("❌ Отчет не найден.")
            return
        # Убираем кнопки и запрашиваем причину отклонения
        await query.message.edit_reply_markup(reply_markup=None)
        context.user_data['reject_report_id'] = report_id
        await query.message.reply_text(f"❓ Пожалуйста, введите причину отклонения отчета ID {report_id}.")
    except Exception as e:
        logging.error(f"Ошибка при инициации отклонения отчета {report_id}: {e}")
        await query.message.edit_text("❌ Не удалось отклонить отчет.")

# Обработчик всех текстовых сообщений (включая этапы создания отчета и рассылок)
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()

    # Delegate to handle_personnel_input if we are in the process of approving a report
    if context.user_data.get('approve_report_id') and context.user_data.get('approve_user_id'):
        await handle_personnel_input(update, context)
        return

    # Existing logic for handling other text messages
    # Если пользователь отменяет отправку отчета кнопкой "Назад"
    if message_text == "Назад" and context.user_data.get('report_state'):
        report_id = context.user_data.get('current_report_id')
        if report_id and os.path.isdir(f"reports/{report_id}"):
            try:
                shutil.rmtree(f"reports/{report_id}")
                logging.info(f"Отчет {report_id} отменен пользователем, папка удалена.")
            except Exception as e:
                logging.error(f"Ошибка при удалении папки отчета {report_id} при отмене: {e}")
        # Сбрасываем состояние отчета
        context.user_data.pop('report_state', None)
        context.user_data.pop('current_report_id', None)
        context.user_data.pop('report_text', None)
        context.user_data.pop('photo_count', None)
        context.user_data.pop('saved_photos', None)
        await update.message.reply_text("❌ Отправка отчета отменена.", reply_markup=ReplyKeyboardRemove())
        await menu(update, context)
        return

    # Если администратор вводит причину отклонения отчета
    if context.user_data.get('reject_report_id'):
        report_id = context.user_data['reject_report_id']
        reason = message_text
        try:
            config = load_reports()
            sec_name = f"report_{report_id}"
            if not config.has_section(sec_name):
                await update.message.reply_text("❌ Отчет не найден.")
            else:
                user_id = int(config[sec_name].get("user_id", 0))
                nick = config[sec_name].get("nick", "Неизвестный")
                # Удаляем файлы отчета (папку с фото и текстом)
                folder = f"reports/{report_id}"
                if os.path.isdir(folder):
                    try:
                        shutil.rmtree(folder)
                        logging.info(f"Папка отчета {report_id} удалена.")
                    except Exception as e:
                        logging.error(f"Ошибка при удалении папки отчета {report_id}: {e}")
                # Удаляем запись об отчете из .ini-файла
                config.remove_section(sec_name)
                with open(REPORTS_FILE, "w", encoding="utf-8") as f:
                    config.write(f)
                logging.info(f"Отчет {report_id} отклонен и удален.")
                # Уведомляем пользователя об отклонении и причине
                try:
                    await context.bot.send_message(user_id, f"❌ Ваш отчёт (ID {report_id}) отклонён. Причина: {reason}")
                except Exception as e:
                    logging.error(f"Ошибка при отправке причины отклонения пользователю {user_id} для отчета {report_id}: {e}")
                    await update.message.reply_text("⚠️ Не удалось отправить сообщение пользователю.")
                else:
                    await update.message.reply_text(f"❌ Отчёт ID {report_id} отклонён. Пользователь уведомлен. Вам начислен 1 балл за модерацию отчёта.")
        except Exception as e:
            logging.error(f"Ошибка при обработке отклонения отчета {report_id}: {e}")
            await update.message.reply_text("❌ Произошла ошибка при отклонении отчета.")
        finally:
            context.user_data.pop('reject_report_id', None)
        return

    # Обработка текста отчета от пользователя (этап отправки текста отчета)
    if context.user_data.get('report_state') == 'await_text':
        report_text = message_text
        report_id = generate_random_id()
        config = load_reports()
        # Генерируем уникальный идентификатор отчета, который отсутствует в файле
        while config.has_section(f"report_{report_id}"):
            report_id = generate_random_id()
        try:
            os.makedirs("reports", exist_ok=True)
            folder = f"reports/{report_id}"
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "text.txt"), "w", encoding="utf-8") as f:
                f.write(report_text)
        except Exception as e:
            logging.error(f"Ошибка при сохранении текста отчета: {e}")
            await update.message.reply_text("❌ Не удалось сохранить текст отчета. Попробуйте позже.")
            context.user_data.pop('report_state', None)
            return
        # Переходим к этапу добавления фотографий
        context.user_data['current_report_id'] = report_id
        context.user_data['report_text'] = report_text
        context.user_data['photo_count'] = 0
        context.user_data['saved_photos'] = []
        context.user_data['report_state'] = 'await_photos'
        await update.message.reply_text(
            "📷 Теперь отправьте до 10 фотографий для отчета. "
            "Отправьте их по одному сообщению. Когда закончите, отправьте команду /done. "
            "Если у вас нет фотографий, отправьте /done сразу."
        )
        return

    # Если ожидаются фотографии, а пользователь прислал текст – напоминаем команду /done
    if context.user_data.get('report_state') == 'await_photos':
        await update.message.reply_text(
            "📷 Пожалуйста, продолжайте отправлять фотографии или введите /done, если больше фотографий нет."
        )
        return

    # Пользователь вводит "войти" вручную (дублирует нажатие кнопки)
    if message_text.lower() == "авторизация":
        await login(update, context)
        return

    # Отправка сообщений для массовой рассылки
    if 'mass_message' in context.user_data:
        # Получаем всех пользователей из файла
        config = load_accounts()
        user_sections = [sec for sec in config.sections() if sec.isdigit()]
        successes = 0
        for sec in user_sections:
            try:
                await context.bot.send_message(chat_id=int(sec), text=message_text)
                successes += 1
            except Exception as e:
                logging.error(f"Ошибка при отправке пользователю {sec}: {e}")
        await update.message.reply_text(f"Массовая рассылка завершена. Отправлено {successes} сообщений.")
        context.user_data.pop('mass_message', None)
        return

    # Отправка сообщения выбранному пользователю (одиночная рассылка)
    if 'single_message_user' in context.user_data:
        user_id = context.user_data['single_message_user']
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            await update.message.reply_text("✅ Сообщение успешно отправлено пользователю.")
        except Exception as e:
            await update.message.reply_text(f"❌ Не удалось отправить сообщение: {e}")
        context.user_data.pop('single_message_user', None)
        return
    
        # Обработка изменения параметра пользователя
    if 'handle_change_param' in context.user_data:
        user_id = context.user_data.get('user_id')
        param = context.user_data.get('change_param')
        if not user_id or not param:
            await update.message.reply_text("Ошибка: Нет данных для изменения.")
            return

        value = update.message.text.strip()
        config = load_accounts()
        if config.has_section(user_id):
            config[user_id][param] = value
            save_accounts(config)
            await update.message.reply_text(f"Значение {param} пользователя {user_id} успешно изменено на {value}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="edit_user")]]))
        else:
            await update.message.reply_text("Ошибка: Пользователь не найден.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="edit_user")]]))
        return

    # Обработка изменения ника
    if context.user_data.get('handle_change_nick'):
        user_id = context.user_data.get('user_id')
        new_nick = message_text
        config = load_accounts()
        if config.has_section(user_id):
            config[user_id]['nick'] = new_nick
            save_accounts(config)
            await update.message.reply_text(f"Ник пользователя {user_id} изменен на {new_nick}.",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        else:
            await update.message.reply_text("Ошибка: Пользователь не найден.",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        context.user_data.pop('handle_change_nick', None)
        context.user_data.pop('user_id', None)
        return

    # Обработка изменения Ball
    if context.user_data.get('handle_change_ball'):
        user_id = context.user_data.get('user_id')
        try:
            new_ball = int(message_text)
        except ValueError:
            await update.message.reply_text("Ошибка: введите целое число для баллов.")
            return
        config = load_accounts()
        if config.has_section(user_id):
            old_ball = int(config[user_id].get('ball', '0'))
            difference = new_ball - old_ball
            config[user_id]['ball'] = str(new_ball)
            save_accounts(config)
            await update.message.reply_text(f"Баллы пользователя {user_id} изменен на {new_ball}.",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
            # Уведомление пользователя
            if difference > 0:
                await context.bot.send_message(chat_id=int(user_id), text=f"✴ Вам зачислено {difference} баллов и теперь на балансе {new_ball}.")
            else:
                await context.bot.send_message(chat_id=int(user_id), text=f"✴ Администратор уменьшил Вам баллы на {abs(difference)} и теперь составляет {new_ball}.")
            # Уведомление администратора
            for admin_id in admin_ids:
                if difference > 0:
                    await context.bot.send_message(chat_id=int(admin_id), text=f"✅✴ Пользователю {user_id} увеличены баллы на {difference} и теперь составляет {new_ball}.")
                else:
                    await context.bot.send_message(chat_id=int(admin_id), text=f"✅✴ Пользователю {user_id} уменьшены баллы на {abs(difference)} и теперь составляет {new_ball}.")
        else:
            await update.message.reply_text("Ошибка: Пользователь не найден.",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        context.user_data.pop('handle_change_ball', None)
        return

    # Обработка изменения личного счета
    if context.user_data.get('handle_change_personal_account'):
        user_id = context.user_data.get('user_id')
        try:
            new_account = int(message_text)
        except ValueError:
            await update.message.reply_text("Ошибка: введите целое число для личного счета.")
            return
        config = load_accounts()
        if config.has_section(user_id):
            config[user_id]['personal_account'] = str(new_account)
            save_accounts(config)
            await update.message.reply_text(f"Личный счет пользователя {user_id} изменен на {new_account}.",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        else:
            await update.message.reply_text("Ошибка: Пользователь не найден.",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        context.user_data.pop('handle_change_personal_account', None)
        return

    # Обработка изменения разряда
    if context.user_data.get('handle_change_rank'):
        user_id = context.user_data.get('user_id')
        try:
            new_rank = int(message_text)
        except ValueError:
            await update.message.reply_text("Ошибка: введите целое число для разряда.")
            return
        config = load_accounts()
        if config.has_section(user_id):
            config[user_id]['rank'] = str(new_rank)
            config[user_id]['daily_rate'] = str(get_daily_rate(new_rank))
            save_accounts(config)
            await update.message.reply_text(f"Разряд пользователя {user_id} изменен на {new_rank}.",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        else:
            await update.message.reply_text("Ошибка: Пользователь не найден.",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        context.user_data.pop('handle_change_rank', None)
        return
    
    # Если ни одно из специальных состояний не активно – обрабатываем как команду меню
    await handle_menu_selection(update, context)

# Обработчик полученных фотографий во время отправки отчета
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('report_state') != 'await_photos':
        return
    report_id = context.user_data.get('current_report_id')
    photo_count = context.user_data.get('photo_count', 0)
    if photo_count >= 10:
        await update.message.reply_text("Вы уже отправили 10 фотографий. Отправьте /done для завершения отчета.")
        return
    try:
        file_id = update.message.photo[-1].file_id
        file = await context.bot.get_file(file_id)
        folder = f"reports/{report_id}"
        os.makedirs(folder, exist_ok=True)
        photo_count += 1
        # Определяем расширение файла фотографии
        ext = ""
        if file.file_path:
            ext = os.path.splitext(file.file_path)[1]
            if not ext:
                ext = ".jpg"
        else:
            ext = ".jpg"
        filename = f"photo{photo_count:02d}{ext}"
        path = os.path.join(folder, filename)
        await file.download_to_drive(path)
        context.user_data['photo_count'] = photo_count
        saved_photos = context.user_data.get('saved_photos', [])
        saved_photos.append(filename)
        context.user_data['saved_photos'] = saved_photos
        logging.info(f"Фото {filename} сохранено для отчета {report_id}.")
    except Exception as e:
        logging.error(f"Ошибка при обработке фото для отчета: {e}")
        await update.message.reply_text("❌ Не удалось сохранить фото. Попробуйте еще раз или отмените отчёт командой /cancel.")
        return
    if context.user_data['photo_count'] == 10:
        await update.message.reply_text("✅ Вы отправили максимальное количество фото (10). Теперь отправьте /done для завершения отчета.")

# Команда /done – завершение отправки отчета (после фотографий)
async def finish_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('report_state') != 'await_photos':
        await update.message.reply_text("У вас нет активного отчета для завершения.")
        return
    report_id = context.user_data.get('current_report_id')
    report_text = context.user_data.get('report_text', '')
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    nick = user_info['nick'] if user_info else (update.effective_user.username or update.effective_user.first_name or "")
    date_str = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        config = load_reports()
        config[f"report_{report_id}"] = {
            "user_id": str(user_id),
            "nick": nick,
            "date": date_str,
            "status": "pending"
        }
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            config.write(f)
        logging.info(f"Отчет {report_id} сохранен в файл данных.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении отчета {report_id} в файл: {e}")
        await update.message.reply_text("❌ Произошла ошибка при сохранении отчета. Попробуйте позже.")
        # Если сохранить не удалось, удаляем папку отчета
        folder = f"reports/{report_id}"
        if os.path.isdir(folder):
            try:
                shutil.rmtree(folder)
                logging.info(f"Удалена папка отчета {report_id} из-за ошибки сохранения.")
            except Exception as e2:
                logging.error(f"Ошибка удаления папки отчета {report_id} при отмене: {e2}")
        # Сбрасываем состояние отчета у пользователя
        context.user_data.pop('report_state', None)
        context.user_data.pop('current_report_id', None)
        context.user_data.pop('report_text', None)
        context.user_data.pop('photo_count', None)
        context.user_data.pop('saved_photos', None)
        return
    # Уведомляем пользователя и администратора
    await update.message.reply_text(f"✅ Ваш отчёт отправлен и ожидает проверки. ID вашего отчета: {report_id}. Вы получите уведомление после проверки.")
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(admin_id, f"🆕 Новый отчёт от пользователя {nick} (ID: {report_id}). Проверьте панель администратора для просмотра.")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомления админу {admin_id} о новом отчете {report_id}: {e}")
    # Сбрасываем состояние отчета у пользователя
    context.user_data.pop('report_state', None)
    context.user_data.pop('current_report_id', None)
    context.user_data.pop('report_text', None)
    context.user_data.pop('photo_count', None)
    context.user_data.pop('saved_photos', None)

# Команда /cancel – досрочная отмена создания отчета
async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('report_state'):
        await update.message.reply_text("У вас нет активного отчета для отмены.")
        return
    report_id = context.user_data.get('current_report_id')
    if report_id and os.path.isdir(f"reports/{report_id}"):
        try:
            shutil.rmtree(f"reports/{report_id}")
            logging.info(f"Отчет {report_id} отменен пользователем, данные удалены.")
        except Exception as e:
            logging.error(f"Ошибка при удалении данных отчета {report_id} при отмене: {e}")
    context.user_data.pop('report_state', None)
    context.user_data.pop('current_report_id', None)
    context.user_data.pop('report_text', None)
    context.user_data.pop('photo_count', None)
    context.user_data.pop('saved_photos', None)
    await update.message.reply_text("❌ Отправка отчета отменена.", reply_markup=ReplyKeyboardRemove())
    await menu(update, context)
    
# =============================================
# СИСТЕМА РЕГИСТРАЦИИ
# =============================================
async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса регистрации"""
    user_id = update.effective_user.id
    accounts = load_accounts()

    # Проверка, существует ли пользователь с данным user_id
    if accounts.has_section(str(user_id)):
        await update.message.reply_text("❌ Не удалось создать аккаунт. Пользователь с таким ID уже существует.")
        return ConversationHandler.END

    await update.message.reply_text(
        "✏️ Введите ваш никнейм:",
        reply_markup=get_back_keyboard()
    )
    return REG_NAME

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка никнейма"""
    if update.message.text == "Назад":
        # Возвращаем пользователя к меню с кнопками "Войти" и "Регистрация"
        await update.message.reply_text(
            "Для входа в систему нажмите кнопку ниже.",
            reply_markup=get_login_keyboard()
        )
        return ConversationHandler.END  # Завершаем диалог регистрации
    
    context.user_data['reg_data'] = {'nick': update.message.text}
    await update.message.reply_text(
        "👤 Введите ваше реальное имя:",
        reply_markup=get_back_keyboard()
    )
    return REG_REALNAME

async def reg_realname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка реального имени"""
    if update.message.text == "Назад":
        # Возвращаем пользователя к вводу никнейма
        await update.message.reply_text(
            "✏️ Введите ваш никнейм:",
            reply_markup=get_back_keyboard()
        )
        return REG_NAME
    
    context.user_data['reg_data']['realname'] = update.message.text
    await update.message.reply_text(
        "🎂 Введите дату рождения (ДД.ММ.ГГГГ):",
        reply_markup=get_back_keyboard()
    )
    return REG_BIRTHDATE

async def reg_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка даты рождения и сохранение заявки"""
    if update.message.text == "Назад":
        await update.message.reply_text(
            "👤 Введите ваше реальное имя:",
            reply_markup=get_back_keyboard()
        )
        return REG_REALNAME
    
    # Валидация даты
    try:
        datetime.strptime(update.message.text, "%d.%m.%Y")
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ",
            reply_markup=get_back_keyboard()
        )
        return REG_BIRTHDATE

    # Сохранение заявки
    reg_data = context.user_data['reg_data']
    reg_id = str(uuid4())[:8]
    
    config = configparser.ConfigParser()
    config.read(REGISTRATIONS_FILE)
    
    config[reg_id] = {
        'user_id': str(update.effective_user.id),
        'nick': reg_data['nick'],
        'realname': reg_data['realname'],
        'birthdate': update.message.text,
        'status': 'pending',
        'timestamp': str(datetime.now())
    }
    
    with open(REGISTRATIONS_FILE, "w") as f:
        config.write(f)
    
    # Уведомление админам 2+ уровня
    await notify_admins_about_new_registration(reg_id, reg_data['nick'], context)
    
    await update.message.reply_text(
        "✅ Заявка отправлена на модерацию!",
        reply_markup=get_login_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

# Новый обработчик
async def view_registrations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = configparser.ConfigParser()

    # Проверка, существует ли файл
    if not os.path.exists(REGISTRATIONS_FILE):
        print(f"❌ Файл {REGISTRATIONS_FILE} не найден!")
        # Используем update.callback_query.message.reply_text, если обновление это callback_query
        if update.callback_query:
            await update.callback_query.message.reply_text("📭 Нет заявок на регистрацию (файл отсутствует).")
        else:
            await update.message.reply_text("📭 Нет заявок на регистрацию (файл отсутствует).")
        return

    config.read(REGISTRATIONS_FILE)  # Читаем файл

    # Отладка: Выводим все секции файла
    print(f"🔍 Загруженные заявки: {config.sections()}")

    keyboard = []  # Список кнопок для отображения заявок

    # Проходим по секциям файла и проверяем статус заявок
    for section in config.sections():
        status = config[section].get('status', 'unknown')  # Получаем статус заявки
        print(f"📝 Заявка ID {section}: статус {status}")  # Отладка

        # Если заявка в статусе "pending", добавляем её в список
        if status == 'pending':
            keyboard.append([
                InlineKeyboardButton(f"{config[section]['nick']} ({section})", callback_data=f"reg_detail_{section}")
            ])

    # Если нет заявок с нужным статусом, информируем пользователя
    if not keyboard:
        if update.callback_query:
            await update.callback_query.message.reply_text("📭 Нет заявок на регистрацию.")
        else:
            await update.message.reply_text("📭 Нет заявок на регистрацию.")
        return

    # Отправляем сообщение с кнопками для администрирования заявок
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "📝 Заявки на регистрацию:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "📝 Заявки на регистрацию:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


def load_admin_ids():
    config = load_accounts()  # Функция для загрузки аккаунтов
    admin_ids = []
    for user_id, user_info in config.items():
        if int(user_info.get('is_admin', 0)) >= 2:
            admin_ids.append(user_id)
    return admin_ids

async def notify_admins_about_new_registration(reg_id: str, nick: str, context: ContextTypes.DEFAULT_TYPE):
    admin_ids = load_admin_ids()
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 Новая заявка на регистрацию:\nID: {reg_id}\nНик: {nick}"
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомления админу {admin_id}: {e}")

                    
# Просмотр деталей заявки
async def reg_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reg_id = update.callback_query.data.split("_")[2]
    config = configparser.ConfigParser()
    config.read(REGISTRATIONS_FILE)
    
    msg = f"""📄 Заявка {reg_id}
👤 Ник: {config[reg_id]['nick']}
📛 Имя: {config[reg_id]['realname']}
🎂 Дата рождения: {config[reg_id]['birthdate']}"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"reg_approve_{reg_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reg_reject_{reg_id}")
        ]
    ]
    
    await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# Одобрение заявки
# Одобрение заявки
async def reg_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reg_id = update.callback_query.data.split("_")[2]
    
    # Чтение регистрационных данных
    config = configparser.ConfigParser()
    try:
        config.read(REGISTRATIONS_FILE, encoding="utf-8")
    except UnicodeDecodeError as e:
        print(f"Ошибка при чтении файла REGISTRATIONS_FILE: {e}")
        await update.callback_query.message.edit_text("❌ Ошибка при обработке заявки.")
        return
    
    # Перенос в аккаунты
    accounts = configparser.ConfigParser()
    try:
        accounts.read(ACCOUNTS_FILE, encoding="utf-8")
    except UnicodeDecodeError as e:
        print(f"Ошибка при чтении файла ACCOUNTS_FILE: {e}")
        await update.callback_query.message.edit_text("❌ Ошибка при обработке аккаунтов.")
        return
    
    # Проверка наличия данных
    if reg_id not in config.sections():
        await update.callback_query.message.edit_text("❌ Заявка не найдена.")
        return
    
    user_id = config[reg_id]['user_id']
    
    # Убедитесь, что rank и daily_rate установлены корректно
    rank = -1  # Устанавливаем разряд как отсутствующий по умолчанию
    daily_rate = get_daily_rate(rank)  # Получаем ставку на основе разряда
    
    accounts[user_id] = {
    'nick': config[reg_id]['nick'],
    'position': config[reg_id].get('position', '-'),
    'rank': rank,
    'daily_rate': daily_rate,
    'warnings': config[reg_id].get('warnings', '0'),
    'predicted_payment': config[reg_id].get('predicted_payment', '0'),
    'personal_account': config[reg_id].get('personal_account', '0'),
    'rating': config[reg_id].get('rating', '0'),
    'is_admin': '-1',  # Статус по умолчанию
    'realname': config[reg_id].get('realname', ''),
    'daterod': config[reg_id].get('birthdate', ''),  # Дата рождения
    'ball': '0'  # сумма баллов
    }
    
    # Запись данных в ACCOUNTS_FILE
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            accounts.write(f)
    except UnicodeEncodeError as e:
        print(f"Ошибка кодировки при записи в файл ACCOUNTS_FILE: {e}")
        await update.callback_query.message.edit_text("❌ Ошибка при записи данных в файл.")
        return
    
    # Уведомление пользователю
    try:
        await context.bot.send_message(
            user_id, 
            "✅ Ваша регистрация одобрена! Теперь вы можете войти в систему."
        )
    except Exception as e:
        print(f"Ошибка при отправке уведомления пользователю: {e}")
        await update.callback_query.message.edit_text("❌ Ошибка при отправке уведомления пользователю.")
        return
    
    # Удаление заявки
    try:
        config.remove_section(reg_id)
    except KeyError:
        print(f"Заявка с ID {reg_id} не найдена для удаления.")
    
    # Запись обновленных данных в REGISTRATIONS_FILE
    try:
        with open(REGISTRATIONS_FILE, "w", encoding="utf-8") as f:
            config.write(f)
    except UnicodeEncodeError as e:
        print(f"Ошибка кодировки при записи в файл REGISTRATIONS_FILE: {e}")
        await update.callback_query.message.edit_text("❌ Ошибка при обновлении файла заявок.")
        return
    
    await update.callback_query.message.edit_text("✅ Заявка одобрена!")


# Добавляем обработчик отмены регистрации
async def reg_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклонение заявки на регистрацию"""
    query = update.callback_query
    await query.answer()
    reg_id = query.data.split('_')[-1]
    
    config = configparser.ConfigParser()
    config.read(REGISTRATIONS_FILE)
    
    # Удаление заявки
    user_id = config[reg_id]['user_id']
    config.remove_section(reg_id)
    
    with open(REGISTRATIONS_FILE, "w") as f:
        config.write(f)
    
    # Уведомление пользователю
    await context.bot.send_message(
        user_id,
        "❌ Ваша заявка на регистрацию отклонена. Обратитесь к администратору."
    )
    await query.edit_message_text(f"❌ Заявка #{reg_id} отклонена")

# ОБРАБОТЧИК ОТМЕНЫ РЕГИСТРАЦИИ
async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена процесса регистрации"""
    await update.message.reply_text(
        "❌ Регистрация отменена",
        reply_markup=get_login_keyboard()  # Возвращаем пользователя к клавиатуре входа
    )
    context.user_data.clear()  # Очищаем временные данные
    return ConversationHandler.END

conv_reg = ConversationHandler(
    entry_points=[MessageHandler(filters.Text("Регистрация"), start_registration)],
    states={
        REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
        REG_REALNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_realname)],
        REG_BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_birthdate)],
        ConversationHandler.TIMEOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_input)]
    },
    fallbacks=[CommandHandler("cancel", cancel_registration)]
)

# =============================================
# РАЗРЯДНАЯ СИСТЕМА
# =============================================
# Обработчик нажатия "Управление пользователями"
async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = load_accounts()
    users = [(user_id, config[user_id].get('nick', 'Неизвестный')) for user_id in config.sections() if user_id.isdigit()]
    if not users:
        await query.message.edit_text("Нет доступных пользователей для управления.")
        return
    keyboard = [[InlineKeyboardButton(nick, callback_data=f"edit_user_{user_id}")] for user_id, nick in users]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("Выберите пользователя для управления:", reply_markup=reply_markup)

async def edit_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.data.split("_")[2]
    context.user_data['user_id'] = user_id

    # Получить информацию о текущем пользователе
    current_user_info = get_user_info(update.effective_user.id)
    admin_level = int(current_user_info.get('is_admin', 0)) if current_user_info else 0

    if admin_level == 1:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data=f"statistics_{user_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="manage_users")]
        ]
    elif admin_level == 2:
        keyboard = [
            [InlineKeyboardButton("✏️ Никнейм", callback_data="change_nick")],
            [InlineKeyboardButton("⚠➕️ Предупреждение", callback_data="add_warning")],
            [InlineKeyboardButton("⚠➖ Предупреждение", callback_data="remove_warning")],
            [InlineKeyboardButton("📊 Статистика", callback_data=f"statistics_{user_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="manage_users")]
        ]
    elif admin_level == 3:
        keyboard = [
            [InlineKeyboardButton("✏️ Никнейм", callback_data="change_nick")],
            [InlineKeyboardButton("📌 Должность", callback_data=f"change_position_{user_id}")],
            [InlineKeyboardButton("⭐ Разряд", callback_data=f"select_user_{user_id}")],
            [InlineKeyboardButton("⚠➕️ Предупреждение", callback_data="add_warning")],
            [InlineKeyboardButton("⚠➖ Предупреждение", callback_data="remove_warning")],
            [InlineKeyboardButton("✴ Баллы", callback_data="change_ball")],
            [InlineKeyboardButton("💳 Личный счёт", callback_data="change_personal_account")],
            [InlineKeyboardButton("📊 Статистика", callback_data=f"statistics_{user_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="manage_users")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="manage_users")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(f"Выберите параметр для изменения пользователя {user_id}:", reply_markup=reply_markup)
    
 
async def change_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = context.user_data.get('user_id')
    context.user_data['handle_change_nick'] = True
    await query.message.edit_text("Введите новый ник пользователя:")

async def change_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Извлекаем user_id из context.user_data, он был установлен в edit_user
    user_id = context.user_data.get('user_id')
    if not user_id:
        await query.message.edit_text("Ошибка: не выбран пользователь.")
        return
    keyboard = [
        [InlineKeyboardButton("ПОЧ ЗАМ", callback_data="set_position_почетный_заместитель")],
        [InlineKeyboardButton("ЗАМ", callback_data="set_position_заместитель")],
        [InlineKeyboardButton("СТАРШИЙ ЗАМ", callback_data="set_position_старший_заместитель")],
        [InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("Выберите новую должность для пользователя:", reply_markup=reply_markup)

async def set_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Извлекаем ключ позиции, например "почетный_заместитель" из "set_position_почетный_заместитель"
    pos_key = query.data.replace("set_position_", "")
    # Используем ключ 'user_id' из context.user_data, установленный в edit_user
    user_id = context.user_data.get('user_id')
    if not user_id:
        await query.message.edit_text("Ошибка: не выбран пользователь.")
        return
    # Сопоставление для позиции и уровня админских прав
    position_mapping = {
        "почетный_заместитель": ("Почётный заместитель", "1"),
        "заместитель": ("Заместитель", "0"),
        "старший_заместитель": ("Старший заместитель", "2")
    }
    if pos_key in position_mapping:
        position, is_admin = position_mapping[pos_key]
        config = load_accounts()
        if config.has_section(user_id):
            config[user_id]['position'] = position
            config[user_id]['is_admin'] = is_admin
            save_accounts(config)
            await query.message.edit_text(f"Должность пользователя изменена на: {position}")
        else:
            await query.message.edit_text("Ошибка: пользователь не найден.")
    else:
        await query.message.edit_text("Ошибка: неизвестная должность.")


async def add_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = context.user_data.get('user_id')
    config = load_accounts()
    if config.has_section(user_id):
        warnings = int(config[user_id].get('warnings', '0')) + 1
        config[user_id]['warnings'] = str(warnings)
        save_accounts(config)
        await query.message.edit_text(f"Предупреждение добавлено. Теперь предупреждений: {warnings}.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        user_info = get_user_info(user_id)
        await context.bot.send_message(user_id, f"⚠️ Вам выдано предупреждение. Теперь у вас {warnings} предупреждений.")
        await context.bot.send_message(admin_ids[0], f"⚠️ Пользователю {user_info['nick']} выдано предупреждение. Теперь у него {warnings} предупреждений.")
    else:
        await query.message.edit_text("Ошибка: Пользователь не найден.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))

async def remove_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = context.user_data.get('user_id')
    config = load_accounts()
    if config.has_section(user_id):
        warnings = max(0, int(config[user_id].get('warnings', '0')) - 1)
        config[user_id]['warnings'] = str(warnings)
        save_accounts(config)
        await query.message.edit_text(f"Предупреждение снято. Теперь предупреждений: {warnings}.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        user_info = get_user_info(user_id)
        await context.bot.send_message(user_id, f"✅ С вас снято предупреждение. Теперь у вас {warnings} предупреждений.")
        await context.bot.send_message(admin_ids[0], f"✅ С пользователя {user_info['nick']} снято предупреждение. Теперь у него {warnings} предупреждений.")
    else:
        await query.message.edit_text("Ошибка: Пользователь не найден.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))

        
async def change_ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = context.user_data.get('user_id')
    context.user_data['handle_change_ball'] = True
    await query.message.edit_text("Введите новое значение баллов:")

async def change_personal_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = context.user_data.get('user_id')
    context.user_data['handle_change_personal_account'] = True
    await query.message.edit_text("Введите новое значение личного счета:")

# Обработчик выбора пользователя для изменения разряда
async def select_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.data.split("_")[2]
    context.user_data['selected_user_id'] = user_id
    
    # Создание кнопок для выбора разряда от -1 до 10
    keyboard = [
        [InlineKeyboardButton(str(rank), callback_data=f"set_rank_{rank}") for rank in range(-1, 4)],
        [InlineKeyboardButton(str(rank), callback_data=f"set_rank_{rank}") for rank in range(4, 8)],
        [InlineKeyboardButton(str(rank), callback_data=f"set_rank_{rank}") for rank in range(8, 11)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text("Выберите новый разряд для пользователя:", reply_markup=reply_markup)

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = context.user_data.get('user_id')
    user_info = get_user_info(user_id)
    if user_info:
        predicted_payment_formatted = locale.format_string("%d", user_info['predicted_payment'], grouping=True).replace(' ', '.')
        daily_rate_formatted = locale.format_string("%d", user_info['daily_rate'], grouping=True).replace(' ', '.')
        personal_account_formatted = locale.format_string("%d", int(user_info['personal_account']), grouping=True).replace(' ', '.')
        message = (
            f"📌 Личный кабинет (ID: {user_id})\n\n"
            f"👤 Никнейм: {user_info['nick']}\n"
            f"🔮 Реальное имя: {user_info['realname']}\n"
            f"🎂 Дата рождения: {user_info['daterod']}\n"
            f"💼 Должность: {user_info['position']}\n"
            f"⭐ Разряд: {user_info['rank']}\n"
            f"💰 Ставка в день: {daily_rate_formatted} RUB\n"
            f"⚠️ Предупреждения: {user_info['warnings']}\n"
            f"✴️ Баллы: {user_info['ball']}\n"
            f"💸 Зарплата: {predicted_payment_formatted} RUB\n"
            f"💳 Личный счет: {personal_account_formatted} RUB" 
        )
        await query.message.edit_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
    else:
        await query.message.edit_text("Информация о пользователе не найдена.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data=f"edit_user_{user_id}")]]))
        

# Обработчик установки нового разряда
async def set_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rank = int(query.data.split("_")[2])
    user_id = context.user_data.get('selected_user_id')
    
    user_info = get_user_info(user_id)
    if not user_info:
        await query.message.reply_text(f"Пользователь с ID {user_id} не найден.")
        return

    config = load_accounts()
    if not config.has_section(user_id):
        await query.message.reply_text(f"Пользователь с ID {user_id} не найден.")
        return

    config[user_id]['rank'] = str(rank)
    config[user_id]['daily_rate'] = str(get_daily_rate(rank))

    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        config.write(f)

    await query.message.reply_text(f"Разряд {rank} и ставка {get_daily_rate(rank)} рублей установлены для пользователя с ID {user_id}.")
    await context.bot.send_message(chat_id=int(user_id), text=f"✅ Вам присвоен новый разряд: {rank}. Ваша ставка теперь составляет {get_daily_rate(rank)} рублей.")
    
    # Очистка данных о выбранном пользователе
    context.user_data.pop('selected_user_id', None)

# Добавьте новую функцию для создания клавиатуры с сообщением о недостатке прав
def get_limited_keyboard():
    keyboard = [[KeyboardButton("Для выдачи прав обратитесь к администратору бота.")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

async def fetch_updates():
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post("https://api.telegram.org/bot{token}/getUpdates")
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as exc:
        logging.error(f"An error occurred while requesting {exc.request.url!r}.")
    except httpx.HTTPStatusError as exc:
        logging.error(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
    except httpx.TimeoutException as exc:
        logging.error("Request timed out.")

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Ваш код обработки команды
        logging.info("Обработка команды: Вывод средств")
        # Пример длительной операции, которая может вызвать таймаут
        await long_running_operation()
        
    except TimeoutError:
        logging.error("Ошибка в обработке меню: Timed out")
        await update.message.reply_text("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте снова.")

async def long_running_operation():
    # Пример длительной операции, которая может вызвать таймаут
    await asyncio.sleep(25)  # Длительная операция

# Функция main – настройка и запуск бота
async def main():
    application = Application.builder().token(TOKEN).build()
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(conv_reg)
    # Обработчики регистрации
    application.add_handler(CallbackQueryHandler(view_registrations, pattern="^view_registrations$"))
    application.add_handler(CallbackQueryHandler(reg_detail, pattern="^reg_detail_.*"))
    application.add_handler(CallbackQueryHandler(reg_approve, pattern="^reg_approve_.*"))
    application.add_handler(CallbackQueryHandler(reg_reject, pattern="^reg_reject_.*"))
    # Обработчики колбэков (заявки на вывод)
    application.add_handler(CallbackQueryHandler(handle_withdrawal_selection, pattern=r'^withdraw_\d+$'))
    application.add_handler(CallbackQueryHandler(confirm_withdraw_request, pattern=r"^confirm_withdraw$"))
    application.add_handler(CallbackQueryHandler(cancel_withdraw_request, pattern=r"^cancel_withdraw$"))
    application.add_handler(CallbackQueryHandler(approve_withdrawal, pattern=r"^approve_\w+$"))
    application.add_handler(CallbackQueryHandler(reject_withdrawal, pattern=r"^reject_[a-zA-Z0-9]+$", block=False))
    application.add_handler(CallbackQueryHandler(view_withdrawal, pattern=r"^view_"))
    application.add_handler(CallbackQueryHandler(admin_withdrawals, pattern="^admin_withdrawals$"))
    # Обработчики колбэков (рассылки и др. функции администратора)
    application.add_handler(CallbackQueryHandler(mass_message, pattern='^mass_message$'))
    application.add_handler(CallbackQueryHandler(cancel_mass_message, pattern='^cancel_mass_message$'))
    application.add_handler(CallbackQueryHandler(single_message, pattern="^start_single_message$"))
    application.add_handler(CallbackQueryHandler(send_single_message, pattern="^single_user_"))
    application.add_handler(CallbackQueryHandler(cancel_single_message, pattern="^cancel_single_message$"))
    #NEW
    application.add_handler(CallbackQueryHandler(manage_users, pattern="^manage_users$"))
    application.add_handler(CallbackQueryHandler(edit_user, pattern="^edit_user_.*"))
    application.add_handler(CallbackQueryHandler(change_nick, pattern="^change_nick$"))
    application.add_handler(CallbackQueryHandler(add_warning, pattern="^add_warning$"))
    application.add_handler(CallbackQueryHandler(remove_warning, pattern="^remove_warning$"))
    application.add_handler(CallbackQueryHandler(change_ball, pattern="^change_ball$"))
    application.add_handler(CallbackQueryHandler(change_personal_account, pattern="^change_personal_account$"))
    application.add_handler(CallbackQueryHandler(select_user, pattern="^select_user_"))
    application.add_handler(CallbackQueryHandler(set_position, pattern="^set_position_"))
    application.add_handler(CallbackQueryHandler(change_position, pattern="^change_position_"))
    application.add_handler(CallbackQueryHandler(set_position, pattern="^set_position_"))
    # Обработчики системы отчетов
    application.add_handler(CallbackQueryHandler(admin_reports, pattern="^reports$"))
    application.add_handler(CallbackQueryHandler(view_report, pattern="^viewReport_"))
    application.add_handler(CallbackQueryHandler(approve_report, pattern="^approveReport_"))
    application.add_handler(CallbackQueryHandler(reject_report, pattern="^rejectReport_"))
    # Обработчики нажатия кнопок
    application.add_handler(CallbackQueryHandler(manage_users, pattern="^manage_users$"))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Авторизация"), button_handler))
    application.add_handler(CallbackQueryHandler(manage_users, pattern="^manage_users$"))
    application.add_handler(CallbackQueryHandler(select_user, pattern="^select_user_.*"))
    application.add_handler(CallbackQueryHandler(set_rank, pattern="^set_rank_.*"))  
    # Обработчики во время создания отчета
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CommandHandler("done", finish_report))
    application.add_handler(CommandHandler("cancel", cancel_report))
    application.add_handler(CommandHandler("rating", rating))
    # Добавление нового обработчика для кнопки "Статистика"
    application.add_handler(CallbackQueryHandler(statistics, pattern="^statistics_.*"))
    
    # Обработчик любых текстовых сообщений (должен идти последним)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    # Вызов функции обновления значений баллов
    logging.info("Бот успешно запущен!")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен вручную")
