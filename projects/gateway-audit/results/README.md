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

## Layout of a `gateway-online-status` run

```
gateway-online-status.2026-07-14.md        the report: worklist sorted by ACTION
gateway-online-status.2026-07-14/
  triage.json                              full machine-readable table (every gateway)
  worklist.csv                             sorted by action — pasteable into a ticket
  worklist.md                              same, as a table
  logs/
    Summary.md                             what the whole fleet is complaining about
    2023110600000332.log                   raw WARNING+ERROR rows for that gateway
    2023110600000332.md                    short summary + diagnosis for that gateway
    …
```

Produced by:

```
python get_gateway_status_table.py --out <run-dir> --lte-results <lte.json>
python get_gateway_logs.py --bucket ANALYZE_LOGS --days 5 --out <run-dir>/logs
```

The run folder is **dated**, so runs never overwrite each other and two weeks can be
diffed against one another.

Logs are written only for the `ANALYZE_LOGS` bucket (MDM green but connect offline).
Those are the devices we can still reach, so their logs are fresh and actually explain
the fault. For MDM-red devices the management channel is dead — there is nothing to ask,
and any log we did pull would be stale.

### Check a raw log's size before committing it

A per-gateway `.log` is normally a few hundred KB and worth committing as evidence. But a
device that is *completely* offline logs the same failure every few seconds for the whole
window, with a full stack trace each time — the 2026-07-14 log for `2023110600000493` came
to **41 MB / 483k lines, only ~7k of them unique**, in a repo otherwise measured in
single-digit MB. Git keeps that forever, in every clone.

So: if a `.log` is more than a couple of MB, commit only the sibling `<serial>.md` and
leave the raw file local. The `.md` already carries what anyone reads — the diagnosis, the
signature counts, and the most recent entries. Nothing of analytical value is lost;
483k repetitions of `Unable to resolve host` say exactly what 7k of them say.

## Never abbreviate identifiers

Write **full** Seriennummer, Vertragsnummer, IMSI and IMEI everywhere in a result —
tables, prose, findings. No `…296`, no truncation, no "last 3 digits".

A result is a worklist: someone has to paste that serial into the monitoring filter, the
Swisscom search box, or a service ticket. A truncated serial cannot be pasted, cannot be
grepped, and is not even unique — the fleet's serials share a long common prefix
(`20231106000004…`), so the tail alone is what distinguishes them and the head is what
gets dropped. Abbreviating turns a usable worklist into a lookup exercise against the
evidence JSON.

If a table feels too wide, drop a *column*, not the digits of the key.
