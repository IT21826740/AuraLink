#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>

const char* ssid = "OnePlus Nord N20 SE";
const char* password = "e97ec3cr";

const char* mqtt_server = "10.91.73.95";  
const int mqtt_port = 1883;
const char* mqtt_user = "";
const char* mqtt_password = "";

const char* topic_sensor_data = "auralink/sensor/data";  
const char* topic_quote = "auralink/backend/message";     
const char* topic_email = "auralink/backend/message";    
const char* topic_priority = "auralink/backend/message";  

#define DHTPIN 4
#define DHTTYPE DHT22
#define MQ135_PIN 34
#define BUTTON_PIN 2
#define BUZZER_PIN 33
#define LED_RED 12
#define LED_GREEN 13
#define LED_BLUE 14

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

DHT dht(DHTPIN, DHTTYPE);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
WiFiClient espClient;
PubSubClient client(espClient);

float temperature = 0;
float humidity = 0;
int airQuality = 0;

String currentQuote = "Initializing...";
String currentEmail = "No emails yet";
int priorityLevel = 0;

unsigned long lastSensorRead = 0;
unsigned long lastPublish = 0;
const long sensorInterval = 2000;
const long publishInterval = 10000;

bool buttonPressed = false;
unsigned long lastButtonPress = 0;
const long debounceDelay = 500;

bool lastButtonState = HIGH;
bool showingEmail = false;
unsigned long emailDisplayStart = 0;
const long emailDisplayDuration = 5000;

unsigned long lastScrollUpdate = 0;
int quoteScrollOffset = 0;
int emailScrollOffset = 0;
const long scrollInterval = 150;
const int visibleChars = 21;

void setupWiFi();
void reconnectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void readSensors();
void publishSensorData();
void updateDisplay();
void handleButtonPress();
void setPriorityIndicator(int level);
void setRGBColor(int red, int green, int blue);
void beep(int duration);
String getScrollingText(String text);

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== AuraLink Starting ===");

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);

  digitalWrite(BUZZER_PIN, LOW);
  setRGBColor(0, 0, 0);

  lastButtonState = digitalRead(BUTTON_PIN);

  dht.begin();
  Serial.println("DHT22 initialized");

  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println("OLED allocation failed!");
    while (1);
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Initializing...");
  display.display();
  Serial.println("OLED initialized");

  setupWiFi();

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
  client.setBufferSize(512);

  beep(100);

  Serial.println("=== Initialization Complete ===\n");
}

void loop() {
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  unsigned long currentMillis = millis();
  
  if (currentMillis - lastSensorRead >= sensorInterval) {
    lastSensorRead = currentMillis;
    readSensors();
  }

  if (currentMillis - lastPublish >= publishInterval) {
    lastPublish = currentMillis;
    publishSensorData();
  }

  bool currentButtonState = digitalRead(BUTTON_PIN);
  if (currentButtonState == LOW && lastButtonState == HIGH && !showingEmail && 
      (currentMillis - lastButtonPress > debounceDelay)) {
    lastButtonPress = currentMillis;
    handleButtonPress();
    showingEmail = true;
    emailDisplayStart = currentMillis;
  }
  lastButtonState = currentButtonState;

  if (showingEmail && (currentMillis - emailDisplayStart >= emailDisplayDuration)) {
    showingEmail = false;
  }

  if (currentMillis - lastScrollUpdate >= scrollInterval) {
    lastScrollUpdate = currentMillis;
    if (currentQuote.length() > visibleChars) {
      quoteScrollOffset = (quoteScrollOffset + 1) % (currentQuote.length() + visibleChars);
    }
    if (currentEmail.length() > visibleChars) {
      emailScrollOffset = (emailScrollOffset + 1) % (currentEmail.length() + visibleChars);
    }
  }

  updateDisplay();
}

void setupWiFi() {
  delay(10);
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Connecting...");
  display.println(ssid);
  display.display();

  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    
    setRGBColor(0, 255, 0);
    beep(200);
    delay(1000);
    setRGBColor(0, 0, 0);
  } else {
    Serial.println("\nWiFi connection failed!");
    setRGBColor(255, 0, 0);
  }
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    
    String clientId = "AuraLink-ESP32-";
    clientId += String(random(0xffff), HEX);

    if (client.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
      Serial.println("connected!");
      
      client.subscribe(topic_quote);
      client.subscribe(topic_email);
      client.subscribe(topic_priority);
      
      Serial.println("Subscribed to topics");
      setRGBColor(0, 0, 255);
      beep(100);
      delay(500);
      setRGBColor(0, 0, 0);
    } else {
      Serial.print("Failed, rc=");
      Serial.print(client.state());
      Serial.println(" Retrying in 5 seconds...");
      setRGBColor(255, 0, 0);
      delay(5000);
    }
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("]: ");

  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);

  DynamicJsonDocument doc(1024);
  DeserializationError error = deserializeJson(doc, message);
  if (error) {
    Serial.print("JSON parse failed: ");
    Serial.println(error.c_str());
    return;
  }

  bool newMessage = false;
  if (doc.containsKey("quote")) {
    currentQuote = doc["quote"].as<String>();
    Serial.println("Quote updated: " + currentQuote);
    newMessage = true;
    quoteScrollOffset = 0;
  }
  if (doc.containsKey("email_summary")) {
    currentEmail = doc["email_summary"].as<String>();
    Serial.println("Email summary updated: " + currentEmail);
    newMessage = true;
    emailScrollOffset = 0;
  }
  if (doc.containsKey("priority")) {
    if (doc["priority"] == "low") priorityLevel = 0;
    else if (doc["priority"] == "medium") priorityLevel = 1;
    else if (doc["priority"] == "high") priorityLevel = 2;
    else priorityLevel = doc["priority"].as<int>();
    setPriorityIndicator(priorityLevel);
    Serial.print("Priority set to: ");
    Serial.println(priorityLevel);
    if (priorityLevel == 2) beep(50);
  }
  if (newMessage) beep(100);
}

void readSensors() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (!isnan(h) && !isnan(t)) {
    humidity = h;
    temperature = t;
    Serial.printf("DHT22 - Temp: %.1f°C, Humidity: %.1f%%\n", temperature, humidity);
  } else {
    Serial.println("Failed to read from DHT22!");
  }

  airQuality = analogRead(MQ135_PIN);
  Serial.printf("MQ-135 - Air Quality: %d\n", airQuality);
}

void publishSensorData() {
  if (!client.connected()) return;

  String payload = "{";
  payload += "\"temperature\":" + String(temperature, 1) + ",";
  payload += "\"humidity\":" + String(humidity, 1) + ",";
  payload += "\"airQuality\":" + String(airQuality);
  payload += "}";

  if (client.publish(topic_sensor_data, payload.c_str())) {
    Serial.println("Sensor data published: " + payload);
  } else {
    Serial.println("Failed to publish sensor data");
  }
}

String getScrollingText(String text) {
  if (text.length() <= visibleChars) return text;
  int totalLength = text.length() + visibleChars;
  int startPos = (quoteScrollOffset > text.length() ? 0 : quoteScrollOffset) % totalLength;
  String padded = text + String(' ', visibleChars);
  return padded.substring(startPos, startPos + visibleChars);
}

void updateDisplay() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);

  if (showingEmail) {
    display.println("*** EMAILS ***");
    display.println();
    
    int lineLength = 21;
    int startPos = 0;
    int line = 2;
    
    while (startPos < currentEmail.length() && line < 8) {
      String segment = currentEmail.substring(startPos, startPos + lineLength);
      display.println(segment);
      startPos += lineLength;
      line++;
    }
  } else {
    display.println("*** AuraLink ***");

    display.print("Temp: ");
    display.print(temperature, 1);
    display.println("C");
    
    display.print("Hum: ");
    display.print(humidity, 0);
    display.println("%");

    display.print("Air Quality: ");
    display.print(airQuality);  
    display.println();

    display.println("---------------");
    
    String quoteDisplay = getScrollingText(currentQuote);
    display.println(quoteDisplay);
    
    display.println("---------------");
    String emailDisplay = getScrollingText(currentEmail);
    display.print("Emails: ");
    display.println(emailDisplay);
  }

  display.display();
}

void handleButtonPress() {
  Serial.println("Button pressed! Showing email summary...");
  
  beep(100);
}

void setPriorityIndicator(int level) {
  switch(level) {
    case 0:
      setRGBColor(0, 255, 0);
      break;
    case 1:
      setRGBColor(255, 255, 0);
      break;
    case 2:
      setRGBColor(255, 0, 0);
      beep(200);
      delay(100);
      beep(200);
      break;
    default:
      setRGBColor(0, 0, 0);
  }
}

void setRGBColor(int red, int green, int blue) {
  analogWrite(LED_RED, red);
  analogWrite(LED_GREEN, green);
  analogWrite(LED_BLUE, blue);
}

void beep(int duration) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(duration);
  digitalWrite(BUZZER_PIN, LOW);
}