# Руководство по развёртыванию

## Вариант 1 — Новый сервер (чистая установка)

### 1. Перенести код
git clone <repo> /path/to/app

### 2. Установить зависимости
pip install -r requirements.txt

### 3. Настроить конфиг и .env
Отредактировать `config.py` — указать актуальные значения:
DB_HOST     = "localhost"
DB_USER     = "root"
DB_PASSWORD = "your_password"
DB_NAME     = "sarwan"
SECRET_KEY  = "your_secret_key"

### 4. Создать базу данных и применить схему
mysql -u root -p -e "CREATE DATABASE sarwan CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p sarwan < schema.sql

### 5. Загрузить разрешения
python seed_permissions.py

### 6. Создать администратора
python create_admin.py
Администратору автоматически выдаются все разрешения.

### 7. Запустить приложение
gunicorn -w 4 -b 127.0.0.1:5000 app:app


## Вариант 2 — Существующий сервер с базой данных

> ⚠️ Не запускать `schema.sql` — он перезапишет все данные.

### 1. Добавить новые таблицы в существующую БД

### 2. Загрузить разрешения
```bash
python seed_permissions.py
```

### 3. Выдать все разрешения существующим администраторам
```sql
INSERT IGNORE INTO user_permissions (user_id, permission_id)
SELECT u.id, p.id
FROM users u
CROSS JOIN permissions p
WHERE u.role = 'admin';
```

### 4. Обновить код
```bash
git pull
```

### 5. Перезапустить приложение
```bash
gunicorn -w 4 -b 127.0.0.1:5000 app:app
```

---

## При каждом следующем обновлении (если добавились новые роуты)

```bash
# 1. Обновить код
git pull

# 2. Загрузить новые разрешения (идемпотентно, старые не затрагивает)
python seed_permissions.py

# 3. Выдать новые разрешения администраторам
mysql -u root -p sarwan -e "
INSERT IGNORE INTO user_permissions (user_id, permission_id)
SELECT u.id, p.id
FROM users u
CROSS JOIN permissions p
LEFT JOIN user_permissions up ON up.user_id = u.id AND up.permission_id = p.id
WHERE u.role = 'admin' AND up.id IS NULL;
"

# 4. Перезапустить приложение
gunicorn -w 4 -b 127.0.0.1:5000 app:app
```

---

## Важные замечания

- Шаги **"Загрузить разрешения" → "Выдать администраторам"** всегда выполнять **до** обновления кода — иначе администраторы потеряют доступ в момент деплоя.
- `seed_permissions.py` идемпотентен — безопасно запускать повторно.
- Остальным пользователям (не admin) разрешения выдаются вручную через API: `POST /api/admin/users/<id>/permissions`.
- Роль пользователя (`role` в таблице `users`) по-прежнему нужна — она влияет на бизнес-логику внутри роутов (например, курьер видит только свои заказы).
