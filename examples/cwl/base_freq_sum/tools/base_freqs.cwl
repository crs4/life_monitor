class: CommandLineTool
cwlVersion: v1.0

baseCommand: ["python3", "-c"]

inputs:
  seqs:
    type: File
  freqs:
    type: string
outputs:
  freqs_file:
    type: File
    outputBinding:
      glob: $(inputs.freqs)

arguments:
  - position: 0
    valueFrom: |
      from collections import Counter
      def fasta_reader(f):
          id_, buf = None, []
          for line in f:
              line = line.strip()
              if not line:
                  continue
              if line.startswith(">"):
                  if id_:
                      yield id_, "".join(buf)
                  id_, buf = line[1:], []
              else:
                  buf.append(line)
          yield id_, "".join(buf)
      def base_frequencies(seq_stream):
          for id_, seq in seq_stream:
              yield id_, Counter(seq)
      with open("$(inputs.seqs.path)") as f, open("$(inputs.freqs)", "w") as fo:
          for id_, c in base_frequencies(fasta_reader(f)):
              freqs = "\\t".join([f"{k}={v}" for k, v in sorted(c.items())])
              fo.write(f"{id_}\\t{freqs}\\n")
