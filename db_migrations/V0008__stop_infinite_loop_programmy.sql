-- Остановить бесконечный цикл парсинга программ 2024, 2026
UPDATE t_p32892808_site_monitoring_syst.parsing_state 
SET status = 'completed', updated_at = CURRENT_TIMESTAMP 
WHERE section = 'programmy' AND year IN (2024, 2026) AND status = 'partial';