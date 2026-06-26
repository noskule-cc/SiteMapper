# Test results

Documented runs of this site's test workflows. A result is a workflow **output**
(see `schema/result.yaml`), not source — in a real host setup the host routes the
`result` to its own sink (e.g. an Azure DevOps test run). These files are the
in-repo, human-readable record.

- **File naming:** `<workflow>.<YYYY-MM-DD>.md`
- **Contents:** run metadata, a per-assertion PASS/FAIL table, the machine-readable
  `result` JSON, and notes/findings.
- **Convention:** routine/CI runs need not be committed; commit **reference runs**
  worth keeping as history.
