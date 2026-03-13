# OffGas dashboard linked to MQTT/Node-RED

Questa versione non usa più dataset finti nel frontend.

## Cosa fa

- legge **G1 live** dalla telemetria MQTT del prototipo
- legge i garage **G2..G11** dal dataset CSV del progetto principale
- visualizza solo **6 unità**: `G1 + primi 5 garage del dataset`
- usa la **soglia reale** del bridge / Node-RED
- invia i comandi `FAN_ON`, `FAN_OFF`, `AUTO` sul topic `garages/G1/cmd`
- riceve anche i payload automatici con `anomaly` e `predicted_crossing`

## Variabili utili

```bash
MQTT_URL=mqtt://localhost:1883
OFFGAS_DATASET_PATH=/percorso/OffGas-main/dataset_other_garage/dataset_garage.csv
PORT=3000
```

## Note architetturali

- `others_mean` è calcolata **solo sugli altri garage**, mai su G1.
- `threshold` arriva dalla telemetria del bridge quando disponibile.
- `anomaly` e `predicted_crossing` vengono letti dal topic `garages/G1/cmd`.
- solo il gauge di **G1** mostra lo stato reale della ventola.
