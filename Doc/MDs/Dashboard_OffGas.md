---
title: "Dashboard OffGas"
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

Questo documento descrive la **dashboard web** del progetto OffGas nella sua forma attuale.

L'obiettivo e' spiegare:

- quale ruolo svolge la dashboard all'interno del sistema;
- con quali tecnologie e' stata realizzata;
- come comunica con **Node-RED** tramite API **HTTP/JSON**;
- quali endpoint utilizza e per quale motivo;
- quali nodi del flow di Node-RED costruiscono lo stato mostrato all'interfaccia;
- come viene generata, compilata e servita nel runtime del progetto.

Il documento non tratta la dashboard come semplice pagina grafica, ma come **frontend operativo** integrato con l'infrastruttura Node-RED.

# 2. Ruolo della dashboard nel sistema OffGas

La dashboard e' la vista operativa del progetto OffGas. Il suo compito e' mostrare in modo compatto e leggibile lo stato del sistema, mantenendo sempre distinta l'unita' reale **G1** dalle unita' simulate **G2-G6**.

La dashboard **non** legge direttamente il sensore fisico e **non** prende decisioni autonome sulla logica di controllo. Tutte le informazioni che visualizza vengono costruite da **Node-RED**, che espone lo stato del sistema tramite API HTTP.

Le responsabilita' della dashboard sono quindi:

1. mostrare i valori delle unita' monitorate;
2. visualizzare media e soglia di sicurezza correnti;
3. rappresentare warning, criticita' e stato della ventilazione;
4. consentire il cambio della modalita' operativa;
5. consentire la selezione del dataset per le unita' simulate;
6. mostrare lo stato di emergenza e di connettivita' del backend.

La dashboard e' quindi il livello di **presentazione e interazione**, mentre la logica applicativa rimane centralizzata nel flow di Node-RED.

# 3. Tecnologie utilizzate

La dashboard e' stata sviluppata come applicazione frontend moderna basata su **React**.

La build del progetto frontend viene gestita tramite **Vite**, scelto perche' leggero, rapido nella compilazione e adatto alla generazione della versione statica usata nel progetto.

Dal punto di vista strutturale, l'interfaccia e' costruita tramite componenti riutilizzabili, ad esempio:

- componenti per i gauge delle unita';
- componente del grafico temporale;
- componente di mappa/contesto spaziale;
- blocchi dedicati ai controlli di sistema e alla visualizzazione dello stato.

Questa impostazione consente di separare la logica visiva dalle chiamate al backend e di mantenere il codice frontend modulare.

# 4. Struttura funzionale della dashboard

La dashboard e' organizzata in sezioni, ognuna con una funzione precisa.

## 4.1 Header principale

L'header contiene:

- il titolo del progetto;
- il sottotitolo della piattaforma;
- il blocco **System Control** con i pulsanti `OFF`, `AUTO`, `ON`;
- il blocco **Safety Protocol** con `Emergency Shutoff` o `Resume System`;
- l'indicatore **Node-RED Link**;
- l'indicatore **Last Updated**.

Questa parte serve a fornire subito una lettura generale dello stato del sistema e dei principali controlli disponibili.

## 4.2 Banner di stato

Sotto l'header e' presente un banner principale che sintetizza lo stato globale del sistema.

Gli stati possibili sono:

| Stato | Significato |
|---|---|
| `SYSTEM STATUS: NOMINAL` | Nessuna unita' in warning o critical |
| `PREDICTIVE WARNING` | Almeno una unita' presenta rischio predittivo |
| `CRITICAL: OFFGASSING DETECTED` | Almeno una unita' ha gia' superato la soglia |
| `EMERGENCY PROTOCOL ACTIVATED` | Lo shutoff di emergenza e' attivo |

Il banner non viene deciso nel frontend, ma dipende dallo stato complessivo restituito da Node-RED.

## 4.3 Ventilation System

La sezione **Ventilation System** riassume lo stato delle ventole.

Quando almeno una ventola e' attiva:

- viene mostrata l'animazione della ventola;
- vengono evidenziate le unita' coinvolte;
- compaiono `Fan Speed` e `Air Flow`.

Quando nessuna ventola e' attiva, la sezione resta in modalita' di standby.

Quando e' attivo lo shutoff, la sezione indica che il sistema e' isolato e tutte le ventole vengono mostrate come spente nella rappresentazione grafica.

## 4.4 Unit Monitoring

La sezione **Unit Monitoring** contiene i gauge di **G1-G6**.

Il significato delle unita' e' il seguente:

- **G1**: prototipo reale collegato al sensore fisico;
- **G2-G6**: unita' simulate a partire dal dataset selezionato.

Ogni gauge mostra:

- valore corrente VOC;
- soglia di sicurezza corrente;
- stato locale della ventola;
- colore/stato coerente con SAFE, WARNING o CRITICAL.

Accanto al titolo della sezione vengono mostrati anche:

- **Avg Concentration**;
- **Safety Threshold**.

Questi due valori riassumono il contesto in cui il valore di G1 viene interpretato.

## 4.5 Temporal Analysis

La sezione **Temporal Analysis** mostra l'andamento nel tempo di:

- valori delle unita' mostrate;
- soglia di sicurezza;
- concentrazione media.

In questa sezione e' presente anche il selettore **Dataset Source**, usato per cambiare il dataset da cui vengono simulate le unita' G2-G6.

## 4.6 System Metrics, Spatial Context e footer

La sezione **System Metrics** riassume informazioni sintetiche come:

- numero di unita' mostrate;
- valore di `anomaly factor`;
- modalita' operativa corrente.

La sezione **Spatial Context** aiuta a leggere il sistema come rete di unita' distribuite.

Il footer contiene le informazioni di progetto, corso e autori.

# 5. Comunicazione tra dashboard e Node-RED

## 5.1 Modello di comunicazione

La dashboard comunica con il backend tramite **HTTP** e scambia dati in formato **JSON**.

Nel setup attuale non viene utilizzato HTTPS, perche' l'applicazione gira in ambiente locale e viene servita da Node-RED su `localhost:1880`. Di conseguenza, il protocollo effettivamente usato dal frontend e' HTTP.

La dashboard **non** comunica direttamente con MQTT e **non** comunica direttamente con il bridge Python. Tutte le richieste passano da Node-RED.

Questo significa che:

- il frontend legge lo stato da endpoint HTTP;
- il frontend invia comandi a endpoint HTTP;
- Node-RED traduce le richieste ricevute in aggiornamenti di stato o in messaggi MQTT verso il bridge.

## 5.2 Perche' e' stata scelta una comunicazione HTTP

L'uso di API HTTP permette di separare chiaramente i livelli del sistema:

- **dashboard**: presentazione e interazione;
- **Node-RED**: backend, orchestrazione e logica;
- **bridge**: collegamento hardware Bluetooth/MQTT.

Questa scelta rende il frontend piu' semplice da mantenere, evita dipendenze dirette da MQTT lato browser e consente a Node-RED di esporre uno stato gia' consolidato e coerente.

# 6. Endpoint HTTP usati dalla dashboard

La dashboard usa diversi endpoint esposti da Node-RED.

## 6.1 `GET /api/state`

Questo e' l'endpoint principale di lettura.

La dashboard lo interroga periodicamente per ottenere lo stato completo del sistema. La risposta contiene:

- telemetria di G1;
- stato locale di G1;
- stato delle unita' simulate G2-G6;
- media degli altri garage;
- soglia di sicurezza;
- modalita' operativa corrente;
- dataset selezionato;
- stato di emergenza;
- ultimo alert rilevante;
- indicazioni sulla connettivita' MQTT.

Il frontend usa questo payload per aggiornare gauge, banner, sezione ventilazione, grafico e informazioni di stato.

## 6.2 `POST /api/control`

Questo endpoint viene chiamato quando l'utente seleziona `OFF`, `AUTO` o `ON`.

La dashboard invia un body JSON con la modalita' desiderata. Node-RED:

1. valida il contenuto;
2. lo traduce nel comando corretto (`FAN_ON`, `FAN_OFF`, `AUTO`);
3. aggiorna lo stato interno del flow;
4. inoltra il comando al bridge via MQTT;
5. restituisce subito al frontend lo stato aggiornato.

## 6.3 `GET /api/datasets`

Questo endpoint restituisce:

- l'elenco dei dataset disponibili;
- l'indice del dataset attualmente selezionato.

Serve alla dashboard per popolare il menu di selezione del dataset.

## 6.4 `POST /api/dataset`

Questo endpoint viene usato quando l'utente cambia dataset dal menu `Dataset Source`.

Il frontend invia l'indice del dataset da attivare. Node-RED legge il file CSV corrispondente, aggiorna il contesto interno e ricostruisce lo stato completo da restituire alla dashboard.

## 6.5 `POST /api/emergency`

Questo endpoint viene chiamato quando l'utente attiva o disattiva l'**Emergency Shutoff**.

La richiesta aggiorna lo stato di emergenza nel flow, modifica la modalita' coerente del sistema e restituisce al frontend il nuovo stato complessivo.

## 6.6 `GET /api/health`

Questo endpoint restituisce uno stato leggero del sistema, utile per:

- verificare che il backend sia attivo;
- verificare se arrivano dati MQTT recenti;
- leggere dataset selezionato e stato di shutoff.

Pur non essendo l'endpoint principale della dashboard, e' utile come riferimento diagnostico.

# 7. Nodi Node-RED che costruiscono la dashboard

La dashboard dipende da un insieme preciso di nodi presenti nel flow Node-RED. I piu' importanti sono quelli che costruiscono e aggiornano lo stato restituito al frontend.

## 7.1 `GET /api/state` + `BuildDashboardState (GET state)`

Questo e' il punto centrale della costruzione della dashboard.

Il nodo `GET /api/state` riceve la richiesta HTTP del frontend. Il nodo function `BuildDashboardState (GET state)` costruisce il payload completo da restituire alla pagina. Il nodo `http response` invia il JSON finale al browser.

`BuildDashboardState` raccoglie dal contesto del flow:

- telemetria corrente di G1;
- ultima decisione automatica;
- ultimo comando manuale;
- ultimo alert;
- valori simulati di G2-G6;
- media degli altri garage;
- soglia effettiva;
- dataset attivo;
- stato di emergenza;
- stato della connettivita' MQTT.

Da questi elementi costruisce i campi usati direttamente dal frontend.

## 7.2 `CacheTelemetry`

Il nodo `CacheTelemetry` e' il punto di ingresso principale dei dati reali per la dashboard.

Quando arriva nuova telemetria da G1:

- salva il payload nel contesto del flow;
- aggiorna l'orario dell'ultima ricezione;
- rigenera i valori simulati G2-G6 a partire dal dataset attivo;
- calcola la media degli altri garage visualizzati;
- calcola la soglia effettiva del sistema;
- aggiorna la prediction locale dei garage simulati.

Questo nodo e' fondamentale perche' prepara i dati che la dashboard andra' poi a mostrare.

## 7.3 `PredictionNextValue` e `AnomalyDetection`

Questi due nodi definiscono lo stato logico di G1.

`PredictionNextValue`:

- mantiene uno storico dei campioni recenti di gas;
- calcola una moving average;
- calcola la differenza tra media corrente e media precedente;
- stima `predicted_gas`;
- determina `predicted_crossing` se la previsione supera la soglia.

`AnomalyDetection`:

- confronta il gas corrente con la soglia;
- determina `anomaly`;
- conserva l'informazione di `predicted_crossing`.

I risultati di questi nodi confluiscono nello stato locale di G1 visualizzato nella dashboard.

## 7.4 `StoreDataset`

Il nodo `StoreDataset` viene usato quando il dataset cambia o quando viene inizializzato il dataset di default.

Le sue responsabilita' sono:

- salvare nel contesto le righe del dataset;
- rigenerare i valori visualizzati di G2-G6;
- aggiornare `others_mean`;
- aggiornare la soglia effettiva del sistema;
- inizializzare la prediction locale dei garage simulati.

Questo nodo fa si' che il cambio dataset abbia un effetto reale sulla dashboard e non sia una semplice modifica grafica.

## 7.5 `DashboardControl`

Il nodo `DashboardControl` interpreta i comandi inviati dal frontend tramite `POST /api/control`.

Traduce `ON`, `OFF`, `AUTO` nei comandi effettivi del sistema, validando l'input prima che venga inoltrato al bridge.

## 7.6 `SetEmergencyState`

Il nodo `SetEmergencyState` aggiorna lo stato di shutoff interno del flow.

Quando lo shutoff viene attivato:

- imposta lo stato di emergenza;
- aggiorna la modalita' del sistema;
- prepara la risposta coerente da inviare alla dashboard;
- produce il comando necessario per il bridge, se previsto dal flow.

## 7.7 `BuildDashboardState` dopo i comandi

Nel flow esistono piu' istanze di `BuildDashboardState`, usate in risposta a diversi endpoint:

- `BuildDashboardState (GET state)`
- `BuildDashboardState (POST control)`
- `BuildDashboardState (POST dataset)`
- `BuildDashboardState (POST emergency)`

La logica e' la stessa: ricostruire sempre uno stato coerente da restituire al frontend, indipendentemente dal tipo di operazione appena richiesta.

# 8. Come viene costruito lo stato visualizzato

Lo stato mostrato dalla dashboard non e' il semplice risultato di un singolo valore letto dal sensore, ma la composizione di piu' sorgenti interne al flow.

## 8.1 Stato di G1

Lo stato di G1 deriva da:

- valore reale del sensore ricevuto dal bridge;
- prediction su moving average;
- eventuale condizione di anomaly;
- stato reale della ventola del prototipo.

## 8.2 Stato di G2-G6

Le unita' G2-G6 vengono ottenute a partire dal dataset selezionato. Node-RED:

- legge il CSV corrispondente;
- estrae le righe utili;
- applica una lieve variazione casuale per simulare dinamismo;
- aggiorna prediction e stato locale di ciascuna unita'.

## 8.3 Media e soglia

Node-RED calcola:

- `others_mean`, cioe' la media delle unita' simulate mostrate;
- `effective_threshold`, cioe' la soglia di sicurezza usata dal sistema.

Questi valori sono poi restituiti alla dashboard come `Avg Concentration` e `Safety Threshold`.

## 8.4 Stato globale

Lo stato globale della dashboard dipende dal peggiore stato locale tra le unita' mostrate:

- se almeno una unita' e' `CRITICAL`, il banner diventa rosso;
- altrimenti, se almeno una unita' e' `WARNING`, il banner diventa arancione;
- altrimenti il sistema e' nominale.

# 9. Generazione, build e hosting della dashboard

Durante lo sviluppo, il frontend viene modificato nella cartella sorgente della dashboard.

Una volta completata o aggiornata la UI, il progetto viene compilato tramite **Vite**, che produce una build statica contenente:

- `index.html`;
- file JavaScript minificati;
- file CSS;
- cartella `assets`.

Nel runtime del progetto, questi file statici vengono serviti da **Node-RED** tramite static hosting. Questo permette di aprire la dashboard direttamente dal server Node-RED, senza dover mantenere un web server frontend separato.

L'URL di accesso tipico e':

```text
http://localhost:1880/offgas-dashboard/
```

In questo modo la dashboard e il backend appartengono allo stesso runtime applicativo.

# 10. Comportamento durante lo shutoff

La dashboard gestisce in modo specifico la modalita' di **Emergency Shutoff**.

Quando lo shutoff e' attivo:

- la UI congela i dati visualizzati;
- l'indicatore di collegamento mostra Node-RED come disabilitato dal punto di vista dell'interfaccia;
- tutte le ventole vengono rappresentate come spente;
- i comandi manuali risultano disabilitati;
- la sezione della ventilazione mostra il sistema come isolato.

Questo comportamento e' intenzionale: serve a rendere molto evidente all'utente che il sistema si trova in una condizione di sicurezza speciale e non nella normale modalita' operativa.

# 11. Limiti intenzionali della dashboard

La dashboard e' stata progettata con alcuni limiti intenzionali:

- non legge direttamente il sensore;
- non comunica direttamente con il bridge;
- non comunica direttamente con MQTT;
- non decide la logica di controllo;
- non considera G2-G6 come sensori reali.

Questi limiti sono una scelta architetturale precisa: mantengono il frontend focalizzato sulla presentazione e spostano la logica nei livelli backend del sistema.

# 12. Sintesi finale

La dashboard di OffGas e' un frontend operativo integrato con Node-RED, progettato per mostrare in forma chiara e reattiva il comportamento del sistema.

La sua funzione non e' sostituire la logica di controllo, ma renderla leggibile e comandabile dall'utente.

Dal punto di vista tecnico, la dashboard:

- e' realizzata con React e Vite;
- viene compilata come build statica;
- e' servita da Node-RED;
- comunica tramite API HTTP/JSON;
- dipende da un insieme preciso di nodi del flow per la costruzione dello stato;
- visualizza sei unita', di cui una reale e cinque simulate.

In questo modo la dashboard diventa il livello di interfaccia del progetto OffGas, integrando monitoraggio, stato della ventilazione, selezione del contesto simulato e controllo dell'infrastruttura in un'unica vista coerente.
