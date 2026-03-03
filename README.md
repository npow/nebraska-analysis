# Nebraska Block Analysis

Supporting code and data for [Finding Nebraska](https://npow.github.io/posts/finding-nebraska/).

**Nebraska block**: an npm package with an amplification ratio > 1,000× — meaning it runs in thousands of codebases for every one package that lists it as a direct dependency — and is present in > 50,000 repositories. These are the packages at the bottom of transitive dependency chains that nobody deliberately chose to depend on.

```
amplification = dependent_repos_count ÷ (dependent_packages_count + 1)
```

---

## Two datasets, two snapshots

| | 2020 | 2026 |
|---|---|---|
| Source | Libraries.io v1.6.0 | ecosyste.ms February 2026 |
| Packages | 4.6M | 13.1M |
| Nebraska blocks (npm) | 502 | 2,244 |
| Combined codebase reach | 75M | 2B |
| Pipeline | Neo4j graph DB | PostgreSQL (direct) |

---

## 2020 analysis (Libraries.io → Neo4j)

### Data

Download Libraries.io v1.6.0 from [Zenodo](https://zenodo.org/records/3626071) (~30GB compressed).

```
data/
  libraries-1.6.0-2020-01-12/
    projects_with_repository_fields-1.6.0-2020-01-12.csv
    dependencies-1.6.0-2020-01-12.csv   # ~20GB, ~100M rows
    versions-1.6.0-2020-01-12.csv
```

### Setup

Requires Neo4j 5.x and Python 3.10+.

```bash
# 1. Preprocess CSVs into Neo4j admin import format
LIBRARIES_IO_DIR=data/libraries-1.6.0-2020-01-12 python 01_preprocess_csvs.py

# 2. Import into Neo4j
bash 02_import_to_neo4j.sh

# 3. Run Nebraska query
NEO4J_URL=http://localhost:7474/db/neo4j/tx/commit \
NEO4J_PASS=yourpassword \
python scripts/2020/nebraska_query.py

# 4. Sensitivity analysis (36 threshold combinations)
python scripts/2020/sensitivity.py
```

---

## 2026 analysis (ecosyste.ms → PostgreSQL)

### Data

Download the ecosyste.ms packages dataset from [data.ecosyste.ms](https://data.ecosyste.ms/):

```
ecosystems_packages_with_repo_metadata-2026-02-XX.tar.gz  (~60GB compressed)
```

Restore into PostgreSQL:

```bash
createdb ecosystems
tar -xzf ecosystems_packages_*.tar.gz | \
  pg_restore -d ecosystems --no-owner -a -t packages
```

Takes ~30 minutes; the packages table has ~13M rows.

### Run

```bash
# Core Nebraska query (produces results/nebraska_2026_full.csv)
sudo -u postgres psql -d ecosystems -f scripts/2026/nebraska_query.sql

# Analyze the 2026 results
python scripts/2026/analyze_nebraska.py

# Compare 2020 vs 2026
python scripts/2026/compare_snapshots.py
```

---

## Results

| File | Description |
|---|---|
| `results/nebraska_2026_full.csv` | All 2,244 Nebraska blocks (2026), with name, repos, pkgs, amp, owner, maintainers |
| `results/nebraska_2026.json` | Summary: top packages and owner counts |
| `results/ecosystems_results.json` | 2020 Nebraska blocks (502) with 2026 status |
| `results/post_dark_matter.md` | Source for the blog post |

---

## Core PostgreSQL query (2026)

The definitive Nebraska query run against the ecosyste.ms PostgreSQL dump:

```sql
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
ORDER BY amp DESC;
-- Returns 2,244 rows
```
