#include <WiFi.h>
#include <ArduinoOTA.h>
#include <Wire.h>
#include <math.h>
#include "ping1d.h"
#include <ArduinoJson.h>
#include <MS5837.h>

// ============================================
// CONFIGURACIÓN WIFI
// ============================================
const char* ssid = "esp32_rov";
const char* password = "12345678";

// ============================================
// CONFIGURACIÓN PINS
// ============================================
#define SONAR_RX 16
#define SONAR_TX 17
#define I2C_SDA 21
#define I2C_SCL 22
#define MPU6050_ADDR 0x68
#define PWR_MGMT_1 0x6B
#define ACCEL_XOUT_H 0x3B

// Pines para los ESCs de los T200 (Verticales)
#define ESC_DERECHO_PIN 13
#define ESC_IZQUIERDO_PIN 14

// Pines para las turbinas horizontales M3-M6
#define M3_PIN 27
#define M4_PIN 26
#define M5_PIN 25
#define M6_PIN 33

// LUMEN SUBSEA LIGHT - PWM en GPIO32
#define LUMEN_PWM_PIN 32
#define PWM_FREQ 50
#define PWM_RESOLUTION 8

// ============================================
// CONSTANTES PARA ESCs VERTICALES
// ============================================
#define ESC_NEUTRAL_US 1500
#define ESC_MIN_US 1100
#define ESC_MAX_US 1900

// ============================================
// CONSTANTES - OPTIMIZADAS PARA VELOCIDAD
// ============================================
#define SENSIBILIDAD 0.15
#define VELOCIDAD_SONIDO_AGUA 1500000

// ¡Reducidos al mínimo para máxima velocidad!
#define DELAY_SONAR 30     // Lectura cada 30ms
#define DELAY_MPU 20       // Lectura cada 20ms
#define DELAY_PRESION 20   // Lectura cada 20ms
#define STREAM_INTERVAL 20 // Enviar datos cada 20ms (50Hz)

// ============================================
// OBJETOS GLOBALES
// ============================================
HardwareSerial PingSerial(2);
Ping1D ping { PingSerial };
MS5837 sensorPresion;

unsigned long lastSonarRead = 0;
unsigned long lastMPURead = 0;
unsigned long lastPresionRead = 0;
unsigned long lastStreamTime = 0;

float ultimaDistancia = 0;
int ultimaConfianza = 0;
float ultimoAX = 0, ultimoAY = 0, ultimoAZ = 0;

float presionMbar = 0;
float profundidadM = 0;
float temperaturaC = 0;
bool sensorPresionOK = false;

bool lumenEncendido = false;
String inputBuffer = "";
bool streamMode = true;  // Stream activo por defecto

// ============================================
// VARIABLES PARA PWM INDEPENDIENTE
// ============================================
int pwmDerechoActual = 1500;
int pwmIzquierdoActual = 1500;

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  Serial.println("\n=== INICIANDO ESP32 ===\n");
  
  initMotoresVerticales();
  initMotoresHorizontales();
  initLumen();
  initSonar();
  initMPU();
  initPresion();
  initWiFiAndOTA();
  
  Serial.println("\n=== SISTEMA LISTO ===");
  Serial.println("✅ Modo STREAM activado (50Hz)");
}

// ============================================
// LOOP - MÁXIMA VELOCIDAD
// ============================================
void loop() {
  ArduinoOTA.handle();
  
  unsigned long now = millis();
  
  // Leer comandos seriales (prioridad alta)
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      if (inputBuffer.length() > 0) {
        if (inputBuffer.startsWith("{")) {
          procesarComando(inputBuffer);
        }
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }
  
  // Leer sensores en intervalos
  if (now - lastSonarRead >= DELAY_SONAR) {
    lastSonarRead = now;
    readSonar();
  }
  
  if (now - lastMPURead >= DELAY_MPU) {
    lastMPURead = now;
    readMPU();
  }
  
  if (now - lastPresionRead >= DELAY_PRESION) {
    lastPresionRead = now;
    readPresion();
  }
  
  // Enviar datos en STREAM cada 20ms (50Hz)
  if (streamMode && (now - lastStreamTime >= STREAM_INTERVAL)) {
    lastStreamTime = now;
    enviarDatosSensores();
  }
  
  // SIN DELAY - Loop lo más rápido posible
  // delay(1);  // ¡ELIMINADO!
}

// ============================================
// FUNCIONES DE CONTROL DE MOTORES VERTICALES
// ============================================
void initMotoresVerticales() {
  pinMode(ESC_DERECHO_PIN, OUTPUT);
  pinMode(ESC_IZQUIERDO_PIN, OUTPUT);
  
  ledcAttach(ESC_DERECHO_PIN, 50, 16);
  ledcAttach(ESC_IZQUIERDO_PIN, 50, 16);
  
  escribirMotorVertical(ESC_DERECHO_PIN, ESC_NEUTRAL_US);
  escribirMotorVertical(ESC_IZQUIERDO_PIN, ESC_NEUTRAL_US);
  
  Serial.printf("[MOTORES V] ESCs T200 inicializados\n");
}

void escribirMotorVertical(int pin, int microsegundos) {
  microsegundos = constrain(microsegundos, ESC_MIN_US, ESC_MAX_US);
  uint32_t duty = map(microsegundos, 0, 20000, 0, 65535);
  ledcWrite(pin, duty);
}

void actualizarMotores() {
  pwmDerechoActual = constrain(pwmDerechoActual, ESC_MIN_US, ESC_MAX_US);
  pwmIzquierdoActual = constrain(pwmIzquierdoActual, ESC_MIN_US, ESC_MAX_US);
  
  escribirMotorVertical(ESC_DERECHO_PIN, pwmDerechoActual);
  escribirMotorVertical(ESC_IZQUIERDO_PIN, pwmIzquierdoActual);
}

// ============================================
// FUNCIONES DE CONTROL HORIZONTAL
// ============================================
void initMotoresHorizontales() {
  setMotorHorizontal(M3_PIN, 0);
  setMotorHorizontal(M4_PIN, 0);
  setMotorHorizontal(M5_PIN, 0);
  setMotorHorizontal(M6_PIN, 0);
}

void setMotorHorizontal(int pin, int velocidadPorcentaje) {
  velocidadPorcentaje = constrain(velocidadPorcentaje, -100, 100);
  
  int us;
  if (velocidadPorcentaje >= 0) {
    us = map(velocidadPorcentaje, 0, 100, ESC_NEUTRAL_US, ESC_MAX_US);
  } else {
    us = map(velocidadPorcentaje, -100, 0, ESC_MIN_US, ESC_NEUTRAL_US);
  }
  
  ledcAttach(pin, 50, 16);
  uint32_t duty = map(us, 0, 20000, 0, 65535);
  ledcWrite(pin, duty);
}

void controlMovimientoHorizontal(float avance, float giro, float lateral, int potenciaGeneral) {
  avance = constrain(avance, -1.0, 1.0);
  giro = constrain(giro, -1.0, 1.0);
  lateral = constrain(lateral, -1.0, 1.0);
  
  float factor = potenciaGeneral / 100.0;
  avance *= factor;
  giro *= factor;
  lateral *= factor;
  
  float m3 = avance - giro + lateral;
  float m4 = avance + giro - lateral;
  float m5 = -avance - giro - lateral;
  float m6 = -avance + giro + lateral;
  
  float max_val = max(max(abs(m3), abs(m4)), max(abs(m5), abs(m6)));
  if (max_val > 1.0) {
    m3 /= max_val;
    m4 /= max_val;
    m5 /= max_val;
    m6 /= max_val;
  }
  
  int m3_porc = constrain(m3 * 100, -100, 100);
  int m4_porc = constrain(m4 * 100, -100, 100);
  int m5_porc = constrain(m5 * 100, -100, 100);
  int m6_porc = constrain(m6 * 100, -100, 100);
  
  setMotorHorizontal(M3_PIN, m3_porc);
  setMotorHorizontal(M4_PIN, m4_porc);
  setMotorHorizontal(M5_PIN, m5_porc);
  setMotorHorizontal(M6_PIN, m6_porc);
}

void detenerMotoresHorizontales() {
  setMotorHorizontal(M3_PIN, 0);
  setMotorHorizontal(M4_PIN, 0);
  setMotorHorizontal(M5_PIN, 0);
  setMotorHorizontal(M6_PIN, 0);
}

// ============================================
// FUNCIONES DEL LUMEN
// ============================================
void initLumen() {
  ledcAttach(LUMEN_PWM_PIN, PWM_FREQ, PWM_RESOLUTION);
  lumenOFF();
}

void lumenON() {
  int duty = map(1900, 0, 20000, 0, 255);
  ledcWrite(LUMEN_PWM_PIN, duty);
  lumenEncendido = true;
}

void lumenOFF() {
  int duty = map(1100, 0, 20000, 0, 255);
  ledcWrite(LUMEN_PWM_PIN, duty);
  lumenEncendido = false;
}

// ============================================
// FUNCIONES DEL SENSOR DE PRESIÓN
// ============================================
void initPresion() {
  Wire.begin(I2C_SDA, I2C_SCL);
  sensorPresionOK = sensorPresion.init();
  
  if (sensorPresionOK) {
    sensorPresion.setFluidDensity(997);
    sensorPresion.read();
  }
}

void readPresion() {
  if (!sensorPresionOK) return;
  sensorPresion.read();
  presionMbar = sensorPresion.pressure();
  profundidadM = sensorPresion.depth();
  temperaturaC = sensorPresion.temperature();
}

// ============================================
// FUNCIÓN DEL SONAR
// ============================================
void initSonar() {
  PingSerial.begin(115200, SERIAL_8N1, SONAR_RX, SONAR_TX);
  if (!ping.initialize()) {
    Serial.println("[SONAR] ERROR");
  } else {
    ping.set_speed_of_sound(VELOCIDAD_SONIDO_AGUA, true);
    ping.set_range(100, 5000);
  }
}

void readSonar() {
  if (ping.update()) {
    ultimaDistancia = ping.distance() / 10.0;
    ultimaConfianza = ping.confidence();
  }
}

// ============================================
// FUNCIONES DEL MPU6050
// ============================================
void initMPU() {
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(PWR_MGMT_1);
  Wire.write(0);
  Wire.endTransmission();
}

void readMPU() {
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(ACCEL_XOUT_H);
  Wire.endTransmission();
  Wire.requestFrom(MPU6050_ADDR, 6);
  
  if (Wire.available() >= 6) {
    int16_t rawX = Wire.read() << 8 | Wire.read();
    int16_t rawY = Wire.read() << 8 | Wire.read();
    int16_t rawZ = Wire.read() << 8 | Wire.read();
    
    ultimoAX = rawX / 16384.0;
    ultimoAY = rawY / 16384.0;
    ultimoAZ = rawZ / 16384.0;
  }
}

// ============================================
// WIFI Y OTA
// ============================================
void initWiFiAndOTA() {
  WiFi.begin(ssid, password);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    attempts++;
  }
  
  ArduinoOTA.setHostname("ESP32-Submarino");
  ArduinoOTA.setPassword("1234");
  ArduinoOTA.begin();
}

// ============================================
// PROCESAMIENTO DE COMANDOS
// ============================================
void procesarComando(String jsonString) {
  jsonString.trim();
  if (jsonString.length() == 0) return;
  
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, jsonString);
  
  if (error) return;
  
  const char* tipo = doc["tipo"];
  
  if (strcmp(tipo, "luz") == 0) {
    int estado = doc["estado"] | 0;
    if (estado == 1) lumenON();
    else lumenOFF();
    String response = "{\"tipo\":\"luz_response\",\"estado\":" + String(lumenEncendido ? 1 : 0) + "}\n";
    Serial.print(response);
    
  } else if (strcmp(tipo, "movimiento") == 0) {
    float avance = doc["avance"] | 0.0;
    float giro = doc["giro"] | 0.0;
    float lateral = doc["lateral"] | 0.0;
    int potenciaGeneral = doc["potencia"] | 50;
    
    int pwmDerecho = doc["pwm_derecho"] | 1500;
    int pwmIzquierdo = doc["pwm_izquierdo"] | 1500;
    
    pwmDerechoActual = constrain(pwmDerecho, ESC_MIN_US, ESC_MAX_US);
    pwmIzquierdoActual = constrain(pwmIzquierdo, ESC_MIN_US, ESC_MAX_US);
    actualizarMotores();
    
    avance = constrain(avance, -1.0, 1.0);
    giro = constrain(giro, -1.0, 1.0);
    lateral = constrain(lateral, -1.0, 1.0);
    
    if (abs(avance) > 0.05 || abs(giro) > 0.05 || abs(lateral) > 0.05) {
      controlMovimientoHorizontal(avance, giro, lateral, potenciaGeneral);
    } else {
      detenerMotoresHorizontales();
    }
    
    // Respuesta rápida sin esperar
    String response = "{\"tipo\":\"movimiento_response\",\"estado\":\"ok\"}\n";
    Serial.print(response);
    
  } else if (strcmp(tipo, "stream") == 0) {
    int estado = doc["estado"] | 1;
    streamMode = (estado == 1);
    String response = "{\"tipo\":\"stream_response\",\"estado\":" + String(streamMode ? 1 : 0) + "}\n";
    Serial.print(response);
    
  } else if (strcmp(tipo, "consultar_sensores") == 0) {
    enviarDatosSensores();
  }
}

// ============================================
// ENVIAR DATOS DE SENSORES (STREAM)
// ============================================
void enviarDatosSensores() {
  StaticJsonDocument<512> doc;
  
  doc["tipo"] = "datos_sensores";
  
  doc["presion"]["mbar"] = presionMbar;
  doc["presion"]["profundidad_m"] = profundidadM;
  doc["presion"]["temperatura_c"] = temperaturaC;
  doc["presion"]["ok"] = sensorPresionOK;
  
  doc["sonar"]["distancia_cm"] = ultimaDistancia;
  doc["sonar"]["confianza"] = ultimaConfianza;
  
  doc["mpu"]["ax"] = ultimoAX;
  doc["mpu"]["ay"] = ultimoAY;
  doc["mpu"]["az"] = ultimoAZ;
  
  doc["luz"]["encendida"] = lumenEncendido;
  
  String output;
  serializeJson(doc, output);
  Serial.println(output);
}