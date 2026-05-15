from flask import jsonify, request
from acl import permission_required
from . import admin_bp
from db import Db


@admin_bp.route('/brands', methods=['GET'])
@permission_required('brands.view')
def get_brands():
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, is_active FROM brands")
            brands = cursor.fetchall()
        return jsonify(brands), 200
    finally:
        conn.close()


@admin_bp.route('/brands', methods=['POST'])
@permission_required('brands.create')
def create_brand():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({"error": "Имя обязательно"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO brands (name) VALUES (%s)", (name,))
            conn.commit()
            brand_id = cursor.lastrowid
            cursor.execute("SELECT id, name, is_active FROM brands WHERE id = %s", (brand_id,))
            brand = cursor.fetchone()
        return jsonify(brand), 201
    finally:
        conn.close()


@admin_bp.route('/brands/<int:brand_id>', methods=['PUT'])
@permission_required('brands.update')
def update_brand(brand_id):
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({"error": "Имя обязательно"}), 400

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM brands WHERE id = %s", (brand_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Бренд не найден"}), 404

            cursor.execute("UPDATE brands SET name = %s WHERE id = %s", (name, brand_id))
            conn.commit()

            cursor.execute("SELECT id, name, is_active FROM brands WHERE id = %s", (brand_id,))
            updated_brand = cursor.fetchone()
        return jsonify(updated_brand), 200
    finally:
        conn.close()


@admin_bp.route('/brands/<int:brand_id>/block', methods=['PATCH'])
@permission_required('brands.block')
def block_brand(brand_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM brands WHERE id = %s", (brand_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Бренд не найден"}), 404

            cursor.execute("UPDATE brands SET is_active = FALSE WHERE id = %s", (brand_id,))
            conn.commit()

            cursor.execute("SELECT id, name, is_active FROM brands WHERE id = %s", (brand_id,))
            updated_brand = cursor.fetchone()
        return jsonify(updated_brand), 200
    finally:
        conn.close()


@admin_bp.route('/brands/<int:brand_id>/unblock', methods=['PATCH'])
@permission_required('brands.unblock')
def unblock_brand(brand_id):
    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM brands WHERE id = %s", (brand_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Бренд не найден"}), 404

            cursor.execute("UPDATE brands SET is_active = TRUE WHERE id = %s", (brand_id,))
            conn.commit()

            cursor.execute("SELECT id, name, is_active FROM brands WHERE id = %s", (brand_id,))
            updated_brand = cursor.fetchone()
        return jsonify(updated_brand), 200
    finally:
        conn.close()
