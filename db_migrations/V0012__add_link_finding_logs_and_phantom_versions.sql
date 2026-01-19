-- Добавляем логи для поиска связей
CREATE TABLE IF NOT EXISTS link_finding_logs (
    id SERIAL PRIMARY KEY,
    document_id INTEGER,
    document_number TEXT,
    status TEXT NOT NULL,
    references_found INTEGER DEFAULT 0,
    links_created INTEGER DEFAULT 0,
    not_found_refs TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_link_finding_logs_created_at ON link_finding_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_link_finding_logs_document_id ON link_finding_logs(document_id);

-- Добавляем поле для фиктивных версий (упомянутых, но не найденных в системе)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_phantom BOOLEAN DEFAULT FALSE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS phantom_source_id INTEGER;

COMMENT ON COLUMN documents.is_phantom IS 'Фиктивная версия - упомянута в другом документе, но файл не найден на сайте';
COMMENT ON COLUMN documents.phantom_source_id IS 'ID документа, в котором упомянута эта фиктивная версия';
