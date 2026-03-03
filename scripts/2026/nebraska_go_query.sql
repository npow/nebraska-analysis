-- Nebraska block query for Go ecosystem (ecosyste.ms February 2026)
--
-- Go thresholds are lower than npm because:
--   1. Go's explicit go.mod makes direct dependencies more visible,
--      compressing amplification ratios (median Go package: ~2-5x vs npm's >100x)
--   2. The Go ecosystem is ~15x smaller than npm by repository count
--
-- Thresholds: amplification > 100x, present in > 5,000 repositories
-- Returns 122 rows against the February 2026 dataset.

COPY (
  SELECT
    name,
    dependent_repos_count,
    dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner,
    maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'go'
    AND dependent_repos_count > 5000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 100
  ORDER BY amp DESC
) TO '/tmp/nebraska_go_2026.csv' WITH CSV HEADER;
