# Gateway Audit — results

Human-readable records of cross-site workflow runs for the **gateway-audit** project
(see `schema/result.yaml` for the neutral `result` object a run emits).

- **File naming:** `<workflow>.<YYYY-MM-DD>.md`
- **Per-run evidence:** binaries/datasets for a run go in a sibling folder
  `<workflow>.<YYYY-MM-DD>/` and are referenced from the result's `evidence` list.
- **Contents:** run metadata, the headline metrics, the machine-readable `result`
  JSON, and findings/notes.
- **Convention:** routine runs need not be committed; commit **reference runs** worth
  keeping as history.
