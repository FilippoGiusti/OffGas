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
import os
import time
import datetime
import pandas as pd
import paho.mqtt.client as mqtt



# ===============================
# CONFIGURAZIONE
# ===============================

class Config:
    """Contiene parametri di configurazione del sistema."""

    SERIAL_PORT = "COM6"
    BAUD_RATE = 9600

    MQTT_BROKER = "localhost"
    MQTT_PORT = 1883

    TOPIC_TELEMETRY = "garages/G1/telemetry" #G1 è il garage di questo purificatore, nel dataset sono presenti G2,G3...
    TOPIC_ALERTS = "garages/G1/alerts"
    TOPIC_COMMANDS = "garages/G1/cmd"

    ANOMALY_FACTOR = 1.5 #lo imponiamo di 1.5, verrà moltiplicato per la media. Se la media è 100 basta 150 per accendere la ventola
    COOLDOWN_SECONDS = 5


# ===============================
# BLUETOOTH MANAGER
# ===============================

class BluetoothManager:
    """Gestisce comunicazione Bluetooth con Arduino."""

    def __init__(self, config: Config):
        self.port = config.SERIAL_PORT
        self.baud_rate = config.BAUD_RATE
        self.timeout = None

    def connect(self):
        """Apre la connessione seriale."""
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            timeout=self.timeout
        )

    def read_line(self):
        """Legge una riga dalla seriale."""
        read_val = self.ser.readline().decode('utf-8').strip()
        if read_val.startswith("MQ2:"): #MQ2 è il nome del sensore di gas utilizzato
            try:
                val_gas = int(read_val.split(':',1)[1])
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
# DATASET MANAGER
# ===============================

class DatasetManager:
    """Gestisce valori altri garage (simulazione o CSV)."""

    def __init__(self):
        # Ottiene il percorso assoluto del file Python corrente (dataset_manager.py)
        # __file__ → path del file corrente
        # os.path.abspath(...) → converte in percorso assoluto
        # os.path.dirname(...) → prende solo la directory che contiene il file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.dataset = os.path.normpath(os.path.join(
            base_dir,
            "..",
            "dataset_other_garage",
            "dataset_high_pollution.csv"
        ))

    def load_dataset(self):
        """Carica dataset da file o inizializza simulazione."""
        if not os.path.exists(self.dataset):
            raise FileNotFoundError(
                f"Dataset file not found: {self.dataset}"
            )
        df = pd.read_csv(self.dataset, sep=',')

        if df.empty:
            raise ValueError(
                f"Dataset is empty: {self.dataset}"
            )

        others_mean = df['gas_value'].mean() #calcolo la media dei valori degli altri garage
        others_std = df['gas_value'].std() #calcolo la deviazione standard degli altri garage

        return {
            "others_mean": others_mean,
            "others_std": others_std
        }



# ===============================
# FAN CONTROLLER
# ===============================

class FanController:
    """Gestisce stato ventola e prevenzione oscillazioni."""

    def __init__(self, bluetooth_manager: BluetoothManager, config: Config):
        self.fan_state = False #False = OFF, utile come info per dashboard da passare a node-red
        self.bluetooth = bluetooth_manager
        self.manual_override = False  # True = comandi manuali da MQTT attivi

    def force_on(self):
        """Forza accensione"""
        self.fan_state = True
        self.bluetooth.send_command("FAN_ON\n")


    def force_off(self):
        """Forza spegnimento"""
        self.fan_state = False
        self.bluetooth.send_command("FAN_OFF\n")


    def set_auto_mode(self):
        """Disabilita override manuale: torna a modalità automatica."""
        self.manual_override = False #la ventola torna a spegnersi o accendersi in base la soglia



# ===============================
# MQTT MANAGER
# ===============================

class MQTTManager:
    """Gestisce comunicazione MQTT con Node-RED."""

    def __init__(self, config: Config, fan_controller, bridge):
        # Salva configurazione broker e topic
        self.broker = config.MQTT_BROKER
        self.port = config.MQTT_PORT

        self.fan_controller = fan_controller

        self.bridge = bridge

        self.topic_telemetry = config.TOPIC_TELEMETRY
        self.topic_alerts = config.TOPIC_ALERTS
        self.topic_commands = config.TOPIC_COMMANDS

        # Crea client MQTT
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        # Registra callback per gestione messaggi in arrivo
        self.client.on_message = self.on_message

    def connect(self):
        """Connette al broker MQTT."""

        # Connessione al broker
        self.client.connect(self.broker, self.port)

        # Avvia loop di rete MQTT in thread separato
        # (gestisce ricezione messaggi e keepalive)
        self.client.loop_start()


    def publish_telemetry(self, payload: dict):
        """Pubblica telemetria su topic."""
        # Converte il payload in JSON
        message = json.dumps(payload)

        # Pubblica sul topic di telemetria
        self.client.publish(self.topic_telemetry, message)

    def publish_alert(self, payload: dict):
        """Pubblica evento di allarme."""
        # Converte payload in JSON
        message = json.dumps(payload)

        # Pubblica su topic alert
        self.client.publish(self.topic_alerts, message)

    def subscribe_commands(self):
        """Sottoscrive topic comandi manuali."""

        # Sottoscrizione al topic da cui arrivano i comandi
        self.client.subscribe(self.topic_commands)

    def on_message(self, client, userdata, msg):
        """
        Gestisce i messaggi ricevuti dal topic dei comandi.

        I comandi possono essere:
        - JSON (STD mode calcolato da Node-RED)
        - stringa (FAN_ON, FAN_OFF, AUTO)
        """

        try:
            # Decodifica il payload MQTT (che arriva come byte) in stringa UTF-8
            # e rimuove eventuali spazi o newline all'inizio e alla fine
            raw = msg.payload.decode("utf-8").strip()

            try:
                # Prova a interpretare la stringa ricevuta come JSON
                # Questo funziona quando il comando arriva da Node-RED come oggetto JSON,
                # ad esempio: {"mode": "STD", "anomaly": true}

                command = json.loads(raw)

                # condizione aggiornata: anomaly OR predicted_crossing(arriva nel payload da node-red)
                if command["mode"] == "STD":
                    if command["anomaly"] or command["predicted_crossing"]:

                        # Se siamo in manual override ignoriamo i comandi automatici. La ventola resta forzata da node-red
                        if self.fan_controller.manual_override:
                            return

                        print(
                            f"[SERVER] anomaly detected → FAN_ON | gas={self.bridge.last_gas_value} threshold={self.bridge.read_dataset['others_mean']}")

                        print(f"[MQTT COMMAND] Received: {command}")

                        self.fan_controller.force_on()

                    else:
                        print(
                            f"[SERVER] normal condition → FAN_OFF | gas={self.bridge.last_gas_value} threshold={self.bridge.read_dataset['others_mean']}")

                        print(f"[MQTT COMMAND] Received: {command}")

                        self.fan_controller.force_off()

                return #importante: serve a uscire dalla funzione perchè ho già interpretato il command

            except json.JSONDecodeError:
                # Se la conversione JSON fallisce significa che il payload NON è JSON
                # ma una semplice stringa (es: "FAN_ON", "FAN_OFF", "AUTO")
                # In questo caso manteniamo la stringa così com'è
                command = raw

                print(f"[MQTT COMMAND] Received: {command}")


            # Posso forzare l'avvio o spegnimento  della ventola da Nodered
            # Esempio logico:

            if command in ("FAN_ON", "ON"):
                # Override manuale: forza ON
                self.fan_controller.manual_override = True #lo pongo = True in questo modo forza la ventola a restare sempre ON (o OFF)
                self.fan_controller.force_on()
                self.publish_alert({
                    "garage_id": "G1",
                    "event": "manual_override",
                    "command": "FAN_ON",
                    "timestamp": datetime.datetime.now().isoformat()
                })

            elif command in ("FAN_OFF", "OFF"):
                # Override manuale: forza OFF
                self.fan_controller.manual_override = True
                self.fan_controller.force_off()
                self.publish_alert({
                    "garage_id": "G1",
                    "event": "manual_override",
                    "command": "FAN_OFF",
                    "timestamp": datetime.datetime.now().isoformat()
                })

            elif command in ("AUTO_MODE", "AUTO"):
                # Ritorna in automatico (anomaly detector decide al prossimo ciclo)
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
        self.dataset = DatasetManager()
        self.fan_controller = FanController(self.bluetooth, self.config)
        self.mqtt = MQTTManager(self.config, self.fan_controller, self)
        self.running = True
        self.last_gas_value = None

    def start(self):
        """Avvia il sistema."""
        self.bluetooth.connect()

        """Connessione al broker MQTT"""
        self.mqtt.connect()

        """Sottoscrizione ai comandi manuali"""
        self.mqtt.subscribe_commands()

        """Calcola media"""
        self.read_dataset = self.dataset.load_dataset()

        try:
            while self.running:
                """legge valore gas"""
                data = self.bluetooth.read_line()

                if data:
                    self.process_cycle(data)

                time.sleep(0.2) #per rallentare il ciclo

        except KeyboardInterrupt:
            self.stop()


    def process_cycle(self, data):

        self.last_gas_value = data["gas"]

        # ===============================
        # Pubblicazione telemetria MQTT
        # ===============================
        payload = {
        "garage_id": "G1",
        "gas": data["gas"], #valore del gas attuale
        "threshold": self.read_dataset['others_mean'] * self.config.ANOMALY_FACTOR ,
        "timestamp": data["timestamp"],
        "fan_state": self.fan_controller.fan_state
        }

        self.mqtt.publish_telemetry(payload)


    def stop(self):
        """Arresta il sistema."""
        print("Arresto manuale")
        self.fan_controller.force_off()
        self.bluetooth.ser.close()



# ===============================
# ENTRY POINT
# ===============================

if __name__ == "__main__":
    bridge = Bridge()
    bridge.start()
