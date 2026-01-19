-- Удаляем UNIQUE constraint на document_number
-- Номера документов могут повторяться с разными датами (например, №482 от 2022 и №482 от 2024)
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_document_number_key;
