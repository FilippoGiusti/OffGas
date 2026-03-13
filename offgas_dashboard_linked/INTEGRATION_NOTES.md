# Integration notes

## What was wrong in the original dashboard

1. `G1` was fake (`const g1Value = 350`), not read from the prototype.
2. The threshold was computed from the displayed sensors, including `G1`.
3. `others_mean` was therefore conceptually wrong.
4. The fan badge was shown on any garage using a local heuristic, while the real fan exists only on `G1`.
5. The dataset selector changed the UI only, not the bridge / Node-RED logic.
6. The emergency shutoff control had no equivalent command in the current backend.

## What this linked version does

- `G1` comes from MQTT telemetry: `garages/G1/telemetry`
- manual controls publish to: `garages/G1/cmd`
- automatic decisions are read from the same command topic when the payload is JSON
- dataset garages come from the CSV of the main project
- only 6 units are shown: `G1 + G2..G6`
- `others_mean` is calculated on all dataset garages (`G2..G11`), not on visible cards only

## Important discrepancy found

The exported `nodered_flows_offgas.json` contains the automatic MQTT path and the manual inject nodes.
The screenshot you provided may represent a newer or slightly different revision of the flow than the JSON export, so I would treat the JSON as the authoritative source for code-level integration.

## Critical logic issue found in prediction

The Node-RED document says the prediction horizon is about 30 seconds because it uses:
- `predictedGas = gas + (growthRate * 150)`
- and assumes `0.2 s` per cycle

But the actual telemetry is driven by Arduino, which sends a new sensor value every 5 seconds (`intervalloLettura = 5000`).

So the current multiplier `150` is not a 30-second horizon in practice. It is much closer to:
- `150 samples * 5 s ≈ 750 s`

That means `predicted_crossing` is likely calibrated on the wrong time base.

A safer fix is to compute growth using timestamps, or use a horizon near 6 samples for ~30 seconds.

## Optional backend improvements

1. Add `manual_override` or `control_mode` to bridge telemetry, so the dashboard does not have to infer the mode.
2. Add `others_mean` explicitly to telemetry for clarity.
3. If you want to keep a dataset selector in the dashboard, the bridge must support runtime dataset switching; right now it loads the CSV once at startup.
4. If you want a real emergency shutoff, define a new backend command and handle it in bridge + Node-RED.
