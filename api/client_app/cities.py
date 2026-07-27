from flask import jsonify

from db import Db

from . import client_bp


@client_bp.route('/cities', methods=['GET'])
def get_cities():
    """
    Список городов для клиентского приложения.

    Без авторизации: нужен на экране регистрации, когда токена доступа
    ещё нет — есть только pending_token. Отдаём лишь активные города,
    заблокированные клиенту не показываем.
    """
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT id, name FROM cities WHERE is_active = TRUE ORDER BY name'
            )
            cities = cursor.fetchall()
        return jsonify(cities), 200
    finally:
        conn.close()
