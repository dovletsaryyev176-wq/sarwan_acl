"""
Запуск: python seed_permissions.py
Идемпотентный — можно запускать повторно, уже существующие записи не дублируются.
"""

import pymysql
from config import Config

PERMISSIONS = [
    # permissions management
    ("permissions.view",      "Просмотр списка разрешений"),
    ("permissions.view_user", "Просмотр разрешений пользователя"),
    ("permissions.assign",    "Назначение разрешения пользователю"),
    ("permissions.revoke",    "Отзыв разрешения у пользователя"),

    # brands
    ("brands.view",    "Просмотр брендов"),
    ("brands.create",  "Создание бренда"),
    ("brands.update",  "Редактирование бренда"),
    ("brands.block",   "Блокировка бренда"),
    ("brands.unblock", "Разблокировка бренда"),

    # currencies
    ("currencies.view",    "Просмотр валют"),
    ("currencies.create",  "Создание валюты"),
    ("currencies.update",  "Редактирование валюты"),
    ("currencies.block",   "Блокировка валюты"),
    ("currencies.unblock", "Разблокировка валюты"),

    # daily_expenses
    ("daily_expenses.view",   "Просмотр ежедневных расходов"),
    ("daily_expenses.create", "Создание ежедневного расхода"),
    ("daily_expenses.update", "Редактирование ежедневного расхода"),
    ("daily_expenses.delete", "Удаление ежедневного расхода"),

    # cities
    ("cities.view",      "Просмотр городов"),
    ("cities.create",    "Создание города"),
    ("cities.update",    "Редактирование города"),
    ("cities.block",     "Блокировка города"),
    ("cities.unblock",   "Разблокировка города"),
    ("cities.full_list", "Полный список городов с районами и курьерами"),

    # clients
    ("clients.view",               "Просмотр списка клиентов"),
    ("clients.create",             "Создание клиента"),
    ("clients.view_one",           "Просмотр одного клиента"),
    ("clients.update",             "Редактирование клиента"),
    ("clients.toggle_active",      "Блокировка/разблокировка клиента"),
    ("clients.view_block_reasons", "Просмотр причин блокировки клиента"),
    ("clients.view_phones",        "Просмотр телефонов клиента"),
    ("clients.add_phone",          "Добавление телефона клиенту"),
    ("clients.delete_phone",       "Удаление телефона клиента"),
    ("clients.view_addresses",     "Просмотр адресов клиента"),
    ("clients.add_address",        "Добавление адреса клиенту"),
    ("clients.update_address",     "Редактирование адреса клиента"),
    ("clients.delete_address",     "Удаление адреса клиента"),
    ("clients.toggle_address",     "Блокировка/разблокировка адреса клиента"),

    # counterparties
    ("counterparties.view",    "Просмотр контрагентов"),
    ("counterparties.create",  "Создание контрагента"),
    ("counterparties.update",  "Редактирование контрагента"),
    ("counterparties.block",   "Блокировка контрагента"),
    ("counterparties.unblock", "Разблокировка контрагента"),

    # courier_info
    ("courier_info.view_full_list",   "Полный список курьеров с районами и оборудованием"),
    ("courier_info.update_equipment", "Обновление оборудования курьера"),
    ("courier_info.attach_districts", "Прикрепление районов к курьеру"),
    ("courier_info.detach_district",  "Открепление района от курьера"),

    # credits
    ("credits.view",           "Просмотр кредита клиента"),
    ("credits.set_limit",      "Установка/обновление кредитного лимита клиента"),
    ("credits.view_payments",  "Просмотр платежей по кредиту клиента"),
    ("credits.create_payment", "Создание платежа/списания по кредиту"),

    # discounts
    ("discounts.view",   "Просмотр скидок"),
    ("discounts.create", "Создание скидки"),
    ("discounts.update", "Редактирование скидки"),
    ("discounts.delete", "Деактивация скидки"),

    # promotions
    ("promotions.view",   "Просмотр акций"),
    ("promotions.create", "Создание акции"),
    ("promotions.update", "Редактирование акции"),
    ("promotions.toggle", "Блокировка/разблокировка акции"),

    # districts
    ("districts.view",    "Просмотр районов"),
    ("districts.create",  "Создание района"),
    ("districts.update",  "Редактирование района"),
    ("districts.block",   "Блокировка района"),
    ("districts.unblock", "Разблокировка района"),
    ("districts.stats",   "Статистика по районам"),

    # price_types
    ("price_types.view",    "Просмотр типов цен"),
    ("price_types.create",  "Создание типа цены"),
    ("price_types.update",  "Редактирование типа цены"),
    ("price_types.block",   "Блокировка типа цены"),
    ("price_types.unblock", "Разблокировка типа цены"),

    # product_states
    ("product_states.view",    "Просмотр состояний продуктов"),
    ("product_states.create",  "Создание состояния продукта"),
    ("product_states.update",  "Редактирование состояния продукта"),
    ("product_states.block",   "Блокировка состояния продукта"),
    ("product_states.unblock", "Разблокировка состояния продукта"),

    # product_types
    ("product_types.view",    "Просмотр типов продуктов"),
    ("product_types.create",  "Создание типа продукта"),
    ("product_types.update",  "Редактирование типа продукта"),
    ("product_types.block",   "Блокировка типа продукта"),
    ("product_types.unblock", "Разблокировка типа продукта"),

    # products
    ("products.view",    "Просмотр продуктов"),
    ("products.create",  "Создание продукта"),
    ("products.update",  "Редактирование продукта"),
    ("products.block",   "Блокировка продукта"),
    ("products.unblock", "Разблокировка продукта"),

    # services
    ("services.view",         "Просмотр услуг"),
    ("services.create",       "Создание услуги"),
    ("services.toggle",       "Включение/отключение услуги"),
    ("services.set_price",    "Добавление/обновление цены услуги"),
    ("services.delete_price", "Удаление цены услуги"),
    ("services.add_rule",     "Добавление правила услуги"),
    ("services.delete_rule",  "Удаление правила услуги"),

    # sms
    ("sms.send",         "Отправка SMS сообщений"),
    ("sms.view_history", "Просмотр истории SMS"),
    ("sms.view_detail",  "Просмотр детали SMS сообщения"),

    # streets
    ("streets.view",    "Просмотр улиц"),
    ("streets.create",  "Создание улицы"),
    ("streets.update",  "Редактирование улицы"),
    ("streets.block",   "Блокировка улицы"),
    ("streets.unblock", "Разблокировка улицы"),

    # transports
    ("transports.view",    "Просмотр транспортных средств"),
    ("transports.create",  "Создание транспортного средства"),
    ("transports.update",  "Редактирование транспортного средства"),
    ("transports.block",   "Блокировка транспортного средства"),
    ("transports.unblock", "Разблокировка транспортного средства"),

    # users
    ("users.view",    "Просмотр пользователей"),
    ("users.create",  "Создание пользователя"),
    ("users.update",  "Редактирование пользователя"),
    ("users.block",   "Блокировка пользователя"),
    ("users.unblock", "Разблокировка пользователя"),

    # warehouses
    ("warehouses.view",    "Просмотр складов"),
    ("warehouses.create",  "Создание склада"),
    ("warehouses.update",  "Редактирование склада"),
    ("warehouses.block",   "Блокировка склада"),
    ("warehouses.unblock", "Разблокировка склада"),

    # courier
    ("courier.view_orders_summary",  "Сводка по заказам курьера на сегодня"),
    ("courier.view_inventory",       "Информация о таре у курьера"),
    ("courier.update_order_status",  "Смена статуса заказа курьером"),
    ("courier.deliver_order",        "Исполнение заказа (сдача клиенту)"),
    ("courier.view_orders",          "Список заказов курьера на сегодня"),
    ("courier.view_order",           "Детальная информация по одному заказу"),
    ("courier.add_order_note",       "Добавление заметки к заказу"),
    ("courier.view_order_notes",     "Просмотр заметок к заказу"),
    ("courier.view_daily_payments",  "Отчёт по платежам курьера за день"),
    ("courier.view_payments_summary",     "Суммарная информация по платежам курьера"),
    ("courier.view_stocks",               "Просмотр остатков товаров в машине курьера"),
    ("courier.view_transactions",         "Просмотр перемещений курьера за дату"),
    ("courier.create_transfer",           "Перемещение товаров между курьерами"),
    ("courier.view_transaction_detail",   "Детальная информация о транзакции курьера"),

    # warehouse
    ("warehouse.receive_from_counterparty",  "Приём товаров с завода на склад"),
    ("warehouse.view_stocks",                "Просмотр текущих остатков на складе"),
    ("warehouse.view_incoming_transactions", "Просмотр транзакций приёмки с завода"),
    ("warehouse.create_transaction",         "Создание транзакции (перемещение товара между локациями)"),
    ("warehouse.view_transactions",          "Просмотр транзакций выдачи/возврата курьерам"),
    ("warehouse.delete_transaction",         "Отмена транзакции"),
    ("warehouse.view_couriers_stocks",       "Остатки в машинах курьеров"),
    ("warehouse.return_courier_stocks",      "Возврат остатков курьера на склад"),
    ("warehouse.list_warehouses",                "Список складов для возврата"),
    ("warehouse.view_counterparty_locations",    "Просмотр локаций контрагентов"),
    ("warehouse.view_warehouse_locations",       "Просмотр локаций складов"),
    ("warehouse.view_courier_locations",         "Просмотр локаций курьеров"),
    ("warehouse.view_client_locations",          "Просмотр локаций клиентов"),

    # accounter
    ("accounter.view_couriers_debt",       "Список курьеров с долгами за день"),
    ("accounter.view_courier_payments",    "Детализация платежей курьера за день"),
    ("accounter.accept_handover",          "Принять кассу от курьера"),
    ("accounter.view_debt_summary",        "Итоговая сумма долгов по всем курьерам"),
    ("accounter.export_couriers_debt",     "Экспорт долгов курьеров в Excel"),
    ("accounter.view_movements_summary",   "Отчёт по выданным продуктам"),
    ("accounter.export_movements_summary", "Экспорт отчёта по выданным продуктам в Excel"),

    # director
    ("director.clients_by_price_type",  "Клиенты с распределением по типам цен"),
    ("director.blocked_transports",     "Количество заблокированного транспорта"),
    ("director.clients_by_district",    "Клиенты по районам городов"),
    ("director.accepted_money",         "Принятые деньги бухгалтером"),
    ("director.orders_by_status",       "Заказы с распределением по статусам"),
    ("director.yearly_monthly_income",  "Доход по месяцам за год"),
    ("director.monthly_income",         "Доход за конкретный месяц"),

    # department_types
    ("department_types.view",    "Просмотр типов подразделений"),
    ("department_types.create",  "Создание типа подразделения"),
    ("department_types.update",  "Редактирование типа подразделения"),
    ("department_types.block",   "Блокировка типа подразделения"),
    ("department_types.unblock", "Разблокировка типа подразделения"),

    # departments
    ("departments.view",    "Просмотр подразделений"),
    ("departments.create",  "Создание подразделения"),
    ("departments.update",  "Редактирование подразделения"),
    ("departments.block",   "Блокировка подразделения"),
    ("departments.unblock", "Разблокировка подразделения"),

    # staff_positions
    ("staff_positions.view",    "Просмотр штатных позиций"),
    ("staff_positions.create",  "Создание штатной позиции"),
    ("staff_positions.update",  "Редактирование штатной позиции"),
    ("staff_positions.block",   "Блокировка штатной позиции"),
    ("staff_positions.unblock", "Разблокировка штатной позиции"),

    # employees
    ("employees.view",   "Просмотр списка сотрудников"),
    ("employees.create", "Создание сотрудника"),
    ("employees.update", "Редактирование сотрудника"),

    # attendance
    ("attendance.checkin", "Фиксация прихода/ухода сотрудника"),
    ("attendance.view",    "Просмотр посещаемости сотрудников"),

    # marketing
    ("marketing.clients.view", "Просмотр клиентов с маркетинговой статистикой"),

    # points
    ("points.view",   "Просмотр цены услуг за баллы"),
    ("points.create", "Создание записи о цене услуг за баллы"),
    ("points.update", "Редактирование цены услуг за баллы"),
    ("points.delete", "Удаление цены услуг за баллы"),

    # cashback
    ("cashback.view",   "Просмотр кешбэка за услуги"),
    ("cashback.create", "Создание записи кешбэка за услугу"),
    ("cashback.update", "Редактирование кешбэка за услугу"),
    ("cashback.delete", "Удаление кешбэка за услугу"),

    # sms_templates
    ("sms_templates.view",   "Просмотр SMS-шаблонов"),
    ("sms_templates.update", "Редактирование текста SMS-шаблона"),

    # orders
    ("orders.calculate",            "Расчёт стоимости заказа без создания"),
    ("orders.create",               "Создание заказа"),
    ("orders.monitoring",           "Мониторинг всех заказов"),
    ("orders.view_client_history",  "История заказов конкретного клиента"),
    ("orders.search_by_phone",      "Поиск клиента по части номера телефона"),
    ("orders.view_couriers_info",   "Просмотр информации о курьерах"),
    ("orders.view_specific_courier","Мониторинг заказов конкретного курьера"),
    ("orders.update",               "Обновление заказа"),
    ("orders.view",                 "Просмотр конкретного заказа"),
]


def seed():
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            for name, description in PERMISSIONS:
                cursor.execute(
                    """
                    INSERT INTO permissions (name, description)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE description = VALUES(description)
                    """,
                    (name, description),
                )
        conn.commit()
        print(f"Готово: обработано {len(PERMISSIONS)} разрешений.")
    finally:
        conn.close()


SMS_TEMPLATES = [
    ("order_confirmation", "Siziň zakazyňyz üstünikli hasaba alyndy"),
]


def seed_sms_templates():
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            for key, text in SMS_TEMPLATES:
                cursor.execute(
                    """
                    INSERT INTO sms_templates (key, text)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE key = key
                    """,
                    (key, text),
                )
        conn.commit()
        print(f"Готово: обработано {len(SMS_TEMPLATES)} SMS-шаблонов.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    seed_sms_templates()
