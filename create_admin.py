from werkzeug.security import generate_password_hash
from db import Db

Db.init(
    host="localhost",
    user="root",
    password="19121987",
    database="sarwan",
    maxconnections=5
)


def create_admin():
    full_name = input("Full name: ").strip()
    phone = input("Phone: ").strip()
    username = input("Username: ").strip()
    password = input("Password: ").strip()

    if not full_name or not phone or not username or not password:
        print("Все поля обязательны")
        return

    connection = Db.get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username = %s",
                (username,)
            )
            if cursor.fetchone():
                print("Пользователь с таким username уже существует")
                return

            password_hash = generate_password_hash(password)

            cursor.execute("""
                INSERT INTO users
                (full_name, phone, username, password_hash, role, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (full_name, phone, username, password_hash, "admin", 1))

            user_id = cursor.lastrowid

            # Выдаём все существующие разрешения
            cursor.execute("SELECT id FROM permissions")
            permission_ids = [row['id'] for row in cursor.fetchall()]

            if permission_ids:
                cursor.executemany(
                    "INSERT IGNORE INTO user_permissions (user_id, permission_id) VALUES (%s, %s)",
                    [(user_id, pid) for pid in permission_ids]
                )

            connection.commit()
            print(f"Администратор успешно создан, выдано {len(permission_ids)} разрешений.")

    except Exception as e:
        connection.rollback()
        print("Ошибка:", e)

    finally:
        connection.close()


if __name__ == "__main__":
    create_admin()
