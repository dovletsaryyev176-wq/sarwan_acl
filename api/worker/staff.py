from flask import jsonify, request
from acl import permission_required
from . import worker_bp
from db import Db


# =============================================================
# Типы подразделений
# =============================================================

@worker_bp.route('/department-types', methods=['GET'])
@permission_required('department_types.view')
def get_department_types():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name_ru, name_tk, is_active FROM department_types ORDER BY id")
            rows = cursor.fetchall()
        return jsonify(rows), 200
    finally:
        conn.close()


@worker_bp.route('/department-types', methods=['POST'])
@permission_required('department_types.create')
def create_department_type():
    data = request.get_json() or {}
    name_ru = data.get('name_ru', '').strip()
    name_tk = data.get('name_tk', '').strip()
    if not name_ru or not name_tk:
        return jsonify({"error": "name_ru и name_tk обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO department_types (name_ru, name_tk) VALUES (%s, %s)",
                (name_ru, name_tk)
            )
            conn.commit()
            row_id = cursor.lastrowid
            cursor.execute("SELECT id, name_ru, name_tk, is_active FROM department_types WHERE id = %s", (row_id,))
            row = cursor.fetchone()
        return jsonify(row), 201
    finally:
        conn.close()


@worker_bp.route('/department-types/<int:type_id>', methods=['PUT'])
@permission_required('department_types.update')
def update_department_type(type_id):
    data = request.get_json() or {}
    name_ru = data.get('name_ru', '').strip()
    name_tk = data.get('name_tk', '').strip()
    if not name_ru or not name_tk:
        return jsonify({"error": "name_ru и name_tk обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM department_types WHERE id = %s", (type_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Тип подразделения не найден"}), 404
            cursor.execute(
                "UPDATE department_types SET name_ru = %s, name_tk = %s WHERE id = %s",
                (name_ru, name_tk, type_id)
            )
            conn.commit()
            cursor.execute("SELECT id, name_ru, name_tk, is_active FROM department_types WHERE id = %s", (type_id,))
            row = cursor.fetchone()
        return jsonify(row), 200
    finally:
        conn.close()


@worker_bp.route('/department-types/<int:type_id>/block', methods=['PATCH'])
@permission_required('department_types.block')
def block_department_type(type_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM department_types WHERE id = %s", (type_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Тип подразделения не найден"}), 404
            cursor.execute("UPDATE department_types SET is_active = FALSE WHERE id = %s", (type_id,))
            conn.commit()
            cursor.execute("SELECT id, name_ru, name_tk, is_active FROM department_types WHERE id = %s", (type_id,))
            row = cursor.fetchone()
        return jsonify(row), 200
    finally:
        conn.close()


@worker_bp.route('/department-types/<int:type_id>/unblock', methods=['PATCH'])
@permission_required('department_types.unblock')
def unblock_department_type(type_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM department_types WHERE id = %s", (type_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Тип подразделения не найден"}), 404
            cursor.execute("UPDATE department_types SET is_active = TRUE WHERE id = %s", (type_id,))
            conn.commit()
            cursor.execute("SELECT id, name_ru, name_tk, is_active FROM department_types WHERE id = %s", (type_id,))
            row = cursor.fetchone()
        return jsonify(row), 200
    finally:
        conn.close()


# =============================================================
# Подразделения
# =============================================================

@worker_bp.route('/departments', methods=['GET'])
@permission_required('departments.view')
def get_departments():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT d.id, d.name_ru, d.name_tk, d.is_active,
                       d.department_type_id, dt.name_ru as department_type_name_ru, dt.name_tk as department_type_name_tk,
                       d.parent_department_id, pd.name_ru as parent_name_ru, pd.name_tk as parent_name_tk
                FROM departments d
                LEFT JOIN department_types dt ON d.department_type_id = dt.id
                LEFT JOIN departments pd ON d.parent_department_id = pd.id
                ORDER BY d.id
            """)
            rows = cursor.fetchall()
        return jsonify(rows), 200
    finally:
        conn.close()


@worker_bp.route('/departments', methods=['POST'])
@permission_required('departments.create')
def create_department():
    data = request.get_json() or {}
    name_ru = data.get('name_ru', '').strip()
    name_tk = data.get('name_tk', '').strip()
    department_type_id = data.get('department_type_id')
    parent_department_id = data.get('parent_department_id')

    if not name_ru or not name_tk:
        return jsonify({"error": "name_ru и name_tk обязательны"}), 400
    if not department_type_id:
        return jsonify({"error": "department_type_id обязателен"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM department_types WHERE id = %s", (department_type_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Тип подразделения не найден"}), 404

            if parent_department_id is not None:
                cursor.execute("SELECT id FROM departments WHERE id = %s", (parent_department_id,))
                if not cursor.fetchone():
                    return jsonify({"error": "Родительское подразделение не найдено"}), 404

            cursor.execute(
                "INSERT INTO departments (name_ru, name_tk, department_type_id, parent_department_id) VALUES (%s, %s, %s, %s)",
                (name_ru, name_tk, department_type_id, parent_department_id)
            )
            conn.commit()
            row_id = cursor.lastrowid
            cursor.execute("""
                SELECT d.id, d.name_ru, d.name_tk, d.is_active,
                       d.department_type_id, dt.name_ru as department_type_name_ru, dt.name_tk as department_type_name_tk,
                       d.parent_department_id, pd.name_ru as parent_name_ru, pd.name_tk as parent_name_tk
                FROM departments d
                LEFT JOIN department_types dt ON d.department_type_id = dt.id
                LEFT JOIN departments pd ON d.parent_department_id = pd.id
                WHERE d.id = %s
            """, (row_id,))
            row = cursor.fetchone()
        return jsonify(row), 201
    finally:
        conn.close()


@worker_bp.route('/departments/<int:department_id>', methods=['PUT'])
@permission_required('departments.update')
def update_department(department_id):
    data = request.get_json() or {}
    name_ru = data.get('name_ru', '').strip()
    name_tk = data.get('name_tk', '').strip()
    department_type_id = data.get('department_type_id')
    parent_department_id = data.get('parent_department_id')

    if not name_ru or not name_tk:
        return jsonify({"error": "name_ru и name_tk обязательны"}), 400
    if not department_type_id:
        return jsonify({"error": "department_type_id обязателен"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM departments WHERE id = %s", (department_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Подразделение не найдено"}), 404

            cursor.execute("SELECT id FROM department_types WHERE id = %s", (department_type_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Тип подразделения не найден"}), 404

            if parent_department_id is not None:
                if parent_department_id == department_id:
                    return jsonify({"error": "Подразделение не может быть родителем самого себя"}), 400
                cursor.execute("SELECT id FROM departments WHERE id = %s", (parent_department_id,))
                if not cursor.fetchone():
                    return jsonify({"error": "Родительское подразделение не найдено"}), 404

            cursor.execute(
                "UPDATE departments SET name_ru = %s, name_tk = %s, department_type_id = %s, parent_department_id = %s WHERE id = %s",
                (name_ru, name_tk, department_type_id, parent_department_id, department_id)
            )
            conn.commit()
            cursor.execute("""
                SELECT d.id, d.name_ru, d.name_tk, d.is_active,
                       d.department_type_id, dt.name_ru as department_type_name_ru, dt.name_tk as department_type_name_tk,
                       d.parent_department_id, pd.name_ru as parent_name_ru, pd.name_tk as parent_name_tk
                FROM departments d
                LEFT JOIN department_types dt ON d.department_type_id = dt.id
                LEFT JOIN departments pd ON d.parent_department_id = pd.id
                WHERE d.id = %s
            """, (department_id,))
            row = cursor.fetchone()
        return jsonify(row), 200
    finally:
        conn.close()


@worker_bp.route('/departments/<int:department_id>/block', methods=['PATCH'])
@permission_required('departments.block')
def block_department(department_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM departments WHERE id = %s", (department_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Подразделение не найдено"}), 404
            cursor.execute("UPDATE departments SET is_active = FALSE WHERE id = %s", (department_id,))
            conn.commit()
            cursor.execute("""
                SELECT d.id, d.name_ru, d.name_tk, d.is_active,
                       d.department_type_id, dt.name_ru as department_type_name_ru, dt.name_tk as department_type_name_tk,
                       d.parent_department_id, pd.name_ru as parent_name_ru, pd.name_tk as parent_name_tk
                FROM departments d
                LEFT JOIN department_types dt ON d.department_type_id = dt.id
                LEFT JOIN departments pd ON d.parent_department_id = pd.id
                WHERE d.id = %s
            """, (department_id,))
            row = cursor.fetchone()
        return jsonify(row), 200
    finally:
        conn.close()


@worker_bp.route('/departments/<int:department_id>/unblock', methods=['PATCH'])
@permission_required('departments.unblock')
def unblock_department(department_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM departments WHERE id = %s", (department_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Подразделение не найдено"}), 404
            cursor.execute("UPDATE departments SET is_active = TRUE WHERE id = %s", (department_id,))
            conn.commit()
            cursor.execute("""
                SELECT d.id, d.name_ru, d.name_tk, d.is_active,
                       d.department_type_id, dt.name_ru as department_type_name_ru, dt.name_tk as department_type_name_tk,
                       d.parent_department_id, pd.name_ru as parent_name_ru, pd.name_tk as parent_name_tk
                FROM departments d
                LEFT JOIN department_types dt ON d.department_type_id = dt.id
                LEFT JOIN departments pd ON d.parent_department_id = pd.id
                WHERE d.id = %s
            """, (department_id,))
            row = cursor.fetchone()
        return jsonify(row), 200
    finally:
        conn.close()


# =============================================================
# Штатные позиции
# =============================================================

@worker_bp.route('/staff-positions', methods=['GET'])
@permission_required('staff_positions.view')
def get_staff_positions():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT sp.id, sp.position_name_ru, sp.position_name_tk,
                       sp.slots, sp.salary, sp.is_active,
                       sp.department_id, d.name_ru as department_name_ru, d.name_tk as department_name_tk
                FROM staff_positions sp
                LEFT JOIN departments d ON sp.department_id = d.id
                ORDER BY sp.id
            """)
            rows = cursor.fetchall()
            for row in rows:
                row['slots'] = float(row['slots'])
                row['salary'] = float(row['salary'])
        return jsonify(rows), 200
    finally:
        conn.close()


@worker_bp.route('/staff-positions', methods=['POST'])
@permission_required('staff_positions.create')
def create_staff_position():
    data = request.get_json() or {}
    position_name_ru = data.get('position_name_ru', '').strip()
    position_name_tk = data.get('position_name_tk', '').strip()
    slots = data.get('slots')
    salary = data.get('salary')
    department_id = data.get('department_id')

    if not position_name_ru or not position_name_tk:
        return jsonify({"error": "position_name_ru и position_name_tk обязательны"}), 400
    if slots is None or salary is None:
        return jsonify({"error": "slots и salary обязательны"}), 400
    if not department_id:
        return jsonify({"error": "department_id обязателен"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM departments WHERE id = %s", (department_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Подразделение не найдено"}), 404

            cursor.execute(
                "INSERT INTO staff_positions (position_name_ru, position_name_tk, slots, salary, department_id) VALUES (%s, %s, %s, %s, %s)",
                (position_name_ru, position_name_tk, slots, salary, department_id)
            )
            conn.commit()
            row_id = cursor.lastrowid
            cursor.execute("""
                SELECT sp.id, sp.position_name_ru, sp.position_name_tk,
                       sp.slots, sp.salary, sp.is_active,
                       sp.department_id, d.name_ru as department_name_ru, d.name_tk as department_name_tk
                FROM staff_positions sp
                LEFT JOIN departments d ON sp.department_id = d.id
                WHERE sp.id = %s
            """, (row_id,))
            row = cursor.fetchone()
            row['slots'] = float(row['slots'])
            row['salary'] = float(row['salary'])
        return jsonify(row), 201
    finally:
        conn.close()


@worker_bp.route('/staff-positions/<int:position_id>', methods=['PUT'])
@permission_required('staff_positions.update')
def update_staff_position(position_id):
    data = request.get_json() or {}
    position_name_ru = data.get('position_name_ru', '').strip()
    position_name_tk = data.get('position_name_tk', '').strip()
    slots = data.get('slots')
    salary = data.get('salary')
    department_id = data.get('department_id')

    if not position_name_ru or not position_name_tk:
        return jsonify({"error": "position_name_ru и position_name_tk обязательны"}), 400
    if slots is None or salary is None:
        return jsonify({"error": "slots и salary обязательны"}), 400
    if not department_id:
        return jsonify({"error": "department_id обязателен"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM staff_positions WHERE id = %s", (position_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Штатная позиция не найдена"}), 404

            cursor.execute("SELECT id FROM departments WHERE id = %s", (department_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Подразделение не найдено"}), 404

            cursor.execute(
                "UPDATE staff_positions SET position_name_ru = %s, position_name_tk = %s, slots = %s, salary = %s, department_id = %s WHERE id = %s",
                (position_name_ru, position_name_tk, slots, salary, department_id, position_id)
            )
            conn.commit()
            cursor.execute("""
                SELECT sp.id, sp.position_name_ru, sp.position_name_tk,
                       sp.slots, sp.salary, sp.is_active,
                       sp.department_id, d.name_ru as department_name_ru, d.name_tk as department_name_tk
                FROM staff_positions sp
                LEFT JOIN departments d ON sp.department_id = d.id
                WHERE sp.id = %s
            """, (position_id,))
            row = cursor.fetchone()
            row['slots'] = float(row['slots'])
            row['salary'] = float(row['salary'])
        return jsonify(row), 200
    finally:
        conn.close()


@worker_bp.route('/staff-positions/<int:position_id>/block', methods=['PATCH'])
@permission_required('staff_positions.block')
def block_staff_position(position_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM staff_positions WHERE id = %s", (position_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Штатная позиция не найдена"}), 404
            cursor.execute("UPDATE staff_positions SET is_active = FALSE WHERE id = %s", (position_id,))
            conn.commit()
            cursor.execute("""
                SELECT sp.id, sp.position_name_ru, sp.position_name_tk,
                       sp.slots, sp.salary, sp.is_active,
                       sp.department_id, d.name_ru as department_name_ru, d.name_tk as department_name_tk
                FROM staff_positions sp
                LEFT JOIN departments d ON sp.department_id = d.id
                WHERE sp.id = %s
            """, (position_id,))
            row = cursor.fetchone()
            row['slots'] = float(row['slots'])
            row['salary'] = float(row['salary'])
        return jsonify(row), 200
    finally:
        conn.close()


@worker_bp.route('/staff-positions/<int:position_id>/unblock', methods=['PATCH'])
@permission_required('staff_positions.unblock')
def unblock_staff_position(position_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM staff_positions WHERE id = %s", (position_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Штатная позиция не найдена"}), 404
            cursor.execute("UPDATE staff_positions SET is_active = TRUE WHERE id = %s", (position_id,))
            conn.commit()
            cursor.execute("""
                SELECT sp.id, sp.position_name_ru, sp.position_name_tk,
                       sp.slots, sp.salary, sp.is_active,
                       sp.department_id, d.name_ru as department_name_ru, d.name_tk as department_name_tk
                FROM staff_positions sp
                LEFT JOIN departments d ON sp.department_id = d.id
                WHERE sp.id = %s
            """, (position_id,))
            row = cursor.fetchone()
            row['slots'] = float(row['slots'])
            row['salary'] = float(row['salary'])
        return jsonify(row), 200
    finally:
        conn.close()
