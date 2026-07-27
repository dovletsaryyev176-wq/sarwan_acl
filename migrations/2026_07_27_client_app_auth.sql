-- ============================================================
-- Клиентское мобильное приложение — авторизация по SMS-коду
-- Дата: 2026-07-27
--
-- Только CREATE TABLE и один INSERT IGNORE.
-- Ни одна существующая таблица не изменяется.
--
-- Запуск:
--   mysql -u root -p sarwan < migrations/2026_07_27_client_app_auth.sql
-- ============================================================

-- Одноразовые коды подтверждения.
-- phone хранится в нормализованном виде — 8 цифр без кода страны.
CREATE TABLE IF NOT EXISTS client_otp_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    phone VARCHAR(20) NOT NULL,
    code_hash CHAR(64) NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip VARCHAR(45) NULL,
    INDEX idx_client_otp_phone_created (phone, created_at),
    INDEX idx_client_otp_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Refresh-токены. В базе лежит только HMAC-SHA256 от токена,
-- сам токен существует лишь на устройстве клиента.
CREATE TABLE IF NOT EXISTS client_refresh_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL,
    token_hash CHAR(64) NOT NULL,
    device_info VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    last_used_at DATETIME NULL,
    revoked_at DATETIME NULL,
    UNIQUE KEY uq_client_refresh_hash (token_hash),
    INDEX idx_client_refresh_client (client_id),
    CONSTRAINT fk_client_refresh_client
        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Профиль клиента в мобильном приложении.
-- city_id нужен, чтобы показать каталог с ценами до того,
-- как клиент заведёт первый адрес (service_prices привязаны к городу).
CREATE TABLE IF NOT EXISTS client_app_profiles (
    client_id INT NOT NULL PRIMARY KEY,
    city_id INT NULL,
    language VARCHAR(5) NOT NULL DEFAULT 'ru',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_client_app_profile_client
        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    CONSTRAINT fk_client_app_profile_city
        FOREIGN KEY (city_id) REFERENCES cities(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Шаблон SMS с кодом. INSERT IGNORE, чтобы повторный запуск
-- не затирал текст, отредактированный админом через веб-панель.
-- Плейсхолдер {code} подставляется бэкендом.
INSERT IGNORE INTO sms_templates (`key`, `text`)
VALUES ('client_otp', 'Sarwan: tassyklayys kody {code}');
