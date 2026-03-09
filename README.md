# libraries-analysis

[![CI](https://github.com/npow/libraries-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/npow/libraries-analysis/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE) [![Docs](https://img.shields.io/badge/docs-mintlify-18a34a?style=flat-square)](https://mintlify.com/npow/nebraska-analysis)

Find the packages your entire supply chain depends on without knowing it.

## The problem

Open-source dependency chains are deep and invisible. When you add a package, you're also adding everything it depends on — packages nobody on your team ever consciously chose. The ones at the bottom of those chains are load-bearing infrastructure that shows up in thousands of production codebases, maintained by one person, with 9 stars. Existing tools show you your direct dependencies; they don't tell you which packages are holding up your entire ecosystem.

## Quick start

```bash
# Download the ecosyste.ms February 2026 dataset (~60GB) from data.ecosyste.ms
# then restore and run the Nebraska query
createdb ecosystems
pg_restore -d ecosystems --no-owner -a -t packages ecosystems_packages.dump
psql -d ecosystems -f scripts/2026/nebraska_query.sql
```

## Usage

**2026 analysis (ecosyste.ms → PostgreSQL)**

```bash
psql -d ecosystems -f scripts/2026/nebraska_query.sql   # produces nebraska_2026_full.csv
python scripts/2026/analyze_nebraska.py                 # summary JSON
python scripts/2026/compare_snapshots.py                # diff against 2020
```

**2020 analysis (Libraries.io → Neo4j)**

```bash
LIBRARIES_IO_DIR=data/libraries-1.6.0-2020-01-12 python 01_preprocess_csvs.py
bash 02_import_to_neo4j.sh
python scripts/2020/nebraska_query.py
```

## How it works

Each package in the ecosyste.ms database has `dependent_repos_count` (repositories using it transitively) and `dependent_packages_count` (packages listing it directly). The ratio — `dependent_repos_count ÷ (dependent_packages_count + 1)` — identifies packages with extreme transitive reach relative to their direct visibility. Above 1,000×, a package runs in at least 1,000 codebases for every package that knowingly depends on it.

Results from both snapshots are in `results/`. Full methodology and findings in the accompanying blog posts: [Finding Nebraska](https://npow.github.io/posts/finding-nebraska/) (npm) and [Nebraska in Go](https://npow.github.io/posts/nebraska-go/) (Go).

## Data

| Dataset | Source | Size | Coverage |
|---|---|---|---|
| ecosyste.ms Feb 2026 | [data.ecosyste.ms](https://data.ecosyste.ms/) | ~60GB | 13.1M packages |
| Libraries.io v1.6.0 (2020) | [Zenodo](https://zenodo.org/records/3626071) | ~30GB | 4.6M packages |

Neither dataset is included in this repository. Download and restore before running.

## License

Apache 2.0 — see [LICENSE](LICENSE)
