// =============================================================================
// NOVEL ANALYSES - libraries.io graph insights
// Queries designed to find things NOT in existing literature
// =============================================================================

// ---- SETUP: Switch to the libraries database ----
// :use libraries


// =============================================================================
// ANALYSIS 1: CROSS-PLATFORM DEPENDENCY LEAKAGE
// Novel: Are packages secretly depending on packages from OTHER ecosystems?
// Known: npm->npm, pypi->pypi etc.
// Novel: Cross-platform deps (npm package depending on PyPI package)
// =============================================================================

// 1a. Find cross-platform dependencies (where source and target platforms differ)
MATCH (a:Package)-[d:DEPENDS_ON]->(b:Package)
WHERE a.platform <> b.platform
  AND a.platform <> '' AND b.platform <> ''
WITH a.platform AS src_platform, b.platform AS dep_platform, count(*) AS cross_count
ORDER BY cross_count DESC
LIMIT 50
RETURN src_platform, dep_platform, cross_count;

// 1b. Which specific packages are most commonly targeted cross-platform?
MATCH (a:Package)-[d:DEPENDS_ON]->(b:Package)
WHERE a.platform <> b.platform
WITH b.platform AS target_platform, b.name AS dep_name, count(DISTINCT a) AS dependents
WHERE dependents > 10
RETURN target_platform, dep_name, dependents
ORDER BY dependents DESC LIMIT 30;


// =============================================================================
// ANALYSIS 2: DEPENDENCY PHANTOM PACKAGES
// Packages that are depended upon by MANY packages but don't exist in the registry
// This reveals "ghost dependencies" - packages referenced but never published
// This is NOVEL: no one has quantified the phantom dependency problem at scale
// =============================================================================

MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WHERE NOT EXISTS { MATCH (b)-[:HAS_VERSION]->(:Version) }
  AND b.versions_count = 0
WITH b.platform AS platform, b.name AS phantom_name,
     count(DISTINCT a) AS dependent_count
WHERE dependent_count > 5
RETURN platform, phantom_name, dependent_count
ORDER BY dependent_count DESC LIMIT 100;

// 2b. Phantom dependency rate by platform
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WITH b, count(DISTINCT a) AS dependents
WITH b.platform AS platform,
     sum(CASE WHEN b.versions_count = 0 THEN dependents ELSE 0 END) AS phantom_deps,
     sum(dependents) AS total_deps
WHERE total_deps > 100
RETURN platform,
       phantom_deps,
       total_deps,
       round(100.0 * phantom_deps / total_deps, 2) AS phantom_rate_pct
ORDER BY phantom_rate_pct DESC;


// =============================================================================
// ANALYSIS 3: VERSION PINNING vs RANGE ANALYSIS
// Novel: Correlate pinning strictness with actual stability (# of breaking changes)
// Hypothesis: Strict pinning doesn't correlate with fewer breaks -
//             projects using ranges may be MORE resilient
// =============================================================================

// 3a. Distribution of dependency requirement patterns
MATCH (a:Package)-[d:DEPENDS_ON]->(b:Package)
WHERE d.requirements IS NOT NULL AND d.requirements <> ''
WITH d.requirements AS req,
     CASE
       WHEN d.requirements =~ '\\^.*' THEN 'caret_range'
       WHEN d.requirements =~ '~.*' THEN 'tilde_range'
       WHEN d.requirements =~ '>=.*' THEN 'gte_range'
       WHEN d.requirements =~ '>.*' THEN 'gt_range'
       WHEN d.requirements =~ '.*\\*.*' THEN 'wildcard'
       WHEN d.requirements =~ '[0-9]+\\.[0-9]+\\.[0-9]+' THEN 'exact_pin'
       WHEN d.requirements = '*' OR d.requirements = 'latest' THEN 'any'
       ELSE 'other'
     END AS pin_type,
     a.platform AS platform
WITH platform, pin_type, count(*) AS cnt
ORDER BY platform, cnt DESC
RETURN platform, pin_type, cnt,
       round(100.0 * cnt / sum(cnt) OVER (PARTITION BY platform), 2) AS pct_of_platform;

// 3b. Does stricter pinning correlate with higher sourcerank?
// (Sourcerank is a proxy for "quality" packages)
MATCH (a:Package)-[d:DEPENDS_ON]->(b:Package)
WHERE d.requirements IS NOT NULL
WITH a,
     sum(CASE WHEN d.requirements =~ '[0-9]+\\.[0-9]+.*' THEN 1 ELSE 0 END) AS exact_pins,
     sum(CASE WHEN d.requirements =~ '[\\^~>].*' THEN 1 ELSE 0 END) AS range_deps,
     count(d) AS total_deps,
     a.sourcerank AS sourcerank
WHERE total_deps >= 5 AND sourcerank > 0
RETURN
  round(1.0 * exact_pins / total_deps, 2) AS exact_pin_ratio,
  avg(sourcerank) AS avg_sourcerank,
  count(a) AS num_packages
ORDER BY exact_pin_ratio;


// =============================================================================
// ANALYSIS 4: THE "BIG BANG" DEPENDENCY CLUSTERING
// Novel: Find packages that are simultaneously depended on by ALL major ecosystems
// These are truly universal infrastructure - not just popular within one ecosystem
// =============================================================================

MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WHERE a.platform <> b.platform OR a.platform = b.platform
WITH b, collect(DISTINCT a.platform) AS depender_platforms
WHERE size(depender_platforms) >= 3
RETURN b.name AS universal_package,
       b.platform AS package_platform,
       depender_platforms,
       size(depender_platforms) AS platform_count
ORDER BY platform_count DESC, b.name
LIMIT 50;


// =============================================================================
// ANALYSIS 5: DEPENDENCY DEBT - ABANDONED PACKAGES WITH MANY DEPENDENTS
// Novel: Calculate the "technical debt score" = dependents * time_since_update
// We define a "zombie package" as: has dependents, status=deprecated/unmaintained
// =============================================================================

MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WHERE b.status IN ['Deprecated', 'Unmaintained', 'Hidden', 'Removed']
WITH b, count(DISTINCT a) AS dependent_count
WHERE dependent_count > 0
RETURN b.platform AS platform,
       b.name AS zombie_package,
       b.status AS status,
       b.sourcerank AS sourcerank,
       dependent_count
ORDER BY dependent_count DESC LIMIT 100;

// 5b. What fraction of the ecosystem depends on deprecated packages?
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WITH a.platform AS platform,
     sum(CASE WHEN b.status IN ['Deprecated', 'Unmaintained', 'Hidden', 'Removed'] THEN 1 ELSE 0 END) AS zombie_deps,
     count(*) AS total_deps
WHERE total_deps > 100
RETURN platform, zombie_deps, total_deps,
       round(100.0 * zombie_deps / total_deps, 2) AS zombie_dep_pct
ORDER BY zombie_dep_pct DESC;


// =============================================================================
// ANALYSIS 6: SEMANTIC VERSIONING ADHERENCE - VERSION NUMBER ANALYSIS
// Novel: What % of packages actually follow semver?
// Prior work only sampled npm; we do ALL platforms
// =============================================================================

MATCH (p:Package)-[:HAS_VERSION]->(v:Version)
WHERE v.number IS NOT NULL AND v.number <> ''
WITH p.platform AS platform,
     v.number AS version,
     CASE
       WHEN v.number =~ '^[0-9]+\\.[0-9]+\\.[0-9]+(-.*)?$' THEN 'strict_semver'
       WHEN v.number =~ '^[0-9]+\\.[0-9]+(-.*)?$' THEN 'minor_semver'
       WHEN v.number =~ '^[0-9]+(-.*)?$' THEN 'major_only'
       WHEN v.number =~ '^v[0-9].*' THEN 'v_prefix'
       WHEN v.number =~ '^[0-9].*' THEN 'numeric_other'
       ELSE 'non_numeric'
     END AS semver_type
WITH platform, semver_type, count(*) AS cnt
ORDER BY platform, cnt DESC
RETURN platform, semver_type, cnt,
       round(100.0 * cnt / sum(cnt) OVER (PARTITION BY platform), 2) AS pct;


// =============================================================================
// ANALYSIS 7: THE "POPULARITY PARADOX"
// Novel: Are the most-depended-upon packages actually well-maintained?
// Hypothesis: High dependents != high sourcerank (quality)
// This would challenge the assumption that "popular = trustworthy"
// =============================================================================

MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg, count(DISTINCT dep) AS direct_dependents
WHERE direct_dependents >= 100
RETURN pkg.platform AS platform,
       pkg.name AS package_name,
       direct_dependents,
       pkg.sourcerank AS sourcerank,
       pkg.status AS status,
       pkg.versions_count AS version_count
ORDER BY direct_dependents DESC LIMIT 200;

// 7b. Correlation: high dependents + low sourcerank = dangerous packages
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg, count(DISTINCT dep) AS direct_dependents
WHERE direct_dependents >= 50 AND pkg.sourcerank <= 3 AND pkg.sourcerank > 0
RETURN pkg.platform, pkg.name, direct_dependents, pkg.sourcerank, pkg.status
ORDER BY direct_dependents DESC LIMIT 50;


// =============================================================================
// ANALYSIS 8: CIRCULAR DEPENDENCY DETECTION
// Novel: Find packages with CIRCULAR dependencies (A->B->A or longer cycles)
// This is practically harmful - no known comprehensive cross-platform study
// =============================================================================

// 8a. Direct circular deps (A depends on B and B depends on A)
MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)-[:DEPENDS_ON]->(a)
WHERE a.packageId < b.packageId  // avoid duplicates
RETURN a.platform, a.name AS pkg_a, b.name AS pkg_b, b.platform
LIMIT 100;

// 8b. Longer cycles (length 3) - more subtle
MATCH p = (a:Package)-[:DEPENDS_ON*2..3]->(a)
WHERE length(p) > 1
WITH a, length(p) AS cycle_len
RETURN a.platform, a.name, cycle_len, count(*) AS cycle_count
ORDER BY cycle_count DESC LIMIT 50;


// =============================================================================
// ANALYSIS 9: TRANSITIVE BLAST RADIUS
// Novel: If package X disappeared, how many packages would be TRANSITIVELY broken?
// This is the "nuclear dependency" problem - not just direct but transitive impact
// =============================================================================

// Find top candidates (high direct dependents) then estimate transitive impact
// Note: Full transitive traversal is expensive - do for top packages only

// 9a. First, find packages with most direct dependents per platform
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg, count(DISTINCT dep) AS direct_dependents
RETURN pkg.platform, pkg.name, direct_dependents
ORDER BY direct_dependents DESC LIMIT 20;

// 9b. Transitive blast radius for a specific package (example: npm/lodash)
// MATCH (pkg:Package {platform: 'npm', name: 'lodash'})
// MATCH (affected:Package)-[:DEPENDS_ON*1..5]->(pkg)
// RETURN count(DISTINCT affected) AS transitive_blast_radius;


// =============================================================================
// ANALYSIS 10: FORK ECOSYSTEM HEALTH
// Novel: Do forked repositories have better/worse dependency hygiene?
// Are forks creating "dependency divergence" (fork updates deps, original doesn't)?
// =============================================================================

// 10a. Fork vs original: dependency count comparison
MATCH (fork:Repository)-[:FORKED_FROM]->(original:Repository)
MATCH (fork_pkg:Package)-[:HOSTED_ON]->(fork)
MATCH (orig_pkg:Package)-[:HOSTED_ON]->(original)
WITH fork_pkg, orig_pkg,
     size([(fork_pkg)-[:DEPENDS_ON]->() | 1]) AS fork_dep_count,
     size([(orig_pkg)-[:DEPENDS_ON]->() | 1]) AS orig_dep_count
WHERE fork_dep_count > 0 OR orig_dep_count > 0
RETURN
  avg(fork_dep_count) AS avg_fork_deps,
  avg(orig_dep_count) AS avg_orig_deps,
  count(*) AS num_fork_pairs;


// =============================================================================
// ANALYSIS 11: LANGUAGE vs PLATFORM MISMATCH
// Novel: Are packages listed on the wrong platform?
// e.g., Python code published to npm, Ruby code on PyPI
// =============================================================================

MATCH (p:Package)-[:HOSTED_ON]->(r:Repository)
WHERE r.language IS NOT NULL AND r.language <> ''
  AND p.platform IS NOT NULL AND p.platform <> ''
WITH p.platform AS pkg_platform, r.language AS repo_language, count(*) AS cnt
WHERE cnt > 100
// Expected matches
WITH pkg_platform, repo_language, cnt,
     CASE
       WHEN pkg_platform = 'npm' AND repo_language = 'JavaScript' THEN 'expected'
       WHEN pkg_platform = 'npm' AND repo_language = 'TypeScript' THEN 'expected'
       WHEN pkg_platform = 'pypi' AND repo_language = 'Python' THEN 'expected'
       WHEN pkg_platform = 'rubygems' AND repo_language = 'Ruby' THEN 'expected'
       WHEN pkg_platform = 'maven' AND repo_language IN ['Java', 'Kotlin', 'Scala'] THEN 'expected'
       WHEN pkg_platform = 'packagist' AND repo_language = 'PHP' THEN 'expected'
       WHEN pkg_platform = 'nuget' AND repo_language IN ['C#', 'F#', 'VB'] THEN 'expected'
       WHEN pkg_platform = 'cran' AND repo_language = 'R' THEN 'expected'
       WHEN pkg_platform = 'cargo' AND repo_language = 'Rust' THEN 'expected'
       WHEN pkg_platform = 'go' AND repo_language = 'Go' THEN 'expected'
       ELSE 'mismatch'
     END AS match_type
RETURN pkg_platform, repo_language, cnt, match_type
ORDER BY match_type DESC, cnt DESC;


// =============================================================================
// ANALYSIS 12: THE DEPENDENCY MONOCULTURE PROBLEM
// Novel: What % of the total dependency graph points to just top-N packages?
// A high concentration means ecosystem-wide fragility
// =============================================================================

// 12a. Global dependency concentration (Gini coefficient proxy)
MATCH (dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg.platform AS platform, pkg.name AS pkg_name, count(*) AS incoming
WITH platform,
     collect(incoming) AS counts
WITH platform, counts,
     reduce(s = 0, x IN counts | s + x) AS total,
     size(counts) AS num_pkgs
WITH platform, total, num_pkgs,
     // Top 1% of packages
     toInteger(num_pkgs * 0.01) + 1 AS top_1pct_count
RETURN platform, num_pkgs, total, top_1pct_count
ORDER BY total DESC;


// =============================================================================
// ANALYSIS 13: LICENSE COMPATIBILITY HELL
// Novel: Quantify how often incompatible licenses are mixed in dependency trees
// GPL depending on MIT is fine; MIT depending on GPL can be viral
// No one has done this comprehensively across all platforms
// =============================================================================

MATCH (a:Package)-[:DEPENDS_ON]->(b:Package)
WHERE a.licenses IS NOT NULL AND b.licenses IS NOT NULL
  AND a.licenses <> '' AND b.licenses <> ''
WITH a.licenses AS src_license, b.licenses AS dep_license,
     a.platform AS platform, count(*) AS cnt
WHERE cnt > 100
// Flag GPL -> permissive (potentially problematic for the permissive package)
WITH platform, src_license, dep_license, cnt,
     CASE
       WHEN (src_license CONTAINS 'GPL' OR src_license CONTAINS 'AGPL')
            AND (dep_license CONTAINS 'MIT' OR dep_license CONTAINS 'Apache'
                 OR dep_license CONTAINS 'BSD') THEN 'gpl_on_permissive'
       WHEN (src_license CONTAINS 'MIT' OR src_license CONTAINS 'Apache')
            AND (dep_license CONTAINS 'GPL' OR dep_license CONTAINS 'AGPL') THEN 'permissive_depends_on_copyleft'
       ELSE 'same_family'
     END AS compat_type
RETURN platform, compat_type, count(*) AS license_pair_count, sum(cnt) AS total_dep_edges
ORDER BY total_dep_edges DESC;


// =============================================================================
// ANALYSIS 14: THE "LONG TAIL" OF MAINTAINERSHIP
// Novel: What is the distribution of packages per developer?
// Using repository contributor count as proxy
// Quantify what % of packages are truly solo projects
// =============================================================================

MATCH (p:Package)-[:HOSTED_ON]->(r:Repository)
WHERE r.contributors_count > 0
WITH p.platform AS platform, r.contributors_count AS contributors
WITH platform, contributors,
     CASE
       WHEN contributors = 1 THEN 'solo'
       WHEN contributors <= 3 THEN 'tiny_team'
       WHEN contributors <= 10 THEN 'small_team'
       WHEN contributors <= 50 THEN 'medium_team'
       ELSE 'large_team'
     END AS team_size
WITH platform, team_size, count(*) AS pkg_count
RETURN platform, team_size, pkg_count,
       round(100.0 * pkg_count / sum(pkg_count) OVER (PARTITION BY platform), 2) AS pct
ORDER BY platform, pkg_count DESC;


// =============================================================================
// ANALYSIS 15: DEPENDENCY VELOCITY - VERSION CHURN
// Novel: Are frequently-releasing packages actually better maintained?
// Or does high version churn indicate instability?
// =============================================================================

MATCH (p:Package)-[:HAS_VERSION]->(v:Version)
WITH p, count(v) AS version_count
WHERE version_count >= 3
WITH p.platform AS platform,
     p.name AS pkg_name,
     p.sourcerank AS sourcerank,
     p.dependent_projects_count AS dependents,
     version_count
ORDER BY version_count DESC
WITH platform,
     avg(version_count) AS avg_versions,
     avg(sourcerank) AS avg_sourcerank,
     percentileCont(version_count, 0.5) AS median_versions,
     percentileCont(version_count, 0.9) AS p90_versions,
     percentileCont(version_count, 0.99) AS p99_versions,
     count(*) AS num_packages
RETURN platform, avg_versions, median_versions, p90_versions, p99_versions,
       avg_sourcerank, num_packages
ORDER BY avg_versions DESC;


// =============================================================================
// ANALYSIS 16: PLATFORM MIGRATION PATTERNS
// Novel: Find packages that exist with the SAME name on MULTIPLE platforms
// Are they the same project? (Cross-published) or namespace squatting?
// =============================================================================

MATCH (p:Package)
WITH p.name AS name, collect(DISTINCT p.platform) AS platforms
WHERE size(platforms) >= 2
RETURN name, platforms, size(platforms) AS platform_count
ORDER BY platform_count DESC, name
LIMIT 100;

// 16b. Find the most common cross-platform name collisions
MATCH (p:Package)
WITH p.name AS name, collect(p.platform) AS platforms
WHERE size(platforms) >= 3
WITH platforms, count(name) AS name_count
RETURN platforms, name_count
ORDER BY name_count DESC LIMIT 20;


// =============================================================================
// ANALYSIS 17: DEPENDENCY GRAPH DIAMETER AND SMALL-WORLD PROPERTIES
// Novel: What is the actual diameter of each ecosystem's dependency graph?
// Prior work claimed "small world" but didn't measure actual diameter
// =============================================================================

// 17a. Get basic graph statistics per platform
MATCH (p:Package)
WHERE p.platform = 'npm'
WITH count(p) AS npm_nodes
MATCH ()-[d:DEPENDS_ON]->()
WITH npm_nodes, count(d) AS npm_edges
RETURN npm_nodes, npm_edges,
       round(1.0 * npm_edges / npm_nodes, 2) AS avg_out_degree;

// 17b. Find the most "central" packages (highest betweenness proxy)
// Use 2-hop neighborhood size as betweenness proxy
MATCH (pkg:Package)
WHERE pkg.platform = 'npm'
WITH pkg,
     size([(pkg)<-[:DEPENDS_ON]-() | 1]) AS in_degree,
     size([(pkg)-[:DEPENDS_ON]->() | 1]) AS out_degree
WHERE in_degree > 0 AND out_degree > 0
RETURN pkg.name, in_degree, out_degree,
       in_degree * out_degree AS centrality_proxy
ORDER BY centrality_proxy DESC LIMIT 50;


// =============================================================================
// ANALYSIS 18: SECURITY-CRITICAL PACKAGES BY PROPAGATION POTENTIAL
// Novel: Score packages by "security blast radius" =
//        (# direct dependents) * (avg transitive dependent count)
// This identifies which packages most need security investment
// =============================================================================

// 18a. 2-hop propagation impact (direct + 1 level of transitive)
MATCH (direct_dep:Package)-[:DEPENDS_ON]->(pkg:Package)
WITH pkg, collect(DISTINCT direct_dep) AS direct_dependents
WITH pkg, size(direct_dependents) AS direct_count, direct_dependents
UNWIND direct_dependents AS dd
MATCH (transitive_dep:Package)-[:DEPENDS_ON]->(dd)
WITH pkg, direct_count, count(DISTINCT transitive_dep) AS transitive_count
WHERE direct_count >= 50
RETURN pkg.platform, pkg.name, direct_count, transitive_count,
       direct_count + transitive_count AS total_2hop_impact
ORDER BY total_2hop_impact DESC LIMIT 50;


// =============================================================================
// ANALYSIS 19: ORPHANED PACKAGES WITH ACTIVE DEPENDENTS
// Novel: Packages where the repository is gone/deleted but packages still depended on
// This is the "link rot" problem for package ecosystems
// =============================================================================

MATCH (pkg:Package)
WHERE pkg.status IN ['Removed', 'Hidden', 'Deprecated']
   OR NOT EXISTS { (pkg)-[:HOSTED_ON]->(:Repository) }
WITH pkg, size([(pkg)<-[:DEPENDS_ON]-() | 1]) AS dependent_count
WHERE dependent_count > 0
RETURN pkg.platform, pkg.name, pkg.status, dependent_count
ORDER BY dependent_count DESC LIMIT 100;


// =============================================================================
// ANALYSIS 20: DEPENDENCY GRAPH EVOLUTION SIGNAL
// Novel: Using version publication timestamps to reconstruct when ecosystems
// became "mature" (when did dependency depth stop growing?)
// =============================================================================

// Distribution of version publication years
MATCH (v:Version)
WHERE v.published_ts IS NOT NULL AND v.published_ts <> ''
WITH substring(v.published_ts, 0, 4) AS year, v.platform AS platform, count(*) AS releases
WHERE year >= '2010' AND year <= '2020'
RETURN platform, year, releases
ORDER BY platform, year;
