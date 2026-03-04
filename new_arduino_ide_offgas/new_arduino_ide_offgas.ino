#include <SoftwareSerial.h>

// ---- PIN ----
const int mq2Pin = A1;
const int bluetoothRxPin = 10;
const int bluetoothTxPin = 11;
const int PIN_VENTOLA = 9;

// ---- Parametri ----
const unsigned long intervalloLettura = 5000;  // 5 secondi

// ---- Stato ----
unsigned long ultimoTempoLettura = 0;
bool fanState = false;

// ---- Bluetooth ----
SoftwareSerial bluetooth(bluetoothRxPin, bluetoothTxPin);

void setup() {
  pinMode(mq2Pin, INPUT);
  pinMode(PIN_VENTOLA, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);

  digitalWrite(PIN_VENTOLA, LOW);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(9600);
  bluetooth.begin(9600);

  Serial.println("Arduino OffGas Ready.");
}

void loop() {

  unsigned long now = millis();

  // ===============================
  // 1️⃣ Invio periodico valore MQ2
  // ===============================
  if (now - ultimoTempoLettura >= intervalloLettura) {
    ultimoTempoLettura = now;

    int valore = analogRead(mq2Pin);

    bluetooth.print("MQ2:");
    bluetooth.println(valore);

    Serial.print("MQ2:");
    Serial.println(valore);
  }

  // ===============================
  // 2️⃣ Ricezione comandi Bridge
  // ===============================
  if (bluetooth.available()) {

    String comando = bluetooth.readStringUntil('\n');
    comando.trim();

    if (comando.equalsIgnoreCase("FAN_ON")) {

      digitalWrite(PIN_VENTOLA, HIGH);
      digitalWrite(LED_BUILTIN, HIGH);
      fanState = true;

      Serial.println("Ventola ON (da Bridge)");

    } else if (comando.equalsIgnoreCase("FAN_OFF")) {

      digitalWrite(PIN_VENTOLA, LOW);
      digitalWrite(LED_BUILTIN, LOW);
      fanState = false;

      Serial.println("Ventola OFF (da Bridge)");
    }
  }
}