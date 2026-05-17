<div align="center">
  <img src="./Doc/assets/offgas-logo.png" alt="OffGas Logo" width="200"/>
</div>
<div align="center" style="margin-top: -30px;">
  <img src="./Doc/assets/offgas-font-logo.png" alt="OffGas Wordmark" width="300"/>
</div>
<div align="center" style="margin-top: -30px;">
  <b>An IoT monitoring, prediction, and control system for detecting possible EV off-gassing events in underground garage environments.</b>
</div>

<p align="center">
  Arduino · Python Bridge · MQTT · Node-RED · React Dashboard · Docker · AI Demo
</p>

---

## 📘 Overview

**OffGas** is an academic IoT project focused on early gas-risk detection in enclosed EV parking environments.

The current system is built around **one real monitored unit, G1**, equipped with an MQ-2 gas sensor and a ventilation fan. To provide contextual comparison, the platform also visualizes **five additional units, G2-G6**, which are generated from CSV datasets and used as simulated surrounding garages.

This distinction is central to the current implementation:

- **G1** is the **only physical prototype unit**
- **G2-G6** are **simulated comparison units**
- the dashboard intentionally focuses on **6 total displayed units** to keep the system readable and didactically clear

OffGas combines:

- **Arduino** for sensing and actuation
- **HC-05 Bluetooth** for local wireless communication with the prototype
- **Python Bridge** for Bluetooth-to-MQTT communication
- **Node-RED** for orchestration, logic, APIs, dataset management, and state building
- **React + Vite dashboard** for monitoring and operator control
- **Mosquitto MQTT** for messaging
- **Docker** for a reproducible backend runtime
- an **AI demo layer** for future data-driven forecasting and anomaly-oriented evolution

---

## 🎯 Project Goal

The goal of OffGas is not only to read a gas value, but to interpret it inside a contextual monitoring model.

The system tries to distinguish between:

- a **local abnormal increase** in the monitored garage
- a **broader environmental variation** consistent with the surrounding comparison scenario

In practical terms, the system asks:

> **Is the gas increase specific to G1, or is it consistent with the surrounding garage context?**

To support this reasoning, the live telemetry from **G1** is evaluated together with the behavior of **G2-G6**, which are simulated from datasets.

---

## 🧱 Current Architecture at a Glance

The project is organized into four main operational layers.

### 1. Arduino

Arduino is the **edge device** connected to the physical prototype.

It is responsible for:

- reading the **MQ-2 gas sensor**
- applying local filtered acquisition logic
- sending measurements through **HC-05 Bluetooth**
- receiving fan commands from the bridge
- switching the ventilation hardware on or off
- updating the local display and status indicators

Arduino does **not** implement the high-level decision logic.

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

In the current architecture, the bridge is **not** responsible for dataset loading, threshold computation, prediction, or dashboard state construction.

### 3. Node-RED

Node-RED is the **core orchestration layer** of OffGas.

It receives telemetry from the bridge and performs the main application logic, including:

- telemetry caching
- dataset loading and switching
- contextual threshold computation
- prediction and anomaly-oriented evaluation
- dashboard state generation
- manual and automatic control handling
- emergency shutoff logic
- optional Telegram notifications
- HTTP API exposure for the frontend

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
- backend connectivity and update information
- temporal analysis and graph view

The dashboard is served by Node-RED at:

```text
http://localhost:1880/offgas-dashboard/
```

---

## 🧪 Real Unit vs Simulated Units

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

Node-RED loads the selected dataset, rebuilds the simulated context, and uses that information to evaluate G1 inside a broader reference scenario.

---

## 📐 Contextual Threshold Logic

In the current implementation, **Node-RED** is responsible for both:

- selecting and loading the active dataset
- computing the reference threshold used by the system

The general idea is:

```text
others_mean = average concentration of the comparison units
effective_threshold = others_mean × ANOMALY_FACTOR
```

This means the safety threshold is **contextual**, not fixed.

The active dataset defines the simulated environmental scenario for **G2-G6**, while Node-RED uses that scenario to build:

- the comparison values for the simulated units
- the average concentration shown in the UI
- the effective threshold used to evaluate G1
- the global state shown in the dashboard

---

## 📈 Rule-Based Prediction and Detection

Node-RED already performs predictive analysis on the incoming telemetry of **G1**.

The current logic is based on:

- a short history of recent gas values
- a **moving average**
- the variation between the current average and the previous one
- an extrapolated future estimate

In simplified form:

```text
growthRate = movingAvg - previousAvg
predicted_gas = gas + (growthRate × 150)
```

This allows the system to distinguish between two important situations.

### Critical anomaly

```text
gas > effective_threshold
```

The gas value is already above the safety threshold.

### Predictive warning

```text
predicted_gas > effective_threshold
```

The gas value is still below threshold, but the trend suggests that it may cross the threshold soon.

This enables **preventive ventilation**, not only reactive ventilation.

---

## 📡 Main MQTT Topics

The project uses three main MQTT topics around the real prototype unit:

- `garages/G1/telemetry`
- `garages/G1/alerts`
- `garages/G1/cmd`

| Topic | Direction | Purpose |
|---|---|---|
| `garages/G1/telemetry` | Bridge -> Node-RED | Real telemetry from G1 |
| `garages/G1/alerts` | Bridge -> Node-RED | Manual override and system events |
| `garages/G1/cmd` | Node-RED -> Bridge | Automatic or manual fan commands |

---

## 🖥️ Dashboard and API Layer

The dashboard does not communicate directly with MQTT, Arduino, or the bridge.

It interacts with Node-RED through HTTP/JSON APIs such as:

- `GET /api/state`
- `POST /api/control`
- `GET /api/datasets`
- `POST /api/dataset`
- `POST /api/emergency`
- `GET /api/health`

This separation keeps the frontend focused on presentation and interaction, while Node-RED remains the single source of truth for system state.

---

## 🐳 Docker Runtime

The project includes a **Docker-based backend** designed to be reproducible and easy to share across team members.

The idea is:

- keep the **bridge local** on the machine physically connected to the HC-05 module
- run **Node-RED + Mosquitto + dashboard serving** through Docker
- preserve direct access to the real prototype while making the backend portable

### What stays local

- `Bridge/` remains the local gateway for the physical prototype
- Bluetooth communication stays outside Docker
- the operator still runs the bridge manually on the host machine

### What Docker provides

- reproducible Node-RED runtime
- reproducible MQTT broker setup
- shared dashboard serving configuration
- easier onboarding across different team machines

---

## 🔌 Bridge MQTT Configuration

The bridge runs locally on the host machine connected to the HC-05 module.

For this reason, the MQTT broker is expected to be reached through the host itself, using:

- `127.0.0.1`
- or `localhost`

The bridge configuration should therefore use:

```python
MQTT_BROKER = "127.0.0.1"
```

or, equivalently:

```python
MQTT_BROKER = "localhost"
```

---

## 🤖 AI Demo and Future Data-Driven Evolution

The repository also includes an **AI demo module** in:

```text
offgas_ai_demo/
```

This part is not the main runtime of OffGas, but a proof of concept that demonstrates how the system can evolve from **rule-based prediction** to **data-driven prediction**.

The demo is based on:

- historical telemetry stored in `gas_data.csv`
- a training script for a **RandomForestRegressor**
- a prediction demo script for estimating future gas values

The goal of this module is to predict the gas concentration of **G1** about **30 seconds into the future** using recent historical values as input.

This supports an important conceptual evolution:

- **today**: prediction is computed through handcrafted logic in Node-RED
- **future**: prediction can be assisted by a trained ML model

In this approach:

- the **AI predicts**
- **Node-RED still decides**

This preserves the current architecture while extending it with an additional backend intelligence layer.

---

## 🧠 Future AI-Based Anomaly Detection

Beyond forecasting, OffGas also opens the door to a more advanced anomaly-oriented layer.

A future server-side AI module, for example based on **Isolation Forest**, could learn what normal gas behavior looks like from historical telemetry and logs.

Instead of checking only whether a gas value exceeds a threshold, the system could also ask whether the current value and its recent trend are unusual with respect to learned normal behavior.

This would make the platform:

- more adaptive
- more robust to irregular patterns
- less dependent on fixed handcrafted rules alone
- more suitable for false-alarm reduction and maintenance support

The long-term goal is therefore not only to predict the next value, but also to understand when the overall system behavior becomes abnormal.

---

## 🔄 Typical Runtime Flow

A simplified end-to-end flow is:

1. Arduino reads the MQ-2 sensor.
2. Arduino sends the filtered value over Bluetooth through HC-05.
3. The Python bridge receives and validates the message.
4. The bridge publishes G1 telemetry via MQTT.
5. Node-RED receives the telemetry.
6. Node-RED updates datasets, comparison state, threshold, prediction, and system state.
7. Node-RED rebuilds the dashboard state.
8. Node-RED sends automatic or manual commands back through MQTT.
9. The bridge forwards the command to Arduino.
10. Arduino updates the fan state on the real prototype.

---

## 🚀 Quick Start

### 1. Start the Docker stack

#### Windows

```bat
scripts\up.bat
```

#### macOS / Linux

```bash
./scripts/up.sh
```

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
http://127.0.0.1:1880/admin/
```

#### Dashboard

```text
http://localhost:1880/offgas-dashboard/
```

---

## 📂 Main Project Folders

```text
Bridge/                    # Python bridge for the real prototype
Doc/                       # Project documentation and technical PDFs
arduino_ide_offgas/        # Arduino firmware
dataset_other_garage/      # CSV datasets for G2-G6 simulation
docker/                    # Docker runtime files
offgas_ai_demo/            # AI demo for future forecasting integration
offgas_dashboard_linked/   # React + Vite dashboard source
scripts/                   # Start/stop/rebuild helper scripts
```

---

## 🎓 Academic Context

This project was realized for the **UniMORE – IoT Course (2025/2026)**.

**Prof. Roberto Vezzani**  
**Asst. Vittorio Cuculo**

---

## 👥 Contributors

- **Elena Bernini**
- **Filippo Giusti**
- **Piergiorgio Signorino**
