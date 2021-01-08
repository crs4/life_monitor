#!/bin/bash

set -ex

script_path="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
root_project_path="$(realpath "${script_path}/../../../../")"
tmp_path="/tmp/seek_data"
data_path="${tmp_path}/data"
archive_filename="data.tar.gz"

seek_container_id=$(docker-compose -f "${root_project_path}/docker-compose.yml" ps -q seek)

rm -rf "${data_path}"
mkdir -p "${data_path}"
docker cp ${seek_container_id}:/seek/filestore ${data_path}/filestore
docker cp ${seek_container_id}:/seek/sqlite3-db/production.sqlite3 ${data_path}/db.sqlite3

pushd ${tmp_path}
tar -czvf ${archive_filename} data
popd

mv "${tmp_path}/${archive_filename}" .
rm -rf ${tmp_path}