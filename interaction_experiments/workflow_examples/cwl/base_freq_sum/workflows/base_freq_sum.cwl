cwlVersion: v1.0
class: Workflow

inputs:
  fasta_in: File
  freqs_file_name: string
  freqs_sum_file_name: string

outputs:
  freqs_sum:
    type: File
    outputSource: sum_frequencies/freqs_sum_file

steps:
  base_frequencies:
    run: ../tools/base_freqs.cwl
    in:
      seqs: fasta_in
      freqs: freqs_file_name
    out: [freqs_file]
  sum_frequencies:
    run: ../tools/sum_freqs.cwl
    in:
      freqs: base_frequencies/freqs_file
      freqs_sum: freqs_sum_file_name
    out: [freqs_sum_file]
