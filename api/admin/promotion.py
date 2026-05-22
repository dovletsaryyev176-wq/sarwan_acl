from flask import jsonify, request
from . import admin_bp
from acl import permission_required
from db import Db
from all_types_description import PromotionTypes
import datetime


def parse_date(value):
    return datetime.datetime.strptime(value, '%Y-%m-%d').date() if value else None


def serialize_promotion(p, lang='ru'):
    p['fixed_price'] = float(p['fixed_price'])
    p['is_active'] = bool(p['is_active'])

    if p.get('start_date'):
        p['start_date'] = p['start_date'].isoformat()
    if p.get('end_date'):
        p['end_date'] = p['end_date'].isoformat()

    val = p.get('service_ids')
    p['service_ids'] = [int(x) for x in str(val).split(',')] if val else []

    labels = PromotionTypes.LABELS.get(p.get('promotion_type'), {})
    p['promotion_type_label'] = labels.get(lang) or labels.get('ru')

    return p


def validate_promotion_data(data, is_create=False):
    if is_create:
        if not data.get('name'):
            return "Поле 'name' обязательно"
        if not data.get('promotion_type'):
            return "Поле 'promotion_type' обязательно"
        if not data.get('start_date'):
            return "Поле 'start_date' обязательно"
        if not data.get('end_date'):
            return "Поле 'end_date' обязательно"
        if data.get('fixed_price') is None:
            return "Поле 'fixed_price' обязательно"
        if data.get('order_count') is None:
            return "Поле 'order_count' обязательно"

    promo_type = data.get('promotion_type')
    if promo_type and promo_type not in PromotionTypes.CHOICES:
        valid = ', '.join(PromotionTypes.CHOICES)
        return f"Недопустимый тип акции '{promo_type}'. Допустимые: {valid}"

    start = data.get('start_date')
    end = data.get('end_date')
    if start and end and end < start:
        return "'end_date' не может быть раньше 'start_date'"

    if 'fixed_price' in data and data['fixed_price'] is not None:
        try:
            if float(data['fixed_price']) < 0:
                return "'fixed_price' не может быть отрицательным"
        except (TypeError, ValueError):
            return "'fixed_price' должно быть числом"

    if 'order_count' in data and data['order_count'] is not None:
        try:
            if int(data['order_count']) <= 0:
                return "'order_count' должно быть больше 0"
        except (TypeError, ValueError):
            return "'order_count' должно быть целым числом"

    return None


@admin_bp.route('/promotions', methods=['GET'])
@permission_required('promotions.view')
def get_promotions():
    lang = request.args.get('lang', 'ru')
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.*,
                    GROUP_CONCAT(DISTINCT ps.service_id) AS service_ids
                FROM promotions p
                LEFT JOIN promotion_services ps ON p.id = ps.promotion_id
                GROUP BY p.id
                ORDER BY p.id DESC
            """)
            promotions = cursor.fetchall()
            result = [serialize_promotion(p, lang) for p in promotions]
        return jsonify(result), 200
    finally:
        conn.close()


@admin_bp.route('/promotions/<int:id>', methods=['GET'])
@permission_required('promotions.view')
def get_promotion(id):
    lang = request.args.get('lang', 'ru')
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.*,
                    GROUP_CONCAT(DISTINCT ps.service_id) AS service_ids
                FROM promotions p
                LEFT JOIN promotion_services ps ON p.id = ps.promotion_id
                WHERE p.id = %s
                GROUP BY p.id
            """, (id,))
            promotion = cursor.fetchone()
            if not promotion:
                return jsonify({'error': 'Акция не найдена'}), 404
        return jsonify(serialize_promotion(promotion, lang)), 200
    finally:
        conn.close()


@admin_bp.route('/promotions', methods=['POST'])
@permission_required('promotions.create')
def create_promotion():
    data = request.json

    error = validate_promotion_data(data, is_create=True)
    if error:
        return jsonify({'error': error}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO promotions (name, promotion_type, start_date, end_date, fixed_price, order_count, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                data['name'],
                data['promotion_type'],
                parse_date(data['start_date']),
                parse_date(data['end_date']),
                data['fixed_price'],
                data['order_count'],
                data.get('is_active', True),
            ))
            promotion_id = cursor.lastrowid

            if 'service_ids' in data and isinstance(data['service_ids'], list):
                for s_id in data['service_ids']:
                    cursor.execute(
                        "INSERT INTO promotion_services (promotion_id, service_id) VALUES (%s, %s)",
                        (promotion_id, s_id)
                    )

            conn.commit()
        return jsonify({'message': 'Акция создана', 'id': promotion_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()


@admin_bp.route('/promotions/<int:id>', methods=['PUT'])
@permission_required('promotions.update')
def update_promotion(id):
    data = request.json

    error = validate_promotion_data(data, is_create=False)
    if error:
        return jsonify({'error': error}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM promotions WHERE id = %s", (id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Акция не найдена'}), 404

            fields = []
            params = []

            for key in ('name', 'promotion_type', 'fixed_price', 'order_count', 'is_active'):
                if key in data:
                    fields.append(f"{key} = %s")
                    params.append(data[key])

            for field in ('start_date', 'end_date'):
                if field in data:
                    fields.append(f"{field} = %s")
                    params.append(parse_date(data[field]))

            if fields:
                params.append(id)
                cursor.execute(
                    f"UPDATE promotions SET {', '.join(fields)} WHERE id = %s",
                    tuple(params)
                )

            if 'service_ids' in data and isinstance(data['service_ids'], list):
                cursor.execute("DELETE FROM promotion_services WHERE promotion_id = %s", (id,))
                for s_id in data['service_ids']:
                    cursor.execute(
                        "INSERT INTO promotion_services (promotion_id, service_id) VALUES (%s, %s)",
                        (id, s_id)
                    )

            conn.commit()
        return jsonify({'message': 'Акция обновлена'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()


@admin_bp.route('/promotions/<int:id>/toggle', methods=['PATCH'])
@permission_required('promotions.toggle')
def toggle_promotion(id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, is_active FROM promotions WHERE id = %s", (id,))
            promotion = cursor.fetchone()
            if not promotion:
                return jsonify({'error': 'Акция не найдена'}), 404

            new_state = not bool(promotion['is_active'])
            cursor.execute("UPDATE promotions SET is_active = %s WHERE id = %s", (new_state, id))
            conn.commit()

        action = 'разблокирована' if new_state else 'заблокирована'
        return jsonify({'message': f'Акция {action}', 'is_active': new_state}), 200
    finally:
        conn.close()
