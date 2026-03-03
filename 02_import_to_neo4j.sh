#!/bin/bash
# Import preprocessed CSVs into Neo4j using neo4j-admin bulk import
# This is ~100x faster than LOAD CSV for large datasets

export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
IMPORT_DIR=/var/lib/neo4j/import
DB_NAME=libraries

echo "=== Stopping Neo4j ==="
neo4j stop
sleep 5

echo "=== Running neo4j-admin import ==="
# neo4j-admin database import is the correct command for Neo4j 5+
neo4j-admin database import full \
  --database=$DB_NAME \
  --overwrite-destination=true \
  --report-file=/tmp/neo4j-import-report.txt \
  --bad-tolerance=100000 \
  --skip-bad-relationships=true \
  --skip-duplicate-nodes=true \
  --nodes=Package=$IMPORT_DIR/packages.csv \
  --nodes=Version=$IMPORT_DIR/versions.csv \
  --nodes=Repository=$IMPORT_DIR/repositories.csv \
  --relationships=HAS_VERSION=$IMPORT_DIR/has_version.csv \
  --relationships=DEPENDS_ON=$IMPORT_DIR/depends_on.csv \
  --relationships=HOSTED_ON=$IMPORT_DIR/hosted_on.csv \
  --relationships=REPO_DEPENDS_ON=$IMPORT_DIR/repo_depends_on.csv \
  --relationships=FORKED_FROM=$IMPORT_DIR/forks.csv \
  2>&1 | tee /tmp/neo4j-import-progress.txt

echo "=== Import complete. Starting Neo4j ==="
neo4j start
sleep 15

echo "=== Creating indexes ==="
# Use HTTP API to create indexes
curl -s -X POST http://localhost:7474/db/$DB_NAME/tx/commit \
  -H "Content-Type: application/json" \
  -d '{
    "statements": [
      {"statement": "CREATE INDEX pkg_platform IF NOT EXISTS FOR (p:Package) ON (p.platform)"},
      {"statement": "CREATE INDEX pkg_name IF NOT EXISTS FOR (p:Package) ON (p.name)"},
      {"statement": "CREATE INDEX pkg_sourcerank IF NOT EXISTS FOR (p:Package) ON (p.sourcerank)"},
      {"statement": "CREATE INDEX pkg_lang IF NOT EXISTS FOR (p:Package) ON (p.language)"},
      {"statement": "CREATE INDEX pkg_status IF NOT EXISTS FOR (p:Package) ON (p.status)"},
      {"statement": "CREATE INDEX pkg_platform_name IF NOT EXISTS FOR (p:Package) ON (p.platform, p.name)"},
      {"statement": "CREATE INDEX repo_host IF NOT EXISTS FOR (r:Repository) ON (r.host_type)"},
      {"statement": "CREATE INDEX repo_stars IF NOT EXISTS FOR (r:Repository) ON (r.stars_count)"},
      {"statement": "CREATE INDEX repo_lang IF NOT EXISTS FOR (r:Repository) ON (r.language)"}
    ]
  }' | python3 -c "import json,sys; d=json.load(sys.stdin); print('Index errors:', d.get('errors',[]))"

echo "=== Done! ==="
