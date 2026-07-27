import json
import logging
import time

from db import Db

from . import config

logger = logging.getLogger('audit')

# Имена сотрудников кешируются: таблица users маленькая, а лишний SELECT
# на каждом изменяющем запросе удваивал бы стоимость аудита.
_user_cache = {}
_user_cache_at = 0.0


def _refresh_user_cache():
    global _user_cache, _user_cache_at
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, full_name, role FROM users')
            _user_cache = {r['id']: (r['full_name'], r['role']) for r in cursor.fetchall()}
        _user_cache_at = time.time()
    finally:
        conn.close()


def user_info(user_id):
    """(имя, роль) сотрудника или (None, None). Никогда не бросает исключение."""
    if not user_id:
        return None, None
    try:
        if time.time() - _user_cache_at > config.USER_CACHE_TTL or user_id not in _user_cache:
            _refresh_user_cache()
        return _user_cache.get(user_id, (None, None))
    except Exception:
        return None, None


def mask_body(raw_text):
    """
    Заменяет значения секретных полей на ***. Работает рекурсивно,
    включая вложенные объекты и списки.

    Если тело не разбирается как JSON — возвращается как есть, обрезанное.
    """
    if not raw_text:
        return None

    if not config.MASK_FIELDS:
        return raw_text[:config.MAX_BODY_CHARS]

    try:
        data = json.loads(raw_text)
    except Exception:
        return raw_text[:config.MAX_BODY_CHARS]

    def walk(node):
        if isinstance(node, dict):
            return {
                k: (config.MASK_VALUE if str(k).lower() in config.MASK_FIELDS else walk(v))
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    try:
        return json.dumps(walk(data), ensure_ascii=False)[:config.MAX_BODY_CHARS]
    except Exception:
        return raw_text[:config.MAX_BODY_CHARS]


def write(record):
    """
    Пишет запись отдельным соединением из пула.

    К моменту вызова роут уже вернул своё соединение, поэтому откат его
    транзакции на аудит не влияет — неудачные попытки фиксируются.

    Любая ошибка гасится: журнал не имеет права влиять на ответ клиенту.
    """
    if not config.DB_ENABLED:
        return

    conn = None
    try:
        conn = Db.get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO activity_log (
                    actor_type, user_id, client_id, actor_name, role,
                    method, path, endpoint, status_code, duration_ms,
                    ip, user_agent, content_type, request_body, error_text
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record['actor_type'], record['user_id'], record['client_id'],
                    record['actor_name'], record['role'],
                    record['method'], record['path'], record['endpoint'],
                    record['status_code'], record['duration_ms'],
                    record['ip'], record['user_agent'], record['content_type'],
                    record['request_body'], record['error_text'],
                ),
            )
        conn.commit()
    except Exception as e:
        logger.warning('activity_log write failed: %s', e)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
