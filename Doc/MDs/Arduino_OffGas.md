---
title: "Arduino OffGas"
subtitle: "Documentazione tecnica del firmware del prototipo"
author: "OffGas Project"
date: ""
lang: it-IT
geometry: margin=2.2cm
fontsize: 11pt
colorlinks: true
linkcolor: blue
urlcolor: blue
header-includes:
  - |
    \usepackage{longtable}
  - |
    \usepackage{booktabs}
  - |
    \usepackage{array}
  - |
    \usepackage{float}
  - |
    \usepackage{enumitem}
    \setlist{nosep}
  - |
    \usepackage{titlesec}
    \titleformat{\section}{\Large\bfseries}{}{0pt}{}
    \titleformat{\subsection}{\large\bfseries}{}{0pt}{}
---

# 1. Scopo del documento

Questo documento descrive il firmware **Arduino** utilizzato nel progetto OffGas e il ruolo che il microcontrollore svolge all'interno dell'architettura complessiva. L'obiettivo è spiegare in modo chiaro come vengono acquisiti i dati del sensore, come avviene la comunicazione con il bridge Python tramite **HC-05**, come viene controllata la ventola e in che modo il display locale viene aggiornato senza compromettere la stabilità del sistema.

Arduino rappresenta il livello **edge** del prototipo reale **G1**: non prende decisioni autonome sulla qualità dell'aria, ma esegue in modo affidabile le operazioni hardware richieste dal sistema.

# 2. Ruolo di Arduino nel sistema OffGas

Nel progetto OffGas Arduino è il dispositivo fisico che interagisce direttamente con i componenti del prototipo. Le sue responsabilità sono quattro:

- leggere il valore del sensore di gas **MQ-2**;
- inviare periodicamente il valore misurato al bridge Python tramite Bluetooth;
- ricevere dal bridge i comandi di accensione e spegnimento della ventola;
- aggiornare le informazioni locali mostrate sul display OLED.

La logica decisionale non è implementata nel firmware. L'elaborazione della telemetria, la predizione, il calcolo della soglia e la decisione operativa vengono eseguiti a livello software da **Node-RED**, mentre Arduino resta focalizzato sull'acquisizione e sull'attuazione.

# 3. Architettura hardware del prototipo

Il prototipo hardware, mostrato anche nello schema del circuito riportato nel documento sorgente, è composto dai seguenti elementi principali:

| Componente | Funzione |
|---|---|
| Arduino Uno | Microcontrollore principale |
| Sensore MQ-2 | Rilevazione della concentrazione di gas |
| Modulo HC-05 | Comunicazione Bluetooth con il bridge Python |
| Ventola DC | Sistema di ventilazione |
| Transistor NPN | Pilotaggio della ventola |
| Diodo flyback | Protezione del circuito di potenza |
| Display OLED SH1106 | Visualizzazione locale di valore gas e stato ventola |
| LED di stato | Indicazione rapida dello stato della ventola |

Il collegamento del sensore MQ-2 utilizza il pin analogico **A1**, mentre la ventola è controllata tramite un pin digitale che pilota il transistor. Il modulo **HC-05** realizza la comunicazione seriale wireless tra Arduino e il bridge Python. Il display OLED, collegato via **I2C**, consente di visualizzare localmente lo stato del dispositivo.

# 4. Struttura generale del firmware

Come in ogni firmware Arduino, la struttura del programma ruota attorno a due funzioni fondamentali:

- `setup()`
- `loop()`

La funzione `setup()` viene eseguita una sola volta all'avvio e inizializza pin, seriali, display e variabili di stato. La funzione `loop()` esegue invece il ciclo operativo continuo del dispositivo.

Nel caso di OffGas, il ciclo principale gestisce tre attività:

1. acquisizione periodica del valore del sensore MQ-2;
2. ricezione dei comandi inviati dal bridge;
3. aggiornamento del display OLED quando necessario.

Questa organizzazione consente di mantenere il firmware semplice, leggibile e compatibile con un'esecuzione embedded continua.

# 5. Fase di inizializzazione: `setup()`

Durante la fase di inizializzazione vengono preparati tutti i componenti hardware coinvolti nel funzionamento del prototipo.

In particolare, il firmware:

- imposta il pin del sensore MQ-2 come ingresso analogico;
- imposta il pin della ventola come uscita digitale;
- abilita il LED integrato come indicatore di stato;
- inizializza la seriale USB per il debug;
- inizializza la seriale Bluetooth tramite `SoftwareSerial`;
- inizializza il display OLED e prepara l'interfaccia grafica.

Questa fase è importante perché stabilisce i parametri di comunicazione del sistema. La velocità di trasmissione Bluetooth è impostata a **9600 baud**, e deve essere coerente con quella usata dal bridge Python.

# 6. Lettura del sensore MQ-2

Il sensore MQ-2 è un sensore analogico, quindi può essere soggetto a rumore, fluttuazioni momentanee e picchi anomali. Per ridurre l'effetto di queste oscillazioni, il firmware non utilizza una singola lettura diretta, ma applica un semplice filtro statistico.

Ad ogni acquisizione vengono effettuate **cinque letture consecutive** del sensore. Questi valori vengono ordinati e, successivamente, il valore minimo e quello massimo vengono scartati. La misura finale viene ottenuta facendo la media dei **tre valori centrali**.

Questo approccio corrisponde a una **trimmed mean**, cioè una media con esclusione degli estremi, e offre tre vantaggi principali:

- riduce il rumore del sensore;
- elimina eventuali outlier istantanei;
- rende più stabile il valore inviato al bridge.

Il firmware esegue questa acquisizione in modo periodico, sfruttando `millis()` per evitare l'uso di `delay()`. La lettura avviene ogni **5 secondi**, così il sistema resta reattivo anche tra una misura e la successiva.

# 7. Formato del dato inviato al bridge

Una volta ottenuta la misura filtrata, Arduino la invia al bridge tramite Bluetooth usando un formato testuale semplice e robusto:

```text
MQ2:<valore>
```

Un esempio tipico è:

```text
MQ2:178
```

Questo formato è stato scelto perché è facile da generare nel firmware e facile da interpretare dal bridge Python, che esegue poi il parsing della stringa e ne estrae il valore numerico.

In parallelo, lo stesso valore viene anche stampato sulla seriale USB per facilitare le operazioni di debug e verifica tramite Serial Monitor.

# 8. Comunicazione Bluetooth con HC-05

La comunicazione tra Arduino e il bridge avviene tramite il modulo **HC-05**, configurato come collegamento seriale Bluetooth. Nel firmware viene utilizzata la libreria `SoftwareSerial`, che consente di dedicare due pin digitali alla trasmissione e ricezione dei dati.

La velocità di comunicazione è fissata a **9600 baud**, scelta abbastanza stabile per questo tipo di scambio dati e compatibile con il bridge Python. Il canale Bluetooth viene utilizzato in entrambe le direzioni:

- **Arduino -> Bridge**: invio del valore del sensore MQ-2;
- **Bridge -> Arduino**: ricezione dei comandi `FAN_ON` e `FAN_OFF`.

Dal punto di vista del firmware, il Bluetooth viene trattato come una seriale. Questo rende la logica semplice: Arduino scrive periodicamente il dato del sensore e, in parallelo, controlla se sono disponibili comandi in ingresso.

# 9. Ricezione dei comandi dal bridge

Arduino non decide autonomamente quando accendere la ventola. Riceve invece il comando già deciso dal livello superiore del sistema, cioè dal bridge, che a sua volta lo riceve da Node-RED.

I comandi previsti dal firmware sono:

- `FAN_ON`
- `FAN_OFF`

Quando il firmware rileva la presenza di dati Bluetooth in ingresso, legge la stringa fino al carattere di newline e confronta il contenuto con i comandi attesi. Se il comando ricevuto è `FAN_ON`, il pin di controllo della ventola viene portato a livello alto e la variabile `fanState` viene aggiornata a `true`. Se il comando ricevuto è `FAN_OFF`, la ventola viene disattivata e `fanState` torna a `false`.

Lo stesso stato viene riflesso anche sul LED integrato e sul display OLED, in modo che l'utente possa verificare localmente il comportamento del dispositivo.

# 10. Controllo della ventola e circuito di pilotaggio

La ventola DC non è collegata direttamente a un pin digitale di Arduino, perché richiede una corrente superiore a quella che il microcontrollore può fornire direttamente. Per questo viene utilizzato un **transistor NPN** come interruttore elettronico.

Il principio di funzionamento è il seguente:

- Arduino controlla la base del transistor tramite una resistenza;
- il transistor pilota il ramo di alimentazione della ventola;
- un diodo flyback assorbe la tensione inversa generata dal motore allo spegnimento.

Quando il firmware attiva il pin di controllo, il transistor entra in conduzione e la ventola si accende. Quando il pin viene disattivato, il transistor si interdice e la ventola si spegne. Questa soluzione è semplice, sicura e adatta a un prototipo embedded di questo tipo.

# 11. Gestione del display OLED

Il display OLED ha il compito di fornire un'interfaccia locale al dispositivo. Sullo schermo vengono mostrati almeno tre elementi principali:

- il nome del sistema;
- il valore di gas corrente;
- lo stato della ventola.

In aggiunta, il firmware implementa anche una schermata iniziale di avvio e un'animazione grafica della ventola quando questa è attiva. Questi elementi rendono il dispositivo più leggibile e più intuitivo dal punto di vista operativo.

Tuttavia, l'aggiornamento del display non può essere eseguito in modo indiscriminato. La comunicazione del display avviene tramite bus **I2C**, mentre la comunicazione Bluetooth utilizza `SoftwareSerial`. Poiché entrambe le operazioni richiedono timing sufficientemente precisi, un aggiornamento continuo del display potrebbe interferire con la ricezione dei dati Bluetooth.

Per evitare questo problema, il firmware usa una variabile di stato, `displayDirty`, che segnala quando il display necessita davvero di essere aggiornato. L'aggiornamento viene eseguito solo se il contenuto è cambiato e se non ci sono dati Bluetooth in arrivo.

Questa scelta consente di:

- ridurre il carico sul microcontrollore;
- evitare aggiornamenti grafici inutili;
- migliorare la stabilità della comunicazione Bluetooth;
- mantenere il sistema reattivo.

# 12. Gestione non bloccante del tempo

Un aspetto tecnico importante del firmware è l'uso di `millis()` al posto di `delay()`. Questo approccio viene usato sia per la temporizzazione della lettura del sensore sia per l'aggiornamento dell'animazione del display.

L'uso di `millis()` permette di costruire una logica **non bloccante**, in cui il microcontrollore continua a eseguire il ciclo principale e a controllare gli eventi esterni. Questo è particolarmente utile in un sistema come OffGas, in cui è importante:

- leggere il sensore a intervalli regolari;
- ricevere comandi dal bridge senza ritardi;
- aggiornare il display solo quando opportuno.

In pratica, il firmware confronta il tempo corrente con l'ultimo tempo utile per capire se è il momento di eseguire una nuova azione, senza fermare l'intero programma.

# 13. Sequenza operativa del firmware

Il comportamento complessivo del firmware può essere riassunto nella seguente sequenza:

1. Arduino avvia i moduli hardware e inizializza display e seriali.
2. Ogni 5 secondi legge il sensore MQ-2 applicando il filtro a media senza estremi.
3. Invia il valore al bridge via Bluetooth nel formato `MQ2:<valore>`.
4. Controlla continuamente se il bridge ha inviato un comando di controllo.
5. Se riceve `FAN_ON`, attiva la ventola e aggiorna lo stato locale.
6. Se riceve `FAN_OFF`, spegne la ventola e aggiorna lo stato locale.
7. Aggiorna il display OLED quando il contenuto è cambiato e il canale Bluetooth è libero.

Questo rende Arduino un nodo edge semplice ma efficace: raccoglie i dati, esegue i comandi e mantiene una rappresentazione locale dello stato del sistema.

# 14. Comunicazione con il resto dell'architettura

Nel sistema OffGas la catena di comunicazione completa è la seguente:

```text
MQ-2 -> Arduino -> HC-05 -> Bridge Python -> MQTT -> Node-RED
```

nel verso dei dati, e:

```text
Node-RED -> MQTT -> Bridge Python -> HC-05 -> Arduino -> Ventola
```

nel verso dei comandi.

Arduino si colloca quindi nel punto più vicino all'hardware reale e rende possibile la trasformazione del prototipo in un nodo IoT effettivo. Il fatto che il dispositivo invii dati ma non prenda decisioni autonome aiuta a mantenere il firmware semplice, mentre la logica di analisi e controllo resta centralizzata a livello software.

# 15. Vantaggi dell'approccio adottato

L'architettura firmware scelta offre diversi vantaggi pratici:

- separa chiaramente hardware e logica decisionale;
- mantiene il firmware leggero e più facile da debuggare;
- consente di modificare la logica di controllo senza dover riprogrammare Arduino;
- permette di avere un feedback locale tramite display e LED;
- rende il prototipo facilmente integrabile in un sistema IoT più ampio.

Dal punto di vista didattico e progettuale, questa separazione tra acquisizione, bridge, orchestrazione e dashboard rende il sistema più modulare e più chiaro da documentare.

# 16. Checklist finale

Il firmware Arduino del progetto OffGas implementa in modo coerente le seguenti funzionalità:

- lettura del sensore MQ-2;
- filtraggio delle letture per ridurre rumore e outlier;
- invio del valore gas via Bluetooth nel formato `MQ2:<valore>`;
- ricezione dei comandi `FAN_ON` e `FAN_OFF` dal bridge;
- attivazione della ventola tramite transistor;
- aggiornamento del LED di stato;
- visualizzazione locale tramite display OLED;
- gestione non bloccante delle operazioni periodiche.

Nel complesso, Arduino costituisce il livello hardware del prototipo G1 e fornisce la base fisica su cui si appoggia l'intero sistema OffGas.
