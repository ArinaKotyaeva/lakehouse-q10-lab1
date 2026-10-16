ALTER TABLE lakehouse.silver.evolution_demo ADD COLUMN source VARCHAR;
ALTER TABLE lakehouse.silver.evolution_demo RENAME COLUMN source TO data_source;
