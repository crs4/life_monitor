#!/usr/bin/env bash

set -euo pipefail
[ -n "${DEBUG:-}" ] && set -x
this="${BASH_SOURCE:-$0}"
this_dir=$(cd -P -- "$(dirname -- "${this}")" && pwd -P)

pushd "${this_dir}"
cp "${this_dir}/../../../../data/crates/ro-crate-cwl-basefreqsum/test/inputs/seqs.fa" seqs.fa
cp "${this_dir}/../../../../data/crates/ro-crate-cwl-basefreqsum/test/outputs/freqs_sum.tsv" freqs_sum_exp.tsv
# looks for base_freq_sum_tests.yml in the same dir as base_freq_sum.cwl
planemo test --engine cwltool "${this_dir}/base_freq_sum.cwl"
popd
