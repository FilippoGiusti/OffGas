"""
Responsabilità del Bridge:
- leggere il valore gas dall'Arduino via Bluetooth
- pubblicare la telemetria via MQTT
- ricevere comandi da Node-RED
- controllare la ventola tramite Arduino
"""

# ===============================
# IMPORT LIBRARIES
# ===============================

import serial
import json
import time
import datetime
import paho.mqtt.client as mqtt


# ===============================
# CONFIGURAZIONE
# ===============================

class Config:
    """Contiene parametri di configurazione del sistema."""

    SERIAL_PORT = "COM6"
    BAUD_RATE = 9600

    # Se Mosquitto gira in Docker usa "host.docker.internal"
    # Se usi lo stack completamente locale usa "localhost"
    MQTT_BROKER = "host.docker.internal"
    MQTT_PORT = 1883

    TOPIC_TELEMETRY = "garages/G1/telemetry"
    TOPIC_ALERTS = "garages/G1/alerts"
    TOPIC_COMMANDS = "garages/G1/cmd"


# ===============================
# BLUETOOTH MANAGER
# ===============================

class BluetoothManager:
    """Gestisce comunicazione Bluetooth con Arduino."""

    def __init__(self, config: Config):
        self.port = config.SERIAL_PORT
        self.baud_rate = config.BAUD_RATE
        self.timeout = None
        self.ser = None

    def connect(self):
        """Apre la connessione seriale."""
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            timeout=self.timeout
        )

    def read_line(self):
        """Legge una riga dalla seriale."""
        read_val = self.ser.readline().decode("utf-8", errors="ignore").strip()

        if read_val.startswith("MQ2:"):
            try:
                val_gas = int(read_val.split(":", 1)[1])
                timestamp = datetime.datetime.now().isoformat()
                return {
                    "gas": val_gas,
                    "timestamp": timestamp
                }
            except ValueError:
                return None

        return None

    def send_command(self, command: str):
        """Invia comando ad Arduino (FAN_ON / FAN_OFF)."""
        if not self.ser:
            raise RuntimeError("Bluetooth not connected")

        self.ser.write(command.encode("utf-8"))


# ===============================
# FAN CONTROLLER
# ===============================

class FanController:
    """Gestisce stato ventola e override manuale."""

    def __init__(self, bluetooth_manager: BluetoothManager, config: Config):
        self.fan_state = False
        self.bluetooth = bluetooth_manager
        self.manual_override = False

    def force_on(self):
        """Forza accensione."""
        self.fan_state = True
        self.bluetooth.send_command("FAN_ON\n")

    def force_off(self):
        """Forza spegnimento."""
        self.fan_state = False
        self.bluetooth.send_command("FAN_OFF\n")

    def set_auto_mode(self):
        """Disabilita override manuale e torna in automatico."""
        self.manual_override = False


# ===============================
# MQTT MANAGER
# ===============================

class MQTTManager:
    """Gestisce comunicazione MQTT con Node-RED."""

    def __init__(self, config: Config, fan_controller: FanController, bridge):
        self.broker = config.MQTT_BROKER
        self.port = config.MQTT_PORT

        self.fan_controller = fan_controller
        self.bridge = bridge

        self.topic_telemetry = config.TOPIC_TELEMETRY
        self.topic_alerts = config.TOPIC_ALERTS
        self.topic_commands = config.TOPIC_COMMANDS

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_message = self.on_message

    def connect(self):
        """Connette al broker MQTT."""
        self.client.connect(self.broker, self.port)
        self.client.loop_start()

    def publish_telemetry(self, payload: dict):
        """Pubblica telemetria su topic."""
        message = json.dumps(payload)
        self.client.publish(self.topic_telemetry, message)

    def publish_alert(self, payload: dict):
        """Pubblica evento di allarme."""
        message = json.dumps(payload)
        self.client.publish(self.topic_alerts, message)

    def subscribe_commands(self):
        """Sottoscrive topic comandi manuali."""
        self.client.subscribe(self.topic_commands)

    def on_message(self, client, userdata, msg):
        """
        Gestisce i messaggi ricevuti dal topic dei comandi.

        I comandi possono essere:
        - JSON (STD mode calcolato da Node-RED)
        - stringa (FAN_ON, FAN_OFF, AUTO)
        """
        try:
            raw = msg.payload.decode("utf-8").strip()

            try:
                command = json.loads(raw)

                # Se siamo in manual override ignoriamo i comandi automatici
                if self.fan_controller.manual_override:
                    return

                if command.get("mode") == "STD":
                    if command.get("anomaly") or command.get("predicted_crossing"):
                        print(f"[SERVER] anomaly/prediction detected → FAN_ON | gas={self.bridge.last_gas_value}")
                        print(f"[MQTT COMMAND] Received: {command}")
                        self.fan_controller.force_on()
                    else:
                        print(f"[SERVER] normal condition → FAN_OFF | gas={self.bridge.last_gas_value}")
                        print(f"[MQTT COMMAND] Received: {command}")
                        self.fan_controller.force_off()

                return

            except json.JSONDecodeError:
                command = raw
                print(f"[MQTT COMMAND] Received: {command}")

            if command in ("FAN_ON", "ON"):
                self.fan_controller.manual_override = True
                self.fan_controller.force_on()
                self.publish_alert({
                    "garage_id": "G1",
                    "event": "manual_override",
                    "command": "FAN_ON",
                    "timestamp": datetime.datetime.now().isoformat()
                })

            elif command in ("FAN_OFF", "OFF"):
                self.fan_controller.manual_override = True
                self.fan_controller.force_off()
                self.publish_alert({
                    "garage_id": "G1",
                    "event": "manual_override",
                    "command": "FAN_OFF",
                    "timestamp": datetime.datetime.now().isoformat()
                })

            elif command in ("AUTO_MODE", "AUTO"):
                self.fan_controller.set_auto_mode()
                self.publish_alert({
                    "garage_id": "G1",
                    "event": "manual_override",
                    "command": "AUTO_MODE",
                    "timestamp": datetime.datetime.now().isoformat()
                })

            else:
                print(f"[MQTT COMMAND] Unknown command: {command}")

        except Exception as e:
            print(f"[MQTT ERROR] {e}")


# ===============================
# BRIDGE CORE
# ===============================

class Bridge:
    """
    Componente centrale del sistema.

    Coordina:
    - lettura sensore
    - pubblicazione telemetria
    - ricezione comandi MQTT
    """

    def __init__(self):
        self.config = Config()
        self.bluetooth = BluetoothManager(self.config)
        self.fan_controller = FanController(self.bluetooth, self.config)
        self.mqtt = MQTTManager(self.config, self.fan_controller, self)
        self.running = True
        self.last_gas_value = None

    def start(self):
        """Avvia il sistema."""
        self.bluetooth.connect()
        self.mqtt.connect()
        self.mqtt.subscribe_commands()

        try:
            while self.running:
                data = self.bluetooth.read_line()

                if data:
                    self.process_cycle(data)

                time.sleep(0.2)

        except KeyboardInterrupt:
            self.stop()

    def process_cycle(self, data):
        self.last_gas_value = data["gas"]

        payload = {
            "garage_id": "G1",
            "gas": data["gas"],
            "timestamp": data["timestamp"],
            "fan_state": self.fan_controller.fan_state
        }

        self.mqtt.publish_telemetry(payload)

    def stop(self):
        """Arresta il sistema."""
        print("Arresto manuale")
        self.fan_controller.force_off()
        if self.bluetooth.ser:
            self.bluetooth.ser.close()


# ===============================
# ENTRY POINT
# ===============================

if __name__ == "__main__":
    bridge = Bridge()
    bridge.start()