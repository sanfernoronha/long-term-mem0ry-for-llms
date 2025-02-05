#!/bin/bash
chown -R neo4j:neo4j /var/lib/neo4j/plugins
chmod -R 755 /var/lib/neo4j/plugins
/docker-entrypoint.sh