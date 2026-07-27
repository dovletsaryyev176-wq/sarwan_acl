-- ============================================================
-- Журнал действий (activity_log)
-- Дата: 2026-07-27
--
-- Запуск:
--   mysql -u root -p sarwan < migrations/2026_07_27_activity_log.sql
--
-- Существующие таблицы не изменяются.
-- ============================================================

-- Внешних ключей на users и clients намеренно нет: FK с каскадом стёр бы
-- историю вместе с удалённым сотрудником, а без каскада запретил бы его
-- удаление. Журнал должен переживать удаление своих участников, поэтому
-- имя и роль дополнительно сохраняются строкой на момент действия.
CREATE TABLE IF NOT EXISTS activity_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    actor_type VARCHAR(10) NOT NULL,          -- staff | client | anon
    user_id INT NULL,
    client_id INT NULL,
    actor_name VARCHAR(150) NULL,
    role VARCHAR(50) NULL,

    method VARCHAR(10) NOT NULL,
    path VARCHAR(255) NOT NULL,
    endpoint VARCHAR(120) NULL,
    status_code SMALLINT NOT NULL,
    duration_ms INT NOT NULL DEFAULT 0,

    ip VARCHAR(45) NULL,
    user_agent VARCHAR(255) NULL,
    content_type VARCHAR(100) NULL,
    request_body MEDIUMTEXT NULL,
    error_text TEXT NULL,

    INDEX idx_activity_created (created_at),
    INDEX idx_activity_user (user_id, created_at),
    INDEX idx_activity_client (client_id, created_at),
    INDEX idx_activity_status (status_code, created_at),
    INDEX idx_activity_method (method, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Разрешение на просмотр журнала.
-- Через миграцию, а не через seed_permissions.py: его повторный запуск
-- перезаписывает тексты SMS-шаблонов, отредактированные в веб-панели.
INSERT IGNORE INTO permissions (name, description)
VALUES ('activity_log.view', 'Просмотр журнала действий');

-- Выдаём тем, кто уже управляет правами, то есть администраторам.
INSERT IGNORE INTO user_permissions (user_id, permission_id)
SELECT DISTINCT up.user_id, np.id
FROM user_permissions up
JOIN permissions p ON p.id = up.permission_id
CROSS JOIN permissions np
WHERE p.name = 'permissions.assign'
  AND np.name = 'activity_log.view';

-- ------------------------------------------------------------
-- Автоматическая чистка средствами MySQL
--
-- Событие запускается ежедневно и удаляет записи старше 30 дней.
-- Ежедневно, а не раз в месяц, специально: месячный запуск удалял бы
-- разом всю накопленную таблицу и надолго её заблокировал.
-- Окно хранения при этом ровно месяц.
-- ------------------------------------------------------------
SET GLOBAL event_scheduler = ON;

DROP EVENT IF EXISTS ev_activity_log_cleanup;

CREATE EVENT ev_activity_log_cleanup
ON SCHEDULE EVERY 1 DAY
    STARTS (CURRENT_DATE + INTERVAL 1 DAY + INTERVAL 4 HOUR)
DO
    DELETE FROM activity_log WHERE created_at < NOW() - INTERVAL 30 DAY;

-- ВАЖНО: SET GLOBAL event_scheduler не переживает перезапуск MySQL.
-- Чтобы планировщик включался сам, добавьте в /etc/mysql/my.cnf:
--
--   [mysqld]
--   event_scheduler = ON
--
-- Проверка состояния:
--   SHOW VARIABLES LIKE 'event_scheduler';
--   SELECT * FROM information_schema.events WHERE event_name = 'ev_activity_log_cleanup';
