-- Restore spec_coverage columns.
ALTER TABLE pull_requests ADD COLUMN spec_coverage DOUBLE PRECISION;
ALTER TABLE mapping_cache ADD COLUMN spec_coverage DOUBLE PRECISION;
