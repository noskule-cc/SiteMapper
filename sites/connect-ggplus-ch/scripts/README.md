# connect-ggplus-ch scripts

Direct API access to the GG+connect BFF, so workflows don't have to scrape the DOM.

```
python -m pip install -r requirements.txt
python ggplus_auth.py                     # log in once — stored in the OS keyring
python get_gateway_status_table.py        # the fleet, triaged into action buckets
python get_gateway_logs.py <serial>       # Headwind WARNING+ERROR logs for one gateway
```

## Sweep once per run, then pass `--triage`

The fleet sweep is the expensive, un-repeatable step: it opens the **SignalR hub**, and the
server answers a *second* connection in the same session with `Handshake status 404`. It is
also a point-in-time snapshot — the fleet flaps between passes, so two sweeps minutes apart
disagree about who is online.

So a run sweeps **once** and every later step reuses that `triage.json`:

```
RUN=projects/gateway-audit/results/gateway-online-status.$(date +%F)

python get_gateway_status_table.py --json > $RUN/triage.json          # the one sweep
python get_gateway_logs.py --bucket ANALYZE_LOGS --triage $RUN/triage.json --out $RUN/logs
#   ... the Swisscom leg produces $RUN/lte-results.json ...
python get_gateway_status_table.py --triage $RUN/triage.json \
       --lte-results $RUN/lte-results.json --out $RUN                 # the deliverable
```

Without `--triage`, both the `--bucket` and `--out` paths re-run the sweep: `--bucket` simply
fails on the hub handshake, and `--out` silently builds the worklist from a *different* fleet
state than the Swisscom outcomes were gathered against.

| Script | Purpose |
|---|---|
| `ggplus_auth.py` | Real login (`POST /user/api/v1/auth`, `grantType: password`), refresh-token renewal, OS keyring storage. No token is ever pasted or committed. |
| `ggplus_api.py` | API client — fleet list, SignalR connect-Status, Headwind logs & infos, partner names. |
| `get_gateway_status_table.py` | The fleet table + the `gateway_online_status` decision tree. Replaces the DOM scrape. `--triage FILE` reuses an earlier sweep. |
| `get_gateway_logs.py` | The *Analyse Logs from Headwind* node: WARNING+ERROR only, with a diagnosis per gateway. `--triage FILE` resolves `--bucket` without re-sweeping. |

## Credentials

`ggplus_auth.py` stores your login in the **OS keyring** (Windows Credential
Manager) under service `SiteMapper` — never in the repo, never in a file. First run
prompts once; after that it is silent, refreshing the access token via the
`refresh_token` grant until that expires too.

For non-interactive runs (CI), set `GGPLUS_USER_PROD` / `GGPLUS_PASS_PROD` instead.
`python ggplus_auth.py prod --clear` forgets the stored login.

## Three non-obvious things about this API

These are the reason the scripts exist rather than a couple of `curl` calls. All
three were verified against the live app.

**1. There is no CSV endpoint.** The page's *CSV Export* button is a client-side
Blob built from data already in memory (`exportAsCsv(dataSource.filteredData)` →
`convertToCSV()` → `new Blob(...)`). Nothing to call. `get_gateway_status_table.py
--csv` reproduces the same columns from the API instead.

**2. `connectionState` from `/gateway/api/v1/gateway/all` is a placeholder.** It
returns `"Unconfigured"` for *every* gateway. The real connect Status only exists on
the **SignalR hub** `/gateway/device-connection`: connect, then invoke
`AddDeviceWatcher(deviceId, classification)` per device and the server pushes a
`ConnectionState` message back. `get_connection_states()` does this. A plain HTTP
script cannot answer "is this gateway online?" — this is the whole reason the module
speaks websockets.

**3. The "Version" column is a hybrid field**, not one property:

```python
hmdmState != "Grey"  ->  hmdmConnectVersionInstalled
hmdmState == "Grey"  ->  firmwareVersion
```

Reading `firmwareVersion` naively gives a *different, wrong* answer — e.g. serial
`2023010300000004` has `firmwareVersion 1.14.1.0` but displays `1.15.0.3`. Getting this
wrong mis-sorts the entire `FLASH_GATEWAY` bucket. `displayed_version()` mirrors the
app's `getDisplayedVersion()` exactly.

**Never abbreviate identifiers in output.** Serials, Vertragsnummer, IMSI and IMEI go in
full — a report is a worklist, and a truncated serial can't be pasted into the monitoring
filter or a ticket. The fleet's serials share a long common prefix (`20231106000004…`),
so the tail alone is what distinguishes them.

## Log severity and window

Defaults: **severity WARNING, last 5 days.**

The Headwind `severity` filter is **cumulative** (everything at least this severe),
not an exact level — so asking for WARNING **already includes ERROR**:

| `severity` | Returns | Fleet volume / 24 h |
|---:|---|---:|
| `1` | ERROR only (`--errors-only`) | 4,437 |
| `2` | **WARNING + ERROR** ← default | 11,265 |
| `3` | + INFO | 19,248 |
| `-1` | everything, incl. VERBOSE (`--all-severities`) | 138,905 |

The default drops the noise (`Push long polling inquiry` = VERBOSE,
`Configuration updated` = INFO) **server-side** — no client-side message blacklist to
maintain, and 12× less data over the wire.

```
python get_gateway_logs.py <serial>              # WARNING+ERROR, last 5 days
python get_gateway_logs.py <serial> --days 14
python get_gateway_logs.py <serial> --errors-only
```

Paging is capped at 50 pages × 200 rows. If the server holds more than was fetched,
the result carries `truncated: true` and the CLI says so — a cut-short set is never
reported as if it were complete.

## Related

- Workflow: [`../../../projects/gateway-audit/workflows/gateway-online-status.yaml`](../../../projects/gateway-audit/workflows/gateway-online-status.yaml)
- Page map: [`../pages/admin-gateway-monitoring.yaml`](../pages/admin-gateway-monitoring.yaml)
- Auth pattern borrowed from the `CacheUpdater` project (`C:\DEV\CacheUpdater`).
