-- Сбросить статус парсинга для Постановлений 2025 года
UPDATE t_p32892808_site_monitoring_syst.parsing_state 
SET status = 'pending', page = 1, retry_count = 0, last_error = NULL, updated_at = CURRENT_TIMESTAMP 
WHERE section = 'postanovleniya' AND year = 2025;