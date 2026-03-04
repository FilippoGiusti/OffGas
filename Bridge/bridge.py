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

    TOPIC_TELEMETRY = "garages/G1/telemetry"
    TOPIC_ALERTS = "garages/G1/alerts"
    TOPIC_COMMANDS = "garages/G1/cmd"

    ANOMALY_FACTOR = 1.5
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

    def update_state(self, anomaly: bool):
        """Decide se inviare FAN_ON o FAN_OFF."""
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
        """Ritorna in modalità automatica."""
        pass



# ===============================
# MQTT MANAGER
# ===============================

class MQTTManager:
    """Gestisce comunicazione MQTT con Node-RED."""

    def __init__(self, config: Config):
        pass

    def connect(self):
        """Connette al broker MQTT."""
        pass

    def publish_telemetry(self, payload: dict):
        """Pubblica telemetria su topic."""
        pass

    def publish_alert(self, payload: dict):
        """Pubblica evento di allarme."""
        pass

    def subscribe_commands(self):
        """Sottoscrive topic comandi manuali."""
        pass

    def on_message(self, client, userdata, msg):
        """Callback per gestione comandi manuali."""
        pass


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
        self.mqtt = MQTTManager(self.config)
        self.fan_controller = FanController(self.bluetooth, self.config)
        self.running = True

    def start(self):
        """Avvia il sistema."""
        self.bluetooth.connect()

        """Calcola media"""
        self.read_dataset = self.dataset.load_dataset()

        try:
            while self.running:
                """legge valore gas"""
                data = self.bluetooth.read_line()

                if data:
                    self.process_cycle(data)

        except KeyboardInterrupt:
            self.stop()


    def process_cycle(self, data):

        """Verifica anomalia"""
        anomaly = self.anomaly_detector.check_anomaly(data["gas"],int(self.read_dataset['others_mean']))
        if(anomaly == True):
            print(f"[ANOMALY] MQ-2 gas value: {data['gas']} – threshold exceeded - FAN_ON")
            self.fan_controller.update_state(anomaly) #Controlla ventola
        else:
            print(f"[OK] MQ-2 gas value: {data['gas']} – below anomaly threshold - FAN_OFF")
            self.fan_controller.update_state(anomaly) #Controlla ventola

        """
        - Pubblica telemetria
        """


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