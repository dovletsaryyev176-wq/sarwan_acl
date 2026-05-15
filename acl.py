from functools import wraps
from flask import session, jsonify
from db import Db


def permission_required(permission_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({
                    "authenticated": False,
                    "error": "Необходима авторизация"
                }), 401

            user_id = session.get('user_id')
            connection = Db.get_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT 1
                        FROM user_permissions up
                        JOIN permissions p ON up.permission_id = p.id
                        WHERE up.user_id = %s AND p.name = %s
                    """, (user_id, permission_name))
                    has_permission = cursor.fetchone()
            finally:
                connection.close()

            if not has_permission:
                return jsonify({
                    "error": "Доступ запрещен. Недостаточно прав."
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
