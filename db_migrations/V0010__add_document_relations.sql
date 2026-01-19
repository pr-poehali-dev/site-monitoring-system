-- Добавление полей для связей между документами (версионирование)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS related_to INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_actual BOOLEAN DEFAULT TRUE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS related_count INTEGER DEFAULT 0;

-- Индексы для быстрого поиска связанных документов
CREATE INDEX IF NOT EXISTS idx_documents_related_to ON documents(related_to);
CREATE INDEX IF NOT EXISTS idx_documents_is_actual ON documents(is_actual);
CREATE INDEX IF NOT EXISTS idx_documents_number_date ON documents(document_number, document_date);

COMMENT ON COLUMN documents.related_to IS 'ID документа, который был изменён (ссылка на старую версию)';
COMMENT ON COLUMN documents.is_actual IS 'Актуальность документа (false если был изменён новым документом)';
COMMENT ON COLUMN documents.related_count IS 'Количество версий (документов, которые ссылаются на этот)';