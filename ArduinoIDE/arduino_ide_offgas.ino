#include <SoftwareSerial.h>

// ---- PIN ----
const int mq2Pin = A1;             // Pin analogico del sensore MQ2
const int bluetoothRxPin = 10;     // Pin RX Arduino (collegato al TXD dell'HC-05)
const int bluetoothTxPin = 11;     // Pin TX Arduino (collegato all'RXD dell'HC-05 tramite PARTITORE DI TENSIONE!)
const int PIN_VENTOLA = 9;         // Pin di controllo collegato alla BASE del Transistor (NPN)

// ---- Parametri logici ----
const int soglia = 180;                     // Soglia di gas (da tarare)
const unsigned long intervalloLettura = 5000;    // 5 secondi tra una lettura e l'altra
const unsigned long tempoMinimoAttivazione = 5000; // 5 secondi minimo di ventola/LED accesi

// ---- Variabili di stato ----
unsigned long ultimoTempoLettura = 0;
unsigned long tempoAttivazioneVentola = 0;
bool dispositivoAttivo = false; // Controlla lo stato (ventola ON/OFF, LED ON/OFF)

// ---- Inizializzazione Seriale Software per HC-05 ----
// Crea un oggetto seriale virtuale sul pin 10 (RX) e 11 (TX)
SoftwareSerial bluetooth(bluetoothRxPin, bluetoothTxPin);

void setup() {
  pinMode(mq2Pin, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(PIN_VENTOLA, OUTPUT); // Configura il pin del transistor come OUTPUT

  // Inizializzazione (ventola e LED spenti)
  digitalWrite(PIN_VENTOLA, LOW);
  digitalWrite(LED_BUILTIN, LOW);

  // Seriale USB (per debug sul Monitor Seriale del PC)
  Serial.begin(9600);
  Serial.println("Seriale USB OK.");

  // Seriale Bluetooth (per comunicazione wireless con HC-05)
  bluetooth.begin(9600); 
  bluetooth.println("Sistema MQ2 + HC-05 avviato. Ventola pronta (Pin 9).");
}

void loop() {
  unsigned long adesso = millis();

  // --- Lettura periodica del sensore ---
  if (adesso - ultimoTempoLettura >= intervalloLettura) {
    ultimoTempoLettura = adesso;

    int valore = analogRead(mq2Pin);

    // Messaggio via Bluetooth (HC-05)
    bluetooth.print("Valore MQ2: ");
    bluetooth.println(valore);
    
    // Stampa anche su Serial USB per debug
    Serial.print("Lettura (USB): ");
    Serial.println(valore);

    // --- LOGICA DI ATTIVAZIONE (VENTOLA E LED) ---
    if (valore > soglia) {
      // Se la soglia è superata, attiva subito il dispositivo
      if (!dispositivoAttivo) {
        dispositivoAttivo = true;
        tempoAttivazioneVentola = adesso; // Imposta l'inizio dell'attivazione
        
        // ACCENSIONE FISICA (VENTOLA E LED)
        digitalWrite(PIN_VENTOLA, HIGH); // Segnale HIGH al transistor (ACCENDE la ventola)
        digitalWrite(LED_BUILTIN, HIGH);
        bluetooth.println("!!! ALLARME GAS - ATTIVAZIONE VENTOLA !!!");
      }
      // NOTA: Se il valore resta alto, dispositivoAttivo rimane 'true'.
    }
  }
  
  // --- Gestione SPEGNIMENTO (tempo minimo e rientro sotto soglia) ---
  if (dispositivoAttivo) {
    // 1. Controlla se è passato il tempo minimo di attivazione
    if (adesso - tempoAttivazioneVentola >= tempoMinimoAttivazione) {
      
      // 2. Dopo il tempo minimo, verifica il valore attuale
      int valoreAttuale = analogRead(mq2Pin);
      
      if (valoreAttuale <= soglia) {
        // La condizione di allarme è rientrata
        dispositivoAttivo = false;
        
        // SPEGNIMENTO FISICO (VENTOLA E LED)
        digitalWrite(PIN_VENTOLA, LOW); // Segnale LOW al transistor (SPEGNE la ventola)
        digitalWrite(LED_BUILTIN, LOW);
        bluetooth.println("Allarme rientrato. Ventola spenta.");
      }
      // Altrimenti, rimane attivo finché il valore non scende sotto soglia.
    }
  }

  // --- Gestione comandi in arrivo da Bluetooth ---
  if (bluetooth.available()) {
    String comando = bluetooth.readStringUntil('\n');
    Serial.print("Comando BT ricevuto: ");
    Serial.println(comando);
    
    // Esempio: potresti aggiungere qui la logica per spegnere manualmente la ventola
    // if (comando.trim().equalsIgnoreCase("RESET")) { ... }
  }
}