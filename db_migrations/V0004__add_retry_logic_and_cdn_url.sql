-- Добавляем поля для отслеживания процесса парсинга и повторных попыток
CREATE TABLE IF NOT EXISTS parsing_state (
    id SERIAL PRIMARY KEY,
    section VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    page INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(section, year)
);

-- Индексы для быстрого поиска незавершенных задач
CREATE INDEX IF NOT EXISTS idx_parsing_state_status ON parsing_state(status);
CREATE INDEX IF NOT EXISTS idx_parsing_state_section_year ON parsing_state(section, year);

-- Добавляем колонку для CDN URL файла
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_cdn_url VARCHAR(500);

-- Создаем индексы для сортировки
CREATE INDEX IF NOT EXISTS idx_documents_document_date_desc ON documents(document_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_documents_created_at_desc ON documents(created_at DESC);

COMMENT ON TABLE parsing_state IS 'Состояние парсинга для каждого раздела/года - позволяет продолжить с места остановки';
COMMENT ON COLUMN documents.file_cdn_url IS 'CDN URL файла из S3 хранилища';
