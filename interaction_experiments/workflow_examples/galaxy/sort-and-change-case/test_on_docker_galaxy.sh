#!/usr/bin/env bash

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

pushd "${this_dir}"
# looks for sort-and-change-case-test.yml in the same dir as
# sort-and-change-case.ga
planemo test \
	--biocontainers \
	sort-and-change-case.ga
popd
