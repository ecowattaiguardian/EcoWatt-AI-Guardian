#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <PZEM004Tv30.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <Adafruit_NeoPixel.h>

// --- PIN DEFINITIONS ---
const int PZEM_RX_PIN = 16;  // Connects to PZEM TX
const int PZEM_TX_PIN = 17;  // Connects to PZEM RX
const int BUZZER_PIN  = 5;   // Buzzer signal pin
const int RELAY_PIN   = 4;   // Relay control pin
const int RGB_LED_PIN = 48;  // ESP32-S3 built-in addressable RGB LED (WS2812)
const int NUMPIXELS   = 1;
const int SDA_PIN     = 41;  // I2C SDA Pin for ESP32-S3
const int SCL_PIN     = 42;  // I2C SCL Pin for ESP32-S3

// --- CALIBRATION & LIMITS ---
const float VOLTAGE_OFFSET = -3.0;      // Calibration adjustment to match DMM (PZEM reads ~3V high)
const float VOLTAGE_MAX    = 230.0;     // Over-voltage limit
const float VOLTAGE_MIN    = 200.0;     // Under-voltage limit

// --- INITIALIZE DEVICES & STORAGE ---
LiquidCrystal_I2C lcd(0x27, 16, 2);
PZEM004Tv30 pzem(Serial2, PZEM_RX_PIN, PZEM_TX_PIN);
Preferences preferences;
Adafruit_NeoPixel pixels(NUMPIXELS, RGB_LED_PIN, NEO_GRB + NEO_KHZ800);

// --- MQTT CONFIGURATION ---
const char* mqtt_server = "broker.hivemq.com";
WiFiClient espClient;
PubSubClient client(espClient);

// Default Wi-Fi Credentials (overwritten if updated via MQTT/Preferences)
String ssid = "Xperia IV";
String password = "Ashutosh09";

unsigned long previousMillis = 0;
const long interval = 2000; // Update every 2 seconds

// MQTT Callback to handle Wi-Fi credential updates only
void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, message);
  if (error) return;

  if (String(topic) == "ecowatt/wifi/update") {
    const char* newSsid = doc["ssid"];
    const char* newPass = doc["pass"];
    if (newSsid && strlen(newSsid) > 0) {
      preferences.begin("wifi-config", false);
      preferences.putString("ssid", newSsid);
      preferences.putString("pass", newPass ? newPass : "");
      preferences.end();
      Serial.println("New Wi-Fi credentials saved! Restarting...");
      ESP.restart();
    }
  }
}

// --- ROBUST I2C BUS RECOVERY & RE-INITIALIZATION FUNCTION ---
void recoverAndInitLCD() {
  // Toggle SCL clock pulses to clear any stuck slave devices on the bus
  pinMode(SDA_PIN, OUTPUT);
  pinMode(SCL_PIN, OUTPUT);
  digitalWrite(SDA_PIN, HIGH);
  digitalWrite(SCL_PIN, HIGH);
  delay(10);
  for (int i = 0; i < 9; i++) {
    digitalWrite(SCL_PIN, LOW);
    delayMicroseconds(5);
    digitalWrite(SCL_PIN, HIGH);
    delayMicroseconds(5);
  }
  
  // Re-engage Wire and LCD
  Wire.begin(SDA_PIN, SCL_PIN);
  delay(50);
  lcd.init();
  lcd.backlight();
  lcd.clear();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Initialize NeoPixel LED
  pixels.begin();
  pixels.setBrightness(30);
  pixels.setPixelColor(0, pixels.Color(0, 0, 255)); // Blue during boot
  pixels.show();

  // Initialize Pins
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // Default engaged
  digitalWrite(BUZZER_PIN, LOW); // Buzzer OFF

  // --- SAFE INITIAL LCD STARTUP ---
  recoverAndInitLCD();
  
  lcd.setCursor(0, 0);
  lcd.print("EcoWatt Guardian");
  lcd.setCursor(0, 1);
  lcd.print("Booting System...");
  delay(2000);
  lcd.clear();

  // Load saved Wi-Fi credentials if available
  preferences.begin("wifi-config", true);
  String savedSsid = preferences.getString("ssid", "");
  String savedPass = preferences.getString("pass", "");
  preferences.end();

  if (savedSsid.length() > 0) {
    ssid = savedSsid;
    password = savedPass;
  }

  // Connect to Wi-Fi with strict validation (prevent system failure loop)
  WiFi.begin(ssid.c_str(), password.c_str());
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(ssid);

  int wifiRetries = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    wifiRetries++;
    if (wifiRetries > 30) { // 15 seconds timeout
      Serial.println("\n⚠️ Wi-Fi Connection Failed! Running in Offline/Safe Mode.");
      recoverAndInitLCD();
      lcd.setCursor(0, 0);
      lcd.print("WiFi Failed!    ");
      lcd.setCursor(0, 1);
      lcd.print("Offline Mode    ");
      pixels.setPixelColor(0, pixels.Color(255, 165, 0)); // Orange for offline mode
      pixels.show();
      delay(3000);
      break;
    }
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected! IP: " + WiFi.localIP().toString());
    client.setServer(mqtt_server, 1883);
    client.setCallback(callback);
    pixels.setPixelColor(0, pixels.Color(0, 255, 0)); // Green when connected
    pixels.show();
  }
}

void reconnectMQTT() {
  if (WiFi.status() == WL_CONNECTED && !client.connected()) {
    if (client.connect("EcoWatt_ESP32_Guardian")) {
      client.subscribe("ecowatt/wifi/update"); // Subscribed only to Wi-Fi provisioning updates
      Serial.println("Connected to HiveMQ Broker!");
    }
  }
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!client.connected()) {
      reconnectMQTT();
    }
    client.loop();
  }

  unsigned long currentMillis = millis();

  // Read PZEM and update LCD / MQTT every 2 seconds
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    float rawVoltage = pzem.voltage();
    float current   = pzem.current();
    float power     = pzem.power();
    float frequency = pzem.frequency();
    float pf        = pzem.pf();

    // Check if PZEM communication failed (NaN) vs zero voltage load
    if (isnan(rawVoltage)) {
      Serial.println("⚠️ Error: Failed to communicate with PZEM-004T module!");
      recoverAndInitLCD(); // Auto-heal I2C if bus glitch occurred
      lcd.setCursor(0, 0);
      lcd.print("PZEM Comm Error!");
      lcd.setCursor(0, 1);
      lcd.print("Check UART Wiring");
      pixels.setPixelColor(0, pixels.Color(255, 0, 0)); // Red LED on sensor error
      pixels.show();
    } else {
      // Apply calibration offset to match DMM exactly
      float voltage = rawVoltage + VOLTAGE_OFFSET;

      // Print to Serial Monitor
      Serial.print("V(Calibrated): "); Serial.print(voltage, 1); Serial.print("V | ");
      Serial.print("I: "); Serial.print(current, 2); Serial.print("A | ");
      Serial.print("P: "); Serial.print(power, 1); Serial.print("W | ");
      Serial.print("Freq: "); Serial.print(frequency, 1); Serial.print("Hz | ");
      Serial.print("PF: "); Serial.println(pf, 2);

      // Update LCD Display with error-safe execution
      lcd.setCursor(0, 0);
      char row1Buf[17];
      snprintf(row1Buf, sizeof(row1Buf), "%0.1fV  %0.2fA", voltage, current);
      lcd.print(row1Buf);

      lcd.setCursor(0, 1);
      char row2Buf[17];
      snprintf(row2Buf, sizeof(row2Buf), "%0.1fW  %0.1fHz", power, frequency);
      lcd.print(row2Buf);

      // Fault protection logic (Strict 200V - 230V bounds)
      int faultFlag = 0;
      if (voltage > VOLTAGE_MAX || (voltage > 0 && voltage < VOLTAGE_MIN)) {
        digitalWrite(RELAY_PIN, LOW);    // Trip relay
        digitalWrite(BUZZER_PIN, HIGH);   // Alarm ON
        pixels.setPixelColor(0, pixels.Color(255, 0, 0)); // Red LED Warning
        faultFlag = 1;
      } else {
        digitalWrite(RELAY_PIN, HIGH);   // Keep engaged
        digitalWrite(BUZZER_PIN, LOW);    // Alarm OFF
        pixels.setPixelColor(0, pixels.Color(0, 255, 0)); // Green LED Nominal
        faultFlag = 0;
      }
      pixels.show();

      // Publish live telemetry to MQTT if connected
      if (WiFi.status() == WL_CONNECTED && client.connected()) {
        StaticJsonDocument<256> doc;
        doc["voltage_rms"] = voltage;
        doc["current_rms"] = current;
        doc["active_power"] = power;
        doc["frequency"] = frequency;
        doc["power_factor"] = pf;
        doc["dv_dt"] = 0.1;
        doc["vhs_score"] = 95.0;
        doc["fault_flag"] = faultFlag;
        doc["relay_state"] = (faultFlag == 1) ? "TRIPPED" : "CLOSED";

        char buffer[256];
        serializeJson(doc, buffer);
        client.publish("ecowatt/telemetry", buffer);
      }
    }
  }
}