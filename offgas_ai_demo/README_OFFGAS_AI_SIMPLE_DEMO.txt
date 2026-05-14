# OFFGAS AI SIMPLE DEMO - RandomForest Future Prediction

## 1. Scopo della demo

Questa cartella contiene una demo separata dal progetto principale OffGas.
Il suo obiettivo non è modificare il funzionamento reale di Arduino, Bridge, MQTT,
Node-RED o Dashboard, ma mostrare al professore una possibile evoluzione futura:
utilizzare un modello di Machine Learning per predire il valore futuro del gas di G1.

Il progetto principale resta quindi invariato:

Arduino -> Bridge -> MQTT -> Node-RED -> Dashboard

La demo AI resta separata:

gas_data.csv -> train_randomforest.py -> gas_rf_model.pkl -> predict_demo.py

Questo è importante da spiegare: la demo non sostituisce la logica attuale di Node-RED.
È una proof of concept, cioè una prima dimostrazione di fattibilità.


## 2. File presenti nella cartella

La cartella contiene:

- train_randomforest.py
- predict_demo.py
- gas_rf_model.pkl
- gas_data.csv
- README_OFFGAS_AI_SIMPLE_DEMO.txt
- TODO_LIST_DEMO.txt

### train_randomforest.py

È il file che allena il modello RandomForest usando i dati storici salvati in gas_data.csv.
Legge i dati, costruisce le feature temporali, addestra il modello e salva il risultato nel file
`gas_rf_model.pkl`.

Se il Mean Absolute Error ottenuto è circa 3.76 unità gas. Questo significa che, sui dati di test, 
il modello sbaglia in media di meno di 4 unità rispetto al valore reale a 30 secondi. 
È un risultato buono per una proof of concept, soprattutto perché dimostra che la pipeline di training e predizione funziona. 
Tuttavia, il dataset attuale è abbastanza stabile, quindi il risultato va interpretato come una prima dimostrazione, non come una validazione definitiva in scenari critici.

### predict_demo.py

È il file che mostra la predizione. Non allena il modello. Carica il modello già pronto da
`gas_rf_model.pkl`, prende gli ultimi valori del gas dal CSV e stampa il valore previsto tra
circa 30 secondi.

### gas_rf_model.pkl

È il modello RandomForest già allenato e salvato su disco. Serve per poter riutilizzare il modello
senza doverlo riaddestrare ogni volta.

### gas_data.csv

È un esempio di dataset storico prodotto dal Bridge. Nel progetto reale può essere sostituito con
il vostro `gas_data.csv` aggiornato.

### TODO_LIST_DEMO.txt

È una guida operativa passo passo per avviare la demo e per spiegare quali valori sono reali e
quali sono fissati manualmente per scopo dimostrativo.


## 3. Che cosa significa allenare un modello

Allenare un modello significa mostrargli esempi del passato, così che possa imparare una relazione
tra una situazione osservata e un risultato futuro.

Nel nostro caso vogliamo insegnare al modello questa relazione:

valori recenti del gas -> valore del gas tra circa 30 secondi

Il modello non vede solo il valore attuale, perché un singolo valore contiene poca informazione.
Per questo costruiamo alcune feature semplici usando gli ultimi campioni della serie temporale.

Le feature usate sono:

- gas_now: valore attuale del gas
- gas_1_step_ago: valore precedente
- gas_2_steps_ago: valore di due campioni fa
- gas_3_steps_ago: valore di tre campioni fa
- mean_last_4_values: media degli ultimi quattro valori

Il target, cioè ciò che il modello deve imparare a predire, è:

- target_gas_in_30s: valore del gas circa 30 secondi dopo

Quindi ogni riga del dataset di training diventa un esempio supervisionato:

Input:
    gas_now, gas_1_step_ago, gas_2_steps_ago, gas_3_steps_ago, mean_last_4_values

Output atteso:
    gas tra circa 30 secondi


## 4. Perché 6 campioni corrispondono a circa 30 secondi

Nel progetto OffGas, Arduino invia una lettura del gas circa ogni 5 secondi.
Questo significa che ogni riga successiva del CSV rappresenta approssimativamente un passo temporale
di 5 secondi.

Per predire il valore a 30 secondi nel futuro, usiamo 6 passi in avanti:

6 campioni * 5 secondi = circa 30 secondi

Nel codice questo è rappresentato dalla variabile:

PREDICTION_STEPS = 6

E il target viene creato con:

df["target_gas_in_30s"] = df["gas"].shift(-PREDICTION_STEPS)

Il significato è: per ogni riga attuale, il valore da predire è il valore che si trova 6 righe più avanti
nel CSV, cioè circa 30 secondi dopo. Il valore 6 righe avanti è la ground truth.


## 5. Perché RandomForestRegressor

Usiamo `RandomForestRegressor` perché vogliamo predire un numero, non una classe.

Il modello non restituisce direttamente SAFE, WARNING o CRITICAL.
Restituisce invece un valore numerico, ad esempio:

Predicted gas value in 30 seconds: 166.30

Dopo la predizione, possiamo confrontare questo valore con una soglia:

predicted_gas >= threshold

Se il valore previsto supera la soglia, allora possiamo dire che esiste un possibile rischio futuro.


## 6. Come viene creato il file .pkl

Il file `.pkl` viene creato da `train_randomforest.py` alla fine del training.

Il flusso è:

gas_data.csv
    -> train_randomforest.py
        -> gas_rf_model.pkl

Dentro lo script, dopo aver allenato il modello, viene eseguita questa istruzione:

joblib.dump(model_package, MODEL_FILE)

Nel nostro caso `MODEL_FILE` vale:

gas_rf_model.pkl

Questo comando salva su disco il modello già allenato e alcune informazioni utili, come l'elenco delle
feature e l'orizzonte di predizione.

Il file `.pkl` non viene scritto manualmente. Viene generato automaticamente da Python quando si esegue:

python train_randomforest.py


## 7. A cosa serve il file .pkl

Il file `gas_rf_model.pkl` serve a evitare di riaddestrare il modello ogni volta.

Senza il file `.pkl`, ogni volta dovremmo:

1. leggere il CSV
2. costruire le feature
3. addestrare il RandomForest
4. fare la predizione

Con il file `.pkl`, invece, possiamo separare le due fasi.

Fase 1 - Training:

gas_data.csv -> train_randomforest.py -> gas_rf_model.pkl

Fase 2 - Predizione:

gas_rf_model.pkl -> predict_demo.py -> predicted gas value

`predict_demo.py` carica il modello con:

joblib.load("gas_rf_model.pkl")

poi usa il modello già allenato per fare una predizione sugli ultimi valori disponibili.

Il file `.pkl` non è pensato per essere aperto manualmente in VS Code, perché è un file binario.
Se viene aperto come testo, può mostrare caratteri strani o contenuto non leggibile. Questo è normale.
Il modo corretto per usarlo è caricarlo da Python con `joblib.load()`.


## 8. La soglia nella demo

In questa versione semplificata, la soglia è una variabile fissa scritta direttamente dentro
`predict_demo.py`:

THRESHOLD = 220.0

Questo valore è deciso manualmente da noi solo per la demo offline.
Nel progetto reale, invece, la soglia non sarebbe fissa nel codice: verrebbe calcolata dinamicamente da
Node-RED usando il contesto degli altri garage.

Questa scelta serve a semplificare la dimostrazione. La demo AI vuole mostrare soprattutto la predizione:

dati storici -> modello RandomForest -> valore previsto tra 30 secondi

La soglia serve solo per completare il ragionamento:

valore previsto >= soglia -> predicted crossing

Se si vuole cambiare la soglia, basta aprire `predict_demo.py` e modificare:

THRESHOLD = 220.0

per esempio:

THRESHOLD = 180.0

Poi si rilancia:

python predict_demo.py


## 9. Come avviare la demo

### Passo 1 - Installare le librerie

pip install pandas scikit-learn joblib

### Passo 2 - Allenare il modello

python train_randomforest.py

Questo comando crea o aggiorna:

gas_rf_model.pkl

### Passo 3 - Eseguire la predizione

python predict_demo.py

Output atteso, simile a questo:

OFFGAS AI FUTURE DEMO
--------------------------------
This is a separate RandomForest proof of concept.
It does not modify the real OffGas runtime system.

Last 4 gas values used: [164, 163, 162, 161]
Current gas value: 161
Predicted gas value in 30 seconds: 162.45
Demo threshold configured in code: 220.00
Predicted crossing: False


## 10. Posso usare un nuovo gas_data.csv?

Sì. È possibile sostituire `gas_data.csv` con un file aggiornato contenente dati nuovi,
anche se quei dati non sono stati usati per allenare il modello.

In questo caso `predict_demo.py` dovrebbe funzionare comunque, perché non riaddestra il modello:
usa semplicemente il nuovo CSV per prendere gli ultimi valori disponibili e passarli al modello già
salvato in `gas_rf_model.pkl`.

Il flusso diventa quindi:

Training iniziale:

vecchio gas_data.csv -> train_randomforest.py -> gas_rf_model.pkl

Predizione con dati nuovi:

nuovo gas_data.csv -> predict_demo.py + gas_rf_model.pkl -> predizione

Questo significa che il modello contenuto nel file `.pkl` resta lo stesso.
Il nuovo `gas_data.csv` viene usato solo come input per la predizione.

Per funzionare correttamente, il nuovo CSV deve rispettare alcune condizioni:

1. deve contenere una colonna `gas`;
2. deve contenere almeno 4 righe valide;
3. se esiste la colonna `garage_id`, deve contenere righe con `garage_id = G1`;
4. se esiste la colonna `timestamp`, i timestamp devono essere leggibili e ordinabili;
5. i valori di `gas` devono essere numerici o convertibili in numeri.

Esempio di CSV valido:

timestamp,garage_id,gas,fan_state
2026-05-07T17:00:00,G1,160,False
2026-05-07T17:00:05,G1,162,False
2026-05-07T17:00:10,G1,163,False
2026-05-07T17:00:15,G1,164,False

In questo esempio `predict_demo.py` userà gli ultimi 4 valori:

160, 162, 163, 164

e produrrà una predizione a circa 30 secondi.

È importante però ricordare che, se i nuovi dati sono molto diversi da quelli usati durante il training,
la predizione potrebbe essere meno affidabile. Per esempio, se il modello è stato allenato quasi solo su
valori stabili intorno a 160-170 e riceve valori molto più alti, produrrà comunque una predizione, ma non è
detto che sia precisa.


## 11. Quando devo riaddestrare il modello?

Cambiare `gas_data.csv` non aggiorna automaticamente il modello.

Hai due possibilità.

### Caso 1 - Usare il nuovo CSV solo per fare una predizione

Se vuoi solo vedere cosa predice il modello già allenato sugli ultimi valori del nuovo CSV, esegui:

python predict_demo.py

In questo caso:

- `gas_rf_model.pkl` resta invariato;
- il modello non impara dai nuovi dati;
- il nuovo CSV viene usato solo per costruire l'input della predizione.

### Caso 2 - Usare il nuovo CSV per aggiornare il modello

Se vuoi che il modello impari anche dai nuovi dati, devi rieseguire il training:

python train_randomforest.py

Questo comando rigenera:

gas_rf_model.pkl

Poi puoi eseguire:

python predict_demo.py

In questo secondo caso:

- il nuovo CSV viene usato per riaddestrare il modello;
- il vecchio `.pkl` viene sostituito da un nuovo `.pkl`;
- le predizioni successive useranno il modello aggiornato.

In sintesi:

Nuovo CSV solo per inference:

python predict_demo.py

Nuovo CSV anche per training:

python train_randomforest.py
python predict_demo.py


## 12. Cosa dire al professore

Una spiegazione corretta potrebbe essere:

"Abbiamo mantenuto il progetto principale invariato. Per dimostrare una possibile evoluzione futura,
abbiamo creato una proof of concept separata basata su RandomForest. Lo script di training legge il file
`gas_data.csv`, costruisce un dataset supervisionato usando il valore attuale del gas, alcuni valori
precedenti e la media degli ultimi campioni. Poiché Arduino invia un campione circa ogni 5 secondi,
usiamo 6 campioni in avanti per rappresentare una predizione a circa 30 secondi. Il modello viene allenato
a predire il valore futuro del gas e viene salvato nel file `gas_rf_model.pkl`. Lo script di demo carica quel
modello e produce una predizione usando gli ultimi valori disponibili. La soglia presente nella demo è un
valore fisso scelto manualmente solo per simulare il confronto finale; nel progetto reale sarebbe calcolata
in modo dinamico da Node-RED."

Puoi anche aggiungere:

"Se sostituiamo `gas_data.csv` con dati più recenti, lo script di predizione può usarli subito come input.
Questo però non significa che il modello venga aggiornato automaticamente. Per aggiornare davvero il modello,
bisogna rieseguire `train_randomforest.py`, che rigenera il file `gas_rf_model.pkl`."


## 13. Limiti della demo

Questa demo non è un sistema AI production-ready.
È una dimostrazione di fattibilità.

I limiti principali sono:

- usa solo i dati di G1, cioè il prototipo reale;
- il dataset attuale contiene valori abbastanza stabili;
- la soglia è fissata manualmente nel codice;
- non è collegata al bridge live, a MQTT o a Node-RED;
- non controlla la ventola;
- non modifica la dashboard.

Questi limiti sono accettabili per una proof of concept, perché l'obiettivo è mostrare che i dati storici
salvati dal bridge possono essere trasformati in un dataset utile per addestrare un modello predittivo.
