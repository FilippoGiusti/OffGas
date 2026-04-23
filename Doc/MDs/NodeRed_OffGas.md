---
title: "Node-RED OffGas"
subtitle: "Documentazione tecnica e operativa"
author: "Progetto OffGas"
date: "Aprile 2026"
lang: it-IT
toc: true
toc-depth: 2
geometry:
  - margin=2.2cm
colorlinks: true
linkcolor: blue
urlcolor: blue
---

# 1. Scopo del documento

Questo documento descrive il ruolo di **Node-RED** nel progetto OffGas nella sua forma attuale.

L'obiettivo è spiegare:

- come Node-RED si colloca nell'architettura complessiva del sistema;
- quali responsabilità gestisce direttamente nel flow cloud;
- come vengono trattate la telemetria di **G1**, i dataset delle unità simulate e la logica di soglia;
- come vengono esposti gli endpoint HTTP usati dalla dashboard;
- come funzionano controllo manuale, automazione, shutoff di emergenza, health check e notifiche.

Nella revisione corrente del progetto, **il calcolo della soglia e la gestione dei dataset appartengono interamente a Node-RED**. Il bridge Python resta quindi un gateway edge che pubblica la telemetria del prototipo reale e riceve i comandi da eseguire, mentre la logica applicativa viene centralizzata nel flow.

# 2. Ruolo di Node-RED nel sistema OffGas

Node-RED è il livello di **orchestrazione cloud** del progetto OffGas.

Nel sistema attuale riceve dal bridge soltanto la telemetria minima del prototipo reale **G1**, cioè:

- identificativo dell'unità;
- valore corrente del gas;
- timestamp;
- stato reale della ventola.

A partire da questi dati, Node-RED costruisce lo stato applicativo completo del sistema. Le sue responsabilità principali sono:

1. salvare e aggiornare la telemetria di **G1**;
2. caricare e interpretare i dataset CSV delle unità simulate **G2-G6**;
3. calcolare la media delle unità di confronto e la soglia dinamica di sicurezza;
4. eseguire la **prediction** sul valore di gas di **G1** e dei garage simulati;
5. determinare lo stato locale delle unità in termini di `SAFE`, `WARNING` e `CRITICAL`;
6. inviare al bridge i comandi automatici o manuali della ventola;
7. costruire i payload HTTP letti dalla dashboard;
8. gestire dataset switching, emergency shutoff, health check e notifiche Telegram.

Node-RED è quindi il punto in cui i dati grezzi diventano uno **stato operativo coerente** per tutto il sistema.

# 3. Posizionamento di Node-RED nell'architettura

Nel progetto OffGas la catena generale è la seguente:

**Arduino -> HC-05 -> Bridge Python -> MQTT -> Node-RED -> MQTT / HTTP -> Bridge e Dashboard**

In dettaglio:

- Arduino legge il sensore MQ-2 e riceve i comandi di controllo della ventola;
- il bridge Python inoltra su MQTT la telemetria reale di **G1** e riceve i comandi di ritorno;
- Node-RED riceve la telemetria dal topic `garages/G1/telemetry`;
- Node-RED aggiorna dataset, soglia, prediction, stati locali e stato globale;
- Node-RED pubblica sul topic `garages/G1/cmd` i comandi automatici o manuali destinati al bridge;
- Node-RED espone via HTTP gli endpoint usati dalla dashboard.

Questo significa che Node-RED è contemporaneamente:

- un **consumatore MQTT** della telemetria reale;
- un **produttore MQTT** di comandi verso il bridge;
- un **backend HTTP/JSON** per la dashboard;
- un **runtime stateful** che mantiene nel contesto del flow la fotografia corrente del sistema.

# 4. Struttura generale del flow OffGas Cloud API

Il flow attuale è organizzato in blocchi funzionali ben distinti.

## 4.1 Variabili di ambiente del tab

Il tab `OffGas Cloud API` definisce tre variabili di ambiente che influenzano il comportamento del flow:

| Variabile | Significato |
|---|---|
| `DATASET_DIR` | cartella da cui leggere i file CSV dei garage simulati |
| `ANOMALY_FACTOR` | coefficiente moltiplicativo usato per ricavare la soglia |
| `DISPLAY_LIMIT` | numero massimo di unità da mostrare nella dashboard |

Nella configurazione corrente i valori predefiniti sono:

- `DATASET_DIR = /data/offgas-datasets`
- `ANOMALY_FACTOR = 1.5`
- `DISPLAY_LIMIT = 6`

Questi parametri consentono di adattare il flow senza modificare direttamente il codice dei nodi function.

## 4.2 Sezioni logiche del flow

Dal punto di vista operativo, il flow può essere letto come l'unione di sei sottosistemi principali:

1. **telemetria e logica automatica di G1**;
2. **dataset e garage simulati**;
3. **API HTTP per la dashboard**;
4. **controllo manuale locale e via API**;
5. **shutoff di emergenza e health check**;
6. **alert MQTT e notifiche Telegram**.

La catena centrale dell'automazione è la seguente:

**G1 telemetry in -> CacheTelemetry -> PredictionNextValue -> AnomalyDetection -> CacheAutoDecision -> to bridge auto cmd**

Su questa pipeline si appoggiano poi tutte le altre sezioni del sistema.

# 5. Telemetria di G1 e logica automatica

## 5.1 Ingresso MQTT della telemetria reale

Il nodo `G1 telemetry in` ascolta il topic:

```text
garages/G1/telemetry
```

Il payload ricevuto dal bridge contiene soltanto le informazioni essenziali del prototipo reale, cioè `garage_id`, `gas`, `timestamp` e `fan_state`.

Questo è un punto importante dell'architettura attuale: **Node-RED non dipende più da un threshold precalcolato nel bridge**. La telemetria arriva minima e il flow costruisce internamente il resto dello stato.

## 5.2 Nodo `CacheTelemetry`

`CacheTelemetry` è il nodo che aggiorna il contesto applicativo ogni volta che arriva un nuovo dato di **G1**.

Le sue responsabilità sono:

- salvare la telemetria corrente nel contesto del flow;
- aggiornare `lastTelemetryMs` e `updated_at`;
- leggere dal contesto le righe del dataset attualmente attivo;
- generare i valori visualizzati di **G2-G6** applicando una variazione casuale di ±15 ai valori di base;
- calcolare `others_mean` a partire dai garage simulati mostrati;
- calcolare `effective_threshold = others_mean × ANOMALY_FACTOR`;
- aggiornare la prediction locale dei garage simulati.

Il nodo usa quindi la telemetria reale di **G1** come evento che fa avanzare anche lo stato delle unità simulate.

## 5.3 Come viene calcolata la soglia nel flow attuale

Nel flow corrente la soglia di sicurezza è trattata come valore **autorevole di Node-RED**.

La logica è la seguente:

1. si prendono i garage simulati visualizzati, cioè al massimo `DISPLAY_LIMIT - 1` unità oltre a **G1**;
2. a questi valori viene applicato un piccolo rumore casuale per simulare dinamismo;
3. si calcola la media `others_mean`;
4. si ricava la soglia come:

```text
effective_threshold = others_mean × ANOMALY_FACTOR
```

Di conseguenza, nella versione attuale del sistema:

- la soglia non è hardcoded;
- la soglia non viene letta dal bridge;
- la soglia dipende dal dataset attivo e dai valori simulati correnti mantenuti in Node-RED.

## 5.4 Prediction di G1

Il nodo `PredictionNextValue` implementa la predizione sul garage reale **G1**.

La logica usa:

- uno storico locale dei campioni di gas;
- una **moving average** sugli ultimi valori;
- il confronto tra media corrente e media precedente.

Il nodo mantiene al massimo 20 campioni nel proprio context. Quando lo storico è ancora troppo corto, non produce una previsione significativa e inizializza soltanto i dati interni.

Dopo la fase iniziale, il calcolo segue questo schema:

```text
growthRate = movingAvg - previousAvg
predicted_gas = gas + (growthRate × 150)
```

Il nodo aggiunge poi al payload:

- `threshold`
- `predicted_gas`
- `predicted_crossing`
- `mode = "STD"`
- `anomaly`

In questa fase `anomaly` viene già valutato come `gas > threshold`, ma il nodo successivo ricostruisce comunque il payload decisionale finale in forma standardizzata.

## 5.5 Nodo `AnomalyDetection`

`AnomalyDetection` riceve l'output di `PredictionNextValue` e produce il comando automatico strutturato da inviare al bridge.

Il payload finale ha la forma logica seguente:

```json
{
  "mode": "STD",
  "anomaly": true | false,
  "predicted_crossing": true | false,
  "predicted_gas": ...,
  "gas": ...,
  "threshold": ...
}
```

Questo nodo rappresenta il punto in cui la telemetria di **G1** viene trasformata in una decisione operativa leggibile sia dal bridge sia dalla dashboard.

## 5.6 Nodo `CacheAutoDecision`

Il nodo `CacheAutoDecision` salva nel contesto del flow l'ultimo comando automatico generato.

In particolare:

- aggiorna `latest_auto_command`;
- aggiorna `updated_at`;
- se non è attivo un override manuale, forza la modalità logica a `AUTO`.

Questo permette alla dashboard di sapere non solo qual è l'ultimo valore letto, ma anche qual è stata l'ultima decisione automatica prodotta dal backend.

## 5.7 Invio del comando automatico al bridge

Il nodo `to bridge auto cmd` pubblica il payload decisionale sul topic:

```text
garages/G1/cmd
```

Il bridge riceve questo messaggio e decide se accendere o spegnere la ventola del prototipo reale in base ai campi `anomaly` e `predicted_crossing`.

# 6. Garage simulati e gestione dei dataset

## 6.1 Ruolo dei dataset nel sistema attuale

I garage **G2-G6** non sono sensori reali. Sono unità simulate a partire da file CSV caricati da Node-RED.

Nel flow attuale, la gestione dei dataset è interamente spostata nel backend Node-RED. Questo comporta che:

- la dashboard non decide autonomamente il contenuto dei garage simulati;
- il bridge non carica o interpreta i file CSV;
- il cambio dataset ha effetto reale sullo stato del sistema, perché modifica media, soglia e stati locali calcolati dal flow.

## 6.2 Dataset disponibili

Il nodo `ListDatasets` espone quattro scenari predefiniti:

| Indice | Nome mostrato |
|---|---|
| `0` | `Nominal State` |
| `1` | `Critical State` |
| `2` | `Low Pollution` |
| `3` | `Realistic Pollution` |

Questi label vengono riutilizzati sia per la risposta HTTP di `GET /api/datasets` sia per la costruzione dello stato ritornato alla dashboard.

## 6.3 Cambio dataset: `POST /api/dataset`

Quando il frontend richiede il cambio dataset, la catena usata dal flow è la seguente:

**POST /api/dataset -> json -> SelectDatasetMeta -> Read dataset file -> ParseDatasetCsv -> StoreDataset -> BuildDashboardState -> http response**

Il nodo `SelectDatasetMeta` accetta un indice numerico oppure un body JSON contenente il campo `index`. In base al valore ricevuto, associa il dataset a uno dei seguenti file:

- `dataset_garage.csv`
- `dataset_high_pollution.csv`
- `dataset_low_pollution.csv`
- `dataset_realistic_pollution.csv`

Se l'indice non è valido, la richiesta viene rifiutata con errore `400`.

## 6.4 Parsing dei file CSV

Il nodo `ParseDatasetCsv` converte il contenuto del file in un array di righe nel formato:

```json
{ "garage_id": "G2", "value": 100 }
```

Durante il parsing:

- vengono ignorate le righe vuote;
- sono accettati sia separatori `,` sia `;`;
- eventuali righe con `garage_id = G1` vengono escluse;
- vengono mantenute solo le coppie `garage_id/value` numericamente valide.

## 6.5 Nodo `StoreDataset`

`StoreDataset` salva il dataset nel contesto e costruisce lo stato iniziale delle unità simulate.

Il nodo:

- memorizza `dataset_rows`;
- rigenera `others_displayed` con il rumore casuale applicato ai valori dei primi garage mostrati;
- ricalcola `others_mean`;
- ricalcola `effective_threshold`;
- inizializza `garage_predictors`;
- costruisce `evaluated_other_garages`.

Per ogni garage simulato vengono mantenuti:

- valore corrente;
- soglia;
- `predicted_gas`;
- `predicted_crossing`;
- `anomaly`;
- `status`;
- `fan_active`.

Subito dopo il caricamento di un dataset, la prediction dei garage simulati parte in modo conservativo: viene inizializzata la history locale, ma non viene ancora segnalato un crossing predittivo.

## 6.6 Dataset di default all'avvio

All'avvio del flow, il nodo `init default dataset` carica automaticamente il dataset nominale.

La sequenza è:

**init default dataset -> InitDefaultDatasetMeta -> Read dataset file -> ParseDatasetCsv -> StoreDataset**

Questo assicura che il sistema abbia uno stato coerente anche prima dell'arrivo della prima telemetria reale di **G1**.

# 7. Costruzione dello stato per la dashboard

## 7.1 Endpoint `GET /api/state`

`GET /api/state` è l'endpoint principale da cui la dashboard legge lo stato complessivo del sistema.

Il nodo function collegato è `BuildDashboardState`, presente in più istanze del flow ma sempre con la stessa responsabilità: ricostruire un payload completo e coerente a partire dal contesto del flow.

## 7.2 Dati raccolti da `BuildDashboardState`

Per costruire la risposta, il nodo legge dal contesto:

- `telemetry`
- `latest_auto_command`
- `latest_manual_command`
- `latest_alert`
- `mode`
- `shutdown_active`
- `dataset_rows`
- `others_displayed`
- `others_mean`
- `evaluated_other_garages`
- `selected_dataset`
- `dataset_name`
- `available_datasets`
- `effective_threshold`
- `updated_at`
- `lastTelemetryMs`

A partire da questi campi, il nodo ricostruisce sia lo stato del garage reale **G1** sia quello dei garage simulati.

## 7.3 Come viene determinato lo stato di G1

Il garage reale viene ricostruito usando:

- valore `gas` della telemetria corrente;
- ultimo comando automatico prodotto dal flow;
- soglia effettiva calcolata da Node-RED;
- modalità operativa corrente;
- stato reale della ventola riportato dal bridge.

La logica è la seguente:

- `CRITICAL` se `anomaly` è vero oppure se `gas > threshold`;
- `WARNING` se non è `CRITICAL` ma `predicted_crossing` è vero;
- `SAFE` negli altri casi.

Lo stato della ventola di **G1** viene mostrato come attivo se:

- lo shutoff non è attivo;
- la modalità è `ON`, oppure
- la modalità è `AUTO` e G1 è in `WARNING` o `CRITICAL`, oppure
- il bridge riporta `fan_state = true`.

## 7.4 Come vengono determinati gli altri garage

Per **G2-G6** il nodo usa `evaluated_other_garages`, cioè la lista già valutata da `CacheTelemetry` o `StoreDataset`.

Ogni riga contiene:

- `garage_id`
- `value`
- `threshold`
- `status`
- `fan_active`
- `anomaly`
- `predicted_crossing`

I garage simulati seguono la stessa logica concettuale di stato di **G1**, ma vengono pilotati interamente da dati sintetici interni al flow.

## 7.5 Campo `display_sensors`

La dashboard non riceve direttamente strutture separate per reale e simulato. Riceve invece un array unificato chiamato `display_sensors`, in cui:

- il primo elemento è sempre **G1**;
- seguono al massimo `DISPLAY_LIMIT - 1` unità simulate.

In questo modo il frontend può leggere lo stato in maniera uniforme, lasciando a Node-RED la responsabilità di decidere cosa deve comparire e con quale stato.

## 7.6 Altri campi restituiti alla dashboard

Oltre a `display_sensors`, `BuildDashboardState` restituisce anche:

| Campo | Significato |
|---|---|
| `mqtt_connected` | vero se è arrivata telemetria recente |
| `telemetry` | ultimo payload reale di G1 |
| `latest_auto_command` | ultima decisione automatica |
| `latest_manual_command` | ultimo comando manuale registrato |
| `latest_alert` | ultimo alert noto al flow |
| `others_mean` | media corrente dei garage simulati mostrati |
| `threshold` | soglia effettiva calcolata da Node-RED |
| `anomaly_factor` | coefficiente usato per la soglia |
| `mode` | modalità logica corrente |
| `updated_at` | ultimo aggiornamento utile |
| `dataset_name` | nome del dataset attivo |
| `available_datasets` | elenco dei dataset selezionabili |
| `selected_dataset` | indice del dataset attivo |
| `shutdown_active` | stato dello shutoff di emergenza |

Questo payload è il contratto principale tra Node-RED e la dashboard.

# 8. Controllo manuale e automatico

## 8.1 Modalità operative

Nel flow esistono tre modalità logiche principali:

- `AUTO`
- `ON`
- `OFF`

In modalità `AUTO`, la ventola del prototipo reale segue le decisioni automatiche prodotte da `AnomalyDetection`.

In modalità `ON` o `OFF`, il sistema entra in **manual override** e la decisione automatica non ha più priorità sul bridge.

## 8.2 Controllo manuale locale nel canvas

Il flow contiene tre nodi inject locali:

- `FAN_ON`
- `FAN_OFF`
- `AUTO`

Questi pulsanti servono come controllo rapido direttamente da Node-RED.

Tutti passano attraverso `CacheManualCommand (local)`, che:

- valida il comando;
- blocca l'operazione se è attivo lo shutoff;
- aggiorna `latest_manual_command`;
- aggiorna `mode`;
- aggiorna `manual_override`.

Infine il nodo `to bridge manual cmd` pubblica il comando sul topic `garages/G1/cmd`.

## 8.3 Controllo manuale dalla dashboard: `POST /api/control`

La dashboard usa l'endpoint `POST /api/control` per inviare i comandi `ON`, `OFF` e `AUTO`.

La pipeline è:

**POST /api/control -> json -> DashboardControl -> CacheManualCommand (api) -> to bridge manual cmd -> BuildDashboardState -> http response**

Il nodo `DashboardControl` traduce il body JSON in uno dei comandi validi:

- `ON -> FAN_ON`
- `OFF -> FAN_OFF`
- `AUTO -> AUTO`

Se il sistema è in emergency shutoff, la richiesta viene rifiutata con errore `409`.

## 8.4 Rapporto tra manual override e automazione

Quando viene attivato un comando manuale:

- `manual_override` viene impostato a `true` per `FAN_ON` e `FAN_OFF`;
- il `mode` diventa `ON` oppure `OFF`;
- la dashboard vede subito la modalità aggiornata perché il flow ricostruisce la risposta con `BuildDashboardState`.

Quando arriva invece `AUTO`:

- `manual_override` torna a `false`;
- il `mode` torna a `AUTO`;
- il bridge può nuovamente seguire i comandi automatici in JSON prodotti da Node-RED.

# 9. Shutoff di emergenza e health check

## 9.1 Endpoint `POST /api/emergency`

Lo shutoff di emergenza viene gestito da:

**POST /api/emergency -> json -> SetEmergencyState -> BuildDashboardState -> http response**

Il nodo `SetEmergencyState` interpreta il campo `active` del body HTTP e aggiorna il contesto del flow.

Quando lo shutoff viene attivato:

- `shutdown_active` diventa `true`;
- `mode` viene forzato a `OFF`;
- `manual_override` viene impostato a `true`;
- `latest_manual_command` diventa `FAN_OFF`;
- viene creato un alert interno `emergency_shutoff`;
- viene inviato al bridge il comando `FAN_OFF`.

Quando lo shutoff viene disattivato:

- `shutdown_active` torna `false`;
- `mode` torna `AUTO`;
- `manual_override` torna `false`;
- `latest_manual_command` diventa `AUTO`;
- viene inviato al bridge il comando `AUTO`.

Questo meccanismo non è soltanto grafico: modifica realmente lo stato logico del sistema e il comando inviato al bridge.

## 9.2 Effetti dello shutoff sullo stato visualizzato

Quando `shutdown_active` è vero, `BuildDashboardState` forza una rappresentazione coerente con la condizione di isolamento:

- tutte le ventole vengono mostrate come non attive;
- i garage simulati non risultano operativi dal punto di vista della ventilazione;
- anche **G1** viene mostrato come ventola non attiva, indipendentemente dallo stato precedente.

In questo modo la dashboard evidenzia chiaramente che il sistema non si trova più in una normale modalità operativa.

## 9.3 Endpoint `GET /api/health`

Il nodo `BuildHealth` espone un endpoint leggero di diagnostica.

La risposta contiene:

- `ok`
- `mqtt_connected`
- `dataset_name`
- `shutdown_active`

Il campo `mqtt_connected` viene calcolato verificando se l'ultima telemetria è arrivata negli ultimi circa 7 secondi. Questo valore viene usato come indicatore sintetico di vitalità del backend rispetto al flusso reale di **G1**.

# 10. Alert e notifiche Telegram

## 10.1 Topic degli alert del bridge

Il nodo `G1 alerts in` ascolta il topic:

```text
garages/G1/alerts
```

Gli eventi ricevuti dal bridge vengono salvati da `CacheLatestAlert` nel contesto del flow. In questo modo gli alert più recenti possono essere esposti anche alla dashboard.

## 10.2 Nodo `TelegramAlert`

Il nodo `TelegramAlert` prepara i messaggi da inviare al bot Telegram configurato nel flow.

Gestisce due famiglie di input:

- comandi manuali testuali come `FAN_ON`, `FAN_OFF`, `AUTO`;
- payload automatici provenienti dal ramo di decisione di **G1**.

Per evitare duplicazioni, il nodo mantiene nel proprio context:

- lo stato della ventola;
- l'informazione `manual_mode`.

## 10.3 Comportamento attuale delle notifiche

Nel flow corrente:

- i comandi manuali generano notifiche dedicate di attivazione, spegnimento o ritorno in automatico;
- in modalità automatica, il messaggio di alert viene inviato quando il flag `anomaly` passa a vero;
- il messaggio di rientro viene inviato quando `anomaly` torna falso dopo una fase con ventola attiva.

È quindi importante osservare che, nella versione attuale del nodo Telegram, l'invio automatico è agganciato soprattutto al flag `anomaly`. Il campo `predicted_gas` compare nel testo della notifica, ma la logica di invio non è centrata esclusivamente sul solo `predicted_crossing`.

## 10.4 Invio effettivo del messaggio

Una volta preparato il payload, il nodo `TelegramBot` lo invia tramite il bot configurato. Il nodo `debug telegram` permette di verificare nel pannello debug il contenuto dei messaggi generati.

# 11. Configurazione MQTT, topic e dipendenze del flow

## 11.1 Broker MQTT

Nel file di flow corrente il broker MQTT configurato da Node-RED punta al servizio:

```text
mosquitto:1883
```

Questa configurazione è coerente con l'uso previsto del progetto in ambiente Docker, in cui Mosquitto e Node-RED fanno parte dello stesso runtime software.

## 11.2 Topic usati da Node-RED

I topic principali del flow sono i seguenti:

| Topic | Direzione rispetto a Node-RED | Funzione |
|---|---|---|
| `garages/G1/telemetry` | input | ricezione della telemetria reale di G1 |
| `garages/G1/cmd` | output | invio dei comandi automatici o manuali al bridge |
| `garages/G1/alerts` | input | ricezione di alert pubblicati dal bridge |

Node-RED non dialoga direttamente con Arduino: comunica sempre attraverso il bridge e il broker MQTT.

## 11.3 Configurazioni aggiuntive

Oltre al broker MQTT, il flow include:

- configurazione del bot Telegram;
- dipendenza dal pacchetto `node-red-contrib-telegrambot`;
- dipendenza dal filesystem locale per leggere i dataset CSV dalla cartella definita da `DATASET_DIR`.

# 12. Sequenza operativa del sistema dal punto di vista di Node-RED

Il comportamento complessivo del flow può essere riassunto così:

1. all'avvio Node-RED carica il dataset nominale e inizializza i garage simulati;
2. il bridge pubblica la telemetria reale di **G1** su MQTT;
3. `CacheTelemetry` aggiorna il contesto del flow, rigenera i garage simulati e ricalcola la soglia;
4. `PredictionNextValue` stima il comportamento futuro di **G1**;
5. `AnomalyDetection` produce il comando automatico standardizzato;
6. `CacheAutoDecision` salva la decisione corrente;
7. il comando automatico viene pubblicato su `garages/G1/cmd`;
8. la dashboard legge lo stato tramite `GET /api/state` oppure riceve uno stato aggiornato come risposta a `POST /api/control`, `POST /api/dataset` o `POST /api/emergency`;
9. eventuali alert vengono salvati nel contesto e, se configurato, inoltrati anche a Telegram.

Questo flusso rende Node-RED il punto di coordinamento tra il prototipo reale, le unità simulate e l'interfaccia utente.

# 13. Cosa Node-RED non fa

Per leggere correttamente il ruolo di Node-RED è utile chiarire anche ciò che rimane fuori da questo livello.

Node-RED non:

- legge direttamente il sensore MQ-2;
- comunica direttamente con Arduino o con l'HC-05;
- implementa il firmware del prototipo;
- sostituisce il bridge nella gestione fisica della seriale Bluetooth;
- rende reali i garage simulati G2-G6, che restano unità generate da dataset.

Node-RED centralizza la logica applicativa, ma non sostituisce i livelli hardware del sistema.

# 14. Sintesi finale

Nel progetto OffGas, Node-RED è il componente che unifica telemetria reale, simulazione, logica decisionale e interfaccia di controllo.

Nella versione attuale del flow:

- la telemetria minima del prototipo reale arriva dal bridge via MQTT;
- la gestione dei dataset è interamente interna a Node-RED;
- la soglia di sicurezza viene calcolata dal flow e non dal bridge;
- la prediction viene eseguita sia per **G1** sia per i garage simulati mantenuti nel contesto;
- i comandi automatici e manuali passano tutti dal topic `garages/G1/cmd`;
- la dashboard dipende completamente dagli endpoint HTTP costruiti da `BuildDashboardState`;
- emergency shutoff, health check e notifiche sono integrati nello stesso backend.

Questo rende Node-RED il vero **motore logico** dell'architettura OffGas: non è solo un canale di instradamento, ma il livello in cui il sistema interpreta i dati, decide il comportamento operativo e costruisce la vista coerente esposta al frontend.
