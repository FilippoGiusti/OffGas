"""
Bridge IoT - Progetto Rilevazione Gas Distribuita

Responsabilità:
- Connessione Bluetooth con Arduino
- Lettura valore gas
- Calcolo media altri garage
- Regola di anomalia
- Controllo ventola
- Pubblicazione MQTT
- Ricezione comandi manuali
"""


# ===============================
# IMPORT LIBRARIES
# ===============================

import serial
import json
import os
import sys
import time
import datetime
import statistics
import threading
import pandas as pd
from collections import deque
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
            "dataset_low_pollution.csv"
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
# ANOMALY DETECTOR
# ===============================

class AnomalyDetector:
    """Contiene la logica di decisione anomalia."""

    def __init__(self, config: Config):
        self.k = config.ANOMALY_FACTOR


    def check_anomaly(self, my_gas, others_mean):
        """Restituisce True/False in base alla regola scelta."""
        if(my_gas > others_mean*self.k):
            return True
        else:
            return False





# ===============================
# FAN CONTROLLER
# ===============================

class FanController:
    """Gestisce stato ventola e prevenzione oscillazioni."""

    def __init__(self, bluetooth_manager: BluetoothManager, config: Config):
        self.fan_state = False #False = OFF
        self.bluetooth = bluetooth_manager
        self.manual_override = False  # True = comandi manuali da MQTT attivi

    def update_state(self, anomaly: bool):
        """Decide se inviare FAN_ON o FAN_OFF.(o in auto mode)"""

        if self.manual_override:
            # In manual override ignora l'anomaly detector
            return

        if(anomaly == True and self.fan_state == False):
            FanController.force_on(self)
        if(anomaly == False and self.fan_state == True):
            FanController.force_off(self)


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

    def __init__(self, config: Config, fan_controller):
        # Salva configurazione broker e topic
        self.broker = config.MQTT_BROKER
        self.port = config.MQTT_PORT

        self.fan_controller = fan_controller

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
        """Callback per gestione comandi manuali."""
        try:
            # Decodifica payload ricevuto
            command = msg.payload.decode("utf-8").strip().upper() #upper così anche se il comando è minuscolo funziona

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
# GAS PREDICTOR
# ===============================

class GasPredictor:
    """
    Predice andamento del gas usando:
    - moving average
    - velocità di crescita
    """

    def __init__(self, config: Config):

        # Numero di valori storici utilizzati
        self.window_size = 20

        # Orizzonte temporale della predizione
        # Abbiamo impostato nel ciclo un time.sleep(0.2), quindi ogni 0.2 secondi ho un ciclo. Prevedere il valore del gas tra 150 cicli significa prevedere il valore del gas tra 30 secondi --> 30 secondi / 0.2 sec ciclo ≈ 150 step
        self.prediction_steps = 150

        # History dei valori gas -> tiene traccia dei valori passati del gas (ultimi 20 valori se window size = 20)
        self.gas_history = deque(maxlen=self.window_size) #deque: è una coda dimensionale, aggiunge elementi sia a destra che a sinistra, più immediato che usare una lista

        # Media mobile precedente
        self.previous_moving_avg = None


    def update(self, gas_value, threshold):
        """
        Aggiorna history e calcola predizione.
        """

        # Aggiunge nuovo valore alla history
        self.gas_history.append(gas_value)

        # Non predice se non ci sono abbastanza dati
        if len(self.gas_history) < 5:
            return {
                "predicted_gas": gas_value,
                "predicted_crossing": False
            }

        # ===============================
        # Calcolo moving average
        # ===============================
        moving_avg = sum(self.gas_history) / len(self.gas_history) #calcolo la media sugli ultimi 20 valori

        # Prima iterazione
        if self.previous_moving_avg is None:
            self.previous_moving_avg = moving_avg
            return {
                "predicted_gas": gas_value,
                "predicted_crossing": False
            }

        # ===============================
        # Velocità di crescita
        # ===============================
        growth_rate = moving_avg - self.previous_moving_avg #misuro quanto sta crescendo il mio livello di gas

        # Aggiorna media precedente
        self.previous_moving_avg = moving_avg

        # ===============================
        # Predizione valore futuro
        # ===============================
        predicted_gas = gas_value + (growth_rate * self.prediction_steps) #predico il valore di gas che avrò tra 30sec

        # ===============================
        # Verifica superamento soglia
        # ===============================
        if(predicted_gas > threshold):
            predicted_crossing = True
        else:
            predicted_crossing = False

        return {
            "predicted_gas": int(predicted_gas),
            "predicted_crossing": predicted_crossing #se True devo accendere la ventola
        }


# ===============================
# BRIDGE CORE
# ===============================

class Bridge:
    """Coordina tutti i componenti del sistema."""

    def __init__(self):
        self.config = Config()
        self.bluetooth = BluetoothManager(self.config)
        self.dataset = DatasetManager()
        self.anomaly_detector = AnomalyDetector(self.config)
        self.predictor = GasPredictor(self.config)
        self.fan_controller = FanController(self.bluetooth, self.config)
        self.mqtt = MQTTManager(self.config, self.fan_controller)
        self.running = True

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

        """Predizione del valore di gas tra 30 sec"""

        prediction = self.predictor.update(data["gas"],int(self.read_dataset['others_mean']) * self.config.ANOMALY_FACTOR)

        predicted_gas = prediction["predicted_gas"]
        predicted_crossing = prediction["predicted_crossing"] #devo accendere la ventola preventiva?

        """Verifica anomalia"""

        anomaly = self.anomaly_detector.check_anomaly(data["gas"],int(self.read_dataset['others_mean']))

        if anomaly or predicted_crossing:
            self.fan_controller.update_state(True)
            if predicted_crossing:
                print(f"[ANOMALY_PREDICTION] MQ-2 predicted gas value: {predicted_gas} threshold = {int(self.read_dataset['others_mean']) * self.config.ANOMALY_FACTOR} – threshold will be exceeded - FAN_ON")
            else:
                print(f"[ANOMALY] MQ-2 gas value: {data['gas']} threshold = {int(self.read_dataset['others_mean']) * self.config.ANOMALY_FACTOR} – threshold exceeded - FAN_ON")
        else:
            self.fan_controller.update_state(False)
            print(f"[OK] MQ-2 gas value: {data['gas']} – below anomaly threshold - FAN_OFF")


        # ===============================
        # Pubblicazione telemetria MQTT
        # ===============================
        payload = {
        "garage_id": "G1",
        "gas": data["gas"], #valore del gas attuale
        "predicted_gas": predicted_gas, #valore del gas predetto tra 30sec
        "predicted_crossing": predicted_crossing, #devo accendere il valore preventivamente se il valore del gas tra 30sec supera soglia
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