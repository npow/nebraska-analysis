"""
Compare 2020 (Libraries.io) and 2026 (ecosyste.ms) Nebraska blocks.
"""
import json, csv
from collections import Counter, defaultdict

import os

RESULTS_2020 = os.environ.get("RESULTS_2020", "results/ecosystems_results.json")
RESULTS_2026 = os.environ.get("RESULTS_2026", "results/nebraska_2026_full.csv")

# Load 2020 data (502 packages with API-verified 2026 status)
with open(RESULTS_2020) as f:
    data_2020_raw = json.load(f)

# Build 2020 package dict
pkgs_2020 = {p['name']: p for p in data_2020_raw}

# Load 2026 full Nebraska list from database
pkgs_2026 = {}
with open(RESULTS_2026) as f:
    reader = csv.DictReader(f)
    for row in reader:
        pkgs_2026[row['name']] = {
            'name': row['name'],
            'repos': int(row['dependent_repos_count']),
            'pkgs': int(row['dependent_packages_count']),
            'amp': float(row['amp']),
            'owner': row['github_owner'],
            'maintainers': int(row['maintainers_count']),
        }

names_2020 = set(pkgs_2020.keys())
names_2026 = set(pkgs_2026.keys())

# Categories
stable = names_2020 & names_2026          # Nebraska in both
dropped = names_2020 - names_2026         # Was Nebraska in 2020, not in 2026
new_2026 = names_2026 - names_2020        # New Nebraska in 2026

print(f"2020 Nebraska blocks: {len(names_2020)}")
print(f"2026 Nebraska blocks: {len(names_2026)}")
print(f"  Still Nebraska (stable): {len(stable)} ({100*len(stable)/len(names_2020):.0f}% of 2020 list)")
print(f"  Dropped out:             {len(dropped)} ({100*len(dropped)/len(names_2020):.0f}% of 2020 list)")
print(f"  New in 2026:             {len(new_2026)} ({100*len(new_2026)/len(names_2026):.0f}% of 2026 list)")
print()

# Stable: how did their reach change?
print("=== Biggest growers (stable packages, ranked by repo growth) ===")
growth = []
for name in stable:
    old = pkgs_2020[name]['old_repos']
    new = pkgs_2026[name]['repos']
    growth.append((name, old, new, new/old if old > 0 else 0))
growth.sort(key=lambda x: x[3], reverse=True)
for name, old, new, mult in growth[:15]:
    print(f"  {name:40s}  {old:>8,} → {new:>8,}  ({mult:.0f}×)")

print()
print("=== Biggest decliners (stable packages, ranked by repo shrinkage) ===")
growth.sort(key=lambda x: x[3])
for name, old, new, mult in growth[:10]:
    print(f"  {name:40s}  {old:>8,} → {new:>8,}  ({mult:.2f}×)")

print()

# What dropped out?
print("=== Dropped from Nebraska (top 20 by 2020 repo count) ===")
dropped_list = [(name, pkgs_2020[name]['old_repos'], pkgs_2020[name].get('new_repos', 0)) for name in dropped]
dropped_list.sort(key=lambda x: x[1], reverse=True)
for name, old, new in dropped_list[:20]:
    # Get 2020 maintainer
    maintainer = pkgs_2020[name].get('maintainers', ['?'])
    maint_str = maintainer[0] if maintainer else '?'
    print(f"  {name:40s}  {old:>8,} repos in 2020 → {new:>8,} in 2026 ({maint_str})")

print()

# What's new?
print("=== New Nebraska blocks in 2026 (top 20 by repo count) ===")
new_list = [(name, pkgs_2026[name]['repos'], pkgs_2026[name]['amp'], pkgs_2026[name]['owner']) for name in new_2026]
new_list.sort(key=lambda x: x[1], reverse=True)
for name, repos, amp, owner in new_list[:20]:
    print(f"  {name:40s}  {repos:>8,} repos, amp={amp:.0f}×, owner={owner}")

print()

# Maintainer shift
print("=== Maintainer shift: 2020 vs 2026 (stable packages only) ===")
# 2020 concentration (stable packages)
stable_2020_maintainers = []
for name in stable:
    m = pkgs_2020[name].get('maintainers', ['unknown'])
    stable_2020_maintainers.append(m[0] if m else 'unknown')
cnt_2020_stable = Counter(stable_2020_maintainers)

# 2026 owner for stable packages
stable_2026_owners = [pkgs_2026[name]['owner'] for name in stable]
cnt_2026_stable = Counter(stable_2026_owners)

print("\n  2020 maintainer concentration (stable packages):")
for maint, count in cnt_2020_stable.most_common(8):
    print(f"    {maint:20s}: {count}")
print("\n  2026 owner concentration (stable packages):")
for owner, count in cnt_2026_stable.most_common(8):
    print(f"    {owner:20s}: {count}")

print()

# Summary statistics for the blog post
print("=== Key numbers for blog post ===")
stable_repos_2020 = sum(pkgs_2020[n]['old_repos'] for n in stable)
stable_repos_2026 = sum(pkgs_2026[n]['repos'] for n in stable)
print(f"Stable packages total reach: {stable_repos_2020:,} (2020) → {stable_repos_2026:,} (2026) = {stable_repos_2026/stable_repos_2020:.1f}× growth")

# The "dead" blocks: Joyent/request ecosystem
joyent_dropped = [name for name in dropped if pkgs_2020[name].get('maintainers', [''])[0] in ('hichaelmart', 'mikeal', 'joyent', 'substack') or 'request' in name.lower() or pkgs_2020[name]['old_repos'] > 400000]
print(f"\nMajor ecosystem collapse examples from dropped list:")
for name in dropped_list[:5]:
    print(f"  {name[0]}: {name[1]:,} → {name[2]:,} repos")
