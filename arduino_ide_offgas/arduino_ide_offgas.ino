#include <SoftwareSerial.h>     // libreria per seriale software (Bluetooth HC-05)
#include <Wire.h>               // libreria comunicazione I2C
#include <Adafruit_GFX.h>       // libreria grafica base per display
#include <Adafruit_SH110X.h>    // libreria specifica per display OLED SH1106

// ===============================
// CONFIGURAZIONE OLED
// ===============================

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// creazione oggetto display (I2C)
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);


// ===============================
// CONFIGURAZIONE PIN
// ===============================

const int mq2Pin = A1;          // sensore gas MQ2 collegato all'ingresso analogico
const int bluetoothRxPin = 10;  // RX bluetooth (Arduino riceve)
const int bluetoothTxPin = 11;  // TX bluetooth (Arduino trasmette)
const int PIN_VENTOLA = 9;      // pin che controlla la ventola


// ===============================
// PARAMETRI SISTEMA
// ===============================

const unsigned long intervalloLettura = 5000;   // intervallo lettura sensore gas (5s)


// ===============================
// VARIABILI DI STATO
// ===============================

unsigned long ultimoTempoLettura = 0;   // timestamp ultima lettura gas
bool fanState = false;                  // stato ventola
int lastGasValue = 0;                   // ultimo valore gas letto

bool displayDirty = true;               // flag che indica quando aggiornare il display
unsigned long lastDisplayUpdate = 0;    // timestamp ultimo aggiornamento display


// ===============================
// ANIMAZIONE VENTOLA
// ===============================

unsigned long lastFanAnim = 0;   // timestamp ultimo frame animazione
bool fanFrame = false;           // frame corrente (alternanza tra 2 immagini)


// ===============================
// INTRO ALL'AVVIO
// ===============================

bool introActive = true;         // indica se la intro è ancora attiva
unsigned long introStartTime = 0;
unsigned long introLastFrame = 0;
bool introFrame = false;


// ===============================
// BITMAP FRAME 1 VENTOLA
// ===============================

const uint8_t fan_frame1[] PROGMEM = {

0b00000110,0b01100000,
0b00001111,0b11110000,
0b00011000,0b00011000,
0b00110011,0b11001100,
0b01100011,0b11000110,
0b01100111,0b11100110,
0b11001111,0b11110011,
0b11011100,0b00111011,
0b11011100,0b00111011,
0b11001111,0b11110011,
0b01100111,0b11100110,
0b01100011,0b11000110,
0b00110011,0b11001100,
0b00011000,0b00011000,
0b00001111,0b11110000,
0b00000110,0b01100000
};


// ===============================
// BITMAP FRAME 2 VENTOLA
// ===============================

const uint8_t fan_frame2[] PROGMEM = {

0b00000110,0b01100000,
0b00001111,0b11110000,
0b00011000,0b00011000,
0b00110111,0b11101100,
0b01100110,0b01100110,
0b01101100,0b00110110,
0b11011000,0b00011011,
0b11110000,0b00001111,
0b11110000,0b00001111,
0b11011000,0b00011011,
0b01101100,0b00110110,
0b01100110,0b01100110,
0b00110111,0b11101100,
0b00011000,0b00011000,
0b00001111,0b11110000,
0b00000110,0b01100000
};


// ===============================
// BLUETOOTH SERIAL
// ===============================

SoftwareSerial bluetooth(bluetoothRxPin, bluetoothTxPin);


// ===============================
// SETUP
// ===============================

void setup() {

  // configurazione pin hardware
  pinMode(mq2Pin, INPUT);
  pinMode(PIN_VENTOLA, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);

  // ventola inizialmente spenta
  digitalWrite(PIN_VENTOLA, LOW);
  digitalWrite(LED_BUILTIN, LOW);

  // inizializzazione seriali
  Serial.begin(9600);
  bluetooth.begin(9600);

  // inizializzazione display OLED
  if(!display.begin(0x3C, true)) {
    while(true);   // blocca se il display non viene trovato
  }

  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);

  // avvio timer intro
  introStartTime = millis();
}


// ===============================
// LOOP PRINCIPALE
// ===============================

void loop() {

  unsigned long now = millis();


  // ===============================
  // INTRO OFFGAS
  // ===============================

  // per i primi 4 secondi mostra la schermata di avvio
  if (introActive) {

    if (now - introStartTime < 4000) {

      if (now - introLastFrame > 250) {

        introFrame = !introFrame;

        display.clearDisplay();

        display.setTextSize(2);
        display.setCursor(24,12);
        display.print("OFFGAS");

        // animazione ventola
        if (introFrame)
          display.drawBitmap(56,40, fan_frame1,16,16,SH110X_WHITE);
        else
          display.drawBitmap(56,40, fan_frame2,16,16,SH110X_WHITE);

        display.display();

        introLastFrame = now;
      }

      return;   // blocca il resto del programma durante la intro
    }

    // fine intro
    introActive = false;
    displayDirty = true;
  }


  // ===============================
  // LETTURA SENSORE GAS
  // ===============================

  if (now - ultimoTempoLettura >= intervalloLettura) {

    ultimoTempoLettura = now;

    int val[5];
    int valore;
    //MEDIAZIONE
    // lettura multipla sensore
    for(int i=0;i<5;i++){
      valore = analogRead(mq2Pin);
      val[i] = valore;
      delay(5);
    }

    // ordinamento valori
    for(int i=0;i<4;i++){
      for(int j=i+1;j<5;j++){
        if(val[i]>val[j]){
          int a=val[i];
          val[i]=val[j];
          val[j]=a;
        }
      }
    }

    // trimmed mean (elimina min e max)
    valore=(val[1]+val[2]+val[3])/3;
    lastGasValue=valore;

    // invio valore al bridge
    bluetooth.print("MQ2:");
    bluetooth.println(valore);

    Serial.print("MQ2:");
    Serial.println(valore);

    displayDirty=true;
  }


  // ===============================
  // RICEZIONE COMANDI DAL BRIDGE
  // ===============================

  if (bluetooth.available()) {

    String comando = bluetooth.readStringUntil('\n');
    comando.trim();

    if (comando.equalsIgnoreCase("FAN_ON")) {

      digitalWrite(PIN_VENTOLA,HIGH);
      digitalWrite(LED_BUILTIN,HIGH);
      fanState=true;

      Serial.println("Ventola ON");
      displayDirty=true;
    }

    else if (comando.equalsIgnoreCase("FAN_OFF")) {

      digitalWrite(PIN_VENTOLA,LOW);
      digitalWrite(LED_BUILTIN,LOW);
      fanState=false;

      Serial.println("Ventola OFF");
      displayDirty=true;
    }
  }


  // ===============================
  // ANIMAZIONE VENTOLA
  // ===============================

  if (fanState && now-lastFanAnim>200) {

    fanFrame=!fanFrame;
    displayDirty=true;
    lastFanAnim=now;
  }


  // ===============================
  // AGGIORNAMENTO DISPLAY
  // ===============================

  unsigned long displayInterval = fanState ? 200 : 500;

  if (displayDirty && now-lastDisplayUpdate>displayInterval) {

    aggiornaDisplay();

    displayDirty=false;
    lastDisplayUpdate=now;
  }

}


// ===============================
// FUNZIONE DI AGGIORNAMENTO OLED
// ===============================

void aggiornaDisplay() {

  display.clearDisplay();

  // stato ventola
  display.setTextSize(2);
  display.setCursor(0,0);
  display.print("FAN ");
  display.print(fanState ? "ON":"OFF");

  // animazione ventola
  if (fanState) {

    if (fanFrame)
      display.drawBitmap(96,0,fan_frame1,16,16,SH110X_WHITE);
    else
      display.drawBitmap(96,0,fan_frame2,16,16,SH110X_WHITE);
  }

  // valore gas
  display.setTextSize(1);
  display.setCursor(0,34);
  display.print("Gas: ");
  display.print(lastGasValue);

  display.display();
}