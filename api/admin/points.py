from flask import jsonify, request
from acl import permission_required
from . import admin_bp
from db import Db


@admin_bp.route('/points', methods=['GET'])
@permission_required('points.view')
def get_points():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sp.id, sp.service_id, s.name as service_name, sp.points
                FROM service_points sp
                LEFT JOIN services s ON sp.service_id = s.id
            """)
            rows = cursor.fetchall()
        for row in rows:
            row['points'] = float(row['points'])
        return jsonify(rows), 200
    finally:
        conn.close()


@admin_bp.route('/points/<int:point_id>', methods=['GET'])
@permission_required('points.view')
def get_point(point_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sp.id, sp.service_id, s.name as service_name, sp.points
                FROM service_points sp
                LEFT JOIN services s ON sp.service_id = s.id
                WHERE sp.id = %s
            """, (point_id,))
            row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Запись не найдена"}), 404
        row['points'] = float(row['points'])
        return jsonify(row), 200
    finally:
        conn.close()


@admin_bp.route('/points', methods=['POST'])
@permission_required('points.create')
def create_point():
    data = request.get_json()
    service_id = data.get('service_id')
    points = data.get('points')

    if service_id is None or points is None:
        return jsonify({"error": "service_id и points обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM services WHERE id = %s", (service_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Услуга не найдена"}), 404

            cursor.execute(
                "INSERT INTO service_points (service_id, points) VALUES (%s, %s)",
                (service_id, points)
            )
            conn.commit()
            point_id = cursor.lastrowid

            cursor.execute("""
                SELECT sp.id, sp.service_id, s.name as service_name, sp.points
                FROM service_points sp
                LEFT JOIN services s ON sp.service_id = s.id
                WHERE sp.id = %s
            """, (point_id,))
            row = cursor.fetchone()
        row['points'] = float(row['points'])
        return jsonify(row), 201
    finally:
        conn.close()


@admin_bp.route('/points/<int:point_id>', methods=['PUT'])
@permission_required('points.update')
def update_point(point_id):
    data = request.get_json()
    service_id = data.get('service_id')
    points = data.get('points')

    if service_id is None or points is None:
        return jsonify({"error": "service_id и points обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM service_points WHERE id = %s", (point_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Запись не найдена"}), 404

            cursor.execute("SELECT id FROM services WHERE id = %s", (service_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Услуга не найдена"}), 404

            cursor.execute(
                "UPDATE service_points SET service_id = %s, points = %s WHERE id = %s",
                (service_id, points, point_id)
            )
            conn.commit()

            cursor.execute("""
                SELECT sp.id, sp.service_id, s.name as service_name, sp.points
                FROM service_points sp
                LEFT JOIN services s ON sp.service_id = s.id
                WHERE sp.id = %s
            """, (point_id,))
            row = cursor.fetchone()
        row['points'] = float(row['points'])
        return jsonify(row), 200
    finally:
        conn.close()


@admin_bp.route('/points/<int:point_id>', methods=['DELETE'])
@permission_required('points.delete')
def delete_point(point_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM service_points WHERE id = %s", (point_id,))
            if cursor.rowcount == 0:
                return jsonify({"error": "Запись не найдена"}), 404
            conn.commit()
        return jsonify({"message": "Запись удалена"}), 200
    finally:
        conn.close()
