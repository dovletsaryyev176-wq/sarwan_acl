from flask import jsonify, request
from acl import permission_required
from . import admin_bp
from db import Db


@admin_bp.route('/rate', methods=['GET'])
@permission_required('rate.view')
def get_rate():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, `key`, `value` FROM settings WHERE `key` = 'rate'")
            row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Настройка не найдена"}), 404
        row['value'] = float(row['value'])
        return jsonify(row), 200
    finally:
        conn.close()


@admin_bp.route('/rate', methods=['PUT'])
@permission_required('rate.update')
def update_rate():
    data = request.get_json()
    value = data.get('value')

    if value is None:
        return jsonify({"error": "value обязателен"}), 400

    try:
        value = float(value)
    except (TypeError, ValueError):
        return jsonify({"error": "value должен быть числом"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE settings SET `value` = %s WHERE `key` = 'rate'",
                (str(value),)
            )
            conn.commit()

            cursor.execute("SELECT id, `key`, `value` FROM settings WHERE `key` = 'rate'")
            row = cursor.fetchone()
        row['value'] = float(row['value'])
        return jsonify(row), 200
    finally:
        conn.close()
