from datetime import datetime

from flask import g, jsonify, request

from db import Db

from . import client_bp
from .otp import (
    OTP_RESEND_COOLDOWN_SECONDS,
    OTP_TTL_SECONDS,
    SmsError,
    check_rate_limits,
    generate_code,
    send_sms_code,
    store_code,
    verify_code,
)
from .security import (
    TYP_PENDING,
    client_auth_required,
    decode_token,
    digest,
    issue_pending_token,
    issue_token_pair,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
)
from .utils import PHONE_MATCH_SQL, normalize_phone, to_storage_format

# Тип цены для клиентов, зарегистрировавшихся через приложение.
# 1 = Rayat (физлица), под ним 8016 из 8067 существующих клиентов.
DEFAULT_PRICE_TYPE_ID = 1


# -------------------------------------------------------------
# Вспомогательные функции
# -------------------------------------------------------------
def _find_clients_by_phone(cursor, phone):
    """Все карточки клиентов, к которым привязан этот номер."""
    cursor.execute(
        """
        SELECT DISTINCT c.id, c.full_name, c.is_active
        FROM client_phones cp
        JOIN clients c ON c.id = cp.client_id
        WHERE {match} = %s
        ORDER BY c.id
        """.format(match=PHONE_MATCH_SQL.format(col='cp.phone')),
        (phone,),
    )
    return cursor.fetchall()


def _client_public(cursor, client_id):
    cursor.execute(
        """
        SELECT c.id, c.full_name, c.is_active, c.created_at,
               c.price_type_id, pt.name AS price_type_name,
               p.city_id, p.language, ct.name AS city_name
        FROM clients c
        LEFT JOIN price_types pt ON pt.id = c.price_type_id
        LEFT JOIN client_app_profiles p ON p.client_id = c.id
        LEFT JOIN cities ct ON ct.id = p.city_id
        WHERE c.id = %s
        """,
        (client_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'id': row['id'],
        'full_name': row['full_name'],
        'is_active': bool(row['is_active']),
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
        'price_type_id': row['price_type_id'],
        'price_type_name': row['price_type_name'],
        'city_id': row['city_id'],
        'city_name': row['city_name'],
        'language': row['language'],
    }


def _accounts_for_selection(cursor, clients):
    """
    Данные для экрана выбора аккаунта.

    У 42% клиентов full_name — это '.', '-' или пробел, поэтому одного имени
    для опознания мало: отдаём ещё адрес, число заказов и дату последнего.
    """
    ids = [c['id'] for c in clients]
    fmt = ','.join(['%s'] * len(ids))

    cursor.execute(
        """
        SELECT client_id, COUNT(*) AS orders_count, MAX(created_at) AS last_order_at
        FROM orders WHERE client_id IN ({fmt}) GROUP BY client_id
        """.format(fmt=fmt),
        tuple(ids),
    )
    orders_map = {r['client_id']: r for r in cursor.fetchall()}

    cursor.execute(
        """
        SELECT ca.client_id, ca.address_line, ca.appartment,
               ct.name AS city_name, d.name AS district_name, s.name AS street_name
        FROM client_addresses ca
        LEFT JOIN cities ct ON ct.id = ca.city_id
        LEFT JOIN districts d ON d.id = ca.district_id
        LEFT JOIN streets s ON s.id = ca.street_id
        WHERE ca.client_id IN ({fmt}) AND ca.is_active = TRUE
        ORDER BY ca.id
        """.format(fmt=fmt),
        tuple(ids),
    )
    address_map = {}
    for r in cursor.fetchall():
        if r['client_id'] in address_map:
            continue
        parts = [r['city_name'], r['district_name'], r['street_name'], r['address_line'], r['appartment']]
        address_map[r['client_id']] = ', '.join(p.strip() for p in parts if p and p.strip())

    accounts = []
    for c in clients:
        stats = orders_map.get(c['id'])
        accounts.append({
            'id': c['id'],
            'full_name': c['full_name'],
            'address': address_map.get(c['id']),
            'orders_count': stats['orders_count'] if stats else 0,
            'last_order_at': stats['last_order_at'].isoformat() if stats and stats['last_order_at'] else None,
        })
    return accounts


def _pending_phone(data):
    """Достаёт подтверждённый номер из промежуточного токена."""
    token = (data.get('pending_token') or '').strip()
    if not token:
        return None
    payload = decode_token(token, TYP_PENDING)
    return payload.get('phone') if payload else None


# -------------------------------------------------------------
# Запрос кода
# -------------------------------------------------------------
@client_bp.route('/auth/otp/send', methods=['POST'])
def otp_send():
    data = request.get_json(silent=True) or {}
    phone = normalize_phone(data.get('phone'))

    if not phone:
        return jsonify({'error': 'Неверный формат номера. Введите 8 цифр'}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            limited = check_rate_limits(cursor, phone)
            if limited:
                message, retry_after = limited
                return jsonify({'error': message, 'retry_after': retry_after}), 429

            code = generate_code()

            # Сначала отправка: если шлюз недоступен, лимит не расходуется
            try:
                send_sms_code(cursor, phone, code)
            except SmsError as e:
                return jsonify({'error': 'Не удалось отправить SMS. Попробуйте позже', 'detail': str(e)}), 502

            store_code(cursor, phone, code, request.remote_addr)
            conn.commit()

        return jsonify({
            'status': 'sent',
            'expires_in': OTP_TTL_SECONDS,
            'resend_after': OTP_RESEND_COOLDOWN_SECONDS,
        }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------------
# Проверка кода
#
# Три исхода:
#   authenticated         — номер принадлежит одному клиенту
#   select_account        — номер привязан к нескольким карточкам
#   registration_required — номера нет в базе
# -------------------------------------------------------------
@client_bp.route('/auth/otp/verify', methods=['POST'])
def otp_verify():
    data = request.get_json(silent=True) or {}
    phone = normalize_phone(data.get('phone'))
    code = str(data.get('code') or '').strip()

    if not phone:
        return jsonify({'error': 'Неверный формат номера. Введите 8 цифр'}), 400
    if not code:
        return jsonify({'error': 'Введите код из SMS'}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            ok, error = verify_code(cursor, phone, code)
            # Коммитим в любом случае: счётчик попыток должен сохраниться
            conn.commit()
            if not ok:
                return jsonify({'error': error}), 400

            clients = _find_clients_by_phone(cursor, phone)
            active = [c for c in clients if c['is_active']]

            if clients and not active:
                return jsonify({'error': 'Аккаунт заблокирован. Обратитесь в колл-центр'}), 403

            if not clients:
                return jsonify({
                    'status': 'registration_required',
                    'pending_token': issue_pending_token(phone),
                }), 200

            if len(active) > 1:
                return jsonify({
                    'status': 'select_account',
                    'pending_token': issue_pending_token(phone),
                    'accounts': _accounts_for_selection(cursor, active),
                }), 200

            client_id = active[0]['id']
            tokens = issue_token_pair(cursor, client_id, data.get('device_info'))
            client = _client_public(cursor, client_id)
            conn.commit()

        return jsonify(dict(tokens, status='authenticated', client=client)), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------------
# Выбор аккаунта, если номер привязан к нескольким карточкам
# -------------------------------------------------------------
@client_bp.route('/auth/select-account', methods=['POST'])
def select_account():
    data = request.get_json(silent=True) or {}
    phone = _pending_phone(data)
    client_id = data.get('client_id')

    if not phone:
        return jsonify({'error': 'Сессия подтверждения истекла. Запросите код заново'}), 401
    if not client_id:
        return jsonify({'error': 'Не указан client_id'}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            clients = _find_clients_by_phone(cursor, phone)
            chosen = next((c for c in clients if c['id'] == client_id), None)

            if not chosen:
                return jsonify({'error': 'Этот аккаунт не привязан к вашему номеру'}), 403
            if not chosen['is_active']:
                return jsonify({'error': 'Аккаунт заблокирован. Обратитесь в колл-центр'}), 403

            tokens = issue_token_pair(cursor, client_id, data.get('device_info'))
            client = _client_public(cursor, client_id)
            conn.commit()

        return jsonify(dict(tokens, status='authenticated', client=client)), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------------
# Регистрация нового клиента
# -------------------------------------------------------------
@client_bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    phone = _pending_phone(data)
    full_name = str(data.get('full_name') or '').strip()
    city_id = data.get('city_id')

    if not phone:
        return jsonify({'error': 'Сессия подтверждения истекла. Запросите код заново'}), 401
    if not full_name:
        return jsonify({'error': 'Укажите имя'}), 400
    if not city_id:
        return jsonify({'error': 'Выберите город'}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id FROM cities WHERE id = %s AND is_active = TRUE', (city_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Город не найден'}), 404

            # Повторная проверка: номер мог быть занят между verify и register
            if _find_clients_by_phone(cursor, phone):
                return jsonify({'error': 'Этот номер уже зарегистрирован. Запросите код заново'}), 409

            cursor.execute(
                'INSERT INTO clients (full_name, price_type_id) VALUES (%s, %s)',
                (full_name, DEFAULT_PRICE_TYPE_ID),
            )
            client_id = cursor.lastrowid

            cursor.execute(
                'INSERT INTO client_phones (client_id, phone) VALUES (%s, %s)',
                (client_id, to_storage_format(phone)),
            )

            # Локация нужна для учёта тары — так же делает админский create_client
            cursor.execute(
                'INSERT INTO locations (name, type, client_id) VALUES (%s, %s, %s)',
                (full_name, 'client', client_id),
            )

            cursor.execute(
                'INSERT INTO client_app_profiles (client_id, city_id) VALUES (%s, %s)',
                (client_id, city_id),
            )

            tokens = issue_token_pair(cursor, client_id, data.get('device_info'))
            client = _client_public(cursor, client_id)
            conn.commit()

        return jsonify(dict(tokens, status='authenticated', client=client)), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------------
# Обновление пары токенов (с ротацией refresh)
# -------------------------------------------------------------
@client_bp.route('/auth/refresh', methods=['POST'])
def refresh():
    data = request.get_json(silent=True) or {}
    token = str(data.get('refresh_token') or '').strip()

    if not token:
        return jsonify({'error': 'Не передан refresh_token'}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT rt.id, rt.client_id, rt.expires_at, rt.revoked_at, c.is_active
                FROM client_refresh_tokens rt
                JOIN clients c ON c.id = rt.client_id
                WHERE rt.token_hash = %s
                """,
                (digest(token),),
            )
            row = cursor.fetchone()

            if not row or row['revoked_at'] is not None:
                return jsonify({'error': 'Сессия недействительна. Войдите заново'}), 401

            if row['expires_at'] < datetime.now():
                return jsonify({'error': 'Сессия истекла. Войдите заново'}), 401

            if not row['is_active']:
                return jsonify({'error': 'Аккаунт заблокирован. Обратитесь в колл-центр'}), 403

            cursor.execute(
                'UPDATE client_refresh_tokens SET revoked_at = NOW(), last_used_at = NOW() WHERE id = %s',
                (row['id'],),
            )
            tokens = issue_token_pair(cursor, row['client_id'], data.get('device_info'))
            conn.commit()

        return jsonify(tokens), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------------
# Выход
# -------------------------------------------------------------
@client_bp.route('/auth/logout', methods=['POST'])
@client_auth_required
def logout():
    data = request.get_json(silent=True) or {}
    token = str(data.get('refresh_token') or '').strip()
    all_devices = bool(data.get('all_devices'))

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            if token and not all_devices:
                revoke_refresh_token(cursor, token)
            else:
                revoke_all_refresh_tokens(cursor, g.client_id)
            conn.commit()

        return jsonify({'status': 'success', 'message': 'Вы вышли из аккаунта'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# -------------------------------------------------------------
# Текущий профиль
# -------------------------------------------------------------
@client_bp.route('/auth/me', methods=['GET'])
@client_auth_required
def me():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            client = _client_public(cursor, g.client_id)
            if not client:
                return jsonify({'authenticated': False}), 401

            cursor.execute(
                'SELECT id, phone FROM client_phones WHERE client_id = %s',
                (g.client_id,),
            )
            phones = [{'id': r['id'], 'phone': r['phone']} for r in cursor.fetchall()]

            cursor.execute(
                """
                SELECT ca.id, ca.city_id, ca.district_id, ca.street_id, ca.address_line,
                       ca.appartment, ca.entrance, ca.floor,
                       ct.name AS city_name, d.name AS district_name, s.name AS street_name
                FROM client_addresses ca
                LEFT JOIN cities ct ON ct.id = ca.city_id
                LEFT JOIN districts d ON d.id = ca.district_id
                LEFT JOIN streets s ON s.id = ca.street_id
                WHERE ca.client_id = %s AND ca.is_active = TRUE
                ORDER BY ca.id
                """,
                (g.client_id,),
            )
            addresses = cursor.fetchall()

        return jsonify({
            'authenticated': True,
            'client': client,
            'phones': phones,
            'addresses': addresses,
        }), 200
    finally:
        conn.close()
