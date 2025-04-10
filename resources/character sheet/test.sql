-- Ensure the client encoding is set to UTF-8
SET client_encoding = 'UTF8';

SELECT name
FROM characters
WHERE languages = 'English';
