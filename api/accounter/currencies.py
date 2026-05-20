from flask import jsonify, request
from acl import permission_required
from . import accounter_bp
from db import Db


@accounter_bp.route('/currencies', methods=['GET'])
@permission_required('currencies.view')
def get_currencies():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name_ru, name_tk, is_active FROM currencies")
            currencies = cursor.fetchall()
        return jsonify(currencies), 200
    finally:
        conn.close()


@accounter_bp.route('/currencies', methods=['POST'])
@permission_required('currencies.create')
def create_currency():
    data = request.get_json()
    name_ru = data.get('name_ru')
    name_tk = data.get('name_tk')
    if not name_ru or not name_tk:
        return jsonify({"error": "Названия на русском и туркменском обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO currencies (name_ru, name_tk) VALUES (%s, %s)",
                (name_ru, name_tk)
            )
            conn.commit()
            currency_id = cursor.lastrowid
            cursor.execute(
                "SELECT id, name_ru, name_tk, is_active FROM currencies WHERE id = %s",
                (currency_id,)
            )
            currency = cursor.fetchone()
        return jsonify(currency), 201
    finally:
        conn.close()


@accounter_bp.route('/currencies/<int:currency_id>', methods=['PUT'])
@permission_required('currencies.update')
def update_currency(currency_id):
    data = request.get_json()
    name_ru = data.get('name_ru')
    name_tk = data.get('name_tk')
    if not name_ru or not name_tk:
        return jsonify({"error": "Названия на русском и туркменском обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM currencies WHERE id = %s", (currency_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Валюта не найдена"}), 404

            cursor.execute(
                "UPDATE currencies SET name_ru = %s, name_tk = %s WHERE id = %s",
                (name_ru, name_tk, currency_id)
            )
            conn.commit()

            cursor.execute(
                "SELECT id, name_ru, name_tk, is_active FROM currencies WHERE id = %s",
                (currency_id,)
            )
            currency = cursor.fetchone()
        return jsonify(currency), 200
    finally:
        conn.close()


@accounter_bp.route('/currencies/<int:currency_id>/block', methods=['PATCH'])
@permission_required('currencies.block')
def block_currency(currency_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM currencies WHERE id = %s", (currency_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Валюта не найдена"}), 404

            cursor.execute(
                "UPDATE currencies SET is_active = FALSE WHERE id = %s",
                (currency_id,)
            )
            conn.commit()

            cursor.execute(
                "SELECT id, name_ru, name_tk, is_active FROM currencies WHERE id = %s",
                (currency_id,)
            )
            currency = cursor.fetchone()
        return jsonify(currency), 200
    finally:
        conn.close()


@accounter_bp.route('/currencies/<int:currency_id>/unblock', methods=['PATCH'])
@permission_required('currencies.unblock')
def unblock_currency(currency_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM currencies WHERE id = %s", (currency_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Валюта не найдена"}), 404

            cursor.execute(
                "UPDATE currencies SET is_active = TRUE WHERE id = %s",
                (currency_id,)
            )
            conn.commit()

            cursor.execute(
                "SELECT id, name_ru, name_tk, is_active FROM currencies WHERE id = %s",
                (currency_id,)
            )
            currency = cursor.fetchone()
        return jsonify(currency), 200
    finally:
        conn.close()
