-- Таблица документов
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    url VARCHAR(1000) NOT NULL UNIQUE,
    section VARCHAR(100) NOT NULL,
    published_date DATE,
    content_hash VARCHAR(64),
    last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_documents_section ON documents(section);
CREATE INDEX IF NOT EXISTS idx_documents_published_date ON documents(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);

-- Таблица изменений документов
CREATE TABLE IF NOT EXISTS document_changes (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    change_type VARCHAR(20) NOT NULL,
    old_content_hash VARCHAR(64),
    new_content_hash VARCHAR(64),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified BOOLEAN DEFAULT FALSE
);

-- Индекс для истории изменений
CREATE INDEX IF NOT EXISTS idx_changes_detected_at ON document_changes(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_changes_notified ON document_changes(notified);

-- Таблица логов парсинга
CREATE TABLE IF NOT EXISTS parsing_logs (
    id SERIAL PRIMARY KEY,
    section VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    duration_ms INTEGER,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

-- Индекс для логов
CREATE INDEX IF NOT EXISTS idx_logs_started_at ON parsing_logs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_section ON parsing_logs(section);

-- Таблица настроек мониторинга
CREATE TABLE IF NOT EXISTS monitoring_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Вставка дефолтных настроек
INSERT INTO monitoring_settings (key, value) 
SELECT 'sections_enabled', '["postanovleniya", "rasporyazheniya", "programmy"]'
WHERE NOT EXISTS (SELECT 1 FROM monitoring_settings WHERE key = 'sections_enabled');

INSERT INTO monitoring_settings (key, value) 
SELECT 'telegram_enabled', 'true'
WHERE NOT EXISTS (SELECT 1 FROM monitoring_settings WHERE key = 'telegram_enabled');

INSERT INTO monitoring_settings (key, value) 
SELECT 'telegram_chat_id', ''
WHERE NOT EXISTS (SELECT 1 FROM monitoring_settings WHERE key = 'telegram_chat_id');

INSERT INTO monitoring_settings (key, value) 
SELECT 'check_frequency', 'daily'
WHERE NOT EXISTS (SELECT 1 FROM monitoring_settings WHERE key = 'check_frequency');

INSERT INTO monitoring_settings (key, value) 
SELECT 'base_url', 'https://sychevka.admin-smolensk.ru'
WHERE NOT EXISTS (SELECT 1 FROM monitoring_settings WHERE key = 'base_url');
