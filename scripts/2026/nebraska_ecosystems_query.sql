-- Nebraska block queries for all ecosystems except npm and go (see nebraska_query.sql, nebraska_go_query.sql)
-- ecosyste.ms February 2026 dataset
--
-- Thresholds are scaled per ecosystem size and dependency model:
--   - Ecosystems with implicit transitive deps (rubygems, cargo, packagist) use higher amp thresholds
--   - Smaller ecosystems use lower min_repos thresholds
--   - All use the same core formula: dependent_repos_count / (dependent_packages_count + 1)
--
-- Run from psql: \i scripts/2026/nebraska_ecosystems_query.sql

-- rubygems (Ruby)
-- Threshold: amp > 1000x, repos > 5000 → 245 rows
-- High amplification due to implicit gem resolution and GitHub Pages dependency chain
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'rubygems'
    AND dependent_repos_count > 5000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 1000
  ORDER BY amp DESC
) TO '/tmp/nebraska_rubygems.csv' WITH CSV HEADER;

-- cargo (Rust)
-- Threshold: amp > 500x, repos > 2000 → 311 rows
-- Cargo.toml is explicit like go.mod, compressing ratios vs npm/rubygems
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'cargo'
    AND dependent_repos_count > 2000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 500
  ORDER BY amp DESC
) TO '/tmp/nebraska_cargo.csv' WITH CSV HEADER;

-- pypi (Python)
-- Threshold: amp > 200x, repos > 2000 → 195 rows
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'pypi'
    AND dependent_repos_count > 2000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 200
  ORDER BY amp DESC
) TO '/tmp/nebraska_pypi.csv' WITH CSV HEADER;

-- maven (Java)
-- Threshold: amp > 100x, repos > 1000 → 106 rows
-- Maven's explicit POM declarations compress ratios more than npm/rubygems
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'maven'
    AND dependent_repos_count > 1000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 100
  ORDER BY amp DESC
) TO '/tmp/nebraska_maven.csv' WITH CSV HEADER;

-- packagist (PHP)
-- Threshold: amp > 500x, repos > 3000 → 105 rows
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'packagist'
    AND dependent_repos_count > 3000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 500
  ORDER BY amp DESC
) TO '/tmp/nebraska_packagist.csv' WITH CSV HEADER;

-- actions (GitHub Actions)
-- Threshold: amp > 100x, repos > 1000 → 306 rows
-- Note: actions ecosystem has almost no action-to-action dependencies, so amplification
-- equals raw reach directly. Structurally different from package ecosystems.
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'actions'
    AND dependent_repos_count > 1000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 100
  ORDER BY amp DESC
) TO '/tmp/nebraska_actions.csv' WITH CSV HEADER;

-- pub (Dart/Flutter)
-- Threshold: amp > 100x, repos > 1000 → 233 rows
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'pub'
    AND dependent_repos_count > 1000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 100
  ORDER BY amp DESC
) TO '/tmp/nebraska_pub.csv' WITH CSV HEADER;

-- cocoapods (iOS/macOS)
-- Threshold: amp > 100x, repos > 500 → 94 rows
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'cocoapods'
    AND dependent_repos_count > 500
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 100
  ORDER BY amp DESC
) TO '/tmp/nebraska_cocoapods.csv' WITH CSV HEADER;

-- nuget (.NET)
-- Threshold: amp > 50x, repos > 500 → 52 rows
-- NuGet's explicit package declarations compress amplification ratios
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'nuget'
    AND dependent_repos_count > 500
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 50
  ORDER BY amp DESC
) TO '/tmp/nebraska_nuget.csv' WITH CSV HEADER;

-- bower (JavaScript, deprecated 2017)
-- Threshold: amp > 100x, repos > 1000 → 206 rows
-- Ecosystem is frozen — dependency graph has not changed since deprecation
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'bower'
    AND dependent_repos_count > 1000
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 100
  ORDER BY amp DESC
) TO '/tmp/nebraska_bower.csv' WITH CSV HEADER;

-- conda (Anaconda/conda-forge)
-- Threshold: amp > 100x, repos > 200 → 245 rows
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'conda'
    AND dependent_repos_count > 200
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 100
  ORDER BY amp DESC
) TO '/tmp/nebraska_conda.csv' WITH CSV HEADER;

-- hex (Elixir/Erlang)
-- Threshold: amp > 100x, repos > 100 → 38 rows
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'hex'
    AND dependent_repos_count > 100
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 100
  ORDER BY amp DESC
) TO '/tmp/nebraska_hex.csv' WITH CSV HEADER;

-- hackage (Haskell)
-- Threshold: amp > 50x, repos > 100 → 426 rows
-- Small ecosystem; lower thresholds needed to capture the pattern
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'hackage'
    AND dependent_repos_count > 100
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 50
  ORDER BY amp DESC
) TO '/tmp/nebraska_hackage.csv' WITH CSV HEADER;

-- clojars (Clojure)
-- Threshold: amp > 50x, repos > 50 → 130 rows
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'clojars'
    AND dependent_repos_count > 50
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 50
  ORDER BY amp DESC
) TO '/tmp/nebraska_clojars.csv' WITH CSV HEADER;

-- cran (R) — included for completeness; returns 0 rows
-- R's DESCRIPTION file policy enforces explicit dependency declarations.
-- Max amplification across all CRAN packages is ~45x. No Nebraska pattern exists.
COPY (
  SELECT name, dependent_repos_count, dependent_packages_count,
    ROUND((dependent_repos_count::float / (dependent_packages_count + 1))::numeric, 1) AS amp,
    repo_metadata::jsonb->>'owner' AS github_owner, maintainers_count,
    repo_metadata::jsonb->'commit_stats'->>'total_committers' AS committers,
    repo_metadata::jsonb->>'stargazers_count' AS stars
  FROM packages
  WHERE ecosystem = 'cran'
    AND dependent_repos_count > 200
    AND (dependent_repos_count::float / (dependent_packages_count + 1)) > 50
  ORDER BY amp DESC
) TO '/tmp/nebraska_cran.csv' WITH CSV HEADER;
