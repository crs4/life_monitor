#!/bin/bash

rm -Rf /seek/filestore/*
cp -a data/filestore/* /seek/filestore/
cp -a data/db.sqlite3 /seek/sqlite3-db/production.sqlite3

docker/entrypoint.sh
