"""
OFFGAS SYSTEM BRIDGE

Funzioni:
- Legge sensore gas da Arduino via Bluetooth
- Invia telemetria via MQTT
- Riceve comandi da Node-RED
- Controlla ventola
- Salva dati su CSV (AI dataset)
- Salva log di sistema su file testo
"""

# ===============================
# IMPORT LIBRARIES
# ===============================

import serial
import json
import time
import datetime
import csv
import os
import paho.mqtt.client as mqtt


# ===============================
# CONFIGURAZIONE
# ===============================

class Config:

    SERIAL_PORT = "COM6"
    BAUD_RATE = 9600

    MQTT_BROKER = "host.docker.internal"
    MQTT_PORT = 1883

    TOPIC_TELEMETRY = "garages/G1/telemetry"
    TOPIC_ALERTS = "garages/G1/alerts"
    TOPIC_COMMANDS = "garages/G1/cmd"

    CSV_FILE = "gas_data.csv"
    LOG_FILE = "system_logs.txt"


# ===============================
# CSV LOGGER (AI DATASET)
# ===============================

class DataLogger:

    def __init__(self, filename):

        self.filename = filename

        if not os.path.exists(self.filename):

            with open(self.filename, "w", newline="") as file:

                writer = csv.writer(file)

                writer.writerow([
                    "timestamp",
                    "garage_id",
                    "gas",
                    "fan_state"
                ])

    def save(self, payload):

        with open(self.filename, "a", newline="") as file:

            writer = csv.writer(file)

            writer.writerow([
                payload["timestamp"],
                payload["garage_id"],
                payload["gas"],
                payload["fan_state"]
            ])


# ===============================
# SYSTEM LOGGER (EVENT LOG)
# ===============================

class SystemLogger:

    def __init__(self, filename):

        self.filename = filename

        if not os.path.exists(self.filename):

            with open(self.filename, "w") as f:

                f.write(
                    "OFFGAS SYSTEM LOGS\n"
                    "============================================================\n\n"
                )

    def log(self, event, garage="G1", gas=None, topic=None, status="INFO"):

        timestamp = datetime.datetime.now().isoformat()

        line = (
            f"[{timestamp}] "
            f"EVENT={event} | "
            f"GARAGE={garage} | "
            f"GAS={gas} | "
            f"TOPIC={topic} | "
            f"STATUS={status}\n"
        )

        with open(self.filename, "a") as f:
            f.write(line)


# ===============================
# BLUETOOTH MANAGER
# ===============================

class BluetoothManager:

    def __init__(self, config):

        self.port = config.SERIAL_PORT
        self.baud_rate = config.BAUD_RATE
        self.ser = None

    def connect(self):

        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            timeout=None
        )

    def read_line(self):

        line = self.ser.readline().decode("utf-8", errors="ignore").strip()

        if line.startswith("MQ2:"):

            try:

                gas = int(line.split(":")[1])

                return {
                    "gas": gas,
                    "timestamp": datetime.datetime.now().isoformat()
                }

            except:
                return None

        return None

    def send_command(self, cmd):

        if self.ser:
            self.ser.write(cmd.encode("utf-8"))


# ===============================
# FAN CONTROLLER
# ===============================

class FanController:

    def __init__(self, bt):

        self.bluetooth = bt
        self.fan_state = False
        self.manual_override = False

    def force_on(self):

        self.fan_state = True
        self.bluetooth.send_command("FAN_ON\n")

    def force_off(self):

        self.fan_state = False
        self.bluetooth.send_command("FAN_OFF\n")

    def set_auto(self):

        self.manual_override = False


# ===============================
# MQTT MANAGER
# ===============================

class MQTTManager:

    def __init__(self, config, fan, bridge):

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT)
        self.client.loop_start()

        self.topic_telemetry = config.TOPIC_TELEMETRY
        self.topic_alerts = config.TOPIC_ALERTS
        self.topic_commands = config.TOPIC_COMMANDS

        self.fan = fan
        self.bridge = bridge

        self.client.on_message = self.on_message

    def publish(self, payload):

        self.client.publish(
            self.topic_telemetry,
            json.dumps(payload)
        )

    def subscribe(self):

        self.client.subscribe(self.topic_commands)

    def on_message(self, client, userdata, msg):

        try:

            raw = msg.payload.decode().strip()

            try:

                cmd = json.loads(raw)

                if self.fan.manual_override:
                    return

                if cmd.get("mode") == "STD":

                    if cmd.get("anomaly") or cmd.get("predicted_crossing"):
                        self.fan.force_on()
                    else:
                        self.fan.force_off()

                return

            except json.JSONDecodeError:

                cmd = raw

            if cmd in ("FAN_ON", "ON"):

                self.fan.manual_override = True
                self.fan.force_on()

            elif cmd in ("FAN_OFF", "OFF"):

                self.fan.manual_override = True
                self.fan.force_off()

            elif cmd in ("AUTO", "AUTO_MODE"):

                self.fan.set_auto()

        except Exception as e:

            print(f"[MQTT ERROR] {e}")


# ===============================
# BRIDGE CORE
# ===============================

class Bridge:

    def __init__(self):

        self.config = Config()

        self.bluetooth = BluetoothManager(self.config)
        self.fan = FanController(self.bluetooth)
        self.mqtt = MQTTManager(self.config, self.fan, self)

        # FILES
        self.logger = DataLogger(self.config.CSV_FILE)
        self.syslog = SystemLogger(self.config.LOG_FILE)

        self.last_gas = None

    def start(self):

        self.bluetooth.connect()

        self.syslog.log(
            event="BRIDGE_CONNECTED",
            topic=self.config.TOPIC_TELEMETRY,
            status="OK"
        )

        self.mqtt.subscribe()

        try:

            while True:

                data = self.bluetooth.read_line()

                if data:
                    self.process(data)

                time.sleep(0.2)

        except KeyboardInterrupt:

            self.stop()

    def process(self, data):

        self.last_gas = data["gas"]

        payload = {
            "garage_id": "G1",
            "gas": data["gas"],
            "timestamp": data["timestamp"],
            "fan_state": self.fan.fan_state
        }

        # MQTT
        self.mqtt.publish(payload)

        # CSV (AI DATASET)
        self.logger.save(payload)

        # SYSTEM LOG
        self.syslog.log(
            event="TELEMETRY_SENT",
            gas=data["gas"],
            topic=self.config.TOPIC_TELEMETRY,
            status="INFO"
        )

    def stop(self):

        self.syslog.log(
            event="SYSTEM_STOPPED",
            gas=self.last_gas,
            status="WARNING"
        )

        self.fan.force_off()


# ===============================
# MAIN
# ===============================

if __name__ == "__main__":

    bridge = Bridge()
    bridge.start()