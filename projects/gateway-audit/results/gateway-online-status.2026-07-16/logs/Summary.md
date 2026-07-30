# Headwind log summary

2 gateways analysed · last 5 days · severity WARNING+ERROR (the filter is cumulative, so WARNING already includes ERROR).

These are the gateways where **MDM is green but connect is offline** — we can still reach the device, so its logs are fresh and actually explain why it will not talk to connect.

## What the fleet is complaining about

| Signature | Entries | Meaning |
|---|---:|---|
| `NO_DNS` | 297 | No DNS / no network — the gateway cannot reach bff.ggplus.ch at all |
| `OTHER` | 281 | Unclassified |
| `CONFIG_FAILED` | 245 | Config update failing (network error) |
| `HUB_HANDSHAKE` | 94 | Network is up but the SignalR handshake with connect fails — this is how a gateway can be 'offline' in connect while its SIM still moves data |
| `CONNECTIVITY` | 2 | Connectivity flapping |

## Per gateway

| Seriennummer | Entries | Dominant signature | Details |
|---|---:|---|---|
| `2023110600000516` | 510 | `NO_DNS` | [2023110600000516.md](./2023110600000516.md) |
| `2023110600000014` | 409 | `OTHER` | [2023110600000014.md](./2023110600000014.md) |

## Note

`HUB_HANDSHAKE` means the network is up but the gateway cannot complete its SignalR handshake with connect. A gateway showing this **plus** real LTE traffic is alive and moving data — its "offline" status in connect is a false negative, not a dead device.
