import math

from flask import Blueprint, jsonify, request

from acl import permission_required
from db import Db

from . import config

audit_bp = Blueprint('audit', __name__)

PERMISSION = 'activity_log.view'


def _row(r, with_body=False):
    out = {
        'id': r['id'],
        'created_at': r['created_at'].isoformat(sep=' ', timespec='milliseconds') if r['created_at'] else None,
        'actor_type': r['actor_type'],
        'user_id': r['user_id'],
        'client_id': r['client_id'],
        # Имя берём актуальное, а если сотрудника или клиента уже удалили —
        # то, что было записано в момент действия.
        'actor_name': r.get('current_name') or r['actor_name'],
        'role': r['role'],
        'method': r['method'],
        'path': r['path'],
        'endpoint': r['endpoint'],
        'status_code': r['status_code'],
        'duration_ms': r['duration_ms'],
        'ip': r['ip'],
        'error_text': r['error_text'],
    }
    if with_body:
        out['user_agent'] = r['user_agent']
        out['content_type'] = r['content_type']
        out['request_body'] = r['request_body']
    return out


def _filters():
    """Собирает WHERE из query-параметров. Возвращает (sql, params)."""
    clauses = []
    params = []

    date_from = request.args.get('date_from')
    if date_from:
        clauses.append('al.created_at >= %s')
        params.append(date_from)

    date_to = request.args.get('date_to')
    if date_to:
        # Если передана только дата, берём весь день целиком
        clauses.append('al.created_at <= %s')
        params.append(date_to if len(date_to) > 10 else date_to + ' 23:59:59')

    actor_type = request.args.get('actor_type')
    if actor_type:
        clauses.append('al.actor_type = %s')
        params.append(actor_type)

    user_id = request.args.get('user_id', type=int)
    if user_id:
        clauses.append('al.user_id = %s')
        params.append(user_id)

    client_id = request.args.get('client_id', type=int)
    if client_id:
        clauses.append('al.client_id = %s')
        params.append(client_id)

    method = request.args.get('method')
    if method:
        clauses.append('al.method = %s')
        params.append(method.upper())

    path = request.args.get('path')
    if path:
        clauses.append('al.path LIKE %s')
        params.append('%{}%'.format(path))

    status_code = request.args.get('status_code', type=int)
    if status_code:
        clauses.append('al.status_code = %s')
        params.append(status_code)

    status_class = request.args.get('status_class', type=int)  # 2, 4, 5
    if status_class:
        clauses.append('al.status_code >= %s AND al.status_code < %s')
        params.extend([status_class * 100, (status_class + 1) * 100])

    if request.args.get('only_errors', '').lower() in ('1', 'true', 'yes'):
        clauses.append('al.status_code >= 400')

    q = request.args.get('q')
    if q:
        clauses.append('(al.request_body LIKE %s OR al.error_text LIKE %s)')
        params.extend(['%{}%'.format(q)] * 2)

    return ('WHERE ' + ' AND '.join(clauses)) if clauses else '', params


@audit_bp.route('/activity', methods=['GET'])
@permission_required(PERMISSION)
def list_activity():
    page = max(request.args.get('page', 1, type=int) or 1, 1)
    per_page = min(max(request.args.get('per_page', 50, type=int) or 50, 1), 200)
    where_sql, params = _filters()

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) AS total FROM activity_log al {}'.format(where_sql),
                tuple(params),
            )
            total = cursor.fetchone()['total']

            cursor.execute(
                """
                SELECT al.*, COALESCE(u.full_name, c.full_name) AS current_name
                FROM activity_log al
                LEFT JOIN users u ON u.id = al.user_id
                LEFT JOIN clients c ON c.id = al.client_id
                {}
                ORDER BY al.id DESC
                LIMIT %s OFFSET %s
                """.format(where_sql),
                tuple(params + [per_page, (page - 1) * per_page]),
            )
            rows = [_row(r) for r in cursor.fetchall()]

        return jsonify({
            'data': rows,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': math.ceil(total / per_page) if total else 0,
            },
            'retention_days': config.RETENTION_DAYS,
        }), 200
    finally:
        conn.close()


@audit_bp.route('/activity/<int:log_id>', methods=['GET'])
@permission_required(PERMISSION)
def get_activity(log_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT al.*, COALESCE(u.full_name, c.full_name) AS current_name
                FROM activity_log al
                LEFT JOIN users u ON u.id = al.user_id
                LEFT JOIN clients c ON c.id = al.client_id
                WHERE al.id = %s
                """,
                (log_id,),
            )
            row = cursor.fetchone()

        if not row:
            return jsonify({'error': 'Запись не найдена'}), 404
        return jsonify(_row(row, with_body=True)), 200
    finally:
        conn.close()


@audit_bp.route('/activity/meta', methods=['GET'])
@permission_required(PERMISSION)
def activity_meta():
    """Справочники для выпадающих списков на экране просмотра."""
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT al.user_id, COALESCE(u.full_name, al.actor_name) AS name,
                       COUNT(*) AS actions
                FROM activity_log al
                LEFT JOIN users u ON u.id = al.user_id
                WHERE al.user_id IS NOT NULL
                GROUP BY al.user_id, name
                ORDER BY actions DESC
                """
            )
            users = cursor.fetchall()

            cursor.execute(
                'SELECT method, COUNT(*) AS actions FROM activity_log GROUP BY method ORDER BY actions DESC'
            )
            methods = cursor.fetchall()

            cursor.execute(
                'SELECT status_code, COUNT(*) AS actions FROM activity_log '
                'GROUP BY status_code ORDER BY status_code'
            )
            statuses = cursor.fetchall()

            cursor.execute(
                'SELECT actor_type, COUNT(*) AS actions FROM activity_log '
                'GROUP BY actor_type ORDER BY actions DESC'
            )
            actor_types = cursor.fetchall()

            cursor.execute(
                'SELECT MIN(created_at) AS oldest, MAX(created_at) AS newest, '
                'COUNT(*) AS total FROM activity_log'
            )
            span = cursor.fetchone()

        return jsonify({
            'users': users,
            'methods': methods,
            'statuses': statuses,
            'actor_types': actor_types,
            'oldest': span['oldest'].isoformat(sep=' ') if span['oldest'] else None,
            'newest': span['newest'].isoformat(sep=' ') if span['newest'] else None,
            'total': span['total'],
            'retention_days': config.RETENTION_DAYS,
        }), 200
    finally:
        conn.close()
