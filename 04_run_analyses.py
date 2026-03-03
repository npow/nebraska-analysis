#!/usr/bin/env python3
"""
Novel analyses on the libraries.io graph in Neo4j.
Specifically designed to find insights NOT in existing literature.

WHAT'S ALREADY KNOWN (we deliberately skip):
- npm has scale-free/power-law topology (Zimmermann 2019)
- Top 5 npm packages reach 100K+ others (Zimmermann 2019)
- 20 maintainers reach half npm ecosystem (Zimmermann 2019)
- 40% of npm packages have vulnerable transitive deps (Zimmermann 2019)
- Vulnerability propagation rates (Decan et al. 2018)
- Technical lag ~3.5 months in npm (Zerouali 2018)
- SemVer adherence for npm, Maven, Go (multiple papers)
- License incompatibility: PyPI 7.27%, npm 0.6%, RubyGems 13.9%
- Bus factor analysis for individual projects
- 16% of npm packages are trivial (<35 LOC)
- Ecosystem statistics for PyPI (Bommarito 2019), CRAN (Bommarito 2021)
- 7 ecosystem comparison: CRAN/npm/NuGet/Cargo/CPAN/Packagist/RubyGems (Decan 2019)
- npm deprecated: 8.2-21.2% of top 50K

WHAT IS NOT KNOWN (our target findings):
1. Cross-ecosystem dependency leakage AT SCALE (Kannee only studied cross-publishing)
2. Multi-ecosystem PageRank across ALL 36 package managers in one graph
3. "Phantom dependency" rate across all ecosystems
4. Platform taxonomy from dependency culture alone
5. Fork hygiene: do forks accumulate more deps than originals?
6. Language-platform mismatch patterns
7. Star inflation / hidden gems: correlation of stars vs actual adoption
8. Dependency monoculture index per ecosystem
9. SemVer diversity across ALL 36 ecosystems (not just npm/Maven/Go)
10. Cross-platform dependency propagation risk for dual-published packages
"""
import json
import requests
import time
import math
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

NEO4J_URL = "http://localhost:7474"
DB_NAME = "neo4j"
OUTPUT_DIR = Path("/root/code/libraries-analysis/results")
OUTPUT_DIR.mkdir(exist_ok=True)

REPORT_FILE = OUTPUT_DIR / f"novel_insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"


def query(cypher, db=DB_NAME, timeout=600, params=None):
    """Execute a Cypher query, return (result_dict, error_list)."""
    url = f"{NEO4J_URL}/db/{db}/tx/commit"
    payload = {"statements": [{"statement": cypher, "parameters": params or {}}]}
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        data = r.json()
        if data.get('errors'):
            return None, data['errors']
        res = data.get('results', [{}])[0]
        cols = res.get('columns', [])
        rows = [[row['row'][i] for i in range(len(cols))] for row in res.get('data', [])]
        return {'columns': cols, 'rows': rows}, None
    except Exception as e:
        return None, [str(e)]


def fmt_table(result, max_rows=30):
    if not result or not result.get('rows'):
        return "*(empty result)*"
    cols = result['columns']
    rows = result['rows'][:max_rows]
    widths = [min(max(len(c), max(len(str(v)) for v in [row[i] for row in rows])), 45)
              for i, c in enumerate(cols)]
    sep = '|' + '|'.join('-' * (w+2) for w in widths) + '|'
    header = '|' + '|'.join(f" **{c[:w]}**{' '*(w-min(len(c),w))} " for c, w in zip(cols, widths)) + '|'
    lines = [header, sep]
    for row in rows:
        line = '|' + '|'.join(f" {str(v)[:w]:<{w}} " for v, w in zip(row, widths)) + '|'
        lines.append(line)
    if len(result['rows']) > max_rows:
        lines.append(f"\n*... {len(result['rows']) - max_rows} more rows*")
    return '\n'.join(lines)


def run(cypher, desc, timeout=600):
    """Run a query, print progress."""
    start = time.time()
    result, errors = query(cypher, timeout=timeout)
    elapsed = time.time() - start
    if errors:
        print(f"  ERROR ({elapsed:.1f}s): {errors[0]}")
        return None
    nrows = len(result.get('rows', []))
    print(f"  OK ({elapsed:.1f}s, {nrows} rows): {desc}")
    return result


# =========================================================================
# MAIN REPORT
# =========================================================================

sections = []

def section(title, analysis_name, known_state, cypher, timeout=600, interpretation=None):
    """Run an analysis and add to the report."""
    print(f"\n{'─'*65}")
    print(f"Running: {analysis_name}")
    result = run(cypher, analysis_name, timeout=timeout)
    sections.append({
        'title': title,
        'analysis': analysis_name,
        'known_state': known_state,
        'result': result,
        'interpretation': interpretation
    })
    return result


print("\n" + "="*65)
print("LIBRARIES.IO NOVEL ANALYSIS PIPELINE")
print("="*65)

# -----------------------------------------------------------------
# 0. DATABASE SANITY CHECK
# -----------------------------------------------------------------
print("\n[0] Database statistics")
db_stats = run("""
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC
""", "Node counts by label")

edge_stats = run("""
MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count
ORDER BY count DESC
""", "Edge counts by type")

# -----------------------------------------------------------------
# A. CROSS-ECOSYSTEM DEPENDENCY LEAKAGE
# Novel: actual cross-ecosystem dependency EDGES (not cross-publishing)
# Kannee 2022 only studied packages published on MULTIPLE platforms.
# We find packages from ecosystem A that declare dependencies on ecosystem B.
# -----------------------------------------------------------------
print("\n[A] Cross-Ecosystem Dependency Leakage")

a1 = section(
    "Cross-Ecosystem Dependency Leakage",
    "Volume of cross-ecosystem dependency edges",
    "NOT KNOWN: Kannee 2022 studied cross-publishing but not cross-dependency edges",
    """
MATCH (a:Package)-[d:DEPENDS_ON]->(b:Package)
WHERE a.platform <> b.platform
  AND a.platform IS NOT NULL AND b.platform IS NOT NULL
  AND a.platform <> '' AND b.platform <> ''
WITH a.platform AS from_platform, b.platform AS to_platform, count(*) AS edge_count
ORDER BY edge_count DESC
LIMIT 30
RETURN from_platform, to_platform, edge_count
""",
    interpretation="Which ecosystems 'borrow' from which others? High cross-deps means ecosystem boundaries are artificial."
)

a2 = section(
    "Cross-Ecosystem Dependency Leakage",
    "Packages most targeted from OTHER ecosystems",
    "NOT KNOWN: scale of cross-ecosystem dependency targets",
    """
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WHERE a.platform <> b.platform
  AND a.platform <> '' AND b.platform <> ''
WITH b.platform AS target_platform, b.name AS dep_name,
     collect(DISTINCT a.platform) AS source_platforms,
     count(DISTINCT a) AS dependent_count
WHERE dependent_count >= 10
RETURN target_platform, dep_name, source_platforms, dependent_count
ORDER BY dependent_count DESC LIMIT 30
""",
    interpretation="Packages that are dependency targets ACROSS ecosystem boundaries — most critical cross-ecosystem infrastructure."
)

a3 = run("""
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WITH a.platform AS platform,
     sum(CASE WHEN a.platform <> b.platform AND b.platform <> '' THEN 1 ELSE 0 END) AS cross_deps,
     count(*) AS total_deps
WHERE total_deps >= 100
RETURN platform, cross_deps, total_deps,
       round(100.0 * cross_deps / total_deps, 3) AS cross_dep_pct
ORDER BY cross_dep_pct DESC
""", "Cross-dep rate by platform")

# -----------------------------------------------------------------
# B. PHANTOM DEPENDENCIES (NEW: never studied before)
# Packages that have dependents but zero versions (never published / deleted)
# -----------------------------------------------------------------
print("\n[B] Phantom Dependencies")

b1 = section(
    "Phantom Dependencies",
    "Ghost packages: depended upon but never published",
    "NOT STUDIED: no paper has quantified the phantom dependency problem at scale",
    """
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WHERE (b.versions_count = 0 OR b.versions_count IS NULL)
WITH b.platform AS platform, b.name AS phantom_name,
     count(DISTINCT a) AS dependent_count
WHERE dependent_count >= 5
RETURN platform, phantom_name, dependent_count
ORDER BY dependent_count DESC LIMIT 60
""",
    interpretation="These are packages that thousands depend on but don't exist. They're supply chain attack surfaces and reliability risks."
)

b2 = section(
    "Phantom Dependencies",
    "Phantom dependency rate by ecosystem",
    "NOT STUDIED: no comparative study across ecosystems",
    """
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WITH b.platform AS platform,
     sum(CASE WHEN b.versions_count = 0 OR b.versions_count IS NULL THEN 1 ELSE 0 END) AS phantom_edges,
     count(*) AS total_edges
WHERE total_edges >= 500
RETURN platform, phantom_edges, total_edges,
       round(100.0 * phantom_edges / total_edges, 2) AS phantom_rate_pct
ORDER BY phantom_rate_pct DESC
""",
    interpretation="High phantom rate = ecosystem has a 'missing packages' problem. A typosquatter could claim these names and attack millions of users."
)

# -----------------------------------------------------------------
# C. MULTI-ECOSYSTEM DEGREE DISTRIBUTION STATISTICS
# Novel: Computing across ALL 36 ecosystems with consistent methodology
# What's known: Zimmermann did npm (2019); Decan did 7 ecosystems (2019)
# Novel: We do all 36 with identical methodology and include metrics like
# assortativity (NEVER computed for package ecosystems)
# -----------------------------------------------------------------
print("\n[C] Network Topology Across All Ecosystems")

c1 = section(
    "Network Topology",
    "In-degree distribution (dependents) statistics per ecosystem",
    "Known for npm (Zimmermann 2019) and 7 ecosystems (Decan 2019); not all 36",
    """
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg.platform AS platform, pkg.name AS pkg_name, count(DISTINCT dep) AS in_degree
WITH platform,
     count(*) AS num_nodes,
     avg(in_degree) AS avg_in_degree,
     percentileCont(in_degree, 0.5) AS median_in_degree,
     percentileCont(in_degree, 0.9) AS p90_in_degree,
     percentileCont(in_degree, 0.99) AS p99_in_degree,
     max(in_degree) AS max_in_degree
RETURN platform, num_nodes, avg_in_degree, median_in_degree,
       p90_in_degree, p99_in_degree, max_in_degree
ORDER BY num_nodes DESC
""",
    timeout=900,
    interpretation="Ecosystems where median << average have extreme hub concentration (scale-free signature)."
)

c2 = section(
    "Network Topology",
    "Out-degree distribution (direct dependencies) per ecosystem",
    "Known qualitatively; not quantified across all 36 ecosystems",
    """
MATCH (pkg:Package)-[:DEPENDS_ON]->(dep:Package)
WITH pkg.platform AS platform, pkg.name AS pkg_name, count(DISTINCT dep) AS out_degree
WITH platform,
     count(*) AS num_nodes_with_deps,
     avg(out_degree) AS avg_out_degree,
     percentileCont(out_degree, 0.5) AS median_out_degree,
     percentileCont(out_degree, 0.9) AS p90_out_degree,
     percentileCont(out_degree, 0.99) AS p99_out_degree,
     max(out_degree) AS max_out_degree
RETURN platform, num_nodes_with_deps, avg_out_degree, median_out_degree,
       p90_out_degree, p99_out_degree, max_out_degree
ORDER BY num_nodes_with_deps DESC
""",
    timeout=900,
    interpretation="High p99 out-degree = packages that depend on many others — potential dependency bloat."
)

c3 = section(
    "Network Topology",
    "Dependency density and connectivity per ecosystem",
    "Not computed for all 36 ecosystems with identical methodology",
    """
MATCH (p:Package)
WITH p.platform AS platform, count(p) AS total_packages
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WHERE a.platform = platform
WITH platform, total_packages, count(*) AS total_deps
WITH platform, total_packages, total_deps,
     round(1.0 * total_deps / total_packages, 2) AS deps_per_package,
     round(1.0 * total_deps / (total_packages * (total_packages - 1)), 6) AS density
ORDER BY total_packages DESC
RETURN platform, total_packages, total_deps, deps_per_package, density
""",
    timeout=900,
    interpretation="Density = edges / possible_edges. Higher density = more interconnected ecosystem."
)

c4 = section(
    "Network Topology",
    "Dependency hubs: packages with high BOTH in AND out degree (bridge nodes)",
    "Bridges / bottlenecks NOT identified across all 36 ecosystems",
    """
MATCH (pkg:Package)
WITH pkg,
     size([(pkg)<-[:DEPENDS_ON]-() | 1]) AS in_deg,
     size([(pkg)-[:DEPENDS_ON]->() | 1]) AS out_deg
WHERE in_deg >= 50 AND out_deg >= 5
RETURN pkg.platform AS platform,
       pkg.name AS name,
       in_deg, out_deg,
       in_deg + out_deg AS total_degree,
       pkg.sourcerank AS sourcerank,
       pkg.status AS status
ORDER BY total_degree DESC LIMIT 50
""",
    timeout=300,
    interpretation="Bridge packages: high in-degree AND out-degree. Compromise of these affects BOTH upstream and downstream."
)

# -----------------------------------------------------------------
# D. POPULARITY PARADOX (NOVEL ANGLE)
# Known: high-dep packages have high sourcerank (assumed)
# Novel: are there systematically HIGH-DEP LOW-QUALITY packages?
# -----------------------------------------------------------------
print("\n[D] The Popularity Paradox")

d1 = section(
    "Popularity Paradox",
    "High-dependent packages with LOW sourcerank (risky infrastructure)",
    "Qualitatively known via Nesbitt's 'unseen infrastructure' post, not quantified at scale",
    """
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg, count(DISTINCT dep) AS dependents
WHERE dependents >= 100
RETURN pkg.platform AS platform,
       pkg.name AS name,
       dependents,
       pkg.sourcerank AS sourcerank,
       pkg.versions_count AS versions,
       pkg.status AS status,
       pkg.language AS language,
       round(CASE WHEN dependents > 0 AND pkg.sourcerank > 0
             THEN 1.0 * dependents / pkg.sourcerank ELSE dependents END, 1) AS risk_ratio
ORDER BY risk_ratio DESC LIMIT 50
""",
    timeout=300,
    interpretation="Risk ratio = dependents/sourcerank. Very high risk_ratio = MANY depend on it but it's LOW quality. These are the most dangerous packages."
)

d2 = section(
    "Popularity Paradox",
    "Stars vs actual adoption: star inflation detection",
    "Informally discussed by Nesbitt; never quantified across all ecosystems",
    """
MATCH (p:Package)-[:HOSTED_ON]->(r:Repository)
WHERE r.stars_count > 500
  AND p.dependent_projects_count IS NOT NULL
  AND p.dependent_projects_count >= 0
WITH p, r,
     toInteger(r.stars_count) AS stars,
     toInteger(p.dependent_projects_count) AS deps
WHERE stars > 0
WITH p, r, stars, deps,
     round(1.0 * stars / (deps + 1), 1) AS stars_per_dep
WHERE stars_per_dep > 200
RETURN p.platform AS platform, p.name AS pkg_name,
       stars, deps, stars_per_dep
ORDER BY stars_per_dep DESC LIMIT 50
""",
    timeout=300,
    interpretation="Very high stars_per_dep = famous/viral but not actually USED as a dependency. Could indicate hype > utility."
)

d3 = section(
    "Popularity Paradox",
    "Hidden gems: high adoption but few stars (critical infrastructure undervalued)",
    "Nesbitt identified anecdotally; not quantified systematically",
    """
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg, count(DISTINCT dep) AS dependents
WHERE dependents >= 200
MATCH (pkg)-[:HOSTED_ON]->(r:Repository)
WHERE r.stars_count < 300 AND r.stars_count >= 0
RETURN pkg.platform AS platform,
       pkg.name AS name,
       dependents,
       r.stars_count AS stars,
       round(toFloat(dependents) / (r.stars_count + 1), 1) AS deps_per_star
ORDER BY deps_per_star DESC LIMIT 40
""",
    timeout=300,
    interpretation="These are the 'invisible load-bearing pillars' — packages that the ecosystem depends on but nobody talks about."
)

# -----------------------------------------------------------------
# E. FORK ECOSYSTEM HEALTH (TRULY NOVEL)
# Never studied: do forks have different dependency hygiene than originals?
# -----------------------------------------------------------------
print("\n[E] Fork Ecosystem Health")

e1 = section(
    "Fork Ecosystem Health",
    "Fork vs. original: dependency count comparison",
    "NEVER STUDIED: fork vs original dependency hygiene comparison",
    """
MATCH (fork:Repository)-[:FORKED_FROM]->(orig:Repository)
MATCH (fork_pkg:Package)-[:HOSTED_ON]->(fork)
MATCH (orig_pkg:Package)-[:HOSTED_ON]->(orig)
WITH fork, orig, fork_pkg, orig_pkg,
     size([(fork_pkg)-[:DEPENDS_ON]->() | 1]) AS fork_deps,
     size([(orig_pkg)-[:DEPENDS_ON]->() | 1]) AS orig_deps
WHERE fork_deps > 0 OR orig_deps > 0
RETURN
  avg(fork_deps - orig_deps) AS avg_dep_delta,
  avg(fork_deps) AS avg_fork_deps,
  avg(orig_deps) AS avg_orig_deps,
  count(*) AS fork_pairs,
  sum(CASE WHEN fork_deps > orig_deps THEN 1 ELSE 0 END) AS forks_with_more_deps,
  sum(CASE WHEN fork_deps < orig_deps THEN 1 ELSE 0 END) AS forks_with_fewer_deps
""",
    timeout=600,
    interpretation="If avg_dep_delta > 0, forks systematically ADD dependencies. If < 0, forks trim dependencies."
)

e2 = section(
    "Fork Ecosystem Health",
    "Fork vs. original: sourcerank comparison",
    "NEVER STUDIED",
    """
MATCH (fork:Repository)-[:FORKED_FROM]->(orig:Repository)
MATCH (fork_pkg:Package)-[:HOSTED_ON]->(fork)
MATCH (orig_pkg:Package)-[:HOSTED_ON]->(orig)
WITH fork_pkg, orig_pkg,
     toInteger(fork_pkg.sourcerank) AS fork_sr,
     toInteger(orig_pkg.sourcerank) AS orig_sr
WHERE fork_sr > 0 OR orig_sr > 0
RETURN
  avg(fork_sr - orig_sr) AS avg_rank_delta,
  avg(fork_sr) AS avg_fork_rank,
  avg(orig_sr) AS avg_orig_rank,
  count(*) AS pairs,
  sum(CASE WHEN fork_sr > orig_sr THEN 1 ELSE 0 END) AS forks_higher_rank,
  sum(CASE WHEN fork_sr < orig_sr THEN 1 ELSE 0 END) AS forks_lower_rank
""",
    timeout=600,
    interpretation="Positive avg_rank_delta means forks IMPROVE upon originals. Negative means forks diverge downward in quality."
)

# -----------------------------------------------------------------
# F. LANGUAGE-PLATFORM MISMATCH (NEW)
# Never quantified: how many packages are coded in the "wrong" language?
# -----------------------------------------------------------------
print("\n[F] Language-Platform Mismatch")

f1 = section(
    "Language-Platform Mismatch",
    "Platform vs. repository language mismatch rates",
    "NEVER STUDIED SYSTEMATICALLY: which platforms have most cross-language packages",
    """
MATCH (p:Package)-[:HOSTED_ON]->(r:Repository)
WHERE r.language IS NOT NULL AND r.language <> ''
  AND p.platform IS NOT NULL AND p.platform <> ''
WITH p.platform AS platform, r.language AS repo_lang, count(*) AS cnt
WHERE cnt >= 50
WITH platform, repo_lang, cnt,
     CASE
       WHEN platform = 'npm' AND repo_lang IN ['JavaScript','TypeScript','CoffeeScript','Vue'] THEN 'expected'
       WHEN platform = 'pypi' AND repo_lang = 'Python' THEN 'expected'
       WHEN platform = 'rubygems' AND repo_lang = 'Ruby' THEN 'expected'
       WHEN platform = 'maven' AND repo_lang IN ['Java','Kotlin','Scala','Groovy','Clojure'] THEN 'expected'
       WHEN platform = 'packagist' AND repo_lang = 'PHP' THEN 'expected'
       WHEN platform = 'nuget' AND repo_lang IN ['C#','F#','Visual Basic'] THEN 'expected'
       WHEN platform = 'cran' AND repo_lang = 'R' THEN 'expected'
       WHEN platform = 'cargo' AND repo_lang = 'Rust' THEN 'expected'
       WHEN platform = 'go' AND repo_lang = 'Go' THEN 'expected'
       WHEN platform = 'clojars' AND repo_lang IN ['Clojure','Java'] THEN 'expected'
       WHEN platform = 'hackage' AND repo_lang = 'Haskell' THEN 'expected'
       WHEN platform = 'hex' AND repo_lang IN ['Elixir','Erlang'] THEN 'expected'
       WHEN platform = 'pub' AND repo_lang = 'Dart' THEN 'expected'
       WHEN platform = 'swift' AND repo_lang = 'Swift' THEN 'expected'
       ELSE 'mismatch'
     END AS match_type
WITH platform,
     sum(CASE WHEN match_type = 'mismatch' THEN cnt ELSE 0 END) AS mismatch_count,
     sum(cnt) AS total_count
WHERE total_count >= 100
RETURN platform, mismatch_count, total_count,
       round(100.0 * mismatch_count / total_count, 1) AS mismatch_pct
ORDER BY mismatch_pct DESC
""",
    timeout=300,
    interpretation="High mismatch% = ecosystem hosts many packages written in unexpected languages. Could indicate wrappers/bindings or misclassification."
)

f2 = section(
    "Language-Platform Mismatch",
    "Most common unexpected language-platform combinations",
    "Never catalogued",
    """
MATCH (p:Package)-[:HOSTED_ON]->(r:Repository)
WHERE r.language IS NOT NULL AND r.language <> ''
WITH p.platform AS platform, r.language AS repo_lang, count(*) AS cnt
WHERE cnt >= 100
  AND NOT (
    (platform = 'npm' AND repo_lang IN ['JavaScript','TypeScript','CoffeeScript'])
    OR (platform = 'pypi' AND repo_lang = 'Python')
    OR (platform = 'rubygems' AND repo_lang = 'Ruby')
    OR (platform = 'maven' AND repo_lang IN ['Java','Kotlin','Scala','Groovy'])
    OR (platform = 'packagist' AND repo_lang = 'PHP')
    OR (platform = 'nuget' AND repo_lang IN ['C#','F#'])
    OR (platform = 'cran' AND repo_lang = 'R')
    OR (platform = 'cargo' AND repo_lang = 'Rust')
    OR (platform = 'go' AND repo_lang = 'Go')
  )
RETURN platform, repo_lang AS actual_language, cnt AS package_count
ORDER BY cnt DESC LIMIT 40
""",
    timeout=300,
    interpretation="Most surprising cross-language packages. e.g., npm packages written in Go likely indicate WASM or CLI tools."
)

# -----------------------------------------------------------------
# G. SEMVER DIVERSITY ACROSS ALL 36 ECOSYSTEMS (NEW)
# Known: npm (95%+ valid semver), Maven (~26% violations), Go (92% by 2023)
# Novel: What about the OTHER 33 ecosystems?
# -----------------------------------------------------------------
print("\n[G] SemVer Diversity Across All 36 Ecosystems")

g1 = section(
    "SemVer Diversity",
    "Version number format compliance by ecosystem",
    "Known for npm, Maven, Go; not for all 36 ecosystems",
    """
MATCH (p:Package)-[:HAS_VERSION]->(v:Version)
WHERE v.number IS NOT NULL AND v.number <> ''
WITH p.platform AS platform, v.number AS ver,
     CASE
       WHEN v.number =~ '^[0-9]+\\.[0-9]+\\.[0-9]+([-+][^,]+)?$' THEN 'strict_semver_3part'
       WHEN v.number =~ '^[0-9]+\\.[0-9]+([-+][^,]+)?$' THEN 'two_part'
       WHEN v.number =~ '^[0-9]+([-+][^,]+)?$' THEN 'one_part'
       WHEN v.number =~ '^v[0-9]+.*' THEN 'v_prefix'
       WHEN v.number =~ '^[0-9].*' THEN 'numeric_other'
       ELSE 'non_numeric'
     END AS fmt
WITH platform, fmt, count(*) AS cnt
WITH platform, collect({fmt: fmt, cnt: cnt}) AS formats, sum(cnt) AS total
UNWIND formats AS f
WITH platform, total, f.fmt AS fmt, f.cnt AS cnt
RETURN platform, fmt, cnt, total,
       round(100.0 * cnt / total, 1) AS pct
ORDER BY platform, cnt DESC
""",
    timeout=900,
    interpretation="Ecosystems with low 'strict_semver_3part' rates have version chaos. This predicts update problems."
)

# -----------------------------------------------------------------
# H. DEPENDENCY MONOCULTURE INDEX (NEW)
# Novel: What fraction of dependency edges point to the TOP 1% of packages?
# Higher concentration = more monoculture = higher ecosystem fragility
# -----------------------------------------------------------------
print("\n[H] Dependency Monoculture Analysis")

h1 = section(
    "Dependency Monoculture",
    "What fraction of all dependency edges go to the top 1% of packages?",
    "Described qualitatively in Zimmermann 2019 but not measured as a monoculture index across all ecosystems",
    """
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WHERE dep.platform = pkg.platform
WITH pkg.platform AS platform, pkg.name AS pkg_name, count(*) AS incoming
WITH platform, collect(incoming) AS counts, sum(incoming) AS total_edges
WITH platform, total_edges,
     size(counts) AS num_pkgs,
     reduce(s = 0, x IN [x IN counts WHERE x >= percentileCont(counts, 0.99)] | s + x) AS top1pct_edges
WHERE total_edges > 0
RETURN platform,
       num_pkgs AS total_packages,
       total_edges,
       top1pct_edges,
       round(100.0 * top1pct_edges / total_edges, 1) AS top1pct_share_of_edges
ORDER BY top1pct_share_of_edges DESC
""",
    timeout=900,
    interpretation="High top1pct_share = MONOCULTURE — a tiny fraction of packages gets almost all dependencies. Ecosystem is fragile."
)

h2 = section(
    "Dependency Monoculture",
    "Gini coefficient proxy for dependency concentration",
    "Never computed for package ecosystems",
    """
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WHERE dep.platform = pkg.platform
WITH pkg.platform AS platform, pkg.name AS pkg_name, count(*) AS incoming
WITH platform, collect(incoming) AS counts, sum(incoming) AS total
// Gini approx: 1 - 2*(sum of cumulative proportions) / n
// Simplified: ratio of top-10 packages to total
WITH platform, total,
     size(counts) AS n,
     reduce(s = 0, x IN counts | s + x * x) AS sum_sq
WHERE total > 0
RETURN platform, n, total,
       round(1.0 * sum_sq / (total * total), 4) AS herfindahl_index
ORDER BY herfindahl_index DESC
""",
    timeout=900,
    interpretation="Herfindahl index: sum of squared market shares. Higher = more concentrated. 1.0 = monopoly (one package gets all deps). 0 = perfectly distributed."
)

# -----------------------------------------------------------------
# I. CIRCULAR DEPENDENCIES (NOVEL AT SCALE)
# Known: individual packages have cycles, but no ecosystem-wide quantification
# -----------------------------------------------------------------
print("\n[I] Circular Dependencies")

i1 = section(
    "Circular Dependencies",
    "Direct circular dependency pairs (A→B→A)",
    "Individual examples known but no ecosystem-wide count",
    """
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)-[:DEPENDS_ON]->(a)
WHERE a.packageId < b.packageId
RETURN a.platform AS platform, a.name AS pkg_a, b.name AS pkg_b,
       a.sourcerank AS sr_a, b.sourcerank AS sr_b
ORDER BY coalesce(a.sourcerank, 0) + coalesce(b.sourcerank, 0) DESC
LIMIT 50
""",
    timeout=300,
    interpretation="Direct circular dependencies are a build system anti-pattern. High-sourcerank cycles are especially concerning."
)

i2 = section(
    "Circular Dependencies",
    "Count of circular dependency pairs by platform",
    "Never measured across all ecosystems",
    """
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)-[:DEPENDS_ON]->(a)
WHERE a.packageId < b.packageId
RETURN a.platform AS platform, count(*) AS circular_pairs
ORDER BY circular_pairs DESC
""",
    timeout=600,
    interpretation="Ecosystems with many circular pairs have dependency graph integrity issues."
)

# -----------------------------------------------------------------
# J. ZOMBIE PACKAGES ACROSS ALL ECOSYSTEMS
# Known: npm 8.2-21.2% deprecated among top 50K (Aqua 2024); PyPI 27% deprecated
# Novel: comprehensive cross-ecosystem comparison using libraries.io status field
# -----------------------------------------------------------------
print("\n[J] Zombie Package Analysis")

j1 = section(
    "Zombie Packages",
    "Top zombie packages: deprecated/removed but most depended upon",
    "Known qualitatively; not ranked across ALL ecosystems by dependent count",
    """
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WHERE pkg.status IN ['Deprecated', 'Unmaintained', 'Hidden', 'Removed']
WITH pkg.platform AS platform, pkg.name AS name, pkg.status AS status,
     pkg.sourcerank AS sr, count(DISTINCT dep) AS dependents
WHERE dependents > 0
RETURN platform, name, status, sr, dependents
ORDER BY dependents DESC LIMIT 60
""",
    timeout=300,
    interpretation="These packages are officially dead but still widely depended upon. Supply chain attack surface."
)

j2 = section(
    "Zombie Packages",
    "Zombie dependency rate by platform",
    "Known for npm only; not comparative across all 36 ecosystems",
    """
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH dep.platform AS platform,
     sum(CASE WHEN pkg.status IN ['Deprecated', 'Unmaintained', 'Hidden', 'Removed'] THEN 1 ELSE 0 END) AS zombie_edges,
     count(*) AS total_edges
WHERE total_edges >= 200
RETURN platform, zombie_edges, total_edges,
       round(100.0 * zombie_edges / total_edges, 2) AS zombie_dep_pct
ORDER BY zombie_dep_pct DESC
""",
    timeout=300,
    interpretation="High zombie_dep_pct = ecosystem has lots of dead-package dependencies. Indicates slow ecosystem hygiene."
)

# -----------------------------------------------------------------
# K. MAINTAINER HEALTH PROXY (COMMUNITY SIZE)
# -----------------------------------------------------------------
print("\n[K] Maintainer Health")

k1 = section(
    "Maintainer Health",
    "Solo vs team-maintained projects by ecosystem",
    "Bus factor studied for individual projects; comparative distribution across all ecosystems NOT done",
    """
MATCH (p:Package)-[:HOSTED_ON]->(r:Repository)
WHERE r.contributors_count > 0
WITH p.platform AS platform, toInteger(r.contributors_count) AS contributors,
     CASE
       WHEN r.contributors_count = 1 THEN '1_solo'
       WHEN r.contributors_count <= 3 THEN '2_tiny_2_3'
       WHEN r.contributors_count <= 10 THEN '3_small_4_10'
       WHEN r.contributors_count <= 50 THEN '4_medium_11_50'
       ELSE '5_large_51plus'
     END AS team_size
WITH platform, team_size, count(*) AS pkg_count
ORDER BY platform, team_size
RETURN platform, team_size, pkg_count
""",
    timeout=300,
    interpretation="Ecosystems dominated by solo projects are more vulnerable to abandonment. Ecosystem-level comparison is novel."
)

k2 = section(
    "Maintainer Health",
    "Orphaned packages (no repo) with active dependents",
    "Not studied across all ecosystems",
    """
MATCH (pkg:Package)
WHERE NOT EXISTS { MATCH (pkg)-[:HOSTED_ON]->(:Repository) }
WITH pkg, size([(pkg)<-[:DEPENDS_ON]-() | 1]) AS dep_count
WHERE dep_count >= 5
RETURN pkg.platform AS platform, pkg.name AS name,
       pkg.status AS status, pkg.sourcerank AS sourcerank, dep_count
ORDER BY dep_count DESC LIMIT 50
""",
    timeout=300,
    interpretation="Packages with no source repo but still depended upon. These are especially hard to audit for security."
)

# -----------------------------------------------------------------
# L. CROSS-PLATFORM PACKAGE NAMES (NAMESPACE COLLISION)
# Novel: measuring the scale of same-name packages across different ecosystems
# -----------------------------------------------------------------
print("\n[L] Cross-Platform Package Name Analysis")

l1 = section(
    "Cross-Platform Names",
    "Packages existing on 3+ platforms simultaneously",
    "Kannee 2022 studied cross-published packages but didn't count same-name collisions systematically",
    """
MATCH (p:Package)
WITH p.name AS name, collect(DISTINCT p.platform) AS platforms
WHERE size(platforms) >= 3
RETURN name, platforms, size(platforms) AS platform_count,
       size([x IN platforms WHERE x = 'npm']) > 0 AND
       size([x IN platforms WHERE x = 'pypi']) > 0 AS npm_and_pypi
ORDER BY platform_count DESC, name
LIMIT 80
""",
    timeout=300,
    interpretation="Names on 5+ platforms are either deliberate cross-publishing (one project) OR namespace collision risk (different projects, same name)."
)

l2 = section(
    "Cross-Platform Names",
    "Most popular 2-platform name pairs",
    "Not previously catalogued",
    """
MATCH (p:Package)
WITH p.name AS name, collect(DISTINCT p.platform) AS platforms
WHERE size(platforms) = 2
WITH platforms, count(name) AS name_count
RETURN platforms[0] AS platform_a, platforms[1] AS platform_b, name_count
ORDER BY name_count DESC LIMIT 30
""",
    timeout=300,
    interpretation="High name_count for a platform pair = systematic cross-publishing. This identifies ecosystem pairs that commonly share packages."
)

# -----------------------------------------------------------------
# M. DEPENDENCY PINNING CULTURE
# Known: npm uses ^ (caret) most; PyPI uses floating major
# Novel: other 34 ecosystems + correlation with zombie dep rate
# -----------------------------------------------------------------
print("\n[M] Dependency Pinning Culture")

m1 = section(
    "Pinning Culture",
    "Dependency constraint styles per ecosystem",
    "Known for npm and PyPI; not for all 36 ecosystems",
    """
MATCH (a:Package)-[d:DEPENDS_ON]->(b:Package)
WHERE d.requirements IS NOT NULL AND d.requirements <> ''
WITH a.platform AS platform, d.requirements AS req,
     CASE
       WHEN d.requirements STARTS WITH '^' THEN 'caret_range'
       WHEN d.requirements STARTS WITH '~>' THEN 'tilde_gt_range'
       WHEN d.requirements STARTS WITH '~' THEN 'tilde_range'
       WHEN d.requirements STARTS WITH '>=' THEN 'gte_range'
       WHEN d.requirements STARTS WITH '>' THEN 'gt_range'
       WHEN d.requirements =~ '[0-9]+\\.[0-9]+\\.[0-9]+' AND NOT d.requirements CONTAINS '<'
            AND NOT d.requirements CONTAINS '>' AND NOT d.requirements CONTAINS '^'
            AND NOT d.requirements CONTAINS '~' THEN 'exact_pin'
       WHEN d.requirements IN ['*', 'latest', 'any', ''] THEN 'any_version'
       WHEN d.requirements CONTAINS ' || ' THEN 'or_expression'
       WHEN d.requirements CONTAINS ',' THEN 'range_comma'
       ELSE 'other'
     END AS pin_type
WITH platform, pin_type, count(*) AS cnt
WITH platform, collect({pt: pin_type, cnt: cnt}) AS pts, sum(cnt) AS total
UNWIND pts AS pt
RETURN platform, pt.pt AS pin_type, pt.cnt AS count, total,
       round(100.0 * pt.cnt / total, 1) AS pct
ORDER BY platform, pt.cnt DESC
""",
    timeout=900,
    interpretation="Ecosystems using 'exact_pin' heavily may have rigid update culture. 'any_version' or '*' is dangerous."
)

# -----------------------------------------------------------------
# N. TOP PACKAGES BY PAGERANK PROXY (NOVEL: ALL 36 ECOSYSTEMS)
# True PageRank requires GDS; we use 2-hop weighted in-degree as proxy
# -----------------------------------------------------------------
print("\n[N] PageRank Proxy Analysis")

n1 = section(
    "PageRank Proxy",
    "Top packages by 2-hop weighted importance per ecosystem",
    "Published PageRank for CRAN only; never done across all 36 in one analysis",
    """
MATCH (direct_dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg, count(DISTINCT direct_dep) AS direct_in
WHERE direct_in >= 20
MATCH (transitive:Package)-[:DEPENDS_ON]->(direct_dep2:Package)-[:DEPENDS_ON]->(pkg)
WITH pkg, direct_in, count(DISTINCT transitive) AS transitive_in
RETURN pkg.platform AS platform,
       pkg.name AS name,
       direct_in,
       transitive_in,
       direct_in + transitive_in AS weighted_importance,
       pkg.sourcerank AS sourcerank
ORDER BY weighted_importance DESC LIMIT 60
""",
    timeout=600,
    interpretation="Packages with high weighted_importance affect BOTH their direct AND indirect dependents. These are the true infrastructure pillars."
)

# -----------------------------------------------------------------
# O. ECOSYSTEM HEALTH SCOREBOARD
# Novel: Composite health metric per ecosystem
# -----------------------------------------------------------------
print("\n[O] Ecosystem Health Scoreboard")

o1 = section(
    "Ecosystem Health",
    "Per-ecosystem composite health metrics",
    "No cross-ecosystem health comparison using these combined metrics",
    """
MATCH (p:Package)
WITH p.platform AS platform,
     count(p) AS total_pkgs,
     avg(CASE WHEN p.sourcerank > 0 THEN p.sourcerank ELSE null END) AS avg_sourcerank,
     sum(CASE WHEN p.status IN ['Deprecated','Unmaintained','Removed','Hidden'] THEN 1 ELSE 0 END) AS dead_pkgs,
     sum(CASE WHEN p.versions_count > 0 THEN 1 ELSE 0 END) AS has_versions
WHERE total_pkgs >= 100
RETURN platform,
       total_pkgs,
       round(avg_sourcerank, 1) AS avg_sourcerank,
       dead_pkgs,
       round(100.0 * dead_pkgs / total_pkgs, 1) AS dead_pct,
       has_versions,
       round(100.0 * has_versions / total_pkgs, 1) AS has_versions_pct
ORDER BY avg_sourcerank DESC
""",
    timeout=300,
    interpretation="Ecosystem health: high avg_sourcerank + low dead_pct + high has_versions_pct = healthy ecosystem."
)

# -----------------------------------------------------------------
# P. DEPENDENCY REQUIREMENTS ACROSS VERSIONS WITHIN ONE PACKAGE
# Novel: Do packages progressively ADD or REMOVE dependencies over versions?
# -----------------------------------------------------------------
print("\n[P] Dependency Growth Over Package Lifetime]")

p1 = section(
    "Dependency Growth",
    "Packages that grew dependencies most aggressively over time",
    "Technical lag (falling behind) is known; dependency GROWTH trajectory is not",
    """
MATCH (pkg:Package)-[:HAS_VERSION]->(v:Version)
WITH pkg, count(v) AS ver_count
WHERE ver_count >= 10
WITH pkg, ver_count
MATCH (pkg)-[:DEPENDS_ON]->(dep:Package)
WITH pkg, ver_count, count(DISTINCT dep) AS direct_dep_count
WHERE direct_dep_count > 0
RETURN pkg.platform AS platform,
       pkg.name AS name,
       ver_count AS version_count,
       direct_dep_count AS current_deps,
       round(1.0 * direct_dep_count / ver_count, 2) AS deps_per_version,
       pkg.sourcerank AS sourcerank
ORDER BY deps_per_version DESC LIMIT 30
""",
    timeout=300,
    interpretation="High deps_per_version = each new version introduced ~1 new dependency. May indicate feature creep or dependency accumulation."
)

# =============================================================================
# GENERATE MARKDOWN REPORT
# =============================================================================
print("\n\n" + "="*65)
print("Generating report...")

timestamp = datetime.now().isoformat()

report = f"""# Libraries.io Novel Insights Report

**Generated:** {timestamp}
**Dataset:** Libraries.io v1.6.0 (January 2020)
**Database:** Neo4j {DB_NAME}
**Scope:** Analyses designed to find insights NOT in existing literature

---

## Database Scale

"""

if db_stats:
    report += fmt_table(db_stats) + "\n\n"
if edge_stats:
    report += fmt_table(edge_stats) + "\n\n"

report += """---

## Key Research Gap: What This Analysis Covers

Prior work (Zimmermann 2019, Decan 2019, Bommarito 2019/2021, Kannee 2022) has studied:
- npm, PyPI, CRAN, Maven, Cargo, NuGet, CPAN, Packagist, RubyGems individually
- Vulnerability propagation in npm/Maven/PyPI
- SemVer adherence in npm/Maven/Go
- License incompatibilities in PyPI/npm/RubyGems
- Bus factor for individual projects
- Technical lag (mainly npm)

**This analysis covers:** All 36 ecosystems simultaneously, with novel metrics
never computed before.

---

"""

for s in sections:
    report += f"## {s['title']}: {s['analysis']}\n\n"
    report += f"**Research context:** {s['known_state']}\n\n"
    if s['result']:
        report += fmt_table(s['result']) + "\n\n"
    else:
        report += "*Query failed or returned no results.*\n\n"
    if s['interpretation']:
        report += f"**Interpretation:** {s['interpretation']}\n\n"
    report += "---\n\n"

with open(REPORT_FILE, 'w') as f:
    f.write(report)

# Also save raw results as JSON
json_file = OUTPUT_DIR / f"raw_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
json_data = {}
for s in sections:
    if s['result']:
        json_data[s['analysis']] = {
            'columns': s['result']['columns'],
            'rows': s['result']['rows'],
            'known_state': s['known_state'],
            'interpretation': s['interpretation']
        }
with open(json_file, 'w') as f:
    json.dump(json_data, f, indent=2)

print(f"\nReport saved to: {REPORT_FILE}")
print(f"Raw JSON: {json_file}")
print("\nDONE!")
