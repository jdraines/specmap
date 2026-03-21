-- Remove retired spec_coverage metric from pull_requests and mapping_cache.
ALTER TABLE pull_requests DROP COLUMN IF EXISTS spec_coverage;
ALTER TABLE mapping_cache DROP COLUMN IF EXISTS spec_coverage;
