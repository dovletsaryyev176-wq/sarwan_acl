import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from db import Db

# Клиентские токены подписываются ключом, выведенным из SECRET_KEY.
#
# Зачем: before_request в app.py декодирует любой Bearer-токен ключом
# SECRET_KEY и пишет session['user_id']. Так как clients.id и users.id —
# независимые автоинкременты, клиентский токен с таким claim превратил бы
# клиента в сотрудника с тем же id. При отдельном ключе jwt.decode в
# before_request падает с ошибкой подписи и уходит в except: pass —
# существующий код клиентских токенов просто не видит.
_KEY_LABEL = b'sarwan-client-app'

TYP_ACCESS = 'client_access'
TYP_PENDING = 'client_pending'

ACCESS_TOKEN_TTL = timedelta(hours=24)
PENDING_TOKEN_TTL = timedelta(minutes=10)
REFRESH_TOKEN_TTL = timedelta(days=180)


def _client_key():
    base = current_app.config['SECRET_KEY']
    if isinstance(base, str):
        base = base.encode()
    return hmac.new(base, _KEY_LABEL, hashlib.sha256).hexdigest()


def digest(value):
    """HMAC-SHA256 от значения ключом приложения — для кодов и refresh-токенов."""
    return hmac.new(_client_key().encode(), str(value).encode(), hashlib.sha256).hexdigest()


# -------------------------------------------------------------
# Access-токен
# -------------------------------------------------------------
def issue_access_token(client_id):
    now = datetime.now(timezone.utc)
    payload = {
        'client_id': client_id,
        'typ': TYP_ACCESS,
        'iat': now,
        'exp': now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, _client_key(), algorithm='HS256')


# -------------------------------------------------------------
# Промежуточный токен: номер подтверждён, но аккаунт ещё не определён
# (выбор из нескольких карточек либо регистрация)
# -------------------------------------------------------------
def issue_pending_token(phone):
    now = datetime.now(timezone.utc)
    payload = {
        'phone': phone,
        'typ': TYP_PENDING,
        'iat': now,
        'exp': now + PENDING_TOKEN_TTL,
    }
    return jwt.encode(payload, _client_key(), algorithm='HS256')


def decode_token(token, expected_typ):
    try:
        payload = jwt.decode(token, _client_key(), algorithms=['HS256'])
    except Exception:
        return None
    if payload.get('typ') != expected_typ:
        return None
    return payload


# -------------------------------------------------------------
# Refresh-токен: непрозрачная случайная строка, в базе только хеш
# -------------------------------------------------------------
def issue_refresh_token(cursor, client_id, device_info=None):
    token = secrets.token_urlsafe(32)
    device = str(device_info)[:255] if device_info else None
    cursor.execute(
        """
        INSERT INTO client_refresh_tokens (client_id, token_hash, device_info, expires_at)
        VALUES (%s, %s, %s, %s)
        """,
        (client_id, digest(token), device, datetime.now() + REFRESH_TOKEN_TTL),
    )
    return token


def revoke_refresh_token(cursor, token):
    cursor.execute(
        """
        UPDATE client_refresh_tokens
        SET revoked_at = NOW()
        WHERE token_hash = %s AND revoked_at IS NULL
        """,
        (digest(token),),
    )
    return cursor.rowcount


def revoke_all_refresh_tokens(cursor, client_id):
    cursor.execute(
        """
        UPDATE client_refresh_tokens
        SET revoked_at = NOW()
        WHERE client_id = %s AND revoked_at IS NULL
        """,
        (client_id,),
    )
    return cursor.rowcount


def issue_token_pair(cursor, client_id, device_info=None):
    return {
        'access_token': issue_access_token(client_id),
        'refresh_token': issue_refresh_token(cursor, client_id, device_info),
        'token_type': 'Bearer',
        'expires_in': int(ACCESS_TOKEN_TTL.total_seconds()),
    }


# -------------------------------------------------------------
# Декоратор авторизации клиента
#
# Полностью независим от acl.permission_required и session:
# клиенты не являются записями в users, прав в user_permissions у них нет.
# -------------------------------------------------------------
def client_auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization') or ''
        if not auth_header.startswith('Bearer '):
            return jsonify({'authenticated': False, 'error': 'Необходима авторизация'}), 401

        payload = decode_token(auth_header.split(' ', 1)[1].strip(), TYP_ACCESS)
        if not payload:
            return jsonify({'authenticated': False, 'error': 'Токен недействителен или истёк'}), 401

        client_id = payload.get('client_id')
        if not client_id:
            return jsonify({'authenticated': False, 'error': 'Токен недействителен'}), 401

        conn = Db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id, is_active FROM clients WHERE id = %s', (client_id,))
                client = cursor.fetchone()
        finally:
            conn.close()

        if not client:
            return jsonify({'authenticated': False, 'error': 'Аккаунт не найден'}), 401
        if not client['is_active']:
            return jsonify({'error': 'Аккаунт заблокирован. Обратитесь в колл-центр'}), 403

        g.client_id = client_id
        return f(*args, **kwargs)

    return wrapper
