import telebot
from telebot import types
from bd_queue import conn,cursor
from datetime import datetime,timedelta
from collections import defaultdict
import threading
import time

bot = telebot.TeleBot('YOUR KEY')

NAME, LASTNAME, CONFIRMATION, SELECT_MONTH, SELECT_DAY, SELECT_TIME = range(6)

sent_notifications = {}

user_data = {}

sent_notifications = defaultdict(lambda: {
    '1_day': None,
    '1_hour': None,
    '30_min': None,
    '5_min': None,
    'status_process': None,
    'status_completed': None
})

MAX_BOOKINGS_PER_TIME_SLOT = 3
WORKING_MONTHS = [12]


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    cursor.execute("SELECT telegram_id FROM customers WHERE telegram_id = %s", (user_id,))
    existing_user = cursor.fetchone()

    if existing_user:
        bot.send_message(user_id, "Вы уже зарегистрированы! Переходите к меню.")
        menu(user_id)
    else:
        inline_markup = types.InlineKeyboardMarkup()
        inline_registration_button = types.InlineKeyboardButton(text="✏️ Регистрация", callback_data="Регистрация")
        inline_authorization_button = types.InlineKeyboardButton(text="🗒️ Авторизация", callback_data="Авторизация")
        inline_markup.add(inline_registration_button, inline_authorization_button)
        bot.send_message(user_id, "Привет! Пожалуйста, выберите действие:", reply_markup=inline_markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    data = call.data

    if data == "Регистрация":
        cursor.execute("SELECT 1 FROM customers WHERE telegram_id = %s", (user_id,))
        if cursor.fetchone() is not None:
            bot.send_message(user_id, "Вы уже зарегистрированы.")
            menu(user_id)
        else:
            bot.send_message(user_id, "Вы начали процесс регистрации.")
            user_data[user_id] = {'state': NAME}
            bot.send_message(user_id, "Как вас зовут?", reply_markup=types.ReplyKeyboardRemove())


    elif data == "Авторизация":
        user_data[user_id] = {'state': CONFIRMATION}
        bot.send_message(user_id, "Пожалуйста,зарегистрируйтесь", reply_markup=types.ReplyKeyboardRemove())



    elif data == "confirm_registration":
        cursor.execute("SELECT telegram_id FROM customers WHERE telegram_id = %s", (user_id,))
        existing_user = cursor.fetchone()

        if existing_user:
            bot.send_message(user_id, "Вы уже зарегистрированы!")
        else:
            full_name = f"{user_data[user_id]['name']} {user_data[user_id]['lastname']}"
            cursor.execute(""" 
                INSERT INTO customers (telegram_id, full_name) 
                VALUES (%s, %s)
            """, (user_id, full_name))
            conn.commit()

            bot.send_message(user_id, "Ваша регистрация успешно завершена!")
        
        user_data.pop(user_id, None)
        menu(user_id)

    elif data == "retry_registration":
        cursor.execute("SELECT telegram_id FROM customers WHERE telegram_id = %s", (user_id,))
        existing_user = cursor.fetchone()

        if existing_user:
            bot.send_message(user_id, "Вы уже зарегистрированы! Переходите в меню.")
            menu(user_id)
        else:
            user_data[user_id]['state'] = NAME
            bot.send_message(user_id, "Давайте начнем регистрацию заново. Как вас зовут?")

    elif data == "back_to_menu_selection":
        menu(call.message.chat.id)

    elif data == 'book_slot':
        book_slot(call.message)

    elif data.startswith("confirm_cancel_"):
        confirm_cancel(call)

    elif data == "cancel_booking":
        cancel_booking(call.message)

    elif data.startswith("help"):
        send_help_info(call)

    elif data.startswith("date_"):
        selected_date = data.split('_')[1]
        selected_date_obj = datetime.fromisoformat(selected_date).date()
        handle_date_selection(call, selected_date_obj)

    elif data.startswith("time_"):
        handle_time_selection(call)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id

    if user_id not in user_data:
        bot.send_message(user_id, "Пожалуйста, начните с команды /start или нажмите на неё.")
        return

    state = user_data[user_id].get('state', None)

    if state is None:
        bot.send_message(user_id, "Пожалуйста, начните с команды /start или нажмите на неё.")
        return

    if state == NAME:
        name = message.text
        if not name.isalpha():
            bot.send_message(user_id, "Имя должно содержать только буквы. Пожалуйста, введите ваше имя снова.")
        else:
            user_data[user_id]['name'] = name
            user_data[user_id]['state'] = LASTNAME
            bot.send_message(user_id, "Спасибо! А как ваша фамилия?")

    elif state == LASTNAME:
        lastname = message.text
        if not lastname.isalpha():
            bot.send_message(user_id, "Фамилия должна содержать только буквы. Пожалуйста, введите вашу фамилию снова.")
        else:
            user_data[user_id]['lastname'] = lastname
            user_data[user_id]['state'] = CONFIRMATION

            data_text = f"Имя: {user_data[user_id]['name']}\nФамилия: {user_data[user_id]['lastname']}\n\nПодтвердите вашу информацию."
            pl_markup = types.InlineKeyboardMarkup()
            pl_yes_button = types.InlineKeyboardButton(text="Да", callback_data="confirm_registration")
            pl_retry_button = types.InlineKeyboardButton(text="Перепройти регистрацию", callback_data="retry_registration")
            pl_markup.add(pl_yes_button, pl_retry_button)
            bot.send_message(user_id, data_text, reply_markup=pl_markup)


def menu(user_id):
    menu_markup = types.InlineKeyboardMarkup(row_width=2)
    book_button = types.InlineKeyboardButton(text='📅 Записаться', callback_data='book_slot')
    cancel_button = types.InlineKeyboardButton(text='❌ Отменить', callback_data='cancel_booking')
    help_button = types.InlineKeyboardButton(text='ℹ️ Помощь', callback_data='help')
    menu_markup.add(book_button, cancel_button, help_button)
    bot.send_message(user_id, "Добро пожаловать в главное меню! Выберите действие:", reply_markup=menu_markup)

def send_help_info(call):
    user_id = call.message.chat.id
    
   
    help_text = (
        "Привет! Я — бот для записи на прием. Вот как ты можешь меня использовать:\n\n"
        
        "1. **📅 Записаться на прием**:\n"
        "Нажми кнопку 'Записаться' и выбери удобное для тебя время. Ты сможешь выбрать дату и время для визита.\n\n"

        "**❗️Важная информация**:\n"
        "Обрати внимание, что ты можешь записаться только на ближайшие 2 дня. Например, если сегодня 19 августа, ты можешь записаться только на 20 или 21 августа, "
        "но не на более поздние или более ранние даты.\n\n"
        
        
        "2. **❌ Отменить запись**:\n"
        "Если тебе нужно отменить свою запись, нажми кнопку 'Отменить'. Я покажу твою текущую запись, "
        "и ты сможешь выбрать отменить либо назад что бы вернуться в меню.И после отмены записи вы можете снова записаться на прием\n\n"
        
        "3. **📊 Твоя очередь**:\n"
        "После того как ты запишешься на прием я покажу твой номер в очереди, когда ты запишешься на прием.\n"
        "Ты будешь получать уведомления о статусе: когда твой прием начнется и когда закончится.\n\n"
        
        "4. **⏰ Напоминания**:\n"
        "Я отправлю тебе напоминания за день, за час, за 30 минут и за 5 минут до твоего приема.\n"
        "Это поможет тебе не забыть о визите!\n\n"
            
        f"❗️ Важно: на каждый временной слот можно записать только {MAX_BOOKINGS_PER_TIME_SLOT} человека. "
        f"Например, если ты выбрал слот в 14:00, и на это время уже записались {MAX_BOOKINGS_PER_TIME_SLOT} человека, "
        "ты не сможешь записаться на этот слот и тебе нужно будет выбрать другой.\n\n"

    )
    
    bot.send_message(user_id, help_text)
    menu(user_id)



def book_slot(message):
    user_id = message.chat.id
    
    today = datetime.today().date()

    available_dates = [
        today + timedelta(days=i) 
        for i in range(1, 3) 
        if (today + timedelta(days=i)).month in WORKING_MONTHS
    ] 

    if not available_dates:
        bot.send_message(user_id, "На данный момент запись недоступна. Попробуйте позже.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for date in available_dates:
        date_str = date.strftime('%d.%m.%Y')
        date_button = types.InlineKeyboardButton(text=date_str, callback_data=f"date_{date.isoformat()}")
        markup.add(date_button)
    
    back_button = types.InlineKeyboardButton(text="<--\nНазад", callback_data="back_to_menu_selection")
    markup.add(back_button)
    
    bot.send_message(user_id, "Выберите дату для записи (доступны следующие два дня):", reply_markup=markup)


def handle_date_selection(call, selected_date_obj):
    user_id = call.message.chat.id

    times = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    markup = types.InlineKeyboardMarkup(row_width=3)
    row = []

    for time_slot in times:
        selected_datetime = datetime.combine(selected_date_obj, datetime.strptime(time_slot, '%H:%M').time())
        cursor.execute("""SELECT COUNT(*) FROM online_queue
                          WHERE scheduled_time = %s AND status = 'ожидание'""", (selected_datetime,))
        booking_count = cursor.fetchone()[0]

        if booking_count < MAX_BOOKINGS_PER_TIME_SLOT:
            callback_data = f"time_{selected_date_obj.isoformat()}_{time_slot}"
            row.append(types.InlineKeyboardButton(time_slot, callback_data=callback_data))

        if len(row) == 3:
            markup.add(*row)
            row = []

    if row:
        markup.add(*row)

    back_button = types.InlineKeyboardButton(text="<--\nНазад", callback_data="back_to_menu_selection")
    markup.add(back_button)

    bot.send_message(user_id, "Выберите время для выбранной даты:", reply_markup=markup)


def handle_time_selection(call):
    user_id = call.message.chat.id
    selected_date, selected_time = call.data.split('_')[1], call.data.split('_')[2]

    selected_datetime = datetime.fromisoformat(selected_date).replace(
        hour=int(selected_time.split(':')[0]),
        minute=int(selected_time.split(':')[1])
    )

    cursor.execute("""SELECT COUNT(*) FROM online_queue
                      WHERE telegram_id = %s AND status = 'ожидание'""", (user_id,))
    existing_booking = cursor.fetchone()[0]

    if existing_booking > 0:
        bot.send_message(user_id, "Вы уже записаны на прием. Только одна запись на человека.")
        menu(user_id)
        return

    cursor.execute("""SELECT COUNT(*) FROM online_queue
                      WHERE scheduled_time = %s AND status = 'ожидание'""", (selected_datetime,))
    booking_count = cursor.fetchone()[0]

    if booking_count >= MAX_BOOKINGS_PER_TIME_SLOT:
        bot.send_message(user_id, "На это время уже записано максимальное количество людей. Пожалуйста, выберите другое время.")
        return

    cursor.execute("SELECT customer_id FROM customers WHERE telegram_id = %s", (user_id,))
    customer = cursor.fetchone()

    if customer is None:
        bot.send_message(user_id, "Пожалуйста, зарегистрируйтесь или авторизуйтесь для записи.")
        return

    customer_id = customer[0]
    queue_number = generate_queue_number()

    cursor.execute(""" 
        INSERT INTO online_queue (customer_id, scheduled_time, status, telegram_id, queue_number)
        VALUES (%s, %s, %s, %s, %s)
    """, (customer_id, selected_datetime, "ожидание", user_id, queue_number))

    conn.commit()

    bot.send_message(user_id, f"Вы успешно записаны на {selected_datetime.strftime('%Y-%m-%d %H:%M')}.\nВаш номер в очереди: {queue_number}.")
    menu(user_id)




def cancel_booking(message):
    user_id = message.chat.id

    cursor.execute("""SELECT scheduled_time FROM online_queue
                      WHERE customer_id = (SELECT customer_id FROM customers WHERE telegram_id = %s) 
                      AND status = 'ожидание'""", (user_id,))
    booking = cursor.fetchone()

    if booking:
        scheduled_time = booking[0]
        formatted_time = scheduled_time.strftime("%Y-%m-%d %H:%M")
        confirmation_markup = types.InlineKeyboardMarkup()
        confirmation_markup.add(
            types.InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"confirm_cancel_{formatted_time}"),
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu_selection")
        )
        bot.send_message(user_id, f"Ваша текущая запись на {formatted_time}. Вы уверены, что хотите отменить?", reply_markup=confirmation_markup)
    else:
        bot.send_message(user_id, "У вас нет активных записей для отмены.")
        menu(user_id)


def confirm_cancel(call):
    user_id = call.message.chat.id
    cancellation_time = call.data.split('_')[-1]

    try:
        cursor.execute(""" 
            DELETE FROM online_queue
            WHERE customer_id = (SELECT customer_id FROM customers WHERE telegram_id = %s)
        """, (user_id,))
        conn.commit()

        bot.send_message(user_id, f"Запись на {cancellation_time} успешно отменена.")
    except Exception as e:
        bot.send_message(user_id, f"Произошла ошибка при отмене записи: {str(e)}")

    menu(user_id)


def generate_queue_number():
    cursor.execute("SELECT MAX(queue_id) FROM online_queue")
    max_online_queue_id = cursor.fetchone()[0] or 0

    cursor.execute("SELECT MAX(queue_id) FROM live_queue")
    max_live_queue_id = cursor.fetchone()[0] or 0

    max_queue_id = max(max_online_queue_id, max_live_queue_id)

    if max_queue_id >= 999:
        cursor.execute("DELETE FROM online_queue")
        cursor.execute("DELETE FROM live_queue")
        conn.commit()
        print("Данные из обеих таблиц были удалены, так как максимальный queue_id достиг 999.")

        cursor.execute("SELECT setval('online_queue_queue_id_seq', 1, false)")
        cursor.execute("SELECT setval('live_queue_queue_id_seq', 1, false)")
        conn.commit()

        queue_number = f"{1:03d}"
    else:
        if max_queue_id == 0:
            cursor.execute("SELECT setval('online_queue_queue_id_seq', 1, false)")
            cursor.execute("SELECT setval('live_queue_queue_id_seq', 1, false)")
        else:
            cursor.execute("SELECT setval('online_queue_queue_id_seq', %s, false)", (max_queue_id,))
            cursor.execute("SELECT setval('live_queue_queue_id_seq', %s, false)", (max_queue_id,))
        conn.commit()

        cursor.execute("SELECT nextval('online_queue_queue_id_seq')")
        online_queue_id = cursor.fetchone()[0]

        cursor.execute("SELECT nextval('live_queue_queue_id_seq')")
        live_queue_id = cursor.fetchone()[0]

        final_queue_id = max(online_queue_id, live_queue_id)

        queue_number = f"{final_queue_id:03d}"

    return queue_number


def send_time_based_notifications():
    while True:
        current_time = datetime.now()

        cursor.execute("""
            SELECT q.telegram_id, q.scheduled_time, c.full_name, q.status
            FROM online_queue q
            JOIN customers c ON q.telegram_id = c.telegram_id
            WHERE q.status = 'ожидание'
        """)

        records = cursor.fetchall()

        for record in records:
            telegram_id, scheduled_time_str, full_name, status = record

            if telegram_id not in sent_notifications:
                sent_notifications[telegram_id] = {'1_day': None, '1_hour': None, '30_min': None, '5_min': None}

            if isinstance(scheduled_time_str, str):
                try:
                    scheduled_time = datetime.strptime(scheduled_time_str, '%Y-%m-%d %H:%M')
                except ValueError:
                    continue
            elif isinstance(scheduled_time_str, datetime):
                scheduled_time = scheduled_time_str
            else:
                print(f"Неверный тип данных для времени: {scheduled_time_str}")
                continue

            time_to_appointment = scheduled_time - current_time

            if time_to_appointment >= timedelta(days=1) and time_to_appointment < timedelta(days=2):
                if sent_notifications[telegram_id]['1_day'] is None:
                    message = f"Здравствуйте, {full_name}!\nНапоминаем, что ваш прием запланирован на {scheduled_time.strftime('%Y-%m-%d %H:%M')}. Он состоится через 1 день."
                    bot.send_message(telegram_id, message)
                    sent_notifications[telegram_id]['1_day'] = current_time

            elif time_to_appointment >= timedelta(hours=1) and time_to_appointment < timedelta(hours=2):
                if sent_notifications[telegram_id]['1_hour'] is None:
                    message = f"Здравствуйте, {full_name}!\nНапоминаем, что ваш прием запланирован на {scheduled_time.strftime('%Y-%m-%d %H:%M')}. Он состоится через 1 час."
                    bot.send_message(telegram_id, message)
                    sent_notifications[telegram_id]['1_hour'] = current_time

            elif time_to_appointment >= timedelta(minutes=30) and time_to_appointment < timedelta(minutes=31):
                if sent_notifications[telegram_id]['30_min'] is None:
                    message = f"Здравствуйте, {full_name}!\nНапоминаем, что ваш прием запланирован на {scheduled_time.strftime('%Y-%m-%d %H:%M')}. Он состоится через 30 минут."
                    bot.send_message(telegram_id, message)
                    sent_notifications[telegram_id]['30_min'] = current_time

            elif time_to_appointment >= timedelta(minutes=5) and time_to_appointment < timedelta(minutes=6):
                if sent_notifications[telegram_id]['5_min'] is None:
                    message = f"Здравствуйте, {full_name}!\nНапоминаем, что ваш прием запланирован на {scheduled_time.strftime('%Y-%m-%d %H:%M')}. Он состоится через 5 минут."
                    bot.send_message(telegram_id, message)
                    sent_notifications[telegram_id]['5_min'] = current_time

        time.sleep(10)


def check_status_changes():
    while True:
        cursor.execute("""
            SELECT q.telegram_id, q.status, q.scheduled_time, c.full_name
            FROM online_queue q
            JOIN customers c ON q.telegram_id = c.telegram_id
            WHERE q.status IN ('процесс', 'завершен')
        """)
        records = cursor.fetchall()

        for record in records:
            telegram_id, status, scheduled_time_str, full_name = record
            current_time = datetime.now()

            if isinstance(scheduled_time_str, str):
                try:
                    scheduled_time = datetime.strptime(scheduled_time_str, '%Y-%m-%d %H:%M')  
                except ValueError:
                    print(f"Неверный формат времени для {telegram_id}: {scheduled_time_str}")
                    continue
            elif isinstance(scheduled_time_str, datetime):
                scheduled_time = scheduled_time_str 
            else:
                print(f"Неверный тип данных для времени: {scheduled_time_str}")
                continue

            if status == 'процесс':
                if telegram_id not in sent_notifications:
                    sent_notifications[telegram_id] = {}
                
                if sent_notifications[telegram_id].get('status_process') is None:
                    message = f"Здравствуйте, {full_name}!\nВаш прием начался в {scheduled_time.strftime('%Y-%m-%d %H:%M')}. Пожалуйста, проходите."
                    bot.send_message(telegram_id, message)
                    
                    sent_notifications[telegram_id]['status_process'] = current_time


            elif status == 'завершен':
                if sent_notifications.get(telegram_id, {}).get('status_completed') is None:
                    message = f"Спасибо, что посетили нас, {full_name}!\nВаш прием был завершен. До встречи!"
                    bot.send_message(telegram_id, message)
                    
                    if telegram_id not in sent_notifications:
                        sent_notifications[telegram_id] = {}
                    
                    sent_notifications[telegram_id]['status_completed'] = current_time


        time.sleep(10)


time_monitor_thread = threading.Thread(target=send_time_based_notifications)
time_monitor_thread.daemon = True
time_monitor_thread.start()

status_monitor_thread = threading.Thread(target=check_status_changes)
status_monitor_thread.daemon = True
status_monitor_thread.start()

bot.polling(none_stop=True)

