-- ⚠️ MANUAL MIGRATION - REQUIRES USER CONFIRMATION
-- Удаление дублирующихся документов из базы данных
-- Оставляет только самую свежую запись из каждой группы дублей

-- СТАТИСТИКА ПЕРЕД УДАЛЕНИЕМ:
-- Найдено 142 группы дублей
-- К удалению: 150 записей

-- ========================================
-- ШАГ 1: Проверка дублей (для подтверждения)
-- ========================================

SELECT 
  document_number, 
  document_date, 
  title,
  section,
  COUNT(*) as duplicate_count,
  STRING_AGG(CAST(id AS TEXT), ', ') as ids
FROM t_p32892808_site_monitoring_syst.documents
WHERE document_number IS NOT NULL
GROUP BY document_number, document_date, title, section
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- ========================================
-- ШАГ 2: Создание временной таблицы с ID для удаления
-- ========================================

CREATE TEMP TABLE duplicates_to_delete AS
SELECT id
FROM (
  SELECT 
    id,
    created_at,
    updated_at,
    ROW_NUMBER() OVER (
      PARTITION BY document_number, document_date, title, section 
      ORDER BY created_at DESC, id DESC
    ) as rn
  FROM t_p32892808_site_monitoring_syst.documents
  WHERE document_number IS NOT NULL
) ranked
WHERE rn > 1;

-- ========================================
-- ШАГ 3: Проверка количества записей к удалению
-- ========================================

SELECT 
  'Будет удалено записей' as action,
  COUNT(*) as count
FROM duplicates_to_delete;

-- ========================================
-- ШАГ 4: Удаление связанных записей
-- ========================================

-- Удаляем связанные изменения
DELETE FROM t_p32892808_site_monitoring_syst.document_changes
WHERE document_id IN (SELECT id FROM duplicates_to_delete);

-- Удаляем связанные файлы
DELETE FROM t_p32892808_site_monitoring_syst.document_files
WHERE document_id IN (SELECT id FROM duplicates_to_delete);

-- ========================================
-- ШАГ 5: Удаление дубликатов
-- ========================================

DELETE FROM t_p32892808_site_monitoring_syst.documents
WHERE id IN (SELECT id FROM duplicates_to_delete);

-- ========================================
-- ШАГ 6: Проверка результата
-- ========================================

-- Должно вернуть 0 строк
SELECT 
  document_number, 
  document_date, 
  title,
  COUNT(*) as duplicate_count
FROM t_p32892808_site_monitoring_syst.documents
WHERE document_number IS NOT NULL
GROUP BY document_number, document_date, title
HAVING COUNT(*) > 1;

-- Очистка временной таблицы
DROP TABLE IF EXISTS duplicates_to_delete;
