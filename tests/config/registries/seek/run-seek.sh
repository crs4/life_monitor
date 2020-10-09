#!/bin/bash


#docker network create seek_default
docker run -d --network seek_default -p 3001:3000 \
  -v $(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro -v $(pwd):/certs:ro \
  -v $(pwd)/data/config:/seek/config:rw \
  -v $(pwd)/data/public:/seek/public:rw \
  -v $(pwd)/data/solr:/seek/solr:rw \
  -v $(pwd)/data/log:/seek/log:rw \
  -v $(pwd)/data/tmp:/seek/tmp:rw \
  -v $(pwd)/data/db.sqlite3:/seek/sqlite3-db/production.sqlite3:rw \
  -v $(pwd)/data/filestore:/seek/filestore:rw \
  --name seek-test fairdom/seek:workflow


#--add-host seek.org:192.168.1.167 