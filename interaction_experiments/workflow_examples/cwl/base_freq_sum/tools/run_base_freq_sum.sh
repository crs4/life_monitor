#!/usr/bin/env bash

# run tools separately, i.e., not as a workflow

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

pushd "${this_dir}"
# Can also use cwl-runner to run these. Planemo picks up cwltool though.
cwltool base_freqs.cwl base_freqs_job.yml
cwltool sum_freqs.cwl sum_freqs_job.yml
popd
