from flask import jsonify, request
from . import admin_bp
from acl import permission_required
from db import Db


@admin_bp.route('/product-states', methods=['GET'])
@permission_required('product_states.view')
def get_product_states():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, is_active FROM product_states")
            states = cursor.fetchall()
        return jsonify(states), 200
    finally:
        conn.close()


@admin_bp.route('/product-states', methods=['POST'])
@permission_required('product_states.create')
def create_product_state():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({"error": "Имя обязательно"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM product_states WHERE name=%s", (name,))
            if cursor.fetchone():
                return jsonify({"error": "Такое состояние уже существует"}), 400

            cursor.execute("INSERT INTO product_states (name) VALUES (%s)", (name,))
            conn.commit()
            cursor.execute("SELECT id, name, is_active FROM product_states WHERE id=%s", (cursor.lastrowid,))
            new_state = cursor.fetchone()
        return jsonify(new_state), 201
    finally:
        conn.close()


@admin_bp.route('/product-states/<int:ps_id>', methods=['PUT'])
@permission_required('product_states.update')
def update_product_state(ps_id):
    data = request.get_json()
    name = data.get('name')

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM product_states WHERE id=%s", (ps_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Состояние продукта не найдено"}), 404

            if name:
                cursor.execute("UPDATE product_states SET name=%s WHERE id=%s", (name, ps_id))
                conn.commit()

            cursor.execute("SELECT id, name, is_active FROM product_states WHERE id=%s", (ps_id,))
            updated_state = cursor.fetchone()
        return jsonify(updated_state), 200
    finally:
        conn.close()


@admin_bp.route('/product-states/<int:ps_id>/block', methods=['PATCH'])
@permission_required('product_states.block')
def block_product_state(ps_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE product_states SET is_active=FALSE WHERE id=%s", (ps_id,))
            conn.commit()
            cursor.execute("SELECT id, name, is_active FROM product_states WHERE id=%s", (ps_id,))
            state = cursor.fetchone()
        return jsonify(state), 200
    finally:
        conn.close()


@admin_bp.route('/product-states/<int:ps_id>/unblock', methods=['PATCH'])
@permission_required('product_states.unblock')
def unblock_product_state(ps_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE product_states SET is_active=TRUE WHERE id=%s", (ps_id,))
            conn.commit()
            cursor.execute("SELECT id, name, is_active FROM product_states WHERE id=%s", (ps_id,))
            state = cursor.fetchone()
        return jsonify(state), 200
    finally:
        conn.close()
