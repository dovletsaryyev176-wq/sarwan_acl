import math
from flask import jsonify, request
from acl import permission_required
from . import accounter_bp
from db import Db


@accounter_bp.route('/daily_expenses', methods=['GET'])
@permission_required('daily_expenses.view')
def get_daily_expenses():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    date_from = request.args.get('date_from', type=str)
    date_to = request.args.get('date_to', type=str)

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            where_clauses = []
            params = []

            if date_from:
                where_clauses.append("de.date >= %s")
                params.append(date_from)
            if date_to:
                where_clauses.append("de.date <= %s")
                params.append(date_to)

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            cursor.execute(
                f"SELECT COUNT(*) AS total FROM daily_expenses de {where_sql}",
                tuple(params)
            )
            total = cursor.fetchone()['total']
            total_pages = math.ceil(total / per_page) if total > 0 else 0
            offset = (page - 1) * per_page

            cursor.execute(f"""
                SELECT de.id, de.reason, de.amount, de.currency_id,
                       c.name_ru AS currency_name_ru, c.name_tk AS currency_name_tk,
                       de.date
                FROM daily_expenses de
                JOIN currencies c ON c.id = de.currency_id
                {where_sql}
                ORDER BY de.date DESC, de.id DESC
                LIMIT %s OFFSET %s
            """, tuple(params + [per_page, offset]))
            expenses = cursor.fetchall()

        return jsonify({
            "data": expenses,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": total_pages
            }
        }), 200
    finally:
        conn.close()


@accounter_bp.route('/daily_expenses', methods=['POST'])
@permission_required('daily_expenses.create')
def create_daily_expense():
    data = request.get_json()
    reason = data.get('reason')
    amount = data.get('amount')
    currency_id = data.get('currency_id')
    date = data.get('date')

    if not reason or amount is None or not currency_id or not date:
        return jsonify({"error": "Поля reason, amount, currency_id и date обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM currencies WHERE id = %s AND is_active = TRUE", (currency_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Валюта не найдена или заблокирована"}), 404

            cursor.execute(
                "INSERT INTO daily_expenses (reason, amount, currency_id, date) VALUES (%s, %s, %s, %s)",
                (reason, amount, currency_id, date)
            )
            conn.commit()
            expense_id = cursor.lastrowid

            cursor.execute("""
                SELECT de.id, de.reason, de.amount, de.currency_id,
                       c.name_ru AS currency_name_ru, c.name_tk AS currency_name_tk,
                       de.date
                FROM daily_expenses de
                JOIN currencies c ON c.id = de.currency_id
                WHERE de.id = %s
            """, (expense_id,))
            expense = cursor.fetchone()
        return jsonify(expense), 201
    finally:
        conn.close()


@accounter_bp.route('/daily_expenses/<int:expense_id>', methods=['PUT'])
@permission_required('daily_expenses.update')
def update_daily_expense(expense_id):
    data = request.get_json()
    reason = data.get('reason')
    amount = data.get('amount')
    currency_id = data.get('currency_id')
    date = data.get('date')

    if not reason or amount is None or not currency_id or not date:
        return jsonify({"error": "Поля reason, amount, currency_id и date обязательны"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, date FROM daily_expenses WHERE id = %s",
                (expense_id,)
            )
            expense = cursor.fetchone()
            if not expense:
                return jsonify({"error": "Расход не найден"}), 404

            cursor.execute(
                "SELECT DATE(date) = CURDATE() AS is_today FROM daily_expenses WHERE id = %s",
                (expense_id,)
            )
            row = cursor.fetchone()
            if not row['is_today']:
                return jsonify({"error": "Изменить можно только сегодняшние расходы"}), 403

            cursor.execute("SELECT id FROM currencies WHERE id = %s AND is_active = TRUE", (currency_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Валюта не найдена или заблокирована"}), 404

            cursor.execute(
                "UPDATE daily_expenses SET reason = %s, amount = %s, currency_id = %s, date = %s WHERE id = %s",
                (reason, amount, currency_id, date, expense_id)
            )
            conn.commit()

            cursor.execute("""
                SELECT de.id, de.reason, de.amount, de.currency_id,
                       c.name_ru AS currency_name_ru, c.name_tk AS currency_name_tk,
                       de.date
                FROM daily_expenses de
                JOIN currencies c ON c.id = de.currency_id
                WHERE de.id = %s
            """, (expense_id,))
            updated = cursor.fetchone()
        return jsonify(updated), 200
    finally:
        conn.close()


@accounter_bp.route('/daily_expenses/<int:expense_id>', methods=['DELETE'])
@permission_required('daily_expenses.delete')
def delete_daily_expense(expense_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM daily_expenses WHERE id = %s", (expense_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Расход не найден"}), 404

            cursor.execute(
                "SELECT DATE(date) = CURDATE() AS is_today FROM daily_expenses WHERE id = %s",
                (expense_id,)
            )
            row = cursor.fetchone()
            if not row['is_today']:
                return jsonify({"error": "Удалить можно только сегодняшние расходы"}), 403

            cursor.execute("DELETE FROM daily_expenses WHERE id = %s", (expense_id,))
            conn.commit()
        return jsonify({"message": "Расход удалён"}), 200
    finally:
        conn.close()
