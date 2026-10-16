-- Snapshot from this run; discover the current ID before repeating.
INSERT INTO lakehouse.silver.evolution_demo VALUES (-1,'temporary row','demo');
SELECT count(*) FROM lakehouse.silver.evolution_demo FOR VERSION AS OF 875890668398002844;
ALTER TABLE lakehouse.silver.evolution_demo EXECUTE rollback_to_snapshot(875890668398002844);
