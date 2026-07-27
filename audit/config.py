"""
Настройки журнала действий.

Папка называется audit, а не logging, намеренно: корень проекта лежит в sys.path,
и пакет с именем logging перекрыл бы стандартный модуль Python, который импортируют
Flask, waitress и pymysql.
"""
import os


def _flag(name, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


# Аварийный выключатель. AUDIT_ENABLED=0 в .env + перезапуск службы —
# приложение работает ровно как до внедрения, без правки кода.
ENABLED = _flag('AUDIT_ENABLED', True)

# Писать ли записи в БД. При False аудит только пишет в journald.
DB_ENABLED = _flag('AUDIT_DB_ENABLED', True)

LOG_LEVEL = os.getenv('AUDIT_LOG_LEVEL', 'INFO').upper()

# Логируем только изменяющие запросы: GET дал бы в 10-20 раз больше строк
# в основном за счёт мониторинга заказов, который опрашивается постоянно.
AUDITED_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

# Пути, которые не журналируются вообще
SKIP_PATH_PREFIXES = ('/uploads',)

MAX_PATH_CHARS = 255
MAX_BODY_CHARS = 65535
MAX_ERROR_CHARS = 4000
MAX_UA_CHARS = 255

# Срок хранения. Чистку выполняет MySQL EVENT из schema.sql.
RETENTION_DAYS = 30

# Поля, значения которых заменяются на MASK_VALUE.
#
# Тела запросов пишутся целиком, но эти четыре поля — исключение: через них идут
# пароли сотрудников, коды из SMS и токены клиентов. Без маскировки таблица
# аудита превратилась бы в список действующих паролей, который уезжает в каждый
# дамп базы. Чтобы писать буквально всё — очистите этот набор.
MASK_FIELDS = {
    'password',
    'new_password',
    'old_password',
    'password_hash',
    'code',
    'token',
    'access_token',
    'refresh_token',
    'pending_token',
}
MASK_VALUE = '***'

# Как часто перечитывать имена сотрудников для колонки actor_name, секунд
USER_CACHE_TTL = 300
