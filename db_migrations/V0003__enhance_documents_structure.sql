-- Добавляем новые поля в таблицу documents
ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_number VARCHAR(100);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_date DATE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size BIGINT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_path VARCHAR(500);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS changes_count INTEGER DEFAULT 0;

-- Добавляем индексы для быстрой фильтрации и сортировки
CREATE INDEX IF NOT EXISTS idx_documents_document_date ON documents(document_date);
CREATE INDEX IF NOT EXISTS idx_documents_published_date ON documents(published_date);
CREATE INDEX IF NOT EXISTS idx_documents_section ON documents(section);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);

-- Обновляем таблицу изменений для хранения истории
ALTER TABLE document_changes ADD COLUMN IF NOT EXISTS old_title TEXT;
ALTER TABLE document_changes ADD COLUMN IF NOT EXISTS new_title TEXT;
ALTER TABLE document_changes ADD COLUMN IF NOT EXISTS old_file_size BIGINT;
ALTER TABLE document_changes ADD COLUMN IF NOT EXISTS new_file_size BIGINT;