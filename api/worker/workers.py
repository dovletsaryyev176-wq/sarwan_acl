import os
import uuid
import math
import json
import datetime
from pathlib import Path
import qrcode
from flask import jsonify, request, current_app
from acl import permission_required
from . import worker_bp
from db import Db

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_upload_dirs():
    base = os.path.join(current_app.root_path, 'uploads', 'employees')
    photos = os.path.join(base, 'photos')
    qr = os.path.join(base, 'qr')
    os.makedirs(photos, exist_ok=True)
    os.makedirs(qr, exist_ok=True)
    return photos, qr


def _format_timedelta(td):
    if td is None:
        return None
    if isinstance(td, datetime.timedelta):
        total = int(td.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        return f"{h:02d}:{m:02d}"
    return str(td)


def _format_employee(row):
    row['rate'] = float(row['rate']) if row.get('rate') is not None else None
    row['is_official'] = bool(row.get('is_official'))
    row['is_active'] = bool(row.get('is_active'))
    if row.get('birth_date') and hasattr(row['birth_date'], 'isoformat'):
        row['birth_date'] = row['birth_date'].isoformat()
    if row.get('created_at') and hasattr(row['created_at'], 'isoformat'):
        row['created_at'] = row['created_at'].isoformat()
    row['work_start_time'] = _format_timedelta(row.get('work_start_time'))
    row['work_end_time'] = _format_timedelta(row.get('work_end_time'))


_EMPLOYEE_SELECT = """
    SELECT e.id, e.last_name, e.first_name, e.middle_name,
           e.passport_number, e.registered_address, e.actual_address,
           e.gender, e.birth_date, e.rate,
           e.work_start_time, e.work_end_time,
           e.is_official, e.is_active, e.created_at,
           e.photo_path, e.qr_path,
           e.staff_position_id,
           sp.position_name_ru, sp.position_name_tk,
           e.department_id,
           d.name_ru AS department_name_ru, d.name_tk AS department_name_tk,
           e.user_id, u.username
    FROM employees e
    LEFT JOIN staff_positions sp ON e.staff_position_id = sp.id
    LEFT JOIN departments d ON e.department_id = d.id
    LEFT JOIN users u ON e.user_id = u.id
"""


def _parse_employee_form():
    f = request.form
    data = {
        'last_name': (f.get('last_name') or '').strip(),
        'first_name': (f.get('first_name') or '').strip(),
        'middle_name': (f.get('middle_name') or '').strip() or None,
        'passport_number': (f.get('passport_number') or '').strip(),
        'registered_address': (f.get('registered_address') or '').strip(),
        'actual_address': (f.get('actual_address') or '').strip(),
        'gender': (f.get('gender') or '').strip(),
        'birth_date': (f.get('birth_date') or '').strip(),
        'staff_position_id': f.get('staff_position_id', type=int),
        'department_id': f.get('department_id', type=int),
        'rate': f.get('rate'),
        'work_start_time': (f.get('work_start_time') or '').strip(),
        'work_end_time': (f.get('work_end_time') or '').strip(),
        'is_official': (f.get('is_official') or 'false').lower() in ('true', '1', 'yes'),
        'user_id': f.get('user_id', type=int),
        'phones_raw': f.get('phones', '[]'),
    }
    return data


def _validate_employee_data(data):
    required = [
        'last_name', 'first_name', 'passport_number',
        'registered_address', 'actual_address', 'gender',
        'birth_date', 'work_start_time', 'work_end_time',
    ]
    missing = [k for k in required if not data.get(k)]
    if not data.get('staff_position_id'):
        missing.append('staff_position_id')
    if not data.get('department_id'):
        missing.append('department_id')
    if data.get('rate') is None:
        missing.append('rate')
    if missing:
        return None, None, f"Обязательные поля: {', '.join(missing)}"

    try:
        rate = float(data['rate'])
    except (ValueError, TypeError):
        return None, None, "rate должен быть числом"

    try:
        phones = json.loads(data['phones_raw'])
        if not isinstance(phones, list):
            raise ValueError
    except (ValueError, json.JSONDecodeError):
        return None, None, "phones должен быть JSON массивом строк"

    return rate, phones, None


# =============================================================
# Создание сотрудника
# =============================================================

@worker_bp.route('/employees', methods=['POST'])
@permission_required('employees.create')
def create_employee():
    data = _parse_employee_form()
    rate, phones, err = _validate_employee_data(data)
    if err:
        return jsonify({"error": err}), 400

    photo = request.files.get('photo')
    if not photo or not photo.filename:
        return jsonify({"error": "Фотография обязательна"}), 400
    if not _allowed_file(photo.filename):
        return jsonify({"error": "Недопустимый формат фотографии (jpg, jpeg, png, webp)"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM staff_positions WHERE id = %s", (data['staff_position_id'],))
            if not cursor.fetchone():
                return jsonify({"error": "Штатная позиция не найдена"}), 404

            cursor.execute("SELECT id FROM departments WHERE id = %s", (data['department_id'],))
            if not cursor.fetchone():
                return jsonify({"error": "Подразделение не найдено"}), 404

            if data['user_id']:
                cursor.execute("SELECT id FROM users WHERE id = %s", (data['user_id'],))
                if not cursor.fetchone():
                    return jsonify({"error": "Пользователь не найден"}), 404

            cursor.execute(
                """INSERT INTO employees
                   (last_name, first_name, middle_name, passport_number,
                    registered_address, actual_address, gender, birth_date,
                    staff_position_id, department_id, rate,
                    work_start_time, work_end_time, is_official, user_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (data['last_name'], data['first_name'], data['middle_name'], data['passport_number'],
                 data['registered_address'], data['actual_address'], data['gender'], data['birth_date'],
                 data['staff_position_id'], data['department_id'], rate,
                 data['work_start_time'], data['work_end_time'], data['is_official'], data['user_id'])
            )
            employee_id = cursor.lastrowid

            for phone in phones:
                phone = str(phone).strip()
                if phone:
                    cursor.execute(
                        "INSERT INTO employee_phones (employee_id, phone) VALUES (%s, %s)",
                        (employee_id, phone)
                    )

            photos_dir, qr_dir = _get_upload_dirs()

            ext = photo.filename.rsplit('.', 1)[1].lower()
            photo_filename = f"{employee_id}_{uuid.uuid4().hex}.{ext}"
            photo.save(os.path.join(photos_dir, photo_filename))
            photo_rel = f"uploads/employees/photos/{photo_filename}"

            qr_img = qrcode.make(str(employee_id))
            qr_filename = f"{employee_id}_qr.png"
            qr_img.save(os.path.join(qr_dir, qr_filename))
            qr_rel = f"uploads/employees/qr/{qr_filename}"

            cursor.execute(
                "UPDATE employees SET photo_path = %s, qr_path = %s WHERE id = %s",
                (photo_rel, qr_rel, employee_id)
            )
            conn.commit()

            cursor.execute(_EMPLOYEE_SELECT + " WHERE e.id = %s", (employee_id,))
            row = cursor.fetchone()
            _format_employee(row)

            cursor.execute("SELECT id, phone FROM employee_phones WHERE employee_id = %s", (employee_id,))
            row['phones'] = cursor.fetchall()

        return jsonify(row), 201
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =============================================================
# Список сотрудников (с пагинацией и поиском)
# =============================================================

@worker_bp.route('/employees', methods=['GET'])
@permission_required('employees.view')
def get_employees():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = (request.args.get('search') or '').strip()

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            where_clauses = []
            params = []

            if search:
                like = f"%{search}%"
                where_clauses.append(
                    "(e.last_name LIKE %s OR e.first_name LIKE %s OR e.middle_name LIKE %s"
                    " OR e.passport_number LIKE %s"
                    " OR sp.position_name_ru LIKE %s OR sp.position_name_tk LIKE %s"
                    " OR d.name_ru LIKE %s OR d.name_tk LIKE %s)"
                )
                params.extend([like] * 8)

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            cursor.execute(
                f"""SELECT COUNT(e.id) AS total
                    FROM employees e
                    LEFT JOIN staff_positions sp ON e.staff_position_id = sp.id
                    LEFT JOIN departments d ON e.department_id = d.id
                    {where_sql}""",
                tuple(params)
            )
            total = cursor.fetchone()['total']
            total_pages = math.ceil(total / per_page) if total > 0 else 0
            offset = (page - 1) * per_page

            cursor.execute(
                f"{_EMPLOYEE_SELECT} {where_sql} ORDER BY e.last_name, e.first_name LIMIT %s OFFSET %s",
                tuple(params + [per_page, offset])
            )
            rows = cursor.fetchall()

            if rows:
                emp_ids = [r['id'] for r in rows]
                fmt = ','.join(['%s'] * len(emp_ids))
                cursor.execute(
                    f"SELECT id, employee_id, phone FROM employee_phones WHERE employee_id IN ({fmt})",
                    tuple(emp_ids)
                )
                phones_map = {}
                for p in cursor.fetchall():
                    phones_map.setdefault(p['employee_id'], []).append({"id": p['id'], "phone": p['phone']})

                for row in rows:
                    _format_employee(row)
                    row['phones'] = phones_map.get(row['id'], [])

        return jsonify({
            "data": rows,
            "pagination": {"page": page, "per_page": per_page, "total": total, "pages": total_pages}
        }), 200
    finally:
        conn.close()


# =============================================================
# Обновление сотрудника
# =============================================================

@worker_bp.route('/employees/<int:employee_id>', methods=['PUT'])
@permission_required('employees.update')
def update_employee(employee_id):
    data = _parse_employee_form()
    rate, phones, err = _validate_employee_data(data)
    if err:
        return jsonify({"error": err}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, photo_path FROM employees WHERE id = %s", (employee_id,))
            existing = cursor.fetchone()
            if not existing:
                return jsonify({"error": "Сотрудник не найден"}), 404

            cursor.execute("SELECT id FROM staff_positions WHERE id = %s", (data['staff_position_id'],))
            if not cursor.fetchone():
                return jsonify({"error": "Штатная позиция не найдена"}), 404

            cursor.execute("SELECT id FROM departments WHERE id = %s", (data['department_id'],))
            if not cursor.fetchone():
                return jsonify({"error": "Подразделение не найдено"}), 404

            if data['user_id']:
                cursor.execute("SELECT id FROM users WHERE id = %s", (data['user_id'],))
                if not cursor.fetchone():
                    return jsonify({"error": "Пользователь не найден"}), 404

            photo_rel = existing['photo_path']
            photo = request.files.get('photo')
            if photo and photo.filename:
                if not _allowed_file(photo.filename):
                    return jsonify({"error": "Недопустимый формат фотографии (jpg, jpeg, png, webp)"}), 400
                photos_dir, _ = _get_upload_dirs()
                if photo_rel:
                    old_abs = Path(current_app.root_path) / photo_rel
                    if old_abs.exists():
                        old_abs.unlink()
                ext = photo.filename.rsplit('.', 1)[1].lower()
                photo_filename = f"{employee_id}_{uuid.uuid4().hex}.{ext}"
                photo.save(os.path.join(photos_dir, photo_filename))
                photo_rel = f"uploads/employees/photos/{photo_filename}"

            cursor.execute(
                """UPDATE employees SET
                   last_name=%s, first_name=%s, middle_name=%s, passport_number=%s,
                   registered_address=%s, actual_address=%s, gender=%s, birth_date=%s,
                   staff_position_id=%s, department_id=%s, rate=%s,
                   work_start_time=%s, work_end_time=%s, is_official=%s,
                   user_id=%s, photo_path=%s
                   WHERE id=%s""",
                (data['last_name'], data['first_name'], data['middle_name'], data['passport_number'],
                 data['registered_address'], data['actual_address'], data['gender'], data['birth_date'],
                 data['staff_position_id'], data['department_id'], rate,
                 data['work_start_time'], data['work_end_time'], data['is_official'],
                 data['user_id'], photo_rel, employee_id)
            )

            cursor.execute("DELETE FROM employee_phones WHERE employee_id = %s", (employee_id,))
            for phone in phones:
                phone = str(phone).strip()
                if phone:
                    cursor.execute(
                        "INSERT INTO employee_phones (employee_id, phone) VALUES (%s, %s)",
                        (employee_id, phone)
                    )

            conn.commit()

            cursor.execute(_EMPLOYEE_SELECT + " WHERE e.id = %s", (employee_id,))
            row = cursor.fetchone()
            _format_employee(row)
            cursor.execute("SELECT id, phone FROM employee_phones WHERE employee_id = %s", (employee_id,))
            row['phones'] = cursor.fetchall()

        return jsonify(row), 200
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
