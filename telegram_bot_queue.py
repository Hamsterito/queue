import time
import telebot
import threading
from bd_queue import conn, cursor

bot = telebot.TeleBot("YOUR_KEY")

# Ожидаемое состояние пользователя, когда он должен ввести свой номер билета
WAITING_FOR_QUEUE_NUMBER = 'waiting_for_queue_number'

# Словарь для хранения состояния каждого пользователя
user_states = {}

# Словарь для хранения статусов очередей для каждого пользователя
user_statuses = {}

# Словарь для хранения последних отправленных сообщений для каждого пользователя
last_sent_messages = {}

# Функция для отправки обновлений о статусе всем пользователям
def send_notifications():
    while True:
        # Проверяем статус всех подписанных пользователей
        cursor.execute("""
            SELECT ts.telegram_chat_id, lq.queue_number, lq.status
            FROM telegram_subscriptions ts
            JOIN live_queue lq ON ts.queue_number = lq.queue_number
        """)
        users_in_queue = cursor.fetchall()

        for chat_id, queue_number, status in users_in_queue:
            # Если статус изменился, отправляем уведомление
            if queue_number not in user_statuses or user_statuses[queue_number] != status:
                # Определяем сообщение, которое нужно отправить
                if status == 'ожидание':
                    cursor.execute(""" 
                        SELECT COUNT(*) FROM live_queue 
                        WHERE status = 'ожидание' AND queue_id < (SELECT queue_id FROM live_queue WHERE queue_number = %s)
                    """, (queue_number,))
                    people_in_front = cursor.fetchone()[0]

                    if people_in_front == 0:
                        message = "Ваша очередь скоро подойдёт!Осталось совсем чуть чуть! Пожалуйста, подождите."
                    else:
                        message = "Вы стали в очередь! Пожалуйста, подождите."

                elif status == 'процесс':
                    message = "Ваша очередь подошла. Пожалуйста, проходите внутрь."

                elif status == 'завершен':
                    message = "Спасибо, что посетили нас!"

                # Проверяем, было ли уже отправлено это сообщение
                if last_sent_messages.get(chat_id) != message:
                    # Отправляем уведомление
                    notify_user(chat_id, message)

                    # Обновляем статус и сохраняем отправленное сообщение
                    user_statuses[queue_number] = status
                    last_sent_messages[chat_id] = message

        time.sleep(10)  # Пауза между проверками, например, 10 секунд

# Функция отправки уведомлений пользователю
def notify_user(chat_id, message):
    bot.send_message(chat_id, message)


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_message(message):
    user_states[message.chat.id] = WAITING_FOR_QUEUE_NUMBER  # Изменяем состояние пользователя
    bot.send_message(message.chat.id, "Привет! Пожалуйста, отправьте ваш номер билета.")

# Проверка на регистрацию
@bot.message_handler(func=lambda message: message.chat.id not in user_states or user_states[message.chat.id] is None)
def not_registered(message):
    bot.send_message(message.chat.id, "Пожалуйста, отправьте команду /start для начала работы с ботом.")

# Обработчик получения номера билета
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == WAITING_FOR_QUEUE_NUMBER)
def get_queue_number(message):
    queue_number = message.text.strip()

    # Проверка, существует ли уже запись в таблице для этого telegram_chat_id
    cursor.execute("SELECT * FROM telegram_subscriptions WHERE telegram_chat_id = %s", (message.chat.id,))
    existing_registration = cursor.fetchone()

    if existing_registration:
        bot.send_message(message.chat.id, "Вы уже зарегистрировали свой номер билета. Один номер может быть зарегистрирован только один раз. Пожалуйста, ожидайте уведомление.")
        return  # Прерываем выполнение функции, если пользователь уже зарегистрирован

    # Проверка, существует ли queue_number в базе данных
    cursor.execute("SELECT * FROM live_queue WHERE queue_number = %s", (queue_number,))
    result = cursor.fetchone()

    if result:
        # Сохраняем связь с telegram_chat_id
        cursor.execute(""" 
            INSERT INTO telegram_subscriptions (telegram_chat_id, queue_number)
            VALUES (%s, %s)
            ON CONFLICT (queue_number) DO UPDATE SET telegram_chat_id = %s
        """, (message.chat.id, queue_number, message.chat.id))
        conn.commit()

        # Меняем состояние пользователя, чтобы он не снова не вводил номер
        user_states[message.chat.id] = None

        # Запускаем уведомления в отдельном потоке, только если уведомление еще не было отправлено
        if queue_number not in user_statuses:
            threading.Thread(target=send_notifications, daemon=True).start()

        bot.send_message(message.chat.id, "Вы успешно зарегистрированы в системе. Ожидайте уведомления о статусе.")
    else:
        bot.send_message(message.chat.id, "Номер билета не найден в очереди. Пожалуйста, проверьте правильность введенного номера и попробуйте снова.")

# Функция отправки уведомлений пользователю
def notify_user(chat_id, message):
    bot.send_message(chat_id, message)

# Запуск бота
def run_telegram_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    run_telegram_bot()