#!/usr/bin/env bash

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE:-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

pushd "${this_dir}"
# looks for base_freq_sum_tests.yml in the same dir as base_freq_sum.cwl
planemo test --engine cwltool "${this_dir}/base_freq_sum.cwl"
popd
