-- Таблица клиентов
CREATE TABLE customers (
	customer_id SERIAL PRIMARY KEY,                         -- Уникальный идентификатор клиента
	full_name VARCHAR(120) NOT NULL,
	telegram_id BIGINT UNIQUE DEFAULT NULL-- Имя клиента
);

-- Таблица живой очереди
CREATE TABLE live_queue (
	queue_id SERIAL PRIMARY KEY,                             -- Уникальный идентификатор записи в очереди
	customer_id INTEGER REFERENCES customers(customer_id),  -- Связь с билетом клиента
	counter_id INTEGER REFERENCES counters(counter_id) ON DELETE CASCADE,      -- Связь с операционным окном
	status VARCHAR(50) NOT NULL CHECK (status IN ('ожидание', 'процесс', 'завершен')), -- Статус очереди
	queue_number VARCHAR(5)UNIQUE, -- ticket
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP           -- Время создания записи в очереди
);
CREATE TABLE telegram_subscriptions (
    telegram_subscriptions SERIAL PRIMARY KEY,
    telegram_chat_id BIGINT NOT NULL, 
    customer_id INTEGER REFERENCES customers(customer_id), 
    queue_number VARCHAR(5) UNIQUE
);
-- Таблица администраторов
CREATE TABLE admins (
	admin_id SERIAL PRIMARY KEY,                             -- Уникальный идентификатор администратора
	telegram_id BIGINT UNIQUE,                               -- Telegram ID администратора
	admin_login VARCHAR(50) NOT NULL,
	admin_password VARCHAR(255) NOT NULL,
	role VARCHAR(30) DEFAULT 'admin' CHECK (role IN ('admin', 'superadmin')),  -- Роль администратора
	registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	is_logged_in BOOLEAN DEFAULT FALSE
);
CREATE TABLE counters (
	counter_id SERIAL PRIMARY KEY ,                           -- Уникальный идентификатор операционного окна
	counter_name VARCHAR(50),
	admin_id INTEGER REFERENCES admins(admin_id),
	is_active BOOLEAN DEFAULT TRUE                            -- Статус активности операционного окна (активно/неактивно)
);
-- Таблица Аудита
CREATE TABLE audits (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,          -- Имя пользователя, который выполнил действие
    event VARCHAR(50) NOT NULL,              -- Событие, например, "INSERT", "UPDATE"
    command TEXT NOT NULL,                   -- SQL команда
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Время выполнения команды
);	
CREATE TABLE stories_clients (
  customer_id INTEGER,
  full_name VARCHAR(120),
  time_start TIMESTAMP,
  time_end TIMESTAMP,
  total INTERVAL,
  queue_number VARCHAR(5),
  admin_id INTEGER REFERENCES admins(admin_id)
);

CREATE UNIQUE INDEX idx_queue_number ON stories_clients (queue_number);

CREATE TRIGGER trg_update_stories_clients
AFTER UPDATE OF status ON live_queue
FOR EACH ROW
EXECUTE FUNCTION update_stories_clients();

CREATE OR REPLACE FUNCTION update_stories_clients()
RETURNS TRIGGER AS $$
DECLARE
  v_admin_id INTEGER;
  v_time_start TIMESTAMP;
  v_time_end TIMESTAMP;
  v_total INTERVAL;
BEGIN
  IF NEW.counter_id IS DISTINCT FROM OLD.counter_id THEN
    SELECT admin_id
    INTO v_admin_id
    FROM counters
    WHERE counter_id = NEW.counter_id
    LIMIT 1;
  ELSE
    SELECT admin_id
    INTO v_admin_id
    FROM counters
    WHERE counter_id = OLD.counter_id
    LIMIT 1;
  END IF;

  INSERT INTO stories_clients (customer_id, full_name, queue_number, time_start, admin_id)
  VALUES (NEW.customer_id, 
          (SELECT full_name FROM customers WHERE customer_id = NEW.customer_id), 
          NEW.queue_number, 
          CURRENT_TIMESTAMP,
          v_admin_id)
  ON CONFLICT (queue_number) 
  DO NOTHING;

  IF NEW.status = 'завершен' AND OLD.status = 'процесс' THEN
    SELECT time_start INTO v_time_start FROM stories_clients WHERE queue_number = NEW.queue_number;
    
    v_time_end := CURRENT_TIMESTAMP;

    v_total := v_time_end - v_time_start;

    UPDATE stories_clients
    SET time_end = v_time_end,  
        total = v_total,
        admin_id = v_admin_id
    WHERE queue_number = NEW.queue_number;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Функция для аудита команд
CREATE OR REPLACE FUNCTION audit_command()
RETURNS EVENT_TRIGGER
AS
$$
BEGIN
    INSERT INTO audits(username, event, command)
    VALUES (session_user, TG_EVENT, TG_TAG);
END;
$$
LANGUAGE plpgsql;

CREATE EVENT TRIGGER audit_ddl_commands
ON ddl_command_end
EXECUTE FUNCTION audit_command();


CREATE TABLE online_queue (
    queue_id SERIAL PRIMARY KEY,                        -- Уникальный идентификатор записи в очереди
    customer_id INTEGER REFERENCES customers(customer_id),  -- Ссылка на клиента
	telegram_id BIGINT REFERENCES customers(telegram_id),
    counter_id INTEGER REFERENCES counters(counter_id) ON DELETE CASCADE, -- Ссылка на стол
    scheduled_time TIMESTAMP NOT NULL,                  -- Время, на которое назначен прием
    status VARCHAR(50) NOT NULL CHECK (status IN ('ожидание','процесс', 'завершен')), -- Статус записи (ожидание или завершен)
    queue_number VARCHAR(5)UNIQUE,                      -- Номер в очереди
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- Время создания записи
    start_time TIMESTAMP NULL                           -- Время начала приема клиента
);

CREATE OR REPLACE FUNCTION update_stories_clients_online_queue()
RETURNS TRIGGER AS $$
DECLARE
  v_admin_id INTEGER;
  v_time_start TIMESTAMP;
  v_time_end TIMESTAMP;
  v_total INTERVAL;
BEGIN
  IF NEW.counter_id IS DISTINCT FROM OLD.counter_id THEN
    SELECT admin_id
    INTO v_admin_id
    FROM counters
    WHERE counter_id = NEW.counter_id
    LIMIT 1;
  ELSE
    SELECT admin_id
    INTO v_admin_id
    FROM counters
    WHERE counter_id = OLD.counter_id
    LIMIT 1;
  END IF;
  INSERT INTO stories_clients (customer_id, full_name, queue_number, time_start, admin_id)
  VALUES (NEW.customer_id, 
          (SELECT full_name FROM customers WHERE customer_id = NEW.customer_id), 
          NEW.queue_number, 
          CURRENT_TIMESTAMP,
          v_admin_id)
  ON CONFLICT (queue_number) 
  DO NOTHING;

  IF NEW.status = 'завершен' AND OLD.status = 'процесс' THEN
    SELECT time_start INTO v_time_start FROM stories_clients WHERE queue_number = NEW.queue_number;
    
    v_time_end := CURRENT_TIMESTAMP;

    v_total := v_time_end - v_time_start;

    UPDATE stories_clients
    SET time_end = v_time_end,  
        total = v_total,
        admin_id = v_admin_id
    WHERE queue_number = NEW.queue_number;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_stories_clients_online_queue
AFTER UPDATE OF status ON online_queue
FOR EACH ROW
EXECUTE FUNCTION update_stories_clients_online_queue();