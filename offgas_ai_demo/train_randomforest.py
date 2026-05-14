"""
OFFGAS - Demo semplice di training con RandomForest

Questo script è una proof of concept separata dal progetto principale.
Non modifica Bridge, MQTT, Node-RED, Arduino o dashboard.

Obiettivo:
- leggere i valori storici da gas_data.csv
- usare i dati di G1, cioè il prototipo reale
- trasformare la serie temporale in un problema supervisionato
- addestrare un RandomForestRegressor
- predire il valore del gas circa 30 secondi nel futuro
- salvare il modello addestrato in gas_rf_model.pkl
"""

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from pathlib import Path


# ===============================
# CONFIGURAZIONE
# ===============================

#in questo modo cerca i file nella stessa directory di train_randomforest.py
BASE_DIR = Path(__file__).resolve().parent

CSV_FILE = BASE_DIR / "gas_data.csv"
MODEL_FILE = BASE_DIR / "gas_rf_model.pkl"

# Arduino invia circa un valore ogni 5 secondi.
# Quindi 6 campioni * 5 secondi = circa 30 secondi.
PREDICTION_STEPS = 6


# ===============================
# CARICAMENTO DATASET
# ===============================

# Il CSV è prodotto dal Bridge OffGas.
# Colonne attese: timestamp, garage_id, gas, fan_state.
df = pd.read_csv(CSV_FILE)

# Ordiniamo i dati nel tempo, perché stiamo lavorando su una serie temporale.
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp", "gas"])
df = df.sort_values("timestamp")

# In questa demo usiamo solo G1, cioè il prototipo reale.
if "garage_id" in df.columns:
    df = df[df["garage_id"] == "G1"]

df["gas"] = pd.to_numeric(df["gas"], errors="coerce")
df = df.dropna(subset=["gas"])


# ===============================
# FEATURE ENGINEERING
# ===============================

# Trasformiamo la serie temporale in un dataset supervisionato.
# Ogni riga diventa un esempio:
#
# input  = valori recenti del gas
# output = valore del gas circa 30 secondi dopo

df["gas_now"] = df["gas"]
df["gas_1_step_ago"] = df["gas"].shift(1)
df["gas_2_steps_ago"] = df["gas"].shift(2)
df["gas_3_steps_ago"] = df["gas"].shift(3)

# Media semplice degli ultimi 4 valori.
# Aiuta il modello a capire il livello recente del gas.
df["mean_last_4_values"] = df[[
    "gas_now",
    "gas_1_step_ago",
    "gas_2_steps_ago",
    "gas_3_steps_ago"
]].mean(axis=1)

# Target: valore del gas 6 campioni dopo.
# Poiché ogni campione arriva circa ogni 5 secondi,
# 6 campioni corrispondono a circa 30 secondi.
df["target_gas_in_30s"] = df["gas"].shift(-PREDICTION_STEPS)

# Rimuoviamo righe incomplete causate da lag iniziali e target finali mancanti.
df = df.dropna()


# ===============================
# TRAIN / TEST SPLIT
# ===============================

feature_columns = [
    "gas_now",
    "gas_1_step_ago",
    "gas_2_steps_ago",
    "gas_3_steps_ago",
    "mean_last_4_values"
]

target_column = "target_gas_in_30s"

X = df[feature_columns]
y = df[target_column]

# Split temporale: primo 80% per training, ultimo 20% per test.
# Non facciamo shuffle perché l’ordine temporale è importante.
split_index = int(len(df) * 0.8)

X = df[feature_columns]
y = df[target_column]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    shuffle=False
)

#80% iniziale → training
#20% finale   → test

# ===============================
# TRAINING MODELLO
# ===============================

# RandomForestRegressor predice un valore numerico continuo:
# in questo caso il gas previsto tra circa 30 secondi.
model = RandomForestRegressor(
    n_estimators=100,
    random_state=42
)

model.fit(X_train, y_train)


# ===============================
# VALUTAZIONE MODELLO
# ===============================

# Il MAE indica di quante unità gas sbaglia in media il modello sul test set.
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)

print("OFFGAS RANDOMFOREST TRAINING")
print("--------------------------------")
print(f"Rows used for training/test: {len(df)}")
print(f"Training rows: {len(X_train)}")
print(f"Test rows: {len(X_test)}")
print(f"Mean Absolute Error: {mae:.2f} gas units")


# ===============================
# SALVATAGGIO MODELLO COME .PKL
# ===============================

# Il file .pkl contiene il modello già addestrato.
# Serve a predict_demo.py per fare predizioni senza riaddestrare ogni volta.
#
# Salviamo anche alcune informazioni utili:
# - feature_columns: ordine delle feature usate nel training
# - prediction_steps: numero di campioni nel futuro
# - sample_period_seconds: tempo medio tra campioni
# - prediction_horizon_seconds: orizzonte temporale, circa 30 secondi
model_package = {
    "model": model,
    "feature_columns": feature_columns,
    "prediction_steps": PREDICTION_STEPS,
    "sample_period_seconds": 5,
    "prediction_horizon_seconds": PREDICTION_STEPS * 5
}

# Questa riga crea fisicamente gas_rf_model.pkl.
# Il file è binario: non si apre a mano, si carica con joblib.load().
joblib.dump(model_package, MODEL_FILE)

print(f"Model saved as: {MODEL_FILE}")