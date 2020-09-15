#!/usr/bin/env bash

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

pushd "${this_dir}"
# Can also use cwl-runner to run these. Planemo picks up cwltool though.
cwltool base_freq_sum.cwl base_freq_sum_job.yml
popd
