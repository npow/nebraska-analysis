-- Nebraska block query for ecosyste.ms PostgreSQL dump (February 2026)
-- Run against the `packages` table after restoring the ecosyste.ms dataset.
--
-- Nebraska block definition:
--   amplification ratio > 1,000x  (dependent_repos_count / (dependent_packages_count + 1))
--   present in > 50,000 repositories
--   excludes large-org sub-package families (@babel/, @jest/, @types/, workbox-)
--
-- Returns 2,244 rows against the February 2026 dataset.

\COPY (
  SELECT
    name,
    dependent_repos_count,
    dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner,
    maintainers_count
  FROM packages
  WHERE ecosystem = 'npm'
    AND dependent_repos_count > 50000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 1000
    AND name NOT LIKE '@babel/%'
    AND name NOT LIKE '@jest/%'
    AND name NOT LIKE '@types/%'
    AND name NOT LIKE 'workbox-%'
  ORDER BY amp DESC
) TO 'results/nebraska_2026_full.csv' WITH CSV HEADER;
