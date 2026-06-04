from flask import jsonify, request
from acl import permission_required
from . import admin_bp
from db import Db


@admin_bp.route('/sms-templates', methods=['GET'])
@permission_required('sms_templates.view')
def get_sms_templates():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, `key`, `text` FROM sms_templates")
            rows = cursor.fetchall()
        return jsonify(rows), 200
    finally:
        conn.close()


@admin_bp.route('/sms-templates/<int:template_id>', methods=['GET'])
@permission_required('sms_templates.view')
def get_sms_template(template_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, `key`, `text` FROM sms_templates WHERE id = %s", (template_id,))
            row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Шаблон не найден"}), 404
        return jsonify(row), 200
    finally:
        conn.close()


@admin_bp.route('/sms-templates/<int:template_id>', methods=['PUT'])
@permission_required('sms_templates.update')
def update_sms_template(template_id):
    data = request.get_json()
    text = data.get('text')

    if not text:
        return jsonify({"error": "text обязателен"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM sms_templates WHERE id = %s", (template_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Шаблон не найден"}), 404

            cursor.execute("UPDATE sms_templates SET `text` = %s WHERE id = %s", (text, template_id))
            conn.commit()

            cursor.execute("SELECT id, `key`, `text` FROM sms_templates WHERE id = %s", (template_id,))
            row = cursor.fetchone()
        return jsonify(row), 200
    finally:
        conn.close()
