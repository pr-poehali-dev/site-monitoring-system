-- Таблица для хранения связанных документов (упоминания в преамбуле, ссылки, но НЕ версии)
CREATE TABLE IF NOT EXISTS related_documents (
    id SERIAL PRIMARY KEY,
    source_document_id INTEGER NOT NULL REFERENCES documents(id),
    related_document_id INTEGER NOT NULL REFERENCES documents(id),
    relation_type VARCHAR(50) DEFAULT 'reference', -- 'reference', 'based_on', 'amends'
    context TEXT, -- Контекст упоминания (±80 символов)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_document_id, related_document_id)
);

-- Индексы для быстрого поиска
CREATE INDEX idx_related_docs_source ON related_documents(source_document_id);
CREATE INDEX idx_related_docs_related ON related_documents(related_document_id);

-- Добавляем счетчик связанных документов в таблицу documents
ALTER TABLE documents ADD COLUMN IF NOT EXISTS related_docs_count INTEGER DEFAULT 0;

-- Индекс для сортировки по связанным документам
CREATE INDEX IF NOT EXISTS idx_documents_related_count ON documents(related_docs_count);