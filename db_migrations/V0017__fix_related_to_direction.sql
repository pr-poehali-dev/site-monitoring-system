-- Исправление направления связей в related_to
-- Сейчас: новый документ → related_to указывает на старый (неправильно)
-- Нужно: старый документ → related_to указывает на новый (правильно)

-- Шаг 1: Очищаем все related_to (будем заполнять заново)
UPDATE documents SET related_to = NULL;

-- Шаг 2: Для каждой связи в document_relations устанавливаем related_to у СТАРОГО документа
-- source_document_id = новый документ
-- target_document_id = старый документ
-- У старого документа (target) должен быть related_to = новый (source)

UPDATE documents d
SET related_to = dr.source_document_id
FROM document_relations dr
WHERE d.id = dr.target_document_id
  AND NOT d.is_phantom; -- Фантомные документы не обновляем

COMMENT ON COLUMN documents.related_to IS 'ID более новой версии документа (для устаревших документов)';
