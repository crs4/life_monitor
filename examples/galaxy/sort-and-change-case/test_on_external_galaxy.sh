#!/usr/bin/env bash

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

# change these as needed
GALAXY_URL=http://localhost:8080
GALAXY_KEY=fb7df8a266c05d4817710a7a99cd39c5

pushd "${this_dir}"
# looks for sort-and-change-case-test.yml in the same dir as
# sort-and-change-case.ga
planemo test \
	--engine external_galaxy \
	--galaxy_admin_key "${GALAXY_KEY}" \
	--galaxy_user_key "${GALAXY_KEY}" \
	--galaxy_url "${GALAXY_URL}" \
	sort-and-change-case.ga
popd
