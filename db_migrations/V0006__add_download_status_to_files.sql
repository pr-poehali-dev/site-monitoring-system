-- Добавляем статус загрузки для файлов
ALTER TABLE t_p32892808_site_monitoring_syst.document_files 
ADD COLUMN IF NOT EXISTS download_status VARCHAR(20) DEFAULT 'pending';

-- Обновляем существующие файлы
-- Если есть file_cdn_url - значит загружен
UPDATE t_p32892808_site_monitoring_syst.document_files 
SET download_status = 'downloaded' 
WHERE file_cdn_url IS NOT NULL AND file_cdn_url != '';

-- Помечаем документы без файлов - создаём записи для них
INSERT INTO t_p32892808_site_monitoring_syst.document_files (
    document_id, 
    file_url, 
    file_type, 
    file_name, 
    download_status
)
SELECT 
    d.id,
    d.url,
    'main',
    SPLIT_PART(d.url, '/', -1),
    'pending'
FROM t_p32892808_site_monitoring_syst.documents d
WHERE NOT EXISTS (
    SELECT 1 FROM t_p32892808_site_monitoring_syst.document_files f 
    WHERE f.document_id = d.id
)
AND d.url IS NOT NULL 
AND d.url != '';

-- Создаём индекс для быстрого поиска незагруженных файлов
CREATE INDEX IF NOT EXISTS idx_document_files_download_status 
ON t_p32892808_site_monitoring_syst.document_files(download_status);