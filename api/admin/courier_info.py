from flask import jsonify, request
from . import admin_bp
from acl import permission_required
from db import Db


def _ensure_courier_profile(cursor, user_id):
    cursor.execute("INSERT IGNORE INTO courier_profiles (user_id) VALUES (%s)", (user_id,))


@admin_bp.route('/couriers/full-list', methods=['GET'])
@permission_required('courier_info.view_full_list')
def get_all_couriers_data():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            base_query = """
                SELECT u.id, u.username, u.full_name, u.phone, u.is_active,
                       cp.device_info, t.number as transport_number
                FROM users u
                LEFT JOIN courier_profiles cp ON u.id = cp.user_id
                LEFT JOIN transports t ON cp.transport_id = t.id
                WHERE u.role = 'courier'
            """
            params = []

            active_param = request.args.get('active')
            if active_param is not None:
                base_query += " AND u.is_active = %s"
                params.append(active_param.lower() == 'true')

            city_id = request.args.get('city_id', type=int)
            district_id = request.args.get('district_id', type=int)

            if district_id:
                base_query += """ AND EXISTS (
                    SELECT 1 FROM courier_districts cd
                    WHERE cd.courier_id = u.id AND cd.district_id = %s
                )"""
                params.append(district_id)
            elif city_id:
                base_query += """ AND EXISTS (
                    SELECT 1 FROM courier_districts cd
                    JOIN districts d ON cd.district_id = d.id
                    WHERE cd.courier_id = u.id AND d.city_id = %s
                )"""
                params.append(city_id)

            cursor.execute(base_query, tuple(params))
            couriers_raw = cursor.fetchall()

            if not couriers_raw:
                return jsonify([]), 200

            courier_ids = [c['id'] for c in couriers_raw]
            fmt = ','.join(['%s'] * len(courier_ids))

            cursor.execute(f"""
                SELECT cd.courier_id, d.id as district_id, d.name as district_name, c.name as city_name
                FROM courier_districts cd
                JOIN districts d ON cd.district_id = d.id
                JOIN cities c ON d.city_id = c.id
                WHERE cd.courier_id IN ({fmt})
            """, tuple(courier_ids))

            districts_map = {}
            for row in cursor.fetchall():
                cid = row['courier_id']
                if cid not in districts_map:
                    districts_map[cid] = {'districts': [], 'cities': set()}
                districts_map[cid]['districts'].append({"id": row['district_id'], "name": row['district_name']})
                districts_map[cid]['cities'].add(row['city_name'])

            result = []
            for c in couriers_raw:
                cid = c['id']
                c_data = districts_map.get(cid, {'districts': [], 'cities': set()})
                result.append({
                    "id": cid,
                    "username": c['username'],
                    "full_name": c['full_name'] or "Не указано",
                    "phone": c['phone'] or "Нет номера",
                    "is_active": c['is_active'],
                    "cities": list(c_data['cities']),
                    "districts": c_data['districts'],
                    "transport_number": c['transport_number'] or "Не привязано",
                    "device_info": c['device_info'] or "Не указано"
                })

        return jsonify(result), 200
    finally:
        conn.close()


@admin_bp.route('/users/<int:user_id>/equipment', methods=['PUT'])
@permission_required('courier_info.update_equipment')
def update_courier_equipment(user_id):
    data = request.get_json()
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE id=%s", (user_id,))
            user = cursor.fetchone()
            if not user:
                return jsonify({"error": "Пользователь не найден"}), 404

            if user['role'] != 'courier':
                return jsonify({"error": "Этот пользователь не является курьером"}), 400

            _ensure_courier_profile(cursor, user_id)

            if 'transport_number' in data:
                transport_number = data['transport_number']
                if transport_number:
                    cursor.execute("SELECT id FROM transports WHERE number=%s", (transport_number,))
                    transport = cursor.fetchone()
                    if not transport:
                        return jsonify({"error": f"Авто с номером {transport_number} не найдено"}), 404
                    cursor.execute(
                        "UPDATE courier_profiles SET transport_id=%s WHERE user_id=%s",
                        (transport['id'], user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE courier_profiles SET transport_id=NULL WHERE user_id=%s",
                        (user_id,)
                    )

            if 'device_info' in data:
                cursor.execute(
                    "UPDATE courier_profiles SET device_info=%s WHERE user_id=%s",
                    (data['device_info'], user_id)
                )

            conn.commit()

            cursor.execute("""
                SELECT cp.user_id, cp.device_info, t.number as transport_number
                FROM courier_profiles cp
                LEFT JOIN transports t ON cp.transport_id = t.id
                WHERE cp.user_id=%s
            """, (user_id,))
            updated_profile = cursor.fetchone()

        return jsonify({"message": "Оборудование обновлено", "profile": updated_profile}), 200
    finally:
        conn.close()


@admin_bp.route('/users/<int:user_id>/districts/attach', methods=['POST'])
@permission_required('courier_info.attach_districts')
def attach_districts(user_id):
    data = request.get_json()
    city_id = data.get('city_id')
    district_ids = data.get('district_ids')

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE id=%s", (user_id,))
            user = cursor.fetchone()
            if not user or user['role'] != 'courier':
                return jsonify({"error": "Пользователь не является курьером или не найден"}), 400

            _ensure_courier_profile(cursor, user_id)

            to_insert_ids = []

            if district_ids == "all" or data.get('all_districts') is True:
                if not city_id:
                    return jsonify({"error": "city_id обязателен для выбора всех районов"}), 400
                cursor.execute("SELECT id FROM districts WHERE city_id=%s", (city_id,))
                to_insert_ids = [r['id'] for r in cursor.fetchall()]

            elif isinstance(district_ids, list) and district_ids:
                fmt = ','.join(['%s'] * len(district_ids))
                cursor.execute(f"SELECT id FROM districts WHERE id IN ({fmt})", tuple(district_ids))
                to_insert_ids = [r['id'] for r in cursor.fetchall()]
            else:
                return jsonify({"error": "Неверный формат данных"}), 400

            if to_insert_ids:
                cursor.executemany(
                    "INSERT IGNORE INTO courier_districts (courier_id, district_id) VALUES (%s, %s)",
                    [(user_id, did) for did in to_insert_ids]
                )

            conn.commit()

            cursor.execute("SELECT district_id FROM courier_districts WHERE courier_id=%s", (user_id,))
            current_districts = [r['district_id'] for r in cursor.fetchall()]

        return jsonify({
            "message": "Районы успешно добавлены",
            "current_districts": current_districts
        }), 200
    finally:
        conn.close()


@admin_bp.route('/users/<int:user_id>/districts/<int:district_id>', methods=['DELETE'])
@permission_required('courier_info.detach_district')
def detach_single_district(user_id, district_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM districts WHERE id=%s", (district_id,))
            district = cursor.fetchone()
            if not district:
                return jsonify({"error": "Район не найден"}), 404

            cursor.execute(
                "DELETE FROM courier_districts WHERE courier_id=%s AND district_id=%s",
                (user_id, district_id)
            )

            if cursor.rowcount > 0:
                conn.commit()
                return jsonify({"message": f"Район {district['name']} откреплен"}), 200
            else:
                return jsonify({"error": "Район не был закреплен за этим курьером"}), 404
    finally:
        conn.close()
