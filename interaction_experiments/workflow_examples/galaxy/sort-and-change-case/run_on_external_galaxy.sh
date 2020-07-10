#!/usr/bin/env bash

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

# change these as needed
GALAXY_URL=http://localhost:8080
GALAXY_KEY=fb7df8a266c05d4817710a7a99cd39c5
OUT_DIR=galaxy_out

pushd "${this_dir}"
mkdir -p "${OUT_DIR}"
planemo run \
	--engine external_galaxy \
	--galaxy_admin_key "${GALAXY_KEY}" \
	--galaxy_user_key "${GALAXY_KEY}" \
	--galaxy_url "${GALAXY_URL}" \
	--outdir "${OUT_DIR}" \
	sort-and-change-case.ga \
	sort-and-change-case-job.yml 
popd
