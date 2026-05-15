from flask import jsonify, request
from . import admin_bp
from acl import permission_required
from db import Db


@admin_bp.route('/transports', methods=['GET'])
@permission_required('transports.view')
def get_transports():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, number, capacity, is_active FROM transports")
            transports = cursor.fetchall()
        return jsonify(transports), 200
    finally:
        conn.close()


@admin_bp.route('/transports', methods=['POST'])
@permission_required('transports.create')
def create_transport():
    data = request.get_json()
    number = data.get('number')
    capacity = data.get('capacity')

    if not number or not capacity:
        return jsonify({"error": "Номер и вместимость обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transports (number, capacity) VALUES (%s, %s)",
                (number, int(capacity))
            )
            conn.commit()
            cursor.execute(
                "SELECT id, number, capacity, is_active FROM transports WHERE id=%s",
                (cursor.lastrowid,)
            )
            new_t = cursor.fetchone()
        return jsonify(new_t), 201
    finally:
        conn.close()


@admin_bp.route('/transports/<int:t_id>', methods=['PUT'])
@permission_required('transports.update')
def update_transport(t_id):
    data = request.get_json()
    number = data.get('number')
    capacity = data.get('capacity')

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM transports WHERE id=%s", (t_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Транспорт не найден"}), 404

            cursor.execute(
                "UPDATE transports SET number=%s, capacity=COALESCE(%s, capacity) WHERE id=%s",
                (number, int(capacity) if capacity else None, t_id)
            )
            conn.commit()

            cursor.execute("SELECT id, number, capacity, is_active FROM transports WHERE id=%s", (t_id,))
            t = cursor.fetchone()
        return jsonify(t), 200
    finally:
        conn.close()


@admin_bp.route('/transports/<int:t_id>/block', methods=['PATCH'])
@permission_required('transports.block')
def block_transport(t_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE transports SET is_active=FALSE WHERE id=%s", (t_id,))
            conn.commit()
            cursor.execute("SELECT id, number, capacity, is_active FROM transports WHERE id=%s", (t_id,))
            t = cursor.fetchone()
        return jsonify(t), 200
    finally:
        conn.close()


@admin_bp.route('/transports/<int:t_id>/unblock', methods=['PATCH'])
@permission_required('transports.unblock')
def unblock_transport(t_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE transports SET is_active=TRUE WHERE id=%s", (t_id,))
            conn.commit()
            cursor.execute("SELECT id, number, capacity, is_active FROM transports WHERE id=%s", (t_id,))
            t = cursor.fetchone()
        return jsonify(t), 200
    finally:
        conn.close()
