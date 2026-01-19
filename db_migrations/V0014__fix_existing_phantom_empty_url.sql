-- Исправляем URL существующих фантомных документов с пустой строкой
-- Генерируем уникальный phantom:// URL для каждого
UPDATE documents
SET url = 'phantom://' || document_number || '/' || document_date || '/source-' || COALESCE(phantom_source_id::text, id::text)
WHERE is_phantom = TRUE AND url = '';
