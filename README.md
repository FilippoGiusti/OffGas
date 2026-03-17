# 🚗💨 OffGas

> **An IoT monitoring and control system for detecting possible offgassing events in EV garage environments.**

---

## ✨ Overview

**OffGas** is an IoT project designed to monitor gas concentration in a garage environment and react when the measured values suggest a potentially dangerous condition.

The system is built around a **real prototype unit, G1**, equipped with a gas sensor and a ventilation fan. To provide a comparison baseline, the dashboard also shows **five additional units (G2–G6)**, which are **simulated from CSV datasets**.

This is an important design choice:

- **G1** is the **only real physical prototype** in the current implementation.
- **G2–G6** are **comparison units simulated through datasets**.
- The interface is intentionally limited to **6 total units** for clarity and readability.

The project combines:

- **Arduino** for sensing and actuation
- **HC-05 Bluetooth** communication between Arduino and the Python bridge
- **Python Bridge** for hardware/MQTT integration
- **Node-RED** for cloud logic, orchestration, and APIs
- **A web dashboard** for monitoring and manual control
- **Docker** to make the software environment reproducible across different machines

---

## 🎯 Project Goal

The goal of OffGas is not just to read a gas sensor value, but to implement a **distributed monitoring logic** capable of distinguishing between:

- a **local abnormal increase** in the monitored garage (**possible offgassing event in G1**), and
- a **general environmental variation** affecting the comparison units as well.

In other words, the project tries to answer a practical question:

> **Is the detected gas increase specific to the monitored garage, or is it part of a broader environmental trend?**

To support this, the system compares the live value of **G1** against the behavior of the simulated comparison units **G2–G6**.

---

## 🧱 System Architecture

The project is composed of four main layers.

### 1. Arduino (edge device)

Arduino is the hardware node of the system.

It is connected to:

- an **MQ-2 gas sensor**
- an **HC-05 Bluetooth module**
- a **DC fan**
- status LEDs / OLED display (if enabled in the hardware setup)

Its role is intentionally simple:

- read the gas sensor
- send measurements via Bluetooth
- receive commands to switch the fan on or off

Arduino **does not take autonomous control decisions**.

---

### 2. Python Bridge

The file `Bridge/bridge.py` acts as the hardware/software gateway.

It is responsible for:

- opening the Bluetooth serial connection to Arduino through the **HC-05** module
- reading gas values sent by the firmware in the form `MQ2:<value>`
- validating incoming data
- adding timestamps
- loading comparison data from CSV datasets
- computing a reference threshold
- publishing telemetry through MQTT
- receiving commands from Node-RED
- forwarding commands back to Arduino

### MQTT topics used by the bridge

- `garages/G1/telemetry`
- `garages/G1/alerts`
- `garages/G1/cmd`

---

### 3. Node-RED

Node-RED is the **cloud/orchestration layer** of the project.

It receives telemetry from the bridge and performs the main system logic, including:

- telemetry processing
- threshold-based anomaly detection
- predictive analysis
- dashboard state generation
- dataset switching
- manual and automatic fan control
- API exposure for the dashboard
- optional Telegram notifications

Node-RED is the component that turns raw telemetry into an actionable system state.

---

### 4. Web Dashboard

The dashboard is the browser-based interface used to observe the system and interact with it.

It shows:

- the current values for **G1–G6**
- average concentration and safety threshold
- predictive and critical warnings
- ventilation status
- manual control (`OFF / AUTO / ON`)
- emergency shutoff mode
- dataset selection for the simulated comparison units

The dashboard is served by Node-RED at:

```text
http://localhost:1880/offgas-dashboard/
```

---

## 🧪 Real Unit vs Simulated Units

### ✅ G1: real prototype

**G1** is the real, physical monitored garage.

Its data comes from:

- MQ-2 sensor → Arduino
- Arduino → HC-05 Bluetooth
- HC-05 → Python bridge
- Python bridge → MQTT → Node-RED

### 🧩 G2–G6: simulated comparison units

The other displayed units are **not real sensors in the current prototype**.

They are generated from CSV datasets stored in:

```text
dataset_other_garage/
```

These datasets simulate the gas levels of the comparison garages.

The dashboard intentionally displays **only 6 units total**:

- **G1** → real unit
- **G2–G6** → simulated comparison units

This keeps the interface readable while still showing a meaningful distributed comparison.

---

## 📂 Available Datasets

The project includes multiple datasets for the simulated comparison units:

- `dataset_garage.csv`
- `dataset_high_pollution.csv`
- `dataset_low_pollution.csv`
- `dataset_realistic_pollution.csv`

These files represent different environmental scenarios for the comparison garages.

⚠️ Important:

- the datasets are used for the **comparison units only**
- **G1 is never generated from a dataset**

---

## 📐 How the Threshold Is Computed

The system uses a **reference safety threshold** based on the average gas concentration of the comparison units.

The bridge computes:

```text
others_mean = average gas concentration of the comparison dataset
threshold = others_mean × ANOMALY_FACTOR
```

In the current implementation:

```text
ANOMALY_FACTOR = 1.5
```

So, for example:

```text
others_mean = 78
threshold = 78 × 1.5 = 117
```

This threshold is published in the telemetry of **G1** and then used by Node-RED for anomaly detection and prediction logic.

### Why this matters

This means the system does **not** use a hardcoded threshold. Instead, the threshold adapts to the comparison scenario represented by the active dataset.

---

## 📈 How Prediction Works

Node-RED performs a predictive analysis based on the recent trend of gas measurements.

The logic is based on:

- a **moving average** of recent gas values
- the **difference between the current moving average and the previous one**
- an extrapolated predicted gas value

### Prediction steps

1. Node-RED stores a short history of recent gas values.
2. It computes the current **moving average**.
3. It compares the current moving average with the previous moving average:

```text
growthRate = movingAvg - previousAvg
```

4. It predicts a future gas value:

```text
predictedGas = gas + (growthRate × 150)
```

5. If the predicted gas value crosses the threshold, Node-RED flags a:

```text
predicted_crossing = true
```

### Meaning of the prediction

This allows the system to trigger a **predictive warning** even when the current measured value is still below the threshold, if the trend suggests that the threshold is likely to be crossed soon.

---

## 🚨 Detection Logic

Node-RED distinguishes between two main situations:

### 1. Critical anomaly

A critical anomaly occurs when:

```text
gas > threshold
```

In this case the system considers the unit already above the safety threshold.

### 2. Predictive warning

A predictive warning occurs when:

```text
predictedGas > threshold
```

In this case the system detects a likely future crossing based on the recent concentration trend.

This is what enables **preventive ventilation** before the value becomes critical.

---

## 🔁 How Node-RED Uses the Data

Node-RED receives live telemetry from the bridge on:

```text
garages/G1/telemetry
```

Then it performs the main flow:

```text
MQTT IN → PredictionNextValue → AnomalyDetection → MQTT OUT
```

In parallel, Node-RED also:

- exposes HTTP endpoints for the dashboard
- manages dataset selection for G2–G6
- maintains the state of the comparison units
- handles emergency shutoff behavior
- supports manual fan commands

---

## 🐳 Docker Integration

To avoid machine-specific setup issues, the project includes a **Docker-based runtime**.

The idea is simple:

- keep the **bridge local** (because it needs access to the Bluetooth-connected prototype)
- move **Node-RED + Mosquitto + dashboard serving** into Docker
- make the software stack reproducible for the whole team

### Why Docker is used

Docker makes it possible to:

- share the exact same Node-RED environment
- avoid manual installation differences across machines
- keep MQTT configuration consistent
- serve the dashboard in the same way for every team member
- reduce setup friction when cloning the project from Git

### Services included

The Docker stack runs:

- **Mosquitto** → MQTT broker
- **Node-RED** → logic, APIs, and dashboard serving

The bridge remains outside Docker and connects to the MQTT broker exposed on the host machine.

---

## 🔌 Why the Bridge Stays Local

The Python bridge communicates with the real prototype through the **HC-05 Bluetooth module**.

Because Bluetooth serial devices are highly dependent on the local operating system and COM/serial configuration, the bridge is intentionally kept **outside Docker**.

This avoids unnecessary problems with:

- serial port mapping
- Bluetooth permissions
- host-specific device discovery

Instead:

- Docker exposes MQTT on host port **1883**
- the bridge keeps using its normal local MQTT configuration
- Node-RED inside Docker connects to the broker through the Docker network

This keeps the hardware side stable while still making the cloud side reproducible.

---

## ▶️ How to Start, Stop, and Update the Project

The repository includes helper scripts so the team can run the same setup without manually typing Docker commands.

### Available scripts

#### Windows

- `scripts\up.bat` → starts the Docker stack
- `scripts\down.bat` → stops the Docker stack
- `scripts\rebuild-dashboard.bat` → rebuilds the dashboard frontend when the UI code changes

#### Linux / macOS

- `scripts/up.sh` → starts the Docker stack
- `scripts/down.sh` → stops the Docker stack
- `scripts/rebuild-dashboard.sh` → rebuilds the dashboard frontend when the UI code changes

### Start the software stack

From the project root, run one of the following:

#### Windows

```bat
scripts\up.bat
```

#### Linux / macOS

```bash
./scripts/up.sh
```

This starts:

- Mosquitto broker
- Node-RED
- dashboard serving through Node-RED

### Stop the software stack

#### Windows

```bat
scripts\down.bat
```

#### Linux / macOS

```bash
./scripts/down.sh
```

### Rebuild the dashboard after frontend changes

If the dashboard code inside `offgas_dashboard_linked/` is changed, rebuild it with:

#### Windows

```bat
scripts\rebuild-dashboard.bat
```

#### Linux / macOS

```bash
./scripts/rebuild-dashboard.sh
```

### Start the bridge locally

If you want to use the **real prototype**, the bridge must **always** be started locally on the machine that is physically connected to the HC-05 Bluetooth module.

Typical command:

```bash
python Bridge/bridge.py
```

Make sure that:

- the **HC-05** Bluetooth serial connection is available
- the bridge serial port in `bridge.py` matches the local machine configuration
- the Docker stack is already running so MQTT is exposed on host port `1883`

Without the locally running bridge, the software stack still starts correctly, but it will only work with simulated/test data and not with the real prototype.

---

## 🌐 Pages to Open

### Node-RED editor

```text
http://127.0.0.1:1880/admin/#flow/120ca2f2695d22bc
```

### Dashboard

```text
http://localhost:1880/offgas-dashboard/
```

### Useful API endpoints

```text
http://localhost:1880/api/health
http://localhost:1880/api/state
http://localhost:1880/api/datasets
```

---

## 🧭 Typical Runtime Flow

A simplified end-to-end sequence is:

1. Arduino reads the MQ-2 sensor.
2. Arduino sends the value over Bluetooth through the **HC-05** module.
3. The Python bridge receives the value.
4. The bridge computes the reference threshold from the comparison dataset.
5. The bridge publishes telemetry over MQTT.
6. Node-RED receives telemetry.
7. Node-RED computes prediction and anomaly state.
8. Node-RED updates the dashboard state.
9. Node-RED sends automatic or manual commands back to the bridge.
10. The bridge forwards commands to Arduino and the fan is updated.

---

## 🛠️ Main Project Folders

```text
Bridge/                    # Python bridge to the real prototype
Doc/                       # Project documentation PDFs
arduino_ide_offgas/        # Arduino firmware
dataset_other_garage/      # CSV datasets for simulated comparison units
offgas_dashboard_linked/   # Dashboard frontend
.node-red/ or docker/...   # Node-RED runtime data and Docker setup
```

---

## 📝 Notes

- The dashboard is intentionally limited to **6 displayed units**.
- **G1 is real**; **G2–G6 are dataset-driven simulation units**.
- The threshold is derived from the average behavior of the comparison units.
- Prediction is based on **trend**, not only on the current value.
- The bridge remains local because of the real Bluetooth hardware connection through the **HC-05** module.

---

## 🎓 Academic Context

This project was realized for the **UniMORE - IoT Course (2025/2026)**.

**Prof. Roberto Vezzani**  
**Asst. Vittorio Cuculo**

## 👥 Contributors

- **Elena Bernini**
- **Filippo Giusti**
- **Piergiorgio Signorino**