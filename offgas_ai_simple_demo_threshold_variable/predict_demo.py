"""
OFFGAS - Demo semplice di predizione con RandomForest

Questo script carica il file gas_rf_model.pkl e usa gli ultimi valori presenti
in gas_data.csv per predire il valore del gas di G1 circa 30 secondi nel futuro.

Questa è una demo separata dal progetto principale:
- non comunica con Arduino
- non comunica con il Bridge reale
- non pubblica su MQTT
- non legge dati da Node-RED
- non modifica la dashboard

Serve solo a dimostrare che, usando i dati storici raccolti dal Bridge,
è possibile costruire una prima implementazione AI per la predizione
del valore futuro del gas.

IMPORTANTE:
La soglia usata in questo file è una variabile fissa scelta da noi per la demo.
Nel sistema reale OffGas, invece, la soglia verrebbe calcolata dinamicamente
da Node-RED in base al contesto degli altri garage.

Qui la soglia serve solo per mostrare il concetto:

    valore previsto tra 30 secondi >= soglia

Se questa condizione è vera, allora la demo segnala un possibile crossing futuro.
"""

import joblib
import pandas as pd
from pathlib import Path



# ===============================
# CONFIGURAZIONE
# ===============================

BASE_DIR = Path(__file__).resolve().parent

CSV_FILE = BASE_DIR / "gas_data.csv"
MODEL_FILE = BASE_DIR / "gas_rf_model.pkl"

# Soglia dimostrativa usata solo nella demo offline.
#
# Nel progetto reale questa soglia NON sarebbe scritta manualmente qui.
# Verrebbe invece calcolata da Node-RED in modo dinamico, usando il contesto
# degli altri garage e la logica già presente nel sistema OffGas.
#
THRESHOLD = 220.0


# ===============================
# CARICAMENTO DEL MODELLO
# ===============================

# Il file .pkl non contiene solo il modello, ma un "pacchetto" Python.
# In questo pacchetto sono salvate tre informazioni:
#
# 1. model
#    Il RandomForestRegressor già addestrato.
#
# 2. feature_columns
#    L'elenco delle colonne usate durante il training.
#    Serve per garantire che, anche in predizione, le feature vengano passate
#    al modello nello stesso ordine usato durante l'addestramento.
#
# 3. prediction_horizon_seconds: PREDICTION_STEPS * 5 = 6 * 5 = 30
#    L'orizzonte temporale della predizione.
#    In questa demo è circa 30 secondi.
model_package = joblib.load(MODEL_FILE)

# Estraiamo il modello vero e proprio dal pacchetto.
model = model_package["model"]

# Estraiamo i nomi delle feature usate durante il training.
feature_columns = model_package["feature_columns"]

# Estraiamo l'orizzonte temporale della predizione.
# Questo valore viene stampato nell'output finale.
horizon_seconds = model_package["prediction_horizon_seconds"]


# ===============================
# CARICAMENTO DEGLI ULTIMI DATI
# ===============================

# Leggiamo il CSV prodotto dal Bridge.
# Il file contiene i dati storici raccolti dal sensore.
df = pd.read_csv(CSV_FILE)

# Convertiamo la colonna timestamp in formato datetime.
# errors="coerce" significa che eventuali timestamp non validi diventano NaT,
# cioè valori mancanti.
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

# Rimuoviamo le righe che non hanno timestamp valido o valore gas.
# Sono righe inutilizzabili per la predizione.
df = df.dropna(subset=["timestamp", "gas"])

# Ordiniamo i dati in ordine temporale.
# Questo è importante perché vogliamo prendere davvero gli ultimi valori.
df = df.sort_values("timestamp")

# Se nel CSV è presente la colonna garage_id, teniamo solo G1.
#
# Nel vostro prototipo reale G1 è il garage collegato al sensore fisico MQ-2.
# Gli altri garage, nel progetto completo, sono usati da Node-RED come contesto
# o come unità simulate, ma in questa demo semplice usiamo solo G1.
if "garage_id" in df.columns:
    df = df[df["garage_id"] == "G1"]

# Convertiamo la colonna gas in valore numerico.
# Questo evita problemi se il CSV contiene numeri letti come stringhe.
df["gas"] = pd.to_numeric(df["gas"], errors="coerce")

# Rimuoviamo eventuali righe in cui il valore del gas non è valido.
df = df.dropna(subset=["gas"])

# Per questa demo servono almeno 4 valori.
#
# Il modello usa:
# - gas attuale
# - gas di 1 campione fa
# - gas di 2 campioni fa
# - gas di 3 campioni fa
# - media degli ultimi 4 valori
#
# Se abbiamo meno di 4 righe, non possiamo costruire tutte queste feature.
if len(df) < 4:
    raise ValueError("Not enough gas values. At least 4 rows are required for this demo.")

# Prendiamo gli ultimi 4 valori del gas.
#
# L'ordine restituito da tail(4) è:
# dal più vecchio al più recente.
#
# Esempio:
# last_4 = [160, 162, 163, 164]
#
# In questo caso:
# - 160 è il valore di 3 campioni fa
# - 162 è il valore di 2 campioni fa
# - 163 è il valore di 1 campione fa
# - 164 è il valore attuale
last_4 = df.tail(4)["gas"].tolist()

# Assegniamo ogni valore a una variabile esplicita.
# Questo rende più chiaro cosa entra nel modello.
gas_3_steps_ago = last_4[0]
gas_2_steps_ago = last_4[1]
gas_1_step_ago = last_4[2]
gas_now = last_4[3]

# Calcoliamo la media degli ultimi 4 valori.
#
# Questa feature aiuta il modello a capire il livello recente del gas,
# invece di guardare solo il valore istantaneo.
mean_last_4_values = sum(last_4) / len(last_4)

# Costruiamo il DataFrame con le feature da passare al modello.
#
# Le feature devono avere gli stessi nomi usati durante il training.
# In questa demo semplice le feature sono:
#
# - gas_now
# - gas_1_step_ago
# - gas_2_steps_ago
# - gas_3_steps_ago
# - mean_last_4_values
latest_features = pd.DataFrame([{
    "gas_now": gas_now,
    "gas_1_step_ago": gas_1_step_ago,
    "gas_2_steps_ago": gas_2_steps_ago,
    "gas_3_steps_ago": gas_3_steps_ago,
    "mean_last_4_values": mean_last_4_values
}])

# Manteniamo esattamente lo stesso ordine delle colonne usato nel training.
#
# Questo passaggio è importante perché i modelli di machine learning
# ricevono numeri, non "capiscono" semanticamente i nomi delle colonne.
# Se l'ordine delle feature fosse diverso, la predizione potrebbe essere errata.
latest_features = latest_features[feature_columns]


# ===============================
# PREDIZIONE
# ===============================

# Chiediamo al modello di predire il valore futuro del gas.
#
# Il modello restituisce un array di predizioni.
# Siccome stiamo predicendo un solo caso, prendiamo il primo elemento [0].
predicted_gas = model.predict(latest_features)[0]

# Confrontiamo il valore previsto con la soglia dimostrativa.
#
# Se il valore previsto è maggiore o uguale alla soglia,
# allora predicted_crossing diventa True.
#
# In parole semplici:
# "secondo il modello, tra circa 30 secondi il gas supererà la soglia?"
predicted_crossing = predicted_gas >= THRESHOLD


# ===============================
# OUTPUT DELLA DEMO
# ===============================

print("OFFGAS AI FUTURE DEMO")
print("--------------------------------")

# Stampiamo i 4 valori usati come input.
# Questo aiuta a spiegare bene al professore cosa sta usando il modello.
print(f"Last 4 gas values used: {last_4}")

# Stampiamo il valore attuale, cioè l'ultimo valore presente nel CSV.
print(f"Current gas value: {gas_now:.0f}")

# Stampiamo la predizione del modello.
# L'orizzonte temporale viene letto dal file .pkl.
print(f"Predicted gas value in {horizon_seconds} seconds: {predicted_gas:.2f}")

# Stampiamo la soglia fissa configurata nel codice.
print(f"Demo threshold configured in code: {THRESHOLD:.2f}")

# Stampiamo il risultato del confronto tra predizione e soglia.
print(f"Predicted crossing: {predicted_crossing}")
print()
