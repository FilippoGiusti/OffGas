# 🚗💨 OffGas

> **An IoT monitoring and control system for detecting possible offgassing events in EV garage environments.**

---

## Overview

**OffGas** is an academic IoT project built to monitor gas concentration inside a garage-like environment and react when the observed values suggest a potentially dangerous condition.

The project is centered on a **single real prototype unit, G1**, equipped with a gas sensor and a ventilation fan. To give the operator a meaningful comparison baseline, the interface also shows **five additional units, G2-G6**, which are **simulated from CSV datasets**.

This distinction is fundamental to the current version of the project:

- **G1** is the **only physical monitored unit**.
- **G2-G6** are **simulated comparison units** generated from datasets.
- The dashboard is intentionally limited to **6 displayed units total** to keep the system readable and didactically clear.

OffGas combines:

- **Arduino** for sensing and actuation
- **HC-05 Bluetooth** for the link between Arduino and the host machine
- **Python Bridge** for hardware-to-MQTT communication
- **Node-RED** for orchestration, logic, APIs, dataset management, and threshold handling
- **React + Vite dashboard** for monitoring and operator control
- **Docker** for a reproducible software runtime

---

## Project Goal

The goal of OffGas is not just to read a gas value, but to interpret it inside a distributed comparison model.

The system tries to distinguish between:

- a **local abnormal increase** in the monitored garage (**possible offgassing event in G1**), and
- a **broader environmental variation** that also affects the comparison units.

In practical terms, the project asks:

> **Is the gas increase specific to the monitored garage, or is it consistent with the surrounding comparison scenario?**

To support this reasoning, the live data from **G1** is evaluated against the behavior of the simulated units **G2-G6**.

---

## Current Architecture at a Glance

The project is organized into four main layers.

### 1. Arduino

Arduino is the **edge device** connected to the physical prototype.

It is responsible for:

- reading the **MQ-2 gas sensor**
- sending measurements via **HC-05 Bluetooth**
- receiving fan commands from the host machine
- switching the ventilation hardware on or off

Arduino does **not** implement the system logic.

### 2. Python Bridge

`Bridge/bridge.py` is the gateway between the physical prototype and the software stack.

Its responsibilities are intentionally limited:

- opening the Bluetooth serial connection to Arduino
- reading values in the format `MQ2:<value>`
- validating incoming sensor data
- attaching timestamps
- publishing telemetry via MQTT
- receiving commands from Node-RED
- forwarding those commands back to Arduino

In the current architecture, the bridge is **not** responsible for dataset loading, threshold computation, prediction, or global dashboard state construction.

### 3. Node-RED

Node-RED is the **core orchestration layer** of OffGas.

It receives telemetry from the bridge and performs the main application logic, including:

- telemetry caching
- threshold computation
- prediction and anomaly detection
- dataset loading and switching
- state generation for the dashboard
- manual and automatic control handling
- emergency shutoff management
- optional Telegram notifications
- HTTP API exposure for the frontend

This is the most important architectural point in the current version of the project:

> **Threshold logic and dataset management now belong entirely to Node-RED.**

### 4. Web Dashboard

The dashboard is the browser-based operational interface.

It shows:

- live and simulated values for **G1-G6**
- **Avg Concentration** and **Safety Threshold**
- predictive and critical warnings
- ventilation status
- manual control (`OFF / AUTO / ON`)
- emergency shutoff state
- dataset selection for the simulated units
- backend connectivity information

The dashboard is served by Node-RED at:

```text
http://localhost:1880/offgas-dashboard/
```

---

## Real Unit vs Simulated Units

### G1: real prototype

**G1** is the only real monitored unit in the current system.

Its data path is:

```text
MQ-2 sensor -> Arduino -> HC-05 -> Python Bridge -> MQTT -> Node-RED
```

### G2-G6: dataset-driven units

**G2-G6** are not physical sensors in the current prototype.

They are generated from CSV datasets stored in:

```text
dataset_other_garage/
```

Node-RED loads the selected dataset, excludes G1 from the simulated pool, and builds the comparison state shown in the dashboard.

---

## How Threshold and Dataset Logic Work Now

In the current implementation, **Node-RED** is responsible for both:

- selecting and loading the active dataset
- computing the reference threshold used by the system

The general idea is:

```text
others_mean = average concentration of the comparison units
threshold = others_mean × ANOMALY_FACTOR
```

This means the safety threshold is **contextual**, not hardcoded.

The active dataset defines the simulated environmental scenario for **G2-G6**, while Node-RED uses that scenario to build:

- the comparison values for the simulated units
- the average concentration shown in the UI
- the effective threshold used to evaluate G1 and the other displayed units

This is different from earlier versions of the architecture, where part of this responsibility was described inside the bridge.

---

## Prediction and Detection Logic

Node-RED also performs predictive analysis on the incoming telemetry of **G1**.

The logic is based on:

- a short history of recent gas values
- a **moving average**
- the variation between the current average and the previous one
- an extrapolated future estimate

In simplified form:

```text
growthRate = movingAvg - previousAvg
predictedGas = gas + (growthRate × 150)
```

This allows the system to distinguish between two main situations:

### Critical anomaly

```text
gas > threshold
```

The gas value is already above the safety threshold.

### Predictive warning

```text
predictedGas > threshold
```

The gas value is still below threshold now, but the trend suggests that it may cross the threshold soon.

This enables **preventive ventilation**, not only reactive ventilation.

---

## Main MQTT Topics

The project uses three main MQTT topics around the real prototype unit:

- `garages/G1/telemetry`
- `garages/G1/alerts`
- `garages/G1/cmd`

Their roles are:

| Topic | Direction | Purpose |
|---|---|---|
| `garages/G1/telemetry` | Bridge -> Node-RED | Real telemetry from G1 |
| `garages/G1/alerts` | Bridge -> Node-RED | Manual override and system events |
| `garages/G1/cmd` | Node-RED -> Bridge | Automatic or manual fan commands |

---

## Dashboard and API Layer

The dashboard does not talk directly to MQTT and does not communicate directly with Arduino or the bridge.

It interacts with Node-RED through HTTP/JSON APIs such as:

- `GET /api/state`
- `POST /api/control`
- `GET /api/datasets`
- `POST /api/dataset`
- `POST /api/emergency`
- `GET /api/health`

This separation keeps the frontend focused on presentation and interaction, while Node-RED remains the single source of truth for the system state.

---

## Docker Runtime

The project includes a **Docker-based setup** designed to be **additive** rather than invasive.

The idea is:

- keep the **bridge local** on the machine connected to the HC-05 module
- run **Node-RED + Mosquitto + dashboard serving** through Docker
- avoid restructuring the original project folders

### What stays local

- `Bridge/` remains the original local gateway for the real prototype
- Bluetooth communication remains outside Docker
- the operator still runs the bridge manually on the host machine

### What Docker provides

- reproducible Node-RED runtime
- reproducible MQTT broker setup
- shared dashboard serving configuration
- easier onboarding across different team machines

---

## Quick Start

### 1. Start the Docker stack

#### Windows

```bat
scripts\up.bat
```

#### macOS / Linux

```bash
./scripts/up.sh
```

This starts the software stack used by the shared environment.

### 2. Rebuild the dashboard if the frontend changed

#### Windows

```bat
scripts\rebuild-dashboard.bat
```

#### macOS / Linux

```bash
./scripts/rebuild-dashboard.sh
```

### 3. Run the bridge locally for the real prototype

```bash
python Bridge/bridge.py
```

The bridge must be started on the machine that is physically paired with the **HC-05** Bluetooth module.

### 4. Open the interfaces

#### Node-RED editor

```text
http://127.0.0.1:1880/admin/#flow/120ca2f2695d22bc
```

#### Dashboard

```text
http://localhost:1880/offgas-dashboard/
```

---

## Configuration Note

One detail deserves attention: the bridge MQTT host must match the runtime you are actually using.

Depending on your setup, the broker may need to be reached as:

- `localhost`
- `127.0.0.1`
- `host.docker.internal`

So before running the real prototype, check the bridge MQTT configuration and make sure it is coherent with how Mosquitto is exposed on your machine.

---

## Typical Runtime Flow

A simplified end-to-end flow is:

1. Arduino reads the MQ-2 sensor.
2. Arduino sends the value over Bluetooth through HC-05.
3. The Python bridge receives and validates the value.
4. The bridge publishes G1 telemetry via MQTT.
5. Node-RED receives the telemetry.
6. Node-RED updates datasets, comparison state, threshold, and prediction.
7. Node-RED rebuilds the dashboard state.
8. Node-RED sends automatic or manual commands back to the bridge.
9. The bridge forwards the command to Arduino.
10. The fan state is updated on the real prototype.

---

## Main Project Folders

```text
Bridge/                    # Python bridge for the real prototype
Doc/                       # Project documentation and technical PDFs
arduino_ide_offgas/        # Arduino firmware
batchfile/                 # Legacy helper files
build/                     # Frontend build artifacts (when present)
dataset_other_garage/      # CSV datasets for G2-G6 simulation
docker/                    # Docker-specific runtime files (if present in local setup)
offgas_dashboard_linked/   # React + Vite dashboard source
scripts/                   # Start/stop/rebuild helper scripts
```

> Folder contents may vary slightly depending on whether you are looking at the plain repository snapshot or a local working setup enriched with Docker runtime files.

---

## Documentation

The repository includes dedicated technical documentation for the main subsystems, including:

- Arduino firmware
- Python bridge
- Node-RED logic
- dashboard frontend
- Docker runtime

These documents are meant to describe not only what each component contains, but also what role it plays inside the overall OffGas architecture.

---

## Academic Context

This project was realized for the **UniMORE – IoT Course (2025/2026)**.

**Prof. Roberto Vezzani**  
**Asst. Vittorio Cuculo**

---

## Contributors

- **Elena Bernini**
- **Filippo Giusti**
- **Piergiorgio Signorino**
