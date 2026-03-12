#include <SoftwareSerial.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>

// OLED
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ---- PIN ----
const int mq2Pin = A1;
const int bluetoothRxPin = 10;
const int bluetoothTxPin = 11;
const int PIN_VENTOLA = 9;

// ---- Parametri ----
const unsigned long intervalloLettura = 5000;

// ---- Stato ----
unsigned long ultimoTempoLettura = 0;
bool fanState = false;
int lastGasValue = 0;

bool displayDirty = true;   // segnala quando aggiornare OLED

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

  if(!display.begin(0x3C, true)) {
    while(true);
  }

  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);

  aggiornaDisplay();
}

void loop() {

  unsigned long now = millis();

  // ===============================
  // 1️⃣ Invio valore MQ2
  // ===============================
  if (now - ultimoTempoLettura >= intervalloLettura) {

    ultimoTempoLettura = now;
    
    //fase di mediazione --> evito l'invio di falsi positivi o valori anomarli

    int val[5];
    int valore;

    for(int i = 0; i < 5; i++){
      valore = analogRead(mq2Pin);
      val[i] = valore;
      delay(5);
    }

    //ordino in ordine crescente il vettore val, agli estremi ho i valori anormali

    for(int i = 0; i<4;i++){
      for(int j = i+1; j < 5; j++){
        if(val[i]>val[j]){
          int a = val[i];
          val[i] = val[j];
          val[j] = a;
        }
      }
    }

    //medio sui valori nella norma

    valore = (val[1]+val[2]+val[3])/3;
    lastGasValue = valore;

    bluetooth.print("MQ2:");
    bluetooth.println(valore);

    Serial.print("MQ2:");
    Serial.println(valore);

    displayDirty = true;
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
      displayDirty = true;

    } else if (comando.equalsIgnoreCase("FAN_OFF")) {

      digitalWrite(PIN_VENTOLA, LOW);
      digitalWrite(LED_BUILTIN, LOW);
      fanState = false;

      Serial.println("Ventola OFF (da Bridge)");
      displayDirty = true;
    }
  }

  // ===============================
  // 3️⃣ Aggiorna OLED solo quando
  // non arrivano byte Bluetooth
  // ===============================
  if (displayDirty && !bluetooth.available()) {
    aggiornaDisplay();
    displayDirty = false;
  }
}


// ===============================
// OLED
// ===============================

void aggiornaDisplay() {

  display.clearDisplay();

  display.setTextSize(2);
  display.setCursor(0,0);
  display.print("OffGas");

  display.setTextSize(1);
  display.setCursor(0,25);
  display.print("Gas: ");
  display.print(lastGasValue);

  display.setCursor(0,40);
  display.print("Fan: ");
  display.print(fanState ? "ON" : "OFF");

  display.display();
}