import os
import requests

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

# Get ALL npm packages with amp > 1000x and repos > 50k - with their repo data if available
# This is the definitive list
print("=== ALL high-amp npm packages WITH repos (amp>1000, repos>50k) ===")
rows, err = query("""
MATCH (r:Repository)-[:HOSTED_ON]->(pkg:Package {platform:'npm'})
WHERE pkg.dep_repos_count > 50000
  AND pkg.dep_projects_count > 0
  AND pkg.dep_repos_count * 1.0 / (pkg.dep_projects_count + 1) > 1000
  AND NOT pkg.name STARTS WITH '@babel/'
  AND NOT pkg.name STARTS WITH '@jest/'
  AND NOT pkg.name STARTS WITH 'workbox-'
  AND NOT pkg.name STARTS WITH '@svgr/'
  AND NOT pkg.name STARTS WITH '@types/'
  AND NOT pkg.name STARTS WITH 'babel-'
WITH pkg, r,
     round(pkg.dep_repos_count * 1.0 / (pkg.dep_projects_count + 1)) AS amp
ORDER BY amp DESC
RETURN pkg.name AS name,
       pkg.dep_repos_count AS repos,
       pkg.dep_projects_count AS direct_pkgs,
       amp,
       r.contributors_count AS contributors,
       r.stars_count AS stars,
       r.name_with_owner AS repo
""")
if err:
    print("ERR:", err)
elif rows:
    print(f"Total with repos: {len(rows)}")
    for r in rows: print(r)

# Also: how many total qualify (with or without repo)?
print("\n=== TOTAL high-amp npm packages (amp>1000, repos>50k), no org filters ===")
rows, err = query("""
MATCH (pkg:Package {platform:'npm'})
WHERE pkg.dep_repos_count > 50000
  AND pkg.dep_projects_count > 0
  AND pkg.dep_repos_count * 1.0 / (pkg.dep_projects_count + 1) > 1000
RETURN count(*) AS total
""")
if rows: print(rows[0])

print("\n=== After filtering out @babel, @jest, workbox, @svgr, @types, babel- ===")
rows, err = query("""
MATCH (pkg:Package {platform:'npm'})
WHERE pkg.dep_repos_count > 50000
  AND pkg.dep_projects_count > 0
  AND pkg.dep_repos_count * 1.0 / (pkg.dep_projects_count + 1) > 1000
  AND NOT pkg.name STARTS WITH '@babel/'
  AND NOT pkg.name STARTS WITH '@jest/'
  AND NOT pkg.name STARTS WITH 'workbox-'
  AND NOT pkg.name STARTS WITH '@svgr/'
  AND NOT pkg.name STARTS WITH '@types/'
  AND NOT pkg.name STARTS WITH 'babel-'
RETURN count(*) AS filtered_total
""")
if rows: print(rows[0])

# Get the full list without the org filter, to understand what the landscape looks like
print("\n=== Full list of high-amp npm packages (amp>1000, repos>50k) WITH repos ===")
rows, err = query("""
MATCH (r:Repository)-[:HOSTED_ON]->(pkg:Package {platform:'npm'})
WHERE pkg.dep_repos_count > 50000
  AND pkg.dep_projects_count > 0
  AND pkg.dep_repos_count * 1.0 / (pkg.dep_projects_count + 1) > 1000
WITH pkg, r,
     round(pkg.dep_repos_count * 1.0 / (pkg.dep_projects_count + 1)) AS amp
ORDER BY amp DESC LIMIT 50
RETURN pkg.name AS name,
       pkg.dep_repos_count AS repos,
       pkg.dep_projects_count AS direct_pkgs,
       amp,
       r.contributors_count AS contributors,
       r.stars_count AS stars,
       r.name_with_owner AS repo
""")
if rows:
    print(f"Count: {len(rows)}")
    for r in rows: print(r)

