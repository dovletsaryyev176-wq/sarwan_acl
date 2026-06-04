from flask import jsonify, request
from acl import permission_required
from . import admin_bp
from db import Db


@admin_bp.route('/cashback', methods=['GET'])
@permission_required('cashback.view')
def get_cashbacks():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sc.id, sc.service_id, s.name as service_name, sc.cashback
                FROM service_cashback sc
                LEFT JOIN services s ON sc.service_id = s.id
            """)
            rows = cursor.fetchall()
        for row in rows:
            row['cashback'] = float(row['cashback'])
        return jsonify(rows), 200
    finally:
        conn.close()


@admin_bp.route('/cashback/<int:cashback_id>', methods=['GET'])
@permission_required('cashback.view')
def get_cashback(cashback_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sc.id, sc.service_id, s.name as service_name, sc.cashback
                FROM service_cashback sc
                LEFT JOIN services s ON sc.service_id = s.id
                WHERE sc.id = %s
            """, (cashback_id,))
            row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Запись не найдена"}), 404
        row['cashback'] = float(row['cashback'])
        return jsonify(row), 200
    finally:
        conn.close()


@admin_bp.route('/cashback', methods=['POST'])
@permission_required('cashback.create')
def create_cashback():
    data = request.get_json()
    service_id = data.get('service_id')
    cashback = data.get('cashback')

    if service_id is None or cashback is None:
        return jsonify({"error": "service_id и cashback обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM services WHERE id = %s", (service_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Услуга не найдена"}), 404

            cursor.execute(
                "INSERT INTO service_cashback (service_id, cashback) VALUES (%s, %s)",
                (service_id, cashback)
            )
            conn.commit()
            cashback_id = cursor.lastrowid

            cursor.execute("""
                SELECT sc.id, sc.service_id, s.name as service_name, sc.cashback
                FROM service_cashback sc
                LEFT JOIN services s ON sc.service_id = s.id
                WHERE sc.id = %s
            """, (cashback_id,))
            row = cursor.fetchone()
        row['cashback'] = float(row['cashback'])
        return jsonify(row), 201
    finally:
        conn.close()


@admin_bp.route('/cashback/<int:cashback_id>', methods=['PUT'])
@permission_required('cashback.update')
def update_cashback(cashback_id):
    data = request.get_json()
    service_id = data.get('service_id')
    cashback = data.get('cashback')

    if service_id is None or cashback is None:
        return jsonify({"error": "service_id и cashback обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM service_cashback WHERE id = %s", (cashback_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Запись не найдена"}), 404

            cursor.execute("SELECT id FROM services WHERE id = %s", (service_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Услуга не найдена"}), 404

            cursor.execute(
                "UPDATE service_cashback SET service_id = %s, cashback = %s WHERE id = %s",
                (service_id, cashback, cashback_id)
            )
            conn.commit()

            cursor.execute("""
                SELECT sc.id, sc.service_id, s.name as service_name, sc.cashback
                FROM service_cashback sc
                LEFT JOIN services s ON sc.service_id = s.id
                WHERE sc.id = %s
            """, (cashback_id,))
            row = cursor.fetchone()
        row['cashback'] = float(row['cashback'])
        return jsonify(row), 200
    finally:
        conn.close()


@admin_bp.route('/cashback/<int:cashback_id>', methods=['DELETE'])
@permission_required('cashback.delete')
def delete_cashback(cashback_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM service_cashback WHERE id = %s", (cashback_id,))
            if cursor.rowcount == 0:
                return jsonify({"error": "Запись не найдена"}), 404
            conn.commit()
        return jsonify({"message": "Запись удалена"}), 200
    finally:
        conn.close()
