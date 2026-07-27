import logging
import os
import secrets
from datetime import datetime, timedelta

import requests

from .security import digest
from .utils import to_storage_format

logger = logging.getLogger('client_app.otp')

# Параметры одноразовых кодов
OTP_LENGTH = 4
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_PER_HOUR = 5

SMS_GATEWAY_URL = 'https://tagma.biz/otp/send-code'
SMS_TEMPLATE_KEY = 'client_otp'
SMS_FALLBACK_TEXT = 'Sarwan: tassyklayys kody {code}'
SMS_TIMEOUT_SECONDS = 10


def _dev_mode():
    """
    Режим локальной разработки: SMS не отправляется, код печатается в консоль.

    Нужен потому, что код хранится в виде HMAC и восстановить его из базы
    нельзя. Без этого режима разработчик мобильного приложения либо шлёт
    настоящие SMS на настоящие номера, либо не может войти вообще.

    Включается CLIENT_OTP_DEV_MODE=1 в .env.

    Защита от случайного включения на боевом сервере: при FLASK_ENV=production
    режим принудительно выключен, что бы ни стояло во флаге. В .env продакшена
    FLASK_ENV=production уже прописан.
    """
    if os.getenv('FLASK_ENV', '').strip().lower() == 'production':
        return False
    return os.getenv('CLIENT_OTP_DEV_MODE', '').strip().lower() in ('1', 'true', 'yes', 'on')


class SmsError(Exception):
    """Шлюз не принял сообщение — код клиенту не дошёл."""


def generate_code():
    return ''.join(str(secrets.randbelow(10)) for _ in range(OTP_LENGTH))


def check_rate_limits(cursor, phone):
    """
    Возвращает None, если отправка разрешена, иначе (сообщение, retry_after).
    """
    cursor.execute(
        """
        SELECT created_at FROM client_otp_codes
        WHERE phone = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (phone,),
    )
    last = cursor.fetchone()
    if last:
        elapsed = (datetime.now() - last['created_at']).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            retry_after = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            return 'Повторная отправка возможна через {} сек.'.format(retry_after), retry_after

    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM client_otp_codes
        WHERE phone = %s AND created_at > %s
        """,
        (phone, datetime.now() - timedelta(hours=1)),
    )
    if cursor.fetchone()['cnt'] >= OTP_MAX_PER_HOUR:
        return 'Слишком много запросов кода. Попробуйте через час', 3600

    return None


def send_sms_code(cursor, phone, code):
    """
    Отправляет код через тот же шлюз, что и остальные SMS в системе.

    В sms_history не пишем: там sender_id NOT NULL с внешним ключом на users,
    а у клиента записи в users нет.
    """
    cursor.execute("SELECT `text` FROM sms_templates WHERE `key` = %s", (SMS_TEMPLATE_KEY,))
    row = cursor.fetchone()
    template = row['text'] if row and row['text'] else SMS_FALLBACK_TEXT

    text = template.replace('{code}', code)
    if code not in text:
        text = '{} {}'.format(text, code)

    if _dev_mode():
        logger.warning(
            '\n%s\n  РЕЖИМ РАЗРАБОТКИ: SMS НЕ ОТПРАВЛЕНА\n'
            '  телефон: %s\n  код:     %s\n%s',
            '=' * 60, to_storage_format(phone), code, '=' * 60,
        )
        return

    try:
        response = requests.post(
            SMS_GATEWAY_URL,
            json={'code': text, 'phoneNumber': to_storage_format(phone)},
            timeout=SMS_TIMEOUT_SECONDS,
        )
    except Exception as e:
        raise SmsError('SMS-шлюз недоступен') from e

    if response.status_code >= 400:
        raise SmsError('SMS-шлюз вернул ошибку {}'.format(response.status_code))


def store_code(cursor, phone, code, ip=None):
    """Гасит предыдущие коды номера и сохраняет новый."""
    cursor.execute(
        "UPDATE client_otp_codes SET is_used = TRUE WHERE phone = %s AND is_used = FALSE",
        (phone,),
    )
    cursor.execute(
        """
        INSERT INTO client_otp_codes (phone, code_hash, expires_at, ip)
        VALUES (%s, %s, %s, %s)
        """,
        (phone, digest('{}:{}'.format(phone, code)), datetime.now() + timedelta(seconds=OTP_TTL_SECONDS), ip),
    )


def verify_code(cursor, phone, code):
    """
    Проверяет код. Возвращает (ok, error_message).
    При неверном коде увеличивает счётчик попыток.
    """
    cursor.execute(
        """
        SELECT id, code_hash, attempts, expires_at
        FROM client_otp_codes
        WHERE phone = %s AND is_used = FALSE
        ORDER BY id DESC
        LIMIT 1
        """,
        (phone,),
    )
    row = cursor.fetchone()

    if not row:
        return False, 'Код не запрашивался или уже использован'

    if row['expires_at'] < datetime.now():
        return False, 'Срок действия кода истёк. Запросите новый'

    if row['attempts'] >= OTP_MAX_ATTEMPTS:
        cursor.execute("UPDATE client_otp_codes SET is_used = TRUE WHERE id = %s", (row['id'],))
        return False, 'Исчерпаны попытки ввода. Запросите новый код'

    if not secrets.compare_digest(row['code_hash'], digest('{}:{}'.format(phone, code))):
        cursor.execute(
            "UPDATE client_otp_codes SET attempts = attempts + 1 WHERE id = %s",
            (row['id'],),
        )
        left = OTP_MAX_ATTEMPTS - (row['attempts'] + 1)
        if left <= 0:
            return False, 'Исчерпаны попытки ввода. Запросите новый код'
        return False, 'Неверный код. Осталось попыток: {}'.format(left)

    cursor.execute("UPDATE client_otp_codes SET is_used = TRUE WHERE id = %s", (row['id'],))
    return True, None
