-- Создаем таблицу для хранения связей документов (many-to-many)
-- Это позволит одному документу ссылаться на НЕСКОЛЬКО предыдущих версий
CREATE TABLE IF NOT EXISTS document_relations (
    id SERIAL PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    target_document_id INTEGER NOT NULL,
    relation_type VARCHAR(50) NOT NULL DEFAULT 'previous_version',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_document_id, target_document_id)
);

CREATE INDEX IF NOT EXISTS idx_document_relations_source ON document_relations(source_document_id);
CREATE INDEX IF NOT EXISTS idx_document_relations_target ON document_relations(target_document_id);

-- Миграция существующих данных из related_to в новую таблицу
INSERT INTO document_relations (source_document_id, target_document_id, relation_type)
SELECT id, related_to, 'previous_version'
FROM documents
WHERE related_to IS NOT NULL
ON CONFLICT (source_document_id, target_document_id) DO NOTHING;

-- Добавляем комментарии для документации
COMMENT ON TABLE document_relations IS 'Many-to-many таблица связей документов: текущий документ → предыдущие версии';
COMMENT ON COLUMN document_relations.source_document_id IS 'ID текущего документа (новая версия)';
COMMENT ON COLUMN document_relations.target_document_id IS 'ID предыдущего документа (старая версия)';
COMMENT ON COLUMN document_relations.relation_type IS 'Тип связи: previous_version, amendment, cancellation';