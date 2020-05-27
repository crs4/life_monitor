#!/usr/bin/env bash

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

# change these as needed
GALAXY_IMG=bgruening/galaxy-stable:20.05

pushd "${this_dir}"
# looks for sort-and-change-case-test.yml in the same dir as
# sort-and-change-case.ga
planemo test \
	--engine docker_galaxy \
	--docker_galaxy_image "${GALAXY_IMG}" \
	sort-and-change-case.ga
popd
