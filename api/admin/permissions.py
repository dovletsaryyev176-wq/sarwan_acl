from flask import request, jsonify, session
from db import Db
from acl import permission_required
from . import admin_bp


@admin_bp.route('/permissions', methods=['GET'])
@permission_required('permissions.view')
def get_permissions():
    connection = Db.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, description, created_at
                FROM permissions
                ORDER BY name
            """)
            permissions = cursor.fetchall()
        return jsonify(permissions), 200
    finally:
        connection.close()



@admin_bp.route('/me/permissions', methods=['GET'])
def get_my_permissions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Не авторизован"}), 401

    connection = Db.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.name, p.description
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                WHERE up.user_id = %s
                ORDER BY p.name
            """, (user_id,))
            permissions = cursor.fetchall()
        return jsonify(permissions), 200
    finally:
        connection.close()


@admin_bp.route('/users/<int:user_id>/permissions', methods=['GET'])
@permission_required('permissions.view_user')
def get_user_permissions(user_id):
    connection = Db.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Пользователь не найден"}), 404

            cursor.execute("""
                SELECT p.id, p.name, p.description,
                       up.granted_by, up.created_at,
                       u.username AS granted_by_username
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.id
                LEFT JOIN users u ON up.granted_by = u.id
                WHERE up.user_id = %s
                ORDER BY p.name
            """, (user_id,))
            permissions = cursor.fetchall()
        return jsonify(permissions), 200
    finally:
        connection.close()


@admin_bp.route('/users/<int:user_id>/permissions', methods=['POST'])
@permission_required('permissions.assign')
def assign_permission(user_id):
    data = request.get_json()
    permission_id = data.get('permission_id')
    granted_by = session.get('user_id')

    if not permission_id:
        return jsonify({"error": "permission_id обязателен"}), 400

    connection = Db.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Пользователь не найден"}), 404

            cursor.execute("SELECT id FROM permissions WHERE id = %s", (permission_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Разрешение не найдено"}), 404

            cursor.execute("""
                INSERT INTO user_permissions (user_id, permission_id, granted_by)
                VALUES (%s, %s, %s)
            """, (user_id, permission_id, granted_by))
        connection.commit()
        return jsonify({"message": "Разрешение назначено"}), 201
    except Exception as e:
        connection.rollback()
        if "Duplicate entry" in str(e):
            return jsonify({"error": "У пользователя уже есть это разрешение"}), 409
        return jsonify({"error": str(e)}), 500
    finally:
        connection.close()


@admin_bp.route('/users/<int:user_id>/permissions/<int:permission_id>', methods=['DELETE'])
@permission_required('permissions.revoke')
def revoke_permission(user_id, permission_id):
    connection = Db.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                DELETE FROM user_permissions
                WHERE user_id = %s AND permission_id = %s
            """, (user_id, permission_id))
            if cursor.rowcount == 0:
                return jsonify({"error": "Назначение не найдено"}), 404
        connection.commit()
        return jsonify({"message": "Разрешение отозвано"}), 200
    except Exception as e:
        connection.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        connection.close()
