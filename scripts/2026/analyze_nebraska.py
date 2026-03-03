"""
Analyze the 2026 Nebraska blocks from the ecosyste.ms data.
"""
import csv
from collections import Counter, defaultdict

# Known individual→org mappings (where one person controls the org)
ORG_TO_PERSON = {
    'chalk': 'sindresorhus',
    'sindresorhus': 'sindresorhus',
    'micromatch': 'jonschlinkert',
    'jonschlinkert': 'jonschlinkert',
    'wooorm': 'wooorm',
    'mafintosh': 'mafintosh',
    'ljharb': 'ljharb',
    'isaacs': 'isaacs',
    'kevva': 'kevva',
    'inspect-js': 'inspect-js',  # unknown individual
    'es-shims': 'ljharb',  # Jordan Harband runs es-shims
    'blakeembrey': 'blakeembrey',
    'pugjs': 'pugjs',
    'browserify': 'browserify',
    'gulpjs': 'gulpjs',
}

# Institutional/project orgs to note separately
INSTITUTIONAL = {'npm', 'firebase', 'aws', 'jestjs', 'google', 'googleapis',
                 'microsoft', 'facebook', 'meta', 'vercel', 'netlify'}

import os
CSV_PATH = os.environ.get("NEBRASKA_CSV", "results/nebraska_2026_full.csv")

packages = []
with open(CSV_PATH) as f:
    reader = csv.DictReader(f)
    for row in reader:
        packages.append({
            'name': row['name'],
            'repos': int(row['dependent_repos_count']),
            'pkgs': int(row['dependent_packages_count']),
            'amp': float(row['amp']),
            'owner': row['github_owner'],
            'maintainers': int(row['maintainers_count']),
            'namespace': row['namespace'],
        })

print(f"Total Nebraska blocks (2026): {len(packages)}")
print(f"Total repo reach: {sum(p['repos'] for p in packages):,}")
print()

# Owner concentration
owner_counter = Counter(p['owner'] for p in packages)
owner_repos = defaultdict(int)
for p in packages:
    owner_repos[p['owner']] += p['repos']

print("=== Top 25 owners (GitHub org/user) ===")
for owner, count in owner_counter.most_common(25):
    pct = 100 * count / len(packages)
    print(f"  {owner:20s}: {count:4d} pkgs ({pct:.1f}%), {owner_repos[owner]:>12,} repos")

print()

# Top packages
print("=== Top 25 Nebraska packages by repo reach ===")
for p in packages[:25]:
    print(f"  {p['name']:45s} {p['repos']:>8,} repos, amp={p['amp']:.0f}x, owner={p['owner']}, maintainers={p['maintainers']}")

print()

# Maintainers distribution
maint_counts = Counter(p['maintainers'] for p in packages)
print("=== Maintainers count distribution ===")
for m in sorted(maint_counts.keys()):
    count = maint_counts[m]
    pct = 100 * count / len(packages)
    print(f"  {m} maintainer(s): {count} ({pct:.1f}%)")

single_or_two = sum(maint_counts.get(m, 0) for m in [1, 2])
print(f"\n  1-2 maintainers: {single_or_two} ({100*single_or_two/len(packages):.1f}%)")

print()

# Packages by individual owners (exclude institutional)
individual_packages = [p for p in packages if p['owner'] not in INSTITUTIONAL and p['owner'] != 'unknown']
print(f"=== Nebraska blocks by likely-individual owners: {len(individual_packages)} ===")
indiv_counter = Counter(p['owner'] for p in individual_packages)
for owner, count in indiv_counter.most_common(15):
    pct = 100 * count / len(packages)
    print(f"  {owner:20s}: {count:4d} ({pct:.1f}%)")

print()

# Check amplification extremes
print("=== Highest amplification ===")
sorted_by_amp = sorted(packages, key=lambda x: x['amp'], reverse=True)
for p in sorted_by_amp[:10]:
    print(f"  {p['name']:45s} amp={p['amp']:.0f}x, repos={p['repos']:,}")
