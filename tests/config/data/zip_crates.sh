#!/usr/bin/env bash

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

names=(
    ro-crate-cwl-basefreqsum
    ro-crate-cwl-basefreqsum-invalid-service-type
    ro-crate-galaxy-sortchangecase
    ro-crate-galaxy-sortchangecase-invalid-service-url
)

for n in "${names[@]}"; do
    echo -en "\n*** ${n} ***\n"
    pushd "${this_dir}/crates/${n}"
    zip_file="${n}.crate.zip"
    rm -f "${zip_file}"
    zip -r "${zip_file}" *
    mv "${zip_file}" ..
    popd
done
