from flask import Flask, request, render_template, jsonify, redirect, url_for
from bd_queue import conn, cursor
from telegram_bot_queue import run_telegram_bot
import threading

app = Flask(__name__)

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



def get_people_in_front(queue_number):
    cursor.execute("""SELECT COUNT(*) FROM live_queue WHERE queue_number < %s AND status = 'ожидание'""", (queue_number,))
    people_in_front = cursor.fetchone()[0]
    return people_in_front

def register_customer(full_name):
    cursor.execute("""INSERT INTO customers (full_name) VALUES (%s) RETURNING customer_id""", (full_name,))
    customer_id = cursor.fetchone()[0]
    conn.commit()

    queue_number = generate_queue_number()

    cursor.execute("""INSERT INTO live_queue (customer_id, status, queue_number) VALUES (%s, 'ожидание', %s)""", (customer_id, queue_number))
    conn.commit()

    return queue_number


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        full_name = request.form["full_name"]
        queue_number = register_customer(full_name)
        return redirect(url_for("queue1", queue_number=queue_number))

    return render_template("index.html")

@app.route("/queue1")
def queue1():
    queue_number = request.args.get("queue_number")
    
    cursor.execute("""SELECT COUNT(*) FROM live_queue WHERE queue_number < %s AND status = 'ожидание'""", (queue_number,))
    people_in_front = cursor.fetchone()[0]

    if people_in_front == 0:
        return redirect(url_for("queue2", queue_number=queue_number))
    

    return render_template("queue1.html", queue_number=queue_number, people_in_front=people_in_front)

@app.route("/queue2")
def queue2():
    queue_number = request.args.get("queue_number")
    
    return render_template("queue2.html", queue_number=queue_number)

@app.route("/queue3")
def queue3():
    queue_number = request.args.get("queue_number")
    
    cursor.execute("SELECT status, counter_id FROM live_queue WHERE queue_number = %s", (queue_number,))
    queue_data = cursor.fetchone()

    if queue_data:
        status, counter_id = queue_data
    else:
        return "Очередь не найдена", 404  

    if status == 'завершен':
        return redirect(url_for("index"))

    cursor.execute("SELECT counter_name FROM counters WHERE counter_id = %s", (counter_id,))
    counter_name_data = cursor.fetchone()

    if counter_name_data:
        counter_name = counter_name_data[0]
    else:
        counter_name = "Неизвестный стол"

    if status == 'процесс':
        return render_template("queue3.html", queue_number=queue_number, counter_name=counter_name)

    return redirect(url_for("queue1", queue_number=queue_number))



@app.route("/end")
def end():
        queue_number = request.args.get("queue_number") 
        if not queue_number:
            return "Ошибка: номер очереди не передан", 400  

        cursor.execute("SELECT customer_id FROM live_queue WHERE queue_number = %s", (queue_number,))
        customer_id_result = cursor.fetchone()

        if customer_id_result:
            customer_id = customer_id_result[0]
            try:
                cursor.execute("DELETE FROM live_queue WHERE queue_number = %s", (queue_number,))
                conn.commit() 
                print(f"Запись с queue_number = {queue_number} удалена из live_queue")

                cursor.execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))
                conn.commit() 
                print(f"Запись с customer_id = {customer_id} удалена из customers")

                return render_template("end.html")
            except Exception as e:
                print(f"Ошибка при удалении данных: {e}")
                conn.rollback() 
                return "Ошибка при удалении данных", 500  
        else:
            print(f"Запись для queue_number = {queue_number} не найдена")
            return "Пользователь с таким номером очереди не найден", 404


@app.route("/new-data-status", methods=["GET"])
def new_data_status():
    queue_number = request.args.get("queue_number")

    if not queue_number:
        return jsonify({"error": "Queue number is required"}), 400

    cursor.execute("SELECT COUNT(*) FROM live_queue WHERE queue_number = %s", (queue_number,))
    queue_exists = cursor.fetchone()[0]

    if queue_exists == 0:
        return jsonify({"error": "Queue number not found"}), 404

    cursor.execute("SELECT status FROM live_queue WHERE queue_number = %s", (queue_number,))
    status_result = cursor.fetchone()

    status = status_result[0]

    cursor.execute("""
        SELECT COUNT(*) 
        FROM live_queue 
        WHERE queue_number < %s AND status = 'ожидание'
    """, (queue_number,))
    people_in_front_result = cursor.fetchone()

    people_in_front = people_in_front_result[0] if people_in_front_result else 0

    return jsonify({
        "queue_number": queue_number,
        "status": status,
        "people_in_front": people_in_front
    })


def run_flask_app():
    app.run(debug=True, use_reloader=False)

def main():
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()

    run_telegram_bot()

if __name__ == "__main__":
    main()