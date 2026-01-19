-- Пересчитываем related_count на основе реальных данных из document_relations
UPDATE documents d
SET related_count = (
    SELECT COUNT(*) 
    FROM document_relations dr 
    WHERE dr.target_document_id = d.id
);

-- Добавляем комментарий
COMMENT ON COLUMN documents.related_count IS 'Количество документов, ссылающихся на этот документ (пересчитывается из document_relations)';