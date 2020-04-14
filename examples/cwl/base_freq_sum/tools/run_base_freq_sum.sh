#!/usr/bin/env bash

# run tools separately, i.e., not as a workflow

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

pushd "${this_dir}"
cp "${this_dir}/../../../../data/crates/ro-crate-nf-basic/test/inputs/sample.fa" seqs.fa
cwl-runner base_freqs.cwl base_freqs_job.yml
cwl-runner sum_freqs.cwl sum_freqs_job.yml
popd
