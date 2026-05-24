from flask import jsonify, request
from . import marketing_bp
from acl import permission_required
from db import Db
import math
from datetime import datetime


@marketing_bp.route('/clients', methods=['GET'])
@permission_required('marketing.clients.view')
def get_marketing_clients():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    is_active = request.args.get('is_active', type=str)
    price_type_id = request.args.get('price_type_id', type=int)
    city_id = request.args.get('city_id', type=int)
    district_id = request.args.get('district_id', type=int)
    phone = request.args.get('phone', type=str)

    conn = Db.get_connection()
    try:
        with conn.cursor() as cursor:
            where_clauses = []
            params = []

            if phone:
                where_clauses.append("EXISTS (SELECT 1 FROM client_phones cp WHERE cp.client_id = c.id AND cp.phone LIKE %s)")
                params.append(f"%{phone}%")

            if is_active is not None:
                where_clauses.append("c.is_active = %s")
                params.append(is_active.lower() == 'true')

            if price_type_id is not None:
                where_clauses.append("c.price_type_id = %s")
                params.append(price_type_id)

            if city_id is not None:
                where_clauses.append("EXISTS (SELECT 1 FROM client_addresses ca WHERE ca.client_id = c.id AND ca.city_id = %s)")
                params.append(city_id)

            if district_id is not None:
                where_clauses.append("EXISTS (SELECT 1 FROM client_addresses ca WHERE ca.client_id = c.id AND ca.district_id = %s)")
                params.append(district_id)

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            cursor.execute(f"SELECT COUNT(c.id) as total FROM clients c {where_sql}", tuple(params))
            total_items = cursor.fetchone()['total']

            total_pages = math.ceil(total_items / per_page) if total_items > 0 else 0
            offset = (page - 1) * per_page

            cursor.execute(f"""
                SELECT c.id, c.full_name, c.is_active, c.created_at, c.price_type_id, pt.name as price_type_name
                FROM clients c
                LEFT JOIN price_types pt ON c.price_type_id = pt.id
                {where_sql}
                ORDER BY c.id DESC
                LIMIT %s OFFSET %s
            """, tuple(params + [per_page, offset]))
            clients_raw = cursor.fetchall()

            if not clients_raw:
                return jsonify({
                    "data": [],
                    "pagination": {"page": page, "per_page": per_page, "total": 0, "pages": 0}
                }), 200

            client_ids = [c['id'] for c in clients_raw]
            fmt = ','.join(['%s'] * len(client_ids))

            cursor.execute(f"SELECT id, client_id, phone FROM client_phones WHERE client_id IN ({fmt})", tuple(client_ids))
            phones_map = {}
            for p in cursor.fetchall():
                phones_map.setdefault(p['client_id'], []).append({"id": p['id'], "phone": p['phone']})

            # Продукты на руках у клиента (детально)
            cursor.execute(f"""
                SELECT l.client_id,
                       s.quantity,
                       p.id as product_id, p.name as product_name, p.volume, p.quantity_per_block,
                       pt.name as product_type_name,
                       b.name as brand_name,
                       ps.id as product_state_id, ps.name as product_state_name
                FROM locations l
                JOIN stocks s ON s.location_id = l.id
                JOIN products p ON s.product_id = p.id
                JOIN product_types pt ON p.product_type_id = pt.id
                JOIN brands b ON p.brand_id = b.id
                JOIN product_states ps ON s.product_state_id = ps.id
                WHERE l.client_id IN ({fmt}) AND l.type = 'client' AND s.quantity > 0
                ORDER BY l.client_id, p.name
            """, tuple(client_ids))
            stocks_map = {}
            for row in cursor.fetchall():
                cid = row['client_id']
                stocks_map.setdefault(cid, []).append({
                    "product_id": row['product_id'],
                    "product_name": row['product_name'],
                    "brand_name": row['brand_name'],
                    "product_type_name": row['product_type_name'],
                    "volume": row['volume'],
                    "quantity_per_block": row['quantity_per_block'],
                    "product_state_id": row['product_state_id'],
                    "product_state_name": row['product_state_name'],
                    "quantity": float(row['quantity']),
                })

            # Количество заказов и дата последнего заказа
            cursor.execute(f"""
                SELECT client_id, COUNT(*) as order_count, MAX(created_at) as last_order_at
                FROM orders
                WHERE client_id IN ({fmt})
                GROUP BY client_id
            """, tuple(client_ids))
            orders_map = {}
            now = datetime.now()
            for row in cursor.fetchall():
                last_order_at = row['last_order_at']
                days_since_last_order = (now - last_order_at).days if last_order_at else None
                orders_map[row['client_id']] = {
                    "order_count": row['order_count'],
                    "last_order_at": last_order_at.isoformat() if last_order_at else None,
                    "days_since_last_order": days_since_last_order
                }

            clients_data = []
            for c in clients_raw:
                cid = c['id']
                order_info = orders_map.get(cid, {"order_count": 0, "last_order_at": None, "days_since_last_order": None})
                clients_data.append({
                    "id": cid,
                    "full_name": c['full_name'],
                    "is_active": bool(c['is_active']),
                    "created_at": c['created_at'].isoformat() if c['created_at'] else None,
                    "price_type_id": c['price_type_id'],
                    "price_type_name": c['price_type_name'],
                    "phones": phones_map.get(cid, []),
                    "total_items_in_stock": sum(item["quantity"] for item in stocks_map.get(cid, [])),
                    "stock_items": stocks_map.get(cid, []),
                    "order_count": order_info["order_count"],
                    "last_order_at": order_info["last_order_at"],
                    "days_since_last_order": order_info["days_since_last_order"]
                })

        return jsonify({
            "data": clients_data,
            "pagination": {"page": page, "per_page": per_page, "total": total_items, "pages": total_pages}
        }), 200
    finally:
        conn.close()
