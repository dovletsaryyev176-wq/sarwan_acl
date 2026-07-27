import re

COUNTRY_CODE = '993'
PHONE_LENGTH = 8


def normalize_phone(raw):
    """
    Приводит номер к каноничному виду — 8 цифр без кода страны.

    Принимает '+99365717001', '99365717001', '65717001', '65 71 70 01'.
    Возвращает '65717001' либо None, если номер непригоден.
    """
    if not raw:
        return None

    digits = re.sub(r'\D', '', str(raw))

    if len(digits) > PHONE_LENGTH and digits.startswith(COUNTRY_CODE):
        digits = digits[len(COUNTRY_CODE):]

    if len(digits) != PHONE_LENGTH:
        return None

    return digits


def to_storage_format(normalized):
    """Формат, в котором номера лежат в client_phones: +993XXXXXXXX."""
    return '+{}{}'.format(COUNTRY_CODE, normalized)


# Нормализация номера на стороне MySQL.
#
# В client_phones данные грязные: '+99312 471930', '+99365513306  ',
# '+993865623719'. Сравнивать напрямую нельзя, поэтому чистим значение
# в самом запросе. Индекс тут не поможет, но таблица маленькая (~9.4k строк),
# полный скан незаметен.
#
# Использование: PHONE_MATCH_SQL.format(col='cp.phone') + ' = %s'
_CLEAN = (
    "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE({col}, ' ', ''), '-', ''), "
    "'(', ''), ')', ''), '+', '')"
)

PHONE_MATCH_SQL = (
    "CASE WHEN " + _CLEAN + " LIKE '" + COUNTRY_CODE + "%%' "
    "THEN SUBSTRING(" + _CLEAN + ", " + str(len(COUNTRY_CODE) + 1) + ") "
    "ELSE " + _CLEAN + " END"
)
