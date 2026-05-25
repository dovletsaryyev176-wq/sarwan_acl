import datetime
from flask import jsonify, request
from acl import permission_required
from . import worker_bp
from db import Db


def _to_seconds(td):
    if isinstance(td, datetime.timedelta):
        return int(td.total_seconds())
    return td.hour * 3600 + td.minute * 60 + td.second


def _fmt_dt(value):
    if value and hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


# =============================================================
# Фиксация прихода / ухода
# =============================================================

@worker_bp.route('/attendance', methods=['POST'])
@permission_required('attendance.checkin')
def attendance_checkin():
    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    check_type = (data.get('type') or '').strip().lower()

    if not employee_id:
        return jsonify({"error": "employee_id обязателен"}), 400
    if check_type not in ('in', 'out'):
        return jsonify({"error": "type должен быть 'in' или 'out'"}), 400

    now = datetime.datetime.now()
    today = now.date()

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, last_name, first_name, middle_name,
                          photo_path, work_start_time
                   FROM employees WHERE id = %s AND is_active = TRUE""",
                (employee_id,)
            )
            employee = cursor.fetchone()
            if not employee:
                return jsonify({"error": "Сотрудник не найден"}), 404

            if check_type == 'in':
                now_secs = _to_seconds(datetime.timedelta(
                    hours=now.hour, minutes=now.minute, seconds=now.second
                ))
                work_start_secs = _to_seconds(employee['work_start_time'])
                status = 'пришел вовремя' if now_secs <= work_start_secs else 'опоздал'

                cursor.execute(
                    """INSERT INTO employee_attendance (employee_id, date, check_in, status)
                       VALUES (%s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE check_in = VALUES(check_in),
                                               status   = VALUES(status)""",
                    (employee_id, today, now, status)
                )
            else:
                cursor.execute(
                    """INSERT INTO employee_attendance (employee_id, date, check_out, status)
                       VALUES (%s, %s, %s, 'нет')
                       ON DUPLICATE KEY UPDATE check_out = VALUES(check_out)""",
                    (employee_id, today, now)
                )

            conn.commit()

        return jsonify({
            "last_name":   employee['last_name'],
            "first_name":  employee['first_name'],
            "middle_name": employee['middle_name'],
            "photo_path":  employee['photo_path'],
        }), 200
    finally:
        conn.close()


# =============================================================
# Список сотрудников с посещаемостью за дату
# =============================================================

@worker_bp.route('/attendance', methods=['GET'])
@permission_required('attendance.view')
def get_attendance():
    date_str = (request.args.get('date') or '').strip()
    last_name = (request.args.get('last_name') or '').strip()
    first_name = (request.args.get('first_name') or '').strip()
    middle_name = (request.args.get('middle_name') or '').strip()
    staff_position_id = request.args.get('staff_position_id', type=int)
    department_id = request.args.get('department_id', type=int)
    status = (request.args.get('status') or '').strip()

    if date_str:
        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return jsonify({"error": "Неверный формат даты, ожидается YYYY-MM-DD"}), 400
    else:
        target_date = datetime.date.today()

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            where = ["e.is_active = TRUE"]
            params = []

            if last_name:
                where.append("e.last_name LIKE %s")
                params.append(f"%{last_name}%")
            if first_name:
                where.append("e.first_name LIKE %s")
                params.append(f"%{first_name}%")
            if middle_name:
                where.append("e.middle_name LIKE %s")
                params.append(f"%{middle_name}%")
            if staff_position_id:
                where.append("e.staff_position_id = %s")
                params.append(staff_position_id)
            if department_id:
                where.append("e.department_id = %s")
                params.append(department_id)
            if status:
                if status == 'нет':
                    where.append("(ea.status IS NULL OR ea.status = 'нет')")
                else:
                    where.append("ea.status = %s")
                    params.append(status)

            where_sql = "WHERE " + " AND ".join(where)

            cursor.execute(
                f"""SELECT e.id, e.last_name, e.first_name, e.middle_name,
                           e.staff_position_id,
                           sp.position_name_ru, sp.position_name_tk,
                           e.department_id,
                           d.name_ru  AS department_name_ru,
                           d.name_tk  AS department_name_tk,
                           ea.check_in, ea.check_out,
                           COALESCE(ea.status, 'нет') AS status
                    FROM employees e
                    LEFT JOIN staff_positions sp ON e.staff_position_id = sp.id
                    LEFT JOIN departments d ON e.department_id = d.id
                    LEFT JOIN employee_attendance ea
                           ON ea.employee_id = e.id AND ea.date = %s
                    {where_sql}
                    ORDER BY e.last_name, e.first_name""",
                tuple([target_date] + params)
            )
            rows = cursor.fetchall()

            for row in rows:
                row['check_in']  = _fmt_dt(row.get('check_in'))
                row['check_out'] = _fmt_dt(row.get('check_out'))

        return jsonify({
            "date": target_date.isoformat(),
            "data": rows,
        }), 200
    finally:
        conn.close()
