import os
import requests
from collections import Counter

NEO4J_URL = os.environ.get("NEO4J_URL", "http://localhost:7474/db/neo4j/tx/commit")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASS", "password")
AUTH = (NEO4J_USER, NEO4J_PASS)

def query(cypher, params=None):
    payload = {"statements": [{"statement": cypher, "parameters": params or {}}]}
    r = requests.post(NEO4J_URL, json=payload, auth=AUTH, timeout=120)
    data = r.json()
    if data.get("errors"):
        return None, data["errors"]
    results = data["results"][0]
    cols = results["columns"]
    rows = [dict(zip(cols, row["row"])) for row in results["data"]]
    return rows, None

EXCLUSIONS = """
  AND NOT pkg.name STARTS WITH '@babel/'
  AND NOT pkg.name STARTS WITH '@jest/'
  AND NOT pkg.name STARTS WITH 'workbox-'
  AND NOT pkg.name STARTS WITH '@svgr/'
  AND NOT pkg.name STARTS WITH '@types/'
  AND NOT pkg.name STARTS WITH 'babel-'
  AND NOT pkg.name STARTS WITH '@webassemblyjs/'
"""

def run_combo(amp_threshold, repos_threshold, contrib_threshold):
    rows, err = query(f"""
MATCH (pkg:Package {{platform:'npm'}})-[:HOSTED_ON]->(r:Repository)
WHERE pkg.dep_repos_count > {repos_threshold}
  AND pkg.dep_projects_count > 0
  AND toFloat(r.contributors_count) <= {contrib_threshold}
  AND pkg.dep_repos_count * 1.0 / (pkg.dep_projects_count + 1) > {amp_threshold}
  {EXCLUSIONS}
RETURN pkg.name AS name, pkg.dep_repos_count AS repos,
       r.name_with_owner AS repo, r.contributors_count AS contributors
""")
    if err or not rows:
        return 0, {}

    owner_counter = Counter()
    for row in rows:
        repo = row.get('repo')
        if repo:
            owner = repo.split('/')[0].lower()
            owner_counter[owner] += 1

    return len(rows), owner_counter

# Grid of thresholds
amp_thresholds    = [500, 1000, 2000, 5000]
repos_thresholds  = [25000, 50000, 100000]
contrib_thresholds = [1, 3, 5]

print(f"{'amp':>6} {'repos':>7} {'contrib':>8} | {'count':>6} | top-2 owners (name: n, pct%)")
print("-" * 80)

for amp in amp_thresholds:
    for repos in repos_thresholds:
        for contrib in contrib_thresholds:
            count, owner_counter = run_combo(amp, repos, contrib)
            if count == 0:
                print(f"{amp:>6} {repos:>7} {contrib:>8} | {'0':>6} | -")
                continue
            top2 = owner_counter.most_common(2)
            top2_str = ", ".join(
                f"{o}: {c} ({100*c//count}%)" for o, c in top2
            )
            top2_total = sum(c for _, c in top2)
            print(f"{amp:>6} {repos:>7} {contrib:>8} | {count:>6} | {top2_str} → top-2={100*top2_total//count}%")
