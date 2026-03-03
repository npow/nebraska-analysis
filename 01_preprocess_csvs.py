#!/usr/bin/env python3
"""
Preprocess libraries.io 1.6.0 CSV files into Neo4j admin import format.
Optimized for the actual schema of the dataset.

Key design decisions:
- Use projects_with_repository_fields.csv as primary node source
  (has both package + repo data inline, easier to process)
- Use dependencies.csv for DEPENDS_ON edges (100M rows)
- Use versions.csv for Version nodes
- Skip tags.csv (12GB, not needed)
- Skip repository_dependencies.csv (not needed for core analyses)
"""
import csv
import os
import sys
from pathlib import Path

# Path to extracted Libraries.io 1.6.0 CSV files
# Download from: https://zenodo.org/records/3626071
DATA_DIR = Path(os.environ.get("LIBRARIES_IO_DIR", "data/libraries-1.6.0-2020-01-12"))

# Neo4j import directory (neo4j-admin import reads from here)
IMPORT_DIR = Path(os.environ.get("NEO4J_IMPORT_DIR", "/var/lib/neo4j/import"))
IMPORT_DIR.mkdir(parents=True, exist_ok=True)

csv.field_size_limit(10 * 1024 * 1024)

def safe(v, maxlen=200):
    if v is None or v == '':
        return ''
    return str(v).replace('\n', ' ').replace('\r', '').replace('"', "'")[:maxlen]

def clean_platform(p):
    """Normalize platform names to lowercase."""
    return (p or '').strip().lower()

def pkg_id(platform, name):
    """Unique Package node ID."""
    return f"{clean_platform(platform)}::{(name or '').strip()}"


print("=" * 70)
print("Libraries.io -> Neo4j preprocessing pipeline")
print("=" * 70)

CSV_DIR = DATA_DIR

# =========================================================================
# STEP 1: Package nodes + Repository nodes from projects_with_repo_fields
# =========================================================================
print("\n[1/4] Processing packages + repositories (projects_with_repo_fields.csv)...")

proj_repo_file = CSV_DIR / "projects_with_repository_fields-1.6.0-2020-01-12.csv"

pkg_header = [
    "packageId:ID(Package)", "platform", "name",
    "description", "homepage_url", "licenses", "language", "status",
    "versions_count:int", "sourcerank:int",
    "dep_projects_count:int", "dep_repos_count:int",
    "latest_release", "repo_id", "repo_url",
    ":LABEL"
]

repo_header = [
    "repoId:ID(Repository)",
    "host_type", "name_with_owner", "description",
    "fork:boolean", "stars_count:int", "forks_count:int",
    "open_issues_count:int", "contributors_count:int",
    "language", "license", "sourcerank:int",
    "default_branch", "fork_source",
    "has_readme:boolean", "has_changelog:boolean",
    "has_contributing:boolean", "has_coc:boolean",
    ":LABEL"
]

hosted_on_header = [":START_ID(Package)", ":END_ID(Repository)", ":TYPE"]
fork_header = [":START_ID(Repository)", ":END_ID(Repository)", ":TYPE"]

pkg_count = 0
repo_count = 0
hosted_count = 0

# Track repo names for FORKED_FROM edges
repo_name_to_id = {}  # name_with_owner -> repoId

with open(proj_repo_file, 'r', encoding='utf-8', errors='replace') as fin, \
     open(IMPORT_DIR / "packages.csv", 'w', newline='', encoding='utf-8') as fout_pkg, \
     open(IMPORT_DIR / "repositories.csv", 'w', newline='', encoding='utf-8') as fout_repo, \
     open(IMPORT_DIR / "hosted_on.csv", 'w', newline='', encoding='utf-8') as fout_hosted:

    pkg_w = csv.writer(fout_pkg)
    repo_w = csv.writer(fout_repo)
    hosted_w = csv.writer(fout_hosted)

    pkg_w.writerow(pkg_header)
    repo_w.writerow(repo_header)
    hosted_w.writerow(hosted_on_header)

    reader = csv.DictReader(fin)
    seen_repos = set()

    for row in reader:
        platform = clean_platform(row.get('Platform', ''))
        name = (row.get('Name', '') or '').strip()
        if not name:
            continue

        pid = pkg_id(platform, name)

        # Write Package node
        pkg_w.writerow([
            pid,
            platform,
            safe(name),
            safe(row.get('Description', ''), 400),
            safe(row.get('Homepage URL', '')),
            safe(row.get('Licenses', '')),
            safe(row.get('Language', '')),
            safe(row.get('Status', '')),
            row.get('Versions Count', '') or '0',
            row.get('SourceRank', '') or '0',
            row.get('Dependent Projects Count', '') or '0',
            row.get('Dependent Repositories Count', '') or '0',
            safe(row.get('Latest Release Number', '')),
            safe(row.get('Repository ID', '')),
            safe(row.get('Repository URL', '')),
            'Package'
        ])
        pkg_count += 1

        # Write Repository node (if we have one and haven't seen it)
        repo_id_raw = (row.get('Repository ID', '') or '').strip()
        if repo_id_raw and repo_id_raw not in seen_repos:
            seen_repos.add(repo_id_raw)
            repo_node_id = f"repo::{repo_id_raw}"

            name_with_owner = safe(row.get('Repository Name with Owner', ''))
            if name_with_owner:
                repo_name_to_id[name_with_owner] = repo_node_id

            repo_w.writerow([
                repo_node_id,
                safe(row.get('Repository Host Type', '')),
                name_with_owner,
                safe(row.get('Repository Description', ''), 300),
                '1' if str(row.get('Repository Fork?', '')).lower() in ('1', 'true', 't') else '0',
                row.get('Repository Stars Count', '') or '0',
                row.get('Repository Forks Count', '') or '0',
                row.get('Repository Open Issues Count', '') or '0',
                row.get('Repository Contributors Count', '') or '0',
                safe(row.get('Repository Language', '')),
                safe(row.get('Repository License', '')),
                row.get('Repository SourceRank', '') or '0',
                safe(row.get('Repository Default branch', '')),
                safe(row.get('Repository Fork Source Name with Owner', '')),
                '1' if row.get('Repository Readme filename', '') else '0',
                '1' if row.get('Repository Changelog filename', '') else '0',
                '1' if row.get('Repository Contributing guidelines filename', '') else '0',
                '1' if row.get('Repository Code of Conduct filename', '') else '0',
                'Repository'
            ])
            repo_count += 1

            # Write HOSTED_ON edge
            hosted_w.writerow([pid, repo_node_id, 'HOSTED_ON'])
            hosted_count += 1

        if pkg_count % 200000 == 0:
            print(f"  ... {pkg_count:,} packages, {repo_count:,} repos processed")

print(f"  Done: {pkg_count:,} Package nodes, {repo_count:,} Repository nodes, {hosted_count:,} HOSTED_ON rels")

# Now write FORKED_FROM edges
print("  Writing FORKED_FROM relationships...")
fork_count = 0
with open(IMPORT_DIR / "repositories.csv", 'r', encoding='utf-8') as fin, \
     open(IMPORT_DIR / "forks.csv", 'w', newline='', encoding='utf-8') as fout:

    writer = csv.writer(fout)
    writer.writerow(fork_header)
    reader = csv.DictReader(fin)
    for row in reader:
        if str(row.get('fork:boolean', '')) == '1':
            fork_source = (row.get('fork_source', '') or '').strip()
            if fork_source and fork_source in repo_name_to_id:
                writer.writerow([
                    row['repoId:ID(Repository)'],
                    repo_name_to_id[fork_source],
                    'FORKED_FROM'
                ])
                fork_count += 1

print(f"  Done: {fork_count:,} FORKED_FROM rels")


# =========================================================================
# STEP 2: Version nodes + HAS_VERSION rels
# =========================================================================
print("\n[2/4] Processing versions (versions.csv)...")

versions_file = CSV_DIR / "versions-1.6.0-2020-01-12.csv"

ver_header = [
    "versionId:ID(Version)", "platform", "project_name",
    "number", "published_ts", ":LABEL"
]
has_ver_header = [":START_ID(Package)", ":END_ID(Version)", ":TYPE"]

ver_count = 0
with open(versions_file, 'r', encoding='utf-8', errors='replace') as fin, \
     open(IMPORT_DIR / "versions.csv", 'w', newline='', encoding='utf-8') as fver, \
     open(IMPORT_DIR / "has_version.csv", 'w', newline='', encoding='utf-8') as frel:

    ver_w = csv.writer(fver)
    rel_w = csv.writer(frel)
    ver_w.writerow(ver_header)
    rel_w.writerow(has_ver_header)

    reader = csv.DictReader(fin)
    for row in reader:
        row_id = (row.get('ID', '') or '').strip()
        if not row_id:
            continue

        platform = clean_platform(row.get('Platform', ''))
        project_name = (row.get('Project Name', '') or '').strip()
        number = safe(row.get('Number', ''))
        pub_ts = safe(row.get('Published Timestamp', ''))

        vid = f"ver::{row_id}"
        pid = pkg_id(platform, project_name)

        ver_w.writerow([vid, platform, project_name, number, pub_ts, 'Version'])
        rel_w.writerow([pid, vid, 'HAS_VERSION'])

        ver_count += 1
        if ver_count % 2000000 == 0:
            print(f"  ... {ver_count:,} versions processed")

print(f"  Done: {ver_count:,} Version nodes")


# =========================================================================
# STEP 3: DEPENDS_ON relationships from dependencies.csv (LARGEST FILE ~100M rows)
# =========================================================================
print("\n[3/4] Processing dependencies (dependencies.csv) - THIS WILL TAKE A WHILE...")
print("  The dependencies file is ~20GB with ~100M rows")

deps_file = CSV_DIR / "dependencies-1.6.0-2020-01-12.csv"

# Header: ID,Platform,Project Name,Project ID,Version Number,Version ID,
#         Dependency Name,Dependency Platform,Dependency Kind,Optional Dependency,
#         Dependency Requirements,Dependency Project ID

dep_header = [
    ":START_ID(Package)", ":END_ID(Package)", ":TYPE",
    "requirements", "kind", "optional:boolean",
    "version_number"
]

dep_count = 0
skipped_dep = 0

with open(deps_file, 'r', encoding='utf-8', errors='replace') as fin, \
     open(IMPORT_DIR / "depends_on.csv", 'w', newline='', encoding='utf-8') as fout:

    writer = csv.writer(fout)
    writer.writerow(dep_header)

    reader = csv.DictReader(fin)
    for row in reader:
        src_platform = clean_platform(row.get('Platform', ''))
        src_name = (row.get('Project Name', '') or '').strip()
        dep_name = (row.get('Dependency Name', '') or '').strip()
        dep_platform = clean_platform(row.get('Dependency Platform', ''))

        if not src_name or not dep_name:
            skipped_dep += 1
            continue

        # If dep platform empty, use same as source
        if not dep_platform:
            dep_platform = src_platform

        src_id = pkg_id(src_platform, src_name)
        dep_id = pkg_id(dep_platform, dep_name)

        optional = '1' if str(row.get('Optional Dependency', '')).lower() in ('1', 'true', 't') else '0'

        writer.writerow([
            src_id, dep_id, 'DEPENDS_ON',
            safe(row.get('Dependency Requirements', ''), 80),
            safe(row.get('Dependency Kind', '')),
            optional,
            safe(row.get('Version Number', ''))
        ])

        dep_count += 1
        if dep_count % 5000000 == 0:
            print(f"  ... {dep_count:,} dependencies processed ({skipped_dep:,} skipped)")

print(f"  Done: {dep_count:,} DEPENDS_ON rels ({skipped_dep:,} skipped)")


# =========================================================================
# STEP 4: Summary
# =========================================================================
print("\n" + "=" * 70)
print("PREPROCESSING COMPLETE")
print("=" * 70)
print(f"\nFiles in {IMPORT_DIR}:")
total_size = 0
for f in sorted(IMPORT_DIR.glob("*.csv")):
    size = f.stat().st_size
    total_size += size
    print(f"  {f.name:<45} {size/1e9:.2f} GB")
print(f"\n  Total: {total_size/1e9:.2f} GB")
print("\nReady for: neo4j-admin database import full")
