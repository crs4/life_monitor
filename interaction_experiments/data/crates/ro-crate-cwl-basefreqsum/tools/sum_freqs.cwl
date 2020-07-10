class: CommandLineTool
cwlVersion: v1.0

baseCommand: ["python3", "-c"]

inputs:
  freqs:
    type: File
  freqs_sum:
    type: string
outputs:
  freqs_sum_file:
    type: File
    outputBinding:
      glob: $(inputs.freqs_sum)

arguments:
  - position: 0
    valueFrom: |
      from collections import Counter
      c = Counter()
      with open("$(inputs.freqs.path)") as f:
          for line in f:
              d = dict([_.split("=") for _ in line.strip().split("\\t")[1:]])
              c += Counter({k: int(v) for k, v in d.items()})
              freqs = "\\t".join([f"{k}={v}" for k, v in sorted(c.items())])
      with open("$(inputs.freqs_sum)", "w") as fo:
          freqs = "\\t".join([f"{k}={v}" for k, v in sorted(c.items())])
          fo.write(f"{freqs}\\n")
