import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import { connect, MqttClient } from "mqtt";

type ManualMode = "AUTO" | "ON" | "OFF";
type ManualCommand = "FAN_ON" | "FAN_OFF" | "AUTO" | "AUTO_MODE" | null;

interface TelemetryPayload {
  garage_id: string;
  gas: number;
  threshold: number;
  timestamp: string;
  fan_state: boolean;
}

interface AutoDecisionPayload {
  mode: "STD";
  anomaly: boolean;
  predicted_crossing: boolean;
  predicted_gas?: number;
}

interface AlertPayload {
  garage_id?: string;
  event?: string;
  command?: string;
  timestamp?: string;
  [key: string]: unknown;
}

interface DatasetRow {
  garage_id: string;
  value: number;
}

interface DatasetConfig {
  label: string;
  rows: DatasetRow[];
}

interface DashboardSensor {
  garage_id: string;
  value: number;
  threshold: number;
  status: "SAFE" | "WARNING" | "CRITICAL";
  source: "LIVE" | "DATASET";
  fan_active: boolean;
}

interface DashboardState {
  mqtt_connected: boolean;
  broker_url: string;
  telemetry: TelemetryPayload | null;
  latest_auto_command: AutoDecisionPayload | null;
  latest_manual_command: ManualCommand;
  latest_alert: AlertPayload | null;
  others_all: DatasetRow[];
  others_displayed: DatasetRow[];
  others_mean: number;
  threshold: number;
  anomaly_factor: number;
  mode: ManualMode;
  display_sensors: DashboardSensor[];
  updated_at: string;
  dataset_path: string | null;
  dataset_name: string | null;
  available_datasets: string[];
  selected_dataset: number;
  shutdown_active: boolean;
}

const MQTT_HOST = process.env.MQTT_HOST || "localhost";
const MQTT_PORT = Number(process.env.MQTT_PORT || 1883);
const MQTT_URL = process.env.MQTT_URL || `mqtt://${MQTT_HOST}:${MQTT_PORT}`;

const TOPIC_TELEMETRY = process.env.TOPIC_TELEMETRY || "garages/G1/telemetry";
const TOPIC_COMMANDS = process.env.TOPIC_COMMANDS || "garages/G1/cmd";
const TOPIC_ALERTS = process.env.TOPIC_ALERTS || "garages/G1/alerts";

const ANOMALY_FACTOR = Number(process.env.ANOMALY_FACTOR || 1.5);
const DISPLAY_LIMIT = Number(process.env.DISPLAY_LIMIT || 6);
const PORT = Number(process.env.PORT || 3000);

const EMBEDDED_DATASETS: DatasetConfig[] = [
  {
    label: "Nominal State",
    rows: [
      { garage_id: "G2", value: 100 },
      { garage_id: "G3", value: 98 },
      { garage_id: "G4", value: 101 },
      { garage_id: "G5", value: 101 },
      { garage_id: "G6", value: 99 },
      { garage_id: "G7", value: 100 },
      { garage_id: "G8", value: 101 },
      { garage_id: "G9", value: 101 },
      { garage_id: "G10", value: 99 },
      { garage_id: "G11", value: 100 },
    ],
  },
  {
    label: "Critical State",
    rows: [
      { garage_id: "G2", value: 311 },
      { garage_id: "G3", value: 251 },
      { garage_id: "G4", value: 250 },
      { garage_id: "G5", value: 265 },
      { garage_id: "G6", value: 286 },
      { garage_id: "G7", value: 292 },
      { garage_id: "G8", value: 291 },
      { garage_id: "G9", value: 316 },
      { garage_id: "G10", value: 316 },
      { garage_id: "G11", value: 275 },
    ],
  },
  {
    label: "Elevated State",
    rows: [
      { garage_id: "G2", value: 110 },
      { garage_id: "G3", value: 120 },
      { garage_id: "G4", value: 130 },
      { garage_id: "G5", value: 112 },
      { garage_id: "G6", value: 108 },
      { garage_id: "G7", value: 125 },
      { garage_id: "G8", value: 118 },
      { garage_id: "G9", value: 122 },
      { garage_id: "G10", value: 115 },
      { garage_id: "G11", value: 117 },
    ],
  },
  {
    label: "Mixed State",
    rows: [
      { garage_id: "G2", value: 112 },
      { garage_id: "G3", value: 119 },
      { garage_id: "G4", value: 120 },
      { garage_id: "G5", value: 128 },
      { garage_id: "G6", value: 95 },
      { garage_id: "G7", value: 91 },
      { garage_id: "G8", value: 139 },
      { garage_id: "G9", value: 121 },
      { garage_id: "G10", value: 114 },
      { garage_id: "G11", value: 117 },
    ],
  },
];

const runtimeState: DashboardState = {
  mqtt_connected: false,
  broker_url: MQTT_URL,
  telemetry: null,
  latest_auto_command: null,
  latest_manual_command: "AUTO",
  latest_alert: null,
  others_all: [],
  others_displayed: [],
  others_mean: 0,
  threshold: 0,
  anomaly_factor: ANOMALY_FACTOR,
  mode: "AUTO",
  display_sensors: [],
  updated_at: new Date().toISOString(),
  dataset_path: null,
  dataset_name: EMBEDDED_DATASETS[0].label,
  available_datasets: EMBEDDED_DATASETS.map((dataset) => dataset.label),
  selected_dataset: 0,
  shutdown_active: false,
};

let mqttClient: MqttClient | null = null;

function randomNoise() {
  return Math.floor(Math.random() * 31) - 15;
}

function cloneSelectedDatasetWithNoise(): DatasetRow[] {
  const selected = EMBEDDED_DATASETS[runtimeState.selected_dataset] ?? EMBEDDED_DATASETS[0];
  return selected.rows.map((row) => ({
    garage_id: row.garage_id,
    value: Math.max(0, row.value + randomNoise()),
  }));
}

function computeMean(rows: DatasetRow[]): number {
  if (!rows.length) return 0;
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  return Number((total / rows.length).toFixed(2));
}

function computeThreshold() {
  const liveThreshold = runtimeState.telemetry?.threshold;
  if (typeof liveThreshold === "number" && Number.isFinite(liveThreshold)) {
    runtimeState.threshold = Number(liveThreshold.toFixed(2));
    return;
  }
  runtimeState.threshold = Number((runtimeState.others_mean * runtimeState.anomaly_factor).toFixed(2));
}

function computeStatus(value: number, threshold: number): "SAFE" | "WARNING" | "CRITICAL" {
  if (value >= threshold) return "CRITICAL";
  if (value >= threshold * 0.85) return "WARNING";
  return "SAFE";
}

function sensorFanActive(garageId: string, value: number, threshold: number): boolean {
  if (runtimeState.shutdown_active) return false;
  if (runtimeState.mode === "ON") return true;
  if (runtimeState.mode === "OFF") return false;

  if (garageId === "G1" && typeof runtimeState.telemetry?.fan_state === "boolean") {
    return runtimeState.telemetry.fan_state;
  }

  return value >= threshold * 0.75;
}

function refreshDisplaySensors(options?: { regenerateDataset?: boolean }) {
  const regenerateDataset = options?.regenerateDataset ?? false;

  if (regenerateDataset || runtimeState.others_all.length === 0) {
    runtimeState.others_all = cloneSelectedDatasetWithNoise();
    runtimeState.dataset_name = EMBEDDED_DATASETS[runtimeState.selected_dataset]?.label ?? EMBEDDED_DATASETS[0].label;
  }

  runtimeState.others_displayed = runtimeState.others_all.slice(0, Math.max(0, DISPLAY_LIMIT - 1));
  runtimeState.others_mean = computeMean(runtimeState.others_all);
  computeThreshold();

  const g1Value = runtimeState.shutdown_active ? 0 : runtimeState.telemetry?.gas ?? 0;

  const g1Sensor: DashboardSensor = {
    garage_id: "G1",
    value: g1Value,
    threshold: runtimeState.threshold,
    status: computeStatus(g1Value, runtimeState.threshold),
    source: "LIVE",
    fan_active: sensorFanActive("G1", g1Value, runtimeState.threshold),
  };

  const others: DashboardSensor[] = runtimeState.others_displayed.map((row) => {
    const value = runtimeState.shutdown_active ? 0 : row.value;
    return {
      garage_id: row.garage_id,
      value,
      threshold: runtimeState.threshold,
      status: computeStatus(value, runtimeState.threshold),
      source: "DATASET",
      fan_active: sensorFanActive(row.garage_id, value, runtimeState.threshold),
    };
  });

  runtimeState.display_sensors = [g1Sensor, ...others].slice(0, DISPLAY_LIMIT);
  runtimeState.updated_at = new Date().toISOString();
}

function manualCommandToMode(command: ManualCommand): ManualMode {
  if (command === "FAN_ON") return "ON";
  if (command === "FAN_OFF") return "OFF";
  return "AUTO";
}

function disconnectMqtt() {
  if (mqttClient) {
    mqttClient.removeAllListeners();
    mqttClient.end(true);
    mqttClient = null;
  }
  runtimeState.mqtt_connected = false;
  runtimeState.updated_at = new Date().toISOString();
}

function connectMqtt() {
  if (runtimeState.shutdown_active || mqttClient) return;

  mqttClient = connect(MQTT_URL, { reconnectPeriod: 2000 });

  mqttClient.on("connect", () => {
    runtimeState.mqtt_connected = true;
    mqttClient?.subscribe([TOPIC_TELEMETRY, TOPIC_COMMANDS, TOPIC_ALERTS]);
    runtimeState.updated_at = new Date().toISOString();
  });

  mqttClient.on("reconnect", () => {
    runtimeState.mqtt_connected = false;
    runtimeState.updated_at = new Date().toISOString();
  });

  mqttClient.on("offline", () => {
    runtimeState.mqtt_connected = false;
    runtimeState.updated_at = new Date().toISOString();
  });

  mqttClient.on("close", () => {
    runtimeState.mqtt_connected = false;
    runtimeState.updated_at = new Date().toISOString();
    if (!runtimeState.shutdown_active) {
      mqttClient = null;
    }
  });

  mqttClient.on("error", () => {
    runtimeState.mqtt_connected = false;
    runtimeState.updated_at = new Date().toISOString();
  });

  mqttClient.on("message", (topic, payloadBuffer) => {
    if (runtimeState.shutdown_active) return;

    const raw = payloadBuffer.toString("utf-8").trim();

    if (topic === TOPIC_TELEMETRY) {
      try {
        runtimeState.telemetry = JSON.parse(raw) as TelemetryPayload;
        refreshDisplaySensors({ regenerateDataset: true });
      } catch (error) {
        console.error("Invalid telemetry payload:", raw, error);
      }
      return;
    }

    if (topic === TOPIC_COMMANDS) {
      try {
        runtimeState.latest_auto_command = JSON.parse(raw) as AutoDecisionPayload;
        refreshDisplaySensors();
        return;
      } catch {
        const command = raw.toUpperCase();
        if (command === "FAN_ON" || command === "FAN_OFF" || command === "AUTO" || command === "AUTO_MODE") {
          runtimeState.latest_manual_command = command as ManualCommand;
          runtimeState.mode = manualCommandToMode(runtimeState.latest_manual_command);
          refreshDisplaySensors();
        }
      }
      return;
    }

    if (topic === TOPIC_ALERTS) {
      try {
        runtimeState.latest_alert = JSON.parse(raw) as AlertPayload;
      } catch {
        runtimeState.latest_alert = { event: raw };
      }
      runtimeState.updated_at = new Date().toISOString();
    }
  });
}

function publishControl(mode: ManualMode) {
  if (!mqttClient || !runtimeState.mqtt_connected) {
    throw new Error("MQTT bridge is offline");
  }

  const payload = mode === "ON" ? "FAN_ON" : mode === "OFF" ? "FAN_OFF" : "AUTO";
  mqttClient.publish(TOPIC_COMMANDS, payload);
  runtimeState.latest_manual_command = payload as ManualCommand;
  runtimeState.mode = mode;
  refreshDisplaySensors();
}

refreshDisplaySensors({ regenerateDataset: true });

async function startServer() {
  const app = express();
  app.use(express.json());

  connectMqtt();

  app.get("/api/state", (_req, res) => {
    res.json(runtimeState);
  });

  app.post("/api/control", (req, res) => {
    const mode = String(req.body?.mode || "").toUpperCase() as ManualMode;

    if (!["AUTO", "ON", "OFF"].includes(mode)) {
      res.status(400).json({ error: "mode must be AUTO, ON, or OFF" });
      return;
    }

    if (runtimeState.shutdown_active) {
      res.status(409).json({ error: "System is in emergency shutoff" });
      return;
    }

    try {
      publishControl(mode);
      res.json(runtimeState);
    } catch (error) {
      res.status(503).json({ error: error instanceof Error ? error.message : "Unable to publish command" });
    }
  });

  app.get("/api/datasets", (_req, res) => {
    res.json({
      datasets: runtimeState.available_datasets,
      selected_dataset: runtimeState.selected_dataset,
    });
  });

  app.post("/api/dataset", (req, res) => {
    const index = Number(req.body?.index);

    if (!Number.isInteger(index) || index < 0 || index >= EMBEDDED_DATASETS.length) {
      res.status(400).json({ error: "Invalid dataset index" });
      return;
    }

    runtimeState.selected_dataset = index;
    refreshDisplaySensors({ regenerateDataset: true });
    res.json(runtimeState);
  });

  app.post("/api/emergency", (req, res) => {
    const active = Boolean(req.body?.active);
    runtimeState.shutdown_active = active;

    if (active) {
      disconnectMqtt();
      refreshDisplaySensors();
      res.json(runtimeState);
      return;
    }

    connectMqtt();
    refreshDisplaySensors({ regenerateDataset: true });
    res.json(runtimeState);
  });

  app.get("/api/health", (_req, res) => {
    res.json({
      ok: true,
      mqtt_connected: runtimeState.mqtt_connected,
      broker_url: runtimeState.broker_url,
      dataset_name: runtimeState.dataset_name,
      shutdown_active: runtimeState.shutdown_active,
    });
  });

  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
    console.log(`MQTT broker: ${MQTT_URL}`);
    console.log(`Dataset mode: embedded selectable datasets`);
  });
}

startServer();
