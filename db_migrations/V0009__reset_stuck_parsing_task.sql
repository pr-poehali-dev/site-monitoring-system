-- Сброс застрявшей задачи в pending для продолжения парсинга
UPDATE t_p32892808_site_monitoring_syst.parsing_state 
SET status = 'pending', page = 24, updated_at = CURRENT_TIMESTAMP 
WHERE section = 'postanovleniya' AND year = 2025 AND status = 'running';