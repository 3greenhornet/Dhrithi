# Manual labeling guide (dossier 2.2 / 8.2)

Before any semantic model is allowed to touch policy, label a sample by
hand. Labels describe the activity's **relationship to the task**, not
its topic:

| Label | Meaning |
|---|---|
| `direct_execution` | the task itself |
| `necessary_dependency_research` | removing a real obstacle blocking the task |
| `related_nonessential_exploration` | on-topic but not required |
| `repeated_tutorial_consumption` | consuming instead of doing |
| `unrelated_branching` | the curiosity chain |
| `setup` | environment/tooling work |
| `offline_rest` | away from the machine |
| `unknown` | honestly unclassifiable from telemetry |

## Rules

1. Label from the loop log + your own memory, cold (next morning).
2. ~100-200 events is a fine first sample; precision matters more
   than volume.
3. Embedding similarity scores are NOT policy (dossier 8.2): the
   thresholds 0.40/0.65/0.60 seen in early drafts are unvalidated and
   deliberately not implemented.
4. When the sample exists, benchmark candidate models (MiniLM, BGE,
   Qwen embeddings, EmbeddingGemma 2) against THESE labels — measure
   precision/recall/false-block cost/latency — before any adapter is
   enabled. Until then, deterministic rules carry enforcement (D-014).

## Files

- `labeling_template.csv` — copy per labeling batch; `manual_label`
  is the ground truth column.
- `analysis/sequence.py` — produces the event table to label from
  (`--json` gives machine-readable output).
