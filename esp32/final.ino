#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h> 
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ==========================================
// 1. CẤU HÌNH WIFI & SERVER (NICEGUI)
// ==========================================
const char* ssid = "hhhh";       // <--- SỬA TÊN WIFI
const char* password = "12345678";      // <--- SỬA PASS

// IP Máy tính chạy file Python NiceGUI
const char* serverIP = "10.236.105.251";       // <--- SỬA IP MÁY TÍNH
const int   serverPort = 8081;               // <--- CỔNG SERVER

// ==========================================
// 2. CẤU HÌNH CHÂN (HARDWARE)
// ==========================================
#define BUZZER_PIN 2

// --- PHÒNG 1 ---
#define P1_SDA   5
#define P1_SCK   18
#define P1_MOSI  19
#define P1_MISO  21
#define P1_RST   23
#define P1_SERVO 13
#define P1_FIRE  34

// --- PHÒNG 2 ---
#define P2_SDA   26
#define P2_SCK   25
#define P2_MOSI  33  
#define P2_MISO  32 
#define P2_RST   4   
#define P2_SERVO 12
#define P2_FIRE  35

#define I2C_SDA  27
#define I2C_SCL  14

// ==========================================
// 3. KHỞI TẠO ĐỐI TƯỢNG
// ==========================================

MFRC522 rfid1(P1_SDA, P1_RST);
MFRC522 rfid2(P2_SDA, P2_RST);

LiquidCrystal_I2C lcd1(0x27, 16, 2); 
LiquidCrystal_I2C lcd2(0x26, 16, 2); 

Servo servo1;
Servo servo2;

bool isFireP1 = false;
bool isFireP2 = false;
bool emergencySent = false;

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT); digitalWrite(BUZZER_PIN, LOW);

  // --- KẾT NỐI WIFI ---
  WiFi.begin(ssid, password);
  Serial.print("Dang ket noi WiFi");
  int tryCount = 0;
  while (WiFi.status() != WL_CONNECTED && tryCount < 20) {
    delay(500); Serial.print("."); tryCount++;
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " OK!" : " Failed!");

  // --- SETUP PHẦN CỨNG ---
  Wire.begin(I2C_SDA, I2C_SCL); 
  lcd1.init(); lcd1.backlight(); 
  lcd2.init(); lcd2.backlight(); 
  
  servo1.attach(P1_SERVO, 500, 2400);
  servo2.attach(P2_SERVO, 500, 2400);
  servo1.write(10); 
  servo2.write(10);

  pinMode(P1_FIRE, INPUT);
  pinMode(P2_FIRE, INPUT);

  pinMode(P1_SDA, OUTPUT); digitalWrite(P1_SDA, HIGH);
  pinMode(P2_SDA, OUTPUT); digitalWrite(P2_SDA, HIGH);
  pinMode(P1_RST, OUTPUT); digitalWrite(P1_RST, LOW);
  pinMode(P2_RST, OUTPUT); digitalWrite(P2_RST, LOW);
  delay(50);
  digitalWrite(P1_RST, HIGH);
  digitalWrite(P2_RST, HIGH);

  lcd1.setCursor(0,0); lcd1.print("P1: SAN SANG");
  lcd2.setCursor(0,0); lcd2.print("P2: SAN SANG");
  
  beepSuccess(); 
}

// ======================================================
// HÀM ĐIỀU KHIỂN CÒI
// ======================================================
void beepSuccess() {
  digitalWrite(BUZZER_PIN, HIGH); delay(300); digitalWrite(BUZZER_PIN, LOW);
}
void beepFail() {
  for(int i=0; i<3; i++) {
    digitalWrite(BUZZER_PIN, HIGH); delay(80); digitalWrite(BUZZER_PIN, LOW); delay(80);
  }
}

// ======================================================
// PARSE JSON STATUS
// ======================================================
int parseJsonStatus(String json) {
  int keyIndex = json.indexOf("status");
  if (keyIndex == -1) return -1;
  int colonIndex = json.indexOf(":", keyIndex);
  if (colonIndex == -1) return -1;
  for (int i = colonIndex + 1; i < json.length(); i++) {
    char c = json.charAt(i);
    if (c >= '0' && c <= '9') return c - '0';
  }
  return -1;
}

// ======================================================
// GỌI SERVER
// ======================================================
void checkAccess(String uid, String roomID, int roomNum) {
  if (WiFi.status() != WL_CONNECTED) { 
    beepFail(); 
    Serial.println("Offline!");
    return; 
  }

  WiFiClient client;
  HTTPClient http;

  String url = "http://" + String(serverIP) + ":" + String(serverPort) + "/check";
  
  if (http.begin(client, url)) {
    http.addHeader("Content-Type", "application/json");
    String jsonPayload = "{\"uid\": \"" + uid + "\", \"room\": \"" + roomID + "\"}";
    
    int httpCode = http.POST(jsonPayload);
    
    if (httpCode > 0) {
      String response = http.getString();
      Serial.println("Server: " + response);
      
      int status = parseJsonStatus(response);
      
      if (status == 1) {
        Serial.println(">> HOP LE -> MO CUA");
        beepSuccess();
        
        if (roomNum == 1) {
          lcd1.clear(); lcd1.print("P1: THANH CONG"); 
          servo1.write(100); delay(3000); servo1.write(10);
          lcd1.clear(); lcd1.print("P1: SAN SANG");
        } else {
          lcd2.clear(); lcd2.print("P2: THANH CONG");
          servo2.write(100); delay(3000); servo2.write(10);
          lcd2.clear(); lcd2.print("P2: SAN SANG");
        }
      } 
      else {
        Serial.println(">> TU CHOI");
        beepFail();
        if (roomNum == 1) {
          lcd1.clear(); lcd1.print("P1: KHONG HOP LE");
          delay(2000); lcd1.clear(); lcd1.print("P1: SAN SANG");
        } else {
          lcd2.clear(); lcd2.print("P2: KHONG HOP LE");
          delay(2000); lcd2.clear(); lcd2.print("P2: SAN SANG");
        }
      }
    } else {
      Serial.print("Loi HTTP: "); Serial.println(httpCode);
      beepFail(); 
    }
    http.end();
  }
}

void sendEmergency() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    String url = "http://" + String(serverIP) + ":" + String(serverPort) + "/emegency";
    http.begin(client, url);
    http.POST("{}"); 
    http.end();
  }
}

String getUID(MFRC522 &reader) {
  String content = "";
  for (byte i = 0; i < reader.uid.size; i++) {
    if(reader.uid.uidByte[i] < 0x10) content += "0";
    content += String(reader.uid.uidByte[i], HEX);
  }
  return content; 
}

// ==========================================
// HÀM KIỂM TRA CHÁY (ĐÃ SỬA ĐỔI)
// ==========================================
void checkFire() {
  bool fire1 = (digitalRead(P1_FIRE) == LOW); 
  bool fire2 = (digitalRead(P2_FIRE) == LOW);

  // LOGIC MỚI: Chỉ cần 1 phòng cháy là mở TẤT CẢ cửa ngay lập tức
  if (fire1 || fire2) {
    
    // Mở cả 2 cửa
    servo1.write(100);
    servo2.write(100);
    
    digitalWrite(BUZZER_PIN, HIGH); // Hú còi liên tục
    
    // Gửi cảnh báo server (chỉ gửi 1 lần)
    if (!emergencySent) { sendEmergency(); emergencySent = true; }
  }

  // Cập nhật hiển thị LCD (để biết cháy ở đâu)
  if (fire1) {
    if (!isFireP1) {
      isFireP1 = true;
      lcd1.clear(); lcd1.print("! P1 CHAY !");
      
      // Báo luôn màn hình 2 để sơ tán
      if (!isFireP2) { lcd2.clear(); lcd2.print("! CANH BAO !"); }
    }
  }

  if (fire2) {
    if (!isFireP2) {
      isFireP2 = true;
      lcd2.clear(); lcd2.print("! P2 CHAY !");
      
      // Báo luôn màn hình 1 để sơ tán
      if (!isFireP1) { lcd1.clear(); lcd1.print("! CANH BAO !"); }
    }
  }
}

void loop() {
  checkFire();
  
  // Nếu có cháy ở bất kỳ đâu -> Treo hệ thống (chỉ hú còi và giữ cửa mở)
  if (isFireP1 || isFireP2) { 
    digitalWrite(BUZZER_PIN, HIGH); 
    delay(100); 
    return; // Không đọc thẻ từ nữa
  }

  // --- XỬ LÝ PHÒNG 1 ---
  SPI.end(); 
  SPI.begin(P1_SCK, P1_MISO, P1_MOSI, P1_SDA); 
  rfid1.PCD_Init();
  
  if (rfid1.PICC_IsNewCardPresent() && rfid1.PICC_ReadCardSerial()) {
    String uid = getUID(rfid1);
    Serial.println("P1: " + uid);
    lcd1.clear(); lcd1.print("Dang Xu Ly...");
    checkAccess(uid, "p1", 1);
    rfid1.PICC_HaltA(); rfid1.PCD_StopCrypto1();
  }

  // --- XỬ LÝ PHÒNG 2 ---
  SPI.end(); 
  SPI.begin(P2_SCK, P2_MISO, P2_MOSI, P2_SDA); 
  rfid2.PCD_Init();

  if (rfid2.PICC_IsNewCardPresent() && rfid2.PICC_ReadCardSerial()) {
    String uid = getUID(rfid2);
    Serial.println("P2: " + uid);
    lcd2.clear(); lcd2.print("Dang Xu Ly...");
    checkAccess(uid, "p2", 2);
    rfid2.PICC_HaltA(); rfid2.PCD_StopCrypto1();
  }
  
  delay(50);
}