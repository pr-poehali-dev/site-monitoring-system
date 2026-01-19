-- Добавление новых колонок для детального логирования

ALTER TABLE t_p32892808_site_monitoring_syst.link_finding_logs 
  ADD COLUMN IF NOT EXISTS session_id UUID DEFAULT 'ffffffff-ffff-ffff-ffff-ffffffffffff'::uuid,
  ADD COLUMN IF NOT EXISTS document_date DATE,
  ADD COLUMN IF NOT EXISTS step VARCHAR(50) DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS details JSONB DEFAULT '{}'::jsonb;

-- Создаём индексы для быстрой работы
CREATE INDEX IF NOT EXISTS idx_link_finding_logs_session ON t_p32892808_site_monitoring_syst.link_finding_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_link_finding_logs_step ON t_p32892808_site_monitoring_syst.link_finding_logs(step);
CREATE INDEX IF NOT EXISTS idx_link_finding_logs_created ON t_p32892808_site_monitoring_syst.link_finding_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_link_finding_logs_details ON t_p32892808_site_monitoring_syst.link_finding_logs USING gin(details);