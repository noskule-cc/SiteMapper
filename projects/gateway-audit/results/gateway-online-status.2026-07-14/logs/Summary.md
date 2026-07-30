# Headwind log summary

1 gateways analysed · last 5 days · severity WARNING+ERROR (the filter is cumulative, so WARNING already includes ERROR).

These are the gateways where **MDM is green but connect is offline** — we can still reach the device, so its logs are fresh and actually explain why it will not talk to connect.

## What the fleet is complaining about

| Signature | Entries | Meaning |
|---|---:|---|
| `NO_DNS` | 9633 | No DNS / no network — the gateway cannot reach bff.ggplus.ch at all |
| `CONFIG_FAILED` | 211 | Config update failing (network error) |
| `OTHER` | 137 | Unclassified |
| `HUB_HANDSHAKE` | 19 | Network is up but the SignalR handshake with connect fails — this is how a gateway can be 'offline' in connect while its SIM still moves data |

> ⚠️ **Some logs are truncated** — the paging cap was reached, so the counts above are a sample of the most recent entries rather than totals for the whole window. Affected: `2023110600000493` (10000 of 10975)

## Per gateway

| Seriennummer | Entries | Dominant signature | Details |
|---|---:|---|---|
| `2023110600000493` | 10000 of 10975 | `NO_DNS` | [2023110600000493.md](./2023110600000493.md) |

## Note

`HUB_HANDSHAKE` means the network is up but the gateway cannot complete its SignalR handshake with connect. A gateway showing this **plus** real LTE traffic is alive and moving data — its "offline" status in connect is a false negative, not a dead device.
