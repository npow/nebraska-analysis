"""
Nebraska block analysis on ecosyste.ms 2026 data.
Streams the tar.gz, processes npm packages only, computes amplification ratios.
"""
import tarfile, json, sys
from collections import Counter

EXCLUDE_PREFIXES = ['@babel/', '@jest/', 'workbox-', '@svgr/', '@types/', 'babel-', '@webassemblyjs/']
EXCLUDE_ORGS = ['npm']  # commercially maintained namespaces

def is_excluded(name):
    if any(name.startswith(p) for p in EXCLUDE_PREFIXES):
        return True
    return False

def get_maintainer(pkg):
    maintainers = pkg.get('maintainers') or []
    if maintainers and isinstance(maintainers, list):
        m = maintainers[0]
        if isinstance(m, dict):
            return (m.get('login') or m.get('name') or '').lower()
    repo = pkg.get('repository_url') or ''
    if 'github.com/' in repo:
        parts = repo.split('github.com/')[1].split('/')
        if parts:
            return parts[0].lower()
    return 'unknown'

print("Opening archive...", flush=True)
tf = tarfile.open('/root/code/libraries-analysis/data/packages-2026-02-05.tar.gz', 'r|gz')

nebraska = []
total_npm = 0
processed = 0

for member in tf:
    if not member.isfile():
        continue
    # Only process npm files
    if 'npmjs' not in member.name and 'npm' not in member.name:
        continue

    f = tf.extractfile(member)
    if not f:
        continue

    processed += 1
    if processed % 10 == 0:
        print(f"  Files processed: {processed}, npm packages: {total_npm}, Nebraska found: {len(nebraska)}", flush=True)

    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            pkg = json.loads(line)
        except:
            continue

        # Must be npm
        ecosystem = pkg.get('ecosystem') or pkg.get('registry') or ''
        if 'npm' not in str(ecosystem).lower():
            continue

        name = pkg.get('name') or ''
        if is_excluded(name):
            continue

        repos = pkg.get('dependent_repos_count') or 0
        pkgs_count = pkg.get('dependent_packages_count') or 0

        if repos < 50000:
            continue

        total_npm += 1
        amp = repos / (pkgs_count + 1) if pkgs_count is not None else 0

        if amp > 1000:
            maintainer = get_maintainer(pkg)
            # Exclude npm org
            if maintainer in EXCLUDE_ORGS:
                continue
            nebraska.append({
                'name': name,
                'repos': repos,
                'pkgs': pkgs_count,
                'amp': round(amp, 1),
                'maintainer': maintainer,
            })

    f.close()

tf.close()

print(f"\nDone. Total npm packages with >50K repos: {total_npm}", flush=True)
print(f"Nebraska blocks (amp>1000x, repos>50K): {len(nebraska)}", flush=True)

# Sort by repos
nebraska.sort(key=lambda x: x['repos'], reverse=True)

print("\n=== Top 20 Nebraska blocks ===")
for p in nebraska[:20]:
    print(f"  {p['name']}: repos={p['repos']:,}, pkgs={p['pkgs']:,}, amp={p['amp']}x, maintainer={p['maintainer']}")

# Owner concentration
owner_counter = Counter(p['maintainer'] for p in nebraska)
owner_repos = {}
for p in nebraska:
    o = p['maintainer']
    owner_repos[o] = owner_repos.get(o, 0) + p['repos']

total = len(nebraska)
print(f"\n=== Owner concentration ({total} packages) ===")
for owner, count in owner_counter.most_common(15):
    pct = 100 * count // total if total else 0
    print(f"  {owner}: {count} ({pct}%), total_repos={owner_repos[owner]:,}")

top2 = sum(c for _, c in owner_counter.most_common(2))
print(f"\nTop-2 share: {top2}/{total} = {100*top2//total if total else 0}%")

# Save results
import json as json2
with open('/root/code/libraries-analysis/results/nebraska_2026.json', 'w') as f:
    json2.dump({'total': total, 'packages': nebraska, 'owner_counts': dict(owner_counter.most_common(20))}, f)
print("\nSaved to results/nebraska_2026.json")
