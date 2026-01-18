CREATE TABLE IF NOT EXISTS t_p32892808_site_monitoring_syst.document_files (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    file_url TEXT NOT NULL,
    file_type VARCHAR(50) DEFAULT 'main',
    file_name TEXT,
    file_size BIGINT,
    file_path TEXT,
    file_cdn_url TEXT,
    content_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_files_document_id ON t_p32892808_site_monitoring_syst.document_files(document_id);
CREATE INDEX IF NOT EXISTS idx_document_files_type ON t_p32892808_site_monitoring_syst.document_files(file_type);

COMMENT ON TABLE t_p32892808_site_monitoring_syst.document_files IS 'Файлы документов (основной файл + приложения)';
COMMENT ON COLUMN t_p32892808_site_monitoring_syst.document_files.file_type IS 'Тип файла: main (основной), appendix (приложение)';
