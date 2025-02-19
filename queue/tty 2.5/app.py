from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import psycopg2
import re
import decimal
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chinchopa'

conn = psycopg2.connect(
    dbname="tty",
    user="postgres",
    password="123",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

def format_duration(duration):
    """
    Преобразует строку интервала в объект timedelta.
    """
    if isinstance(duration, str):
        pattern = re.compile(r"(?:(\d+) day(?:s)?)? ?(?:(\d+):)?(?:(\d+):)?(\d+)")
        match = pattern.match(duration)
        
        if match:
            days = int(match.group(1) or 0)
            hours = int(match.group(2) or 0)
            minutes = int(match.group(3) or 0)
            seconds = int(match.group(4))
            
            return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        else:
            return timedelta()
    elif isinstance(duration, timedelta):
        return duration
    elif isinstance(duration, (int, float)):
        return timedelta(seconds=duration)
    return timedelta()

def timedelta_to_str(duration):
    """
    Преобразует timedelta в строку формата 'hh:mm:ss'.
    """
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 606
    seconds = total_seconds % 60

    return f"{hours:02}:{minutes:02}:{seconds:02}"
    
def delete_admin(admin_login):
    cursor.execute("DELETE FROM admins WHERE admin_login = %s", (admin_login,))
    conn.commit() 

def get_admin_by_login(admin_login, admin_password):
    cursor.execute("SELECT admin_id, admin_login, role, is_logged_in, admin_password FROM admins WHERE admin_login = %s", 
                   (admin_login,))
    admin = cursor.fetchone()
    
    if admin and check_password_hash(admin[4], admin_password):
        return admin
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        admin_login = request.form['admin_login']
        admin_password = request.form['admin_password']
        
        admin = get_admin_by_login(admin_login, admin_password)
        
        if admin:
            if admin[3]:
                flash('Этот аккаунт уже используется другим пользователем. Пожалуйста, выйдите из системы.', 'danger')
                return redirect(url_for('index'))

            session['admin_login'] = admin[1]
            session['admin_id'] = admin[0]
            session['role'] = admin[2]

            cursor.execute("UPDATE admins SET is_logged_in = TRUE WHERE admin_id = %s", (admin[0],))
            conn.commit()

            flash(f'Добро пожаловать, {admin_login}! Роль: {admin[2]}', 'success')
            return redirect(url_for('choose_table'))
        else:
            flash('Неверный логин или пароль', 'danger')
    
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'role' not in session or session['role'] != 'superadmin':
        flash('У вас нет прав для доступа к этой странице', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        admin_login = request.form['admin_login']
        admin_password = request.form['admin_password']
        role = request.form.get('role', 'admin')
        
        hashed_password = generate_password_hash(admin_password)
        
        cursor.execute("INSERT INTO admins (admin_login, admin_password, role) VALUES (%s, %s, %s)",
                       (admin_login, hashed_password, role))
        conn.commit()
        
        flash(f'Администратор {admin_login} успешно зарегистрирован!', 'success')
        return redirect(url_for('admins'))
    
    return render_template('register_admin.html')

# Для создания супер-админа вручную (например, через консоль или при первичной настройке)
cursor.execute("SELECT COUNT(*) FROM admins WHERE admin_login = %s", ('Chin',))
count = cursor.fetchone()[0]

if count == 0:
    hashed_password = generate_password_hash("321")
    cursor.execute("INSERT INTO admins (admin_login, admin_password, role) VALUES (%s, %s, %s)",
                   ('Chin', hashed_password, 'superadmin'))
    conn.commit()
    print("Супер-администратор успешно создан.")
else:
    print("Супер-администратор с логином 'Chin' уже существует.")

@app.route('/admins')
def admins():
    if 'role' not in session or session['role'] != 'superadmin':
        flash('У вас нет прав для доступа к этому разделу', 'danger')
        return redirect(url_for('choose_table'))
    
    cursor.execute("SELECT admin_login, role FROM admins")
    admins_list = cursor.fetchall()

    cursor.execute("SELECT counter_id, counter_name, is_active FROM counters ORDER BY counter_id ASC")
    counters_list = cursor.fetchall()

    return render_template('admin_list.html', admins=admins_list, counters=counters_list)

@app.route('/delete_admin/<string:admin_login>', methods=['GET', 'POST'])
def delete(admin_login):
    if 'role' not in session or session['role'] != 'superadmin':
        flash('У вас нет прав для удаления администраторов', 'danger')
        return redirect(url_for('admins'))

    if session['admin_login'] == admin_login:
        flash('Нельзя удалить собственного аккаунта', 'danger')
        return redirect(url_for('admins'))
    
    delete_admin(admin_login)
    flash(f'Администратор {admin_login} был успешно удалён.', 'success')
    return redirect(url_for('admins'))

@app.route('/add_counter')
def add_counter():
    if 'role' not in session or session['role'] != 'superadmin':
        flash('У вас нет прав для доступа к этой странице', 'danger')
        return redirect(url_for('dashboard'))
    
    cursor.execute("SELECT MAX(counter_id) FROM counters")
    max_counter_id = cursor.fetchone()[0]
    
    next_counter_id = max_counter_id + 1 if max_counter_id else 1

    counter_name = f"Стол {next_counter_id}"

    cursor.execute("INSERT INTO counters (counter_id, counter_name, is_active) VALUES (%s, %s, %s)", 
                   (next_counter_id, counter_name, True))
    conn.commit()

    flash(f'Новый стол "{counter_name}" успешно добавлен!', 'success')
    return redirect(url_for('admins'))  # Redirect to admins page after adding the table

@app.route('/delete_counter', methods=['GET', 'POST'])
def delete_counter():
    if 'role' not in session or session['role'] != 'superadmin':
        flash('У вас нет прав для удаления столов', 'danger')
        return redirect(url_for('admins'))
    
    cursor.execute("SELECT MAX(counter_id) FROM counters")
    max_counter_id = cursor.fetchone()[0]

    if max_counter_id is None:
        flash('Нет доступных столов для удаления.', 'warning')
        return redirect(url_for('admins'))
    
    cursor.execute("DELETE FROM counters WHERE counter_id = %s", (max_counter_id,))
    conn.commit()
    
    flash(f'Стол с ID {max_counter_id} был успешно удалён.', 'success')
    return redirect(url_for('admins'))


@app.route('/choose_table', methods=['GET', 'POST'])
def choose_table():
    if 'admin_login' not in session:
        return redirect(url_for('index'))
    
    admin_login = session['admin_login']
    admin_id = session.get('admin_id')
    role = session['role']
    
    if role == 'superadmin':
        cursor.execute("SELECT admin_id, admin_login FROM admins ORDER BY admin_login;")
        admins = cursor.fetchall()

        cursor.execute("SELECT counter_id, counter_name, is_active, admin_id FROM counters ORDER BY counter_id;")
        counters = cursor.fetchall()

        if request.method == 'POST':
            counter_id = request.form['counter_id']

            cursor.execute("SELECT is_active, admin_id FROM counters WHERE counter_id = %s", (counter_id,))
            result = cursor.fetchone()
            is_active = result[0]
            current_admin_id = result[1]

            if is_active and current_admin_id is None:
                cursor.execute("""
                    UPDATE counters 
                    SET is_active = FALSE, admin_id = %s 
                    WHERE counter_id = %s
                """, (admin_id, counter_id))
                conn.commit()

                flash(f'Вы выбрали стол {counter_id}.', 'success')
                return redirect(url_for('manage_table', counter_id=counter_id))
            else:
                flash('Этот стол уже занят другим администратором.', 'danger')

        return render_template('choose_table.html', admin_login=admin_login, role=role, counters=counters, admins=admins)
    
    else:
        cursor.execute("SELECT counter_id, counter_name, is_active, admin_id FROM counters ORDER BY counter_id;")
        counters = cursor.fetchall()

        if request.method == 'POST':
            counter_id = request.form['counter_id']

            cursor.execute("SELECT is_active, admin_id FROM counters WHERE counter_id = %s", (counter_id,))
            result = cursor.fetchone()
            is_active = result[0]
            current_admin_id = result[1]

            if is_active and current_admin_id is None:
                cursor.execute("""
                    UPDATE counters 
                    SET is_active = FALSE, admin_id = %s 
                    WHERE counter_id = %s
                """, (admin_id, counter_id))
                conn.commit()

                flash(f'Вы выбрали стол {counter_id}.', 'success')
                return redirect(url_for('manage_table', counter_id=counter_id))
            else:
                flash('Этот стол уже занят другим администратором.', 'danger')

        return render_template('choose_table.html', admin_login=admin_login, role=role, counters=counters)

@app.route('/manage_table/<int:counter_id>', methods=['GET', 'POST'])
def manage_table(counter_id):
    if 'admin_login' not in session:
        return redirect(url_for('index'))
    
    cursor.execute("""
        SELECT queue_id, customer_id, queue_number, status
        FROM live_queue
        WHERE status = 'ожидание'
        ORDER BY created_at ASC
    """)
    waiting_clients = cursor.fetchall()

    if request.method == 'POST':
        if 'queue_id_to_call' in request.form:
            queue_id_to_call = request.form.get('queue_id_to_call')
            if queue_id_to_call:
                cursor.execute("""
                    UPDATE live_queue
                    SET status = 'процесс', counter_id = %s
                    WHERE queue_id = %s
                """, (counter_id, queue_id_to_call))
                conn.commit()

                flash('Клиент вызван вне очереди!', 'success')
                return redirect(url_for('manage_table', counter_id=counter_id))

        if 'delete_queue_id' in request.form:
            queue_id_to_delete = request.form.get('delete_queue_id')
            if queue_id_to_delete:
                cursor.execute("""
                    DELETE FROM live_queue
                    WHERE queue_id = %s
                """, (queue_id_to_delete,))
                conn.commit()

                flash('Клиент удален из очереди.', 'danger')
                return redirect(url_for('manage_table', counter_id=counter_id))

    admin_id = session.get('admin_id')

    cursor.execute("""
        SELECT counter_id, counter_name, is_active, admin_id
        FROM counters
        WHERE counter_id = %s
    """, (counter_id,))
    counter = cursor.fetchone()

    if not counter:
        flash('Стол не найден.', 'danger')
        return redirect(url_for('choose_table'))

    if request.method == 'POST' and 'start_acceptance' in request.form:
        cursor.execute("""
            SELECT queue_id, customer_id, queue_number, status, scheduled_time
            FROM online_queue
            WHERE counter_id IS NULL AND status = 'ожидание' AND scheduled_time <= %s
            ORDER BY scheduled_time ASC
            LIMIT 1
        """, (datetime.now(),))
        client = cursor.fetchone()

        if client:
            start_time = datetime.now()
            cursor.execute("""
                UPDATE online_queue
                SET status = 'процесс', counter_id = %s, start_time = %s
                WHERE queue_id = %s
            """, (counter_id, start_time, client[0]))
            conn.commit()
            flash(f'Начат прием клиента {client[2]} на столе {counter_id}.', 'success')
            return redirect(url_for('manage_table', counter_id=counter_id))
        else:
            cursor.execute("""
                SELECT queue_id, customer_id, queue_number, status
                FROM live_queue
                WHERE counter_id IS NULL AND status = 'ожидание'
                ORDER BY created_at ASC
                LIMIT 1
            """)
            client = cursor.fetchone()

            if client:
                cursor.execute("""
                    UPDATE live_queue
                    SET status = 'процесс', counter_id = %s
                    WHERE queue_id = %s
                """, (counter_id, client[0]))
                conn.commit()
                flash(f'Начат прием клиента {client[2]} на столе {counter_id}.', 'success')
                return redirect(url_for('manage_table', counter_id=counter_id))
            else:
                flash('Нет клиентов в очереди с состоянием "ожидание".', 'warning')
                return redirect(url_for('manage_table', counter_id=counter_id))

    if request.method == 'POST' and 'end_acceptance' in request.form:
        cursor.execute("""
            SELECT queue_id, customer_id, queue_number, status
            FROM live_queue
            WHERE counter_id = %s AND status = 'процесс'
            LIMIT 1
        """, (counter_id,))
        client = cursor.fetchone()

        if client:
            cursor.execute("""
                UPDATE live_queue
                SET status = 'завершен'
                WHERE queue_id = %s
            """, (client[0],))
            conn.commit()
            flash(f'Прием клиента {client[2]} завершен.', 'success')
            return redirect(url_for('manage_table', counter_id=counter_id))

        cursor.execute("""
            SELECT queue_id, customer_id, queue_number, status
            FROM online_queue
            WHERE counter_id = %s AND status = 'процесс'
            LIMIT 1
        """, (counter_id,))
        client = cursor.fetchone()

        if client:
            cursor.execute("""
                UPDATE online_queue
                SET status = 'завершен'
                WHERE queue_id = %s
            """, (client[0],))
            conn.commit()
            flash(f'Прием клиента {client[2]} завершен.', 'success')
            return redirect(url_for('manage_table', counter_id=counter_id))

        flash('Нет клиентов с состоянием "процесс" на этом столе.', 'warning')
        return redirect(url_for('manage_table', counter_id=counter_id))

    if request.method == 'POST' and 'exit' in request.form:
        cursor.execute("""
            UPDATE counters
            SET is_active = TRUE, admin_id = NULL
            WHERE counter_id = %s
        """, (counter_id,))
        conn.commit()
        flash(f'Стол {counter_id} освобожден.', 'success')
        return redirect(url_for('choose_table'))

    if request.method == 'POST' and 'return_to_live_queue' in request.form:
        cursor.execute("""
            SELECT queue_id, customer_id, queue_number, status
            FROM online_queue
            WHERE counter_id = %s AND status = 'процесс'
            LIMIT 1
        """, (counter_id,))
        client = cursor.fetchone()

        if client:
            cursor.execute("""
                DELETE FROM online_queue
                WHERE queue_id = %s
            """, (client[0],))
            
            cursor.execute("""
                INSERT INTO live_queue (customer_id, queue_number, status, created_at)
                VALUES (%s, %s, 'ожидание', %s)
            """, (client[1], client[2], datetime.now()))
            conn.commit()
            flash(f'Клиент {client[2]} возвращен в живую очередь.', 'success')
            return redirect(url_for('manage_table', counter_id=counter_id))

    cursor.execute("""
        SELECT queue_id, customer_id, queue_number, status, start_time
        FROM online_queue
        WHERE counter_id = %s AND status = 'процесс'
        LIMIT 1
    """, (counter_id,))
    client_in_process_online = cursor.fetchone()

    if client_in_process_online:
        start_time = client_in_process_online[4]
        if datetime.now() > start_time + timedelta(minutes=5):
            return render_template('manage_table.html', counter=counter, client=client_in_process_online, in_process=True, queue_type="Онлайн очередь", time_elapsed=True)

    cursor.execute("""
        SELECT queue_id, customer_id, queue_number, status
        FROM live_queue
        WHERE counter_id = %s AND status = 'процесс'
        LIMIT 1
    """, (counter_id,))
    client_in_process = cursor.fetchone()

    if client_in_process:
        queue_type = "Живая очередь"
        return render_template('manage_table.html', counter=counter, client=client_in_process, in_process=True, queue_type=queue_type)

    if client_in_process_online:
        queue_type = "Онлайн очередь"
        return render_template('manage_table.html', counter=counter, client=client_in_process_online, in_process=True, queue_type=queue_type)

    return render_template('manage_table.html', counter=counter, in_process=False,  waiting_clients=waiting_clients, counter_id=counter_id)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if 'admin_id' in session:
        cursor.execute("UPDATE admins SET is_logged_in = FALSE WHERE admin_id = %s", (session['admin_id'],))
        conn.commit()

    session.pop('admin_login', None)
    session.pop('role', None)
    session.pop('admin_id', None)

    flash('Вы успешно вышли из системы.', 'success')

    return redirect(url_for('index'))

@app.route('/statistics', methods=['GET'])
def statistics():
    if 'admin_login' not in session:
        flash('Пожалуйста, войдите в систему.', 'danger')
        return redirect(url_for('index'))
    
    admin_id = session.get('admin_id')
    period = request.args.get('period', 'all_time')

    if period == '1_day':
        start_date = datetime.now() - timedelta(days=1)
    elif period == '10_days':
        start_date = datetime.now() - timedelta(days=10)
    elif period == '1_month':
        start_date = datetime.now() - timedelta(days=30)
    else:
        start_date = datetime(2000, 1, 1)  # Дата, с которой начинаются данные

    if session.get('role') == 'superadmin':
        cursor.execute("""
            SELECT a.admin_login, 
                   COUNT(s.customer_id) AS total_clients,
                   AVG(EXTRACT(EPOCH FROM (s.time_end - s.time_start))) AS avg_duration
            FROM admins a
            LEFT JOIN stories_clients s ON a.admin_id = s.admin_id
            WHERE s.time_start >= %s
            AND s.time_end IS NOT NULL
            GROUP BY a.admin_login
            ORDER BY total_clients DESC
        """, (start_date,))
        stats = cursor.fetchall()

        for i in range(len(stats)):
            avg_duration_seconds = stats[i][2]
            
            if isinstance(avg_duration_seconds, decimal.Decimal):
                avg_duration_seconds = float(avg_duration_seconds)

            if avg_duration_seconds:
                avg_duration = timedelta(seconds=avg_duration_seconds)
                stats[i] = stats[i] + (timedelta_to_str(avg_duration),)
            else:
                stats[i] = stats[i] + ('00:00:00',)

        # Фильтрация по полю time_end
        cursor.execute("""
            SELECT 
                s.full_name, 
                s.time_start, 
                s.time_end, 
                s.total, 
                s.queue_number
            FROM stories_clients s
            WHERE s.admin_id = %s AND s.time_start >= %s
            AND s.time_end IS NOT NULL
            ORDER BY s.time_start DESC
        """, (admin_id, start_date))
        personal_stats = cursor.fetchall()

        total_clients = len(personal_stats)
        total_duration = timedelta()

        for i in range(len(personal_stats)):
            personal_stats[i] = list(personal_stats[i])  # Преобразуем кортеж в список, чтобы можно было изменить

            # Проверяем, является ли время началом и концом датой
            if isinstance(personal_stats[i][1], datetime):
                personal_stats[i][1] = personal_stats[i][1].strftime('%d %B %Y, %H:%M:%S')  # Время начала
            else:
                personal_stats[i][1] = 'Неверная дата'

            if isinstance(personal_stats[i][2], datetime):
                personal_stats[i][2] = personal_stats[i][2].strftime('%d %B %Y, %H:%M:%S')  # Время окончания
            else:
                personal_stats[i][2] = 'Неверная дата'

            duration = personal_stats[i][3]  # Интервал из базы данных, например
            duration_timedelta = format_duration(duration)
            personal_stats[i][3] = timedelta_to_str(duration_timedelta)  # Преобразуем продолжительность в строку
            total_duration += duration_timedelta  # Добавляем к общей продолжительности

        if total_clients > 0:
            average_duration_seconds = total_duration.total_seconds() / total_clients  # Среднее время
            average_duration = timedelta(seconds=average_duration_seconds)  # Средняя продолжительность
            average_duration_str = timedelta_to_str(average_duration)
        else:
            average_duration_str = '00:00:00'

        return render_template('statistics.html', stats=stats, period=period, personal_stats=personal_stats,
                               total_clients=total_clients, average_duration=average_duration_str)

    # Фильтрация по полю total
    cursor.execute("""
        SELECT 
            s.full_name, 
            s.time_start, 
            s.time_end, 
            s.total, 
            s.queue_number
        FROM stories_clients s
        WHERE s.admin_id = %s AND s.time_start >= %s 
        AND s.time_end IS NOT NULL
        ORDER BY s.time_start DESC
    """, (admin_id, start_date))
    stats = cursor.fetchall()

    total_clients = len(stats)
    total_duration = timedelta()

    for i in range(len(stats)):
        stats[i] = list(stats[i])
        
        # Проверяем, является ли время началом и концом датой
        if isinstance(stats[i][1], datetime):
            stats[i][1] = stats[i][1].strftime('%d %B %Y, %H:%M:%S')  # Время начала
        else:
            stats[i][1] = 'Неверная дата'
        
        if isinstance(stats[i][2], datetime):
            stats[i][2] = stats[i][2].strftime('%d %B %Y, %H:%M:%S')  # Время окончания
        else:
            stats[i][2] = 'Неверная дата'

        duration = stats[i][3]
        duration_timedelta = format_duration(duration)
        stats[i][3] = timedelta_to_str(duration_timedelta)
        total_duration += duration_timedelta

    if total_clients > 0:
        average_duration_seconds = total_duration.total_seconds() / total_clients
        average_duration = timedelta(seconds=average_duration_seconds)
        average_duration_str = timedelta_to_str(average_duration)
    else:
        average_duration_str = '00:00:00'

    return render_template('statistics.html', stats=stats, period=period, total_clients=total_clients, average_duration=average_duration_str)

@app.route('/check_admin_status')
def check_admin_status():
    admin_id = session.get('admin_id')
    
    if admin_id:
        cursor.execute("""
            SELECT counter_id 
            FROM counters 
            WHERE admin_id = %s AND is_active = FALSE
        """, (admin_id,))
        result = cursor.fetchone()

        if result:
            # Если стол назначен, возвращаем ID стола
            return jsonify({'tableAssigned': True, 'tableId': result[0]})
        else:
            # Если стол не назначен
            return jsonify({'tableAssigned': False})
    
    return jsonify({'tableAssigned': False})


if __name__ == '__main__':
    app.run(debug=True)