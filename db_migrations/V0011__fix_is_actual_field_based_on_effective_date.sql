-- Исправляем поле is_actual: актуальной должна быть только версия с самой свежей эффективной датой
-- (эффективная дата = document_date или published_date или created_at, в порядке приоритета)

-- Сначала сбрасываем все is_actual в false для документов с версиями
UPDATE documents
SET is_actual = false
WHERE related_to IS NOT NULL OR related_count > 0;

-- Теперь устанавливаем is_actual = true только для самой свежей версии в каждой цепочке
WITH latest_versions AS (
  SELECT DISTINCT ON (COALESCE(related_to, id))
    id
  FROM documents
  WHERE related_to IS NOT NULL OR related_count > 0
  ORDER BY 
    COALESCE(related_to, id),
    COALESCE(document_date, published_date, created_at) DESC,
    created_at DESC
)
UPDATE documents
SET is_actual = true
WHERE id IN (SELECT id FROM latest_versions);