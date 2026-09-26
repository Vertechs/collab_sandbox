//SPAGETTI
// + Zenoh publisher test (temp/humidity) — see "ZENOH" sections below

#include <WiFi.h>
#include <WiFiUdp.h>
#include <DHT.h>
#include <Adafruit_TMP117.h>
#include <Adafruit_SH110X.h>
#include "time.h"
#include "math.h"
#include "thermostat.h"
#include "led_pulse.h"
#include <zenoh-pico.h>

// Wifi Vars
const char* ssid = "Hello There";
const char* password = "FishTreeCatLamp";
const char* computerIP = "10.0.0.11";  //logging computer IP
const int udpPort = 4211;

// TCP listener
WiFiServer tcpServer(4212);
WiFiClient tcpClient;

// Remote control TCP listener - hands full mode control to a PC
WiFiServer remoteServer(4213);
WiFiClient remoteClient;

// NPT Server
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = -28800;
const int   daylightOffset_sec = 3600;

// Pin Setup
const int LED_Pins[] = {16,17,18};
const int Relay_Pins[] = {25,26,27};
const int RelayN = 3;

#define DHT22_PIN 13
#define ENC_A_PIN 32
#define ENC_B_PIN 33
#define ENC_BTN_PIN 34

// Scan times
#define SENSOR_INTERVAL 1000
#define SCAN_INTERVAL 100
#define STARTUP_DELAY 15000
#define LOG_INTERVAL 5000
#define DISPLAY_INTERVAL 100
#define EDIT_TIME 20000

#define REMOTE_TIMEOUT_MS 15*60*1000

#define LED_PWM_FREQ 5000
#define LED_PWM_RES  8      // 8-bit duty cycle, 0-255
#define LED_UPDATE_INTERVAL 20
#define LED_COMMON_ANODE

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SH1106_ADDR 0x3C

// ==== ZENOH: config. "peer" mode — no router, no connect locator. Discovery
// and (for this test) data transport both ride the default multicast group
// below; any other peer on the same LAN segment scouting that group can see
// this node with zero configuration on either side.
#define ZENOH_MODE "peer"
#define ZENOH_MULTICAST_LOCATOR "udp/224.0.0.225:7447"
#define ZENOH_KEYEXPR_TEMP "thermostat/esp32/temp_f"
#define ZENOH_KEYEXPR_HUM  "thermostat/esp32/humidity"

typedef enum{
  PAGE_TEMP,
  PAGE_MODE,
  PAGE_TIMERS
}page_select;

// library objects
DHT dht22(DHT22_PIN, DHT22);
WiFiUDP udp;

Adafruit_TMP117 tmp_1;

Adafruit_SH1106G screen(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

therm_ctrl_intlkd_t controller;

page_select activePage = PAGE_TEMP;

//globals
float dht22_temp_f = NAN;
float tmp117_temp_f = NAN;
bool  tmp117_ok = false;
bool dht22_ok = false;
bool tmp_1_exists = true;

volatile uint8_t lastEncoderState = 0;
volatile int encoderCount = 0;
bool lastButtonState = 0;
bool buttonPressed = 0;

int64_t buttonPresTime = 0;
int lastEncoderCount = 0;
bool buttonEditing = 0;

int64_t lastSensorRead = 0;
int64_t lastScan = 0;
int64_t lastLog = 0;
int64_t lastLEDUpdate = 0;
int64_t lastScreenUpdate = 0;
float local_humidity = 0;
float local_temp = 0;
esp_err_t last_err = ESP_OK;

// Remote control state
bool remoteControlActive = false;
int64_t lastRemoteCmdTime = 0;
mode_HVAC preRemoteModeCmd = THERM_OFF;  // stashed mode_cmd from before remote took over, restored on watchdog trip

// ==== ZENOH: session + publisher globals. zenoh_ok gates the publish calls
// so a failed/absent session doesn't jam up the rest of loop().
z_owned_session_t z_s;
z_owned_publisher_t z_pub_temp;
z_owned_publisher_t z_pub_hum;
bool zenoh_ok = false;


// logging functions
const char* mode_to_str(mode_HVAC m) {
  switch (m) {
    case THERM_OFF:  return "IDLE";
    case THERM_CIRC: return "CIRC";
    case THERM_COOL: return "COOL";
    case THERM_HEAT: return "HEAT";
    default:         return "UNKN";
  }
}

// Builds the CSV status line into buf. Pulled out of log_status() so the
// remote "query status" command can grab the exact same string without
// duplicating the format.
void build_status_string(char *buf, size_t buf_len, therm_ctrl_intlkd_t *therm, float dht22_temp, float tmp117_temp, float local_temp, float local_humidity, esp_err_t last_err) {
  //dht22_temp,tmp117_temp,local_temp,local_humidity,mode,fan_state,sys_state,mode_out_state,cool_sp,cool_db,heat_sp,heat_db,cool_on_acc,cool_off_acc,heat_on_acc,heat_off_acc,fan_pre_acc,fan_post_acc,last_err
  snprintf(buf, buf_len,
    "%.1f,%.1f,%.1f,%.1f,%s,%d,%d,%d,%.1f,%.1f,%.1f,%.1f,%lld,%lld,%lld,%lld,%lld,%lld,%d",
    dht22_temp,
    tmp117_temp,
    local_temp,
    local_humidity,
    mode_to_str(therm->mode),
    therm->fan_out.state,
    therm->system_out.state,
    therm->mode_out.state,
    therm->cool_setpoint,
    therm->cool_deadband,
    therm->heat_setpoint,
    therm->heat_deadband,
    (long long)therm->cool_on_delay.accum,
    (long long)therm->cool_off_delay.accum,
    (long long)therm->heat_on_delay.accum,
    (long long)therm->heat_off_delay.accum,
    (long long)therm->fan_pre_run_delay.accum,
    (long long)therm->fan_post_run_delay.accum,
    (int) last_err
  );
}

void log_status(therm_ctrl_intlkd_t *therm, float dht22_temp, float tmp117_temp, float local_temp, float local_humidity, esp_err_t last_err) {
  char buf[300];  // bumped from 256 to fit two extra float fields

  build_status_string(buf, sizeof(buf), therm, dht22_temp, tmp117_temp, local_temp, local_humidity, last_err);

  Serial.println(buf);

  udp.beginPacket(computerIP, udpPort);
  udp.write((const uint8_t*)buf, strlen(buf));
  udp.endPacket();
}

// ==== ZENOH: open a session and declare the two publishers. Called once
// from setup(), after WiFi is up. Non-fatal on failure — sets zenoh_ok =
// false and the rest of the sketch runs exactly as before, just without
// the zenoh publishes.
void zenoh_setup() {
  // Modem-sleep power saving delays/coalesces incoming frames to save power,
  // which is exactly what you don't want when measuring multicast latency —
  // and some ESP-IDF WiFi builds drop multicast entirely while asleep.
  // Must be set after WiFi.begin() has associated; belt-and-suspenders here
  // since setup() already waited for WL_CONNECTED before calling this.
  WiFi.setSleep(false);

  z_owned_config_t z_config;
  z_config_default(&z_config);
  zp_config_insert(z_config_loan_mut(&z_config), Z_CONFIG_MODE_KEY, ZENOH_MODE);
  // No Z_CONFIG_CONNECT_KEY in peer mode — that key is for dialing a specific
  // unicast endpoint (a router). Instead we tell it which multicast group to
  // scout AND publish/subscribe over; every peer on the segment using the
  // same group finds every other peer with no central point at all.
  zp_config_insert(z_config_loan_mut(&z_config), Z_CONFIG_MULTICAST_LOCATOR_KEY, ZENOH_MULTICAST_LOCATOR);

  Serial.printf("ZENOH: opening peer session on %s...\n", ZENOH_MULTICAST_LOCATOR);
  if (z_open(&z_s, z_config_move(&z_config), NULL) < 0) {
    Serial.println("ZENOH: z_open failed, continuing without zenoh");
    zenoh_ok = false;
    return;
  }

  zp_start_read_task(z_loan_mut(z_s), NULL);
  zp_start_lease_task(z_loan_mut(z_s), NULL);

  z_view_keyexpr_t ke_temp;
  z_view_keyexpr_from_str(&ke_temp, ZENOH_KEYEXPR_TEMP);
  if (z_declare_publisher(z_loan(z_s), &z_pub_temp, z_loan(ke_temp), NULL) < 0) {
    Serial.println("ZENOH: failed to declare temp publisher");
    zenoh_ok = false;
    return;
  }

  z_view_keyexpr_t ke_hum;
  z_view_keyexpr_from_str(&ke_hum, ZENOH_KEYEXPR_HUM);
  if (z_declare_publisher(z_loan(z_s), &z_pub_hum, z_loan(ke_hum), NULL) < 0) {
    Serial.println("ZENOH: failed to declare humidity publisher");
    zenoh_ok = false;
    return;
  }

  Serial.println("ZENOH: session up, publishers declared");
  zenoh_ok = true;
}

// ==== ZENOH: publish the current fused temp/humidity as plain ASCII
// float strings. Cheap first cut — switch to a binary/CBOR encoding later
// if you want to carry units, timestamps, or multiple fields in one put.
void zenoh_publish_readings(float temp_f, float humidity) {
  if (!zenoh_ok) return;

  char buf[16];
  z_owned_bytes_t payload;

  snprintf(buf, sizeof(buf), "%.2f", temp_f);
  z_bytes_copy_from_str(&payload, buf);
  z_publisher_put(z_loan(z_pub_temp), z_move(payload), NULL);

  snprintf(buf, sizeof(buf), "%.2f", humidity);
  z_bytes_copy_from_str(&payload, buf);
  z_publisher_put(z_loan(z_pub_hum), z_move(payload), NULL);
}

// LED functions
void update_led(uint8_t r, uint8_t g, uint8_t b, float pulse_hz) {
    float brightness;

    if (pulse_hz <= 0) {
        brightness = 1.0f;  // solid on, no pulsing
    } else {
        uint32_t period_ms = (uint32_t)(1000.0f / pulse_hz);
        if (period_ms == 0) period_ms = 1;  // guard against absurdly high frequencies

        uint32_t phase_ms = millis() % period_ms;   // bounded integer math, rollover-safe
        float phase = (float)phase_ms / (float)period_ms;  // 0.0 - 1.0

        brightness = (sinf(2 * PI * phase) + 1.0f) / 2.0f;  // 0.0 - 1.0
    }

    uint8_t out_r = (uint8_t)(r * brightness);
    uint8_t out_g = (uint8_t)(g * brightness);
    uint8_t out_b = (uint8_t)(b * brightness);

#ifdef LED_COMMON_ANODE
    out_r = 255 - out_r;
    out_g = 255 - out_g;
    out_b = 255 - out_b;
#endif

    ledcWrite(LED_Pins[0], out_r);
    ledcWrite(LED_Pins[1], out_g);
    ledcWrite(LED_Pins[2], out_b);
}

rgb_pulse_t get_color_ctrl(therm_ctrl_intlkd_t *therm){
  rgb_pulse_t c;
  switch (therm->mode){
    case THERM_OFF:
      c.r = 50; c.g = 255; c.b = 80; c.freq = 1.0/2.5;
      break;
    case THERM_CIRC:
      c.r = 255; c.g = 255; c.b = 255; c.freq = 1.0;
      break;
    case THERM_COOL:
      c.r = 0; c.g = 50; c.b = 255; c.freq = 1.0;
      break;
    case THERM_HEAT:
      c.r = 255; c.g = 60; c.b = 0; c.freq = 1.0;
      break;

    default:
      c.r = 255; c.g = 0; c.b = 0; c.freq = 2.5;
  }
  return c;
}

// TCP Listener
void process_tcp_commands(therm_ctrl_intlkd_t *therm) {
  if (!tcpClient || !tcpClient.connected()) {
    tcpClient = tcpServer.available();
  }

  if (!tcpClient || !tcpClient.available()) {
    return;
  }

  String line = tcpClient.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  // Expect commands strucuted like "cool_sp=75.0"
  int eqIdx = line.indexOf('=');
  if (eqIdx == -1) {
    tcpClient.println("Unable to parse command, expect <setpoint>=<value>");
    return;
  }

  String key = line.substring(0, eqIdx);
  float value = line.substring(eqIdx + 1).toFloat();

  if      (key == "cool_sp") therm->cool_setpoint = value;
  else if (key == "cool_db") therm->cool_deadband = value;
  else if (key == "heat_sp") therm->heat_setpoint = value;
  else if (key == "heat_db") therm->heat_deadband = value;
  else if (key == "cool_on_dly") therm->cool_on_delay.preset = value*1000;
  else if (key == "cool_off_dly") therm->cool_off_delay.preset = value*1000;
  else if (key == "fan_pre_dly") therm->fan_pre_run_delay.preset = value*1000;
  else if (key == "fan_post_dly") therm->fan_post_run_delay.preset = value*1000;
  else {
    tcpClient.println("ERR unknown key: " + key);
    return;
  }

  tcpClient.println("OK " + key + "=" + String(value, 1));
  Serial.println("TCP Coomand: Set " + key + " = " + String(value, 1));
}

// Remote control TCP listener. Recognized lines (case-insensitive):
//   command mode {IDLE|CIRC|HEAT|COOL}  - take control, set mode_cmd
//   command relinquish                  - hand control back to local now
//   query status                        - reply with the same CSV log_status() emits
// Taking control sets ctrl_loc = REMOTE_CTRL and drives mode_cmd directly;
// the watchdog in loop() is what hands ctrl_loc back to LOCAL_CTRL if the
// PC disappears, and "command relinquish" does the same thing on request.
void process_remote_commands(therm_ctrl_intlkd_t *therm, int64_t now) {
  if (!remoteClient || !remoteClient.connected()) {
    remoteClient = remoteServer.available();
  }

  if (!remoteClient || !remoteClient.available()) {
    return;
  }

  String line = remoteClient.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  String lineUpper = line;
  lineUpper.toUpperCase();

  if (lineUpper == "QUERY STATUS") {
    char buf[300];
    build_status_string(buf, sizeof(buf), therm, dht22_temp_f, tmp117_temp_f, local_temp, local_humidity, last_err);
    remoteClient.println(buf);
    return;
  }

  if (lineUpper == "COMMAND RELINQUISH") {
    if (remoteControlActive) {
      remoteControlActive = false;
      therm->ctrl_loc = LOCAL_CTRL;
      therm->mode_cmd = preRemoteModeCmd;
      remoteClient.println("confirm relinquish");
      Serial.println("REMOTE: relinquished, falling back to local control (" + String(mode_to_str(preRemoteModeCmd)) + ")");
    } else {
      remoteClient.println("confirm reinquish, already local");
    }
    return;
  }

  if (lineUpper.startsWith("COMMAND MODE ")) {
    String modeStr = lineUpper.substring(strlen("COMMAND MODE "));
    modeStr.trim();

    mode_HVAC newMode;
    if      (modeStr == "IDLE") newMode = THERM_OFF;
    else if (modeStr == "CIRC") newMode = THERM_CIRC;
    else if (modeStr == "HEAT") newMode = THERM_HEAT;
    else if (modeStr == "COOL") newMode = THERM_COOL;
    else {
      remoteClient.println("error, unknown mode: " + modeStr + " (expect IDLE/CIRC/HEAT/COOL)");
      return;
    }

    if (!remoteControlActive) {
      preRemoteModeCmd = therm->mode_cmd;  // stash whatever local control had commanded, so we can fail back to it
      therm->ctrl_loc = REMOTE_CTRL;
      remoteControlActive = true;
      Serial.println("REMOTE: PC has taken control");
    }

    therm->mode_cmd = newMode;
    lastRemoteCmdTime = now;

    remoteClient.println("confirm " + modeStr);
    Serial.println("REMOTE: mode_cmd -> " + modeStr);
    return;
  }

  remoteClient.println("error, unrecognized command: " + line);
}

// Watchdog - if remote is active and hasn't heard a valid command in
// REMOTE_TIMEOUT_MS, hand ctrl_loc back to LOCAL_CTRL and restore whatever
// mode_cmd was in effect before the PC took over.
void check_remote_watchdog(therm_ctrl_intlkd_t *therm, int64_t now) {
  if (!remoteControlActive) return;

  if (now - lastRemoteCmdTime >= REMOTE_TIMEOUT_MS) {
    remoteControlActive = false;
    therm->ctrl_loc = LOCAL_CTRL;
    therm->mode_cmd = preRemoteModeCmd;
    Serial.println("REMOTE: timeout, falling back to local control (" + String(mode_to_str(preRemoteModeCmd)) + ")");
  }
}

void IRAM_ATTR checkEncoder(){
  uint8_t state = (digitalRead(ENC_A_PIN) << 1) | digitalRead(ENC_B_PIN);

  if (state != lastEncoderState){
    uint8_t state_code = (lastEncoderState << 2) | state;

    if (state_code == 0b1011 || state_code == 0b1001) {
      encoderCount--;
    }
    else if (state_code == 0b0001 || state_code == 0b0011) {
      encoderCount++;
    }

    lastEncoderState = state;
  }
}

bool checkEncButton(){
  bool state = digitalRead(ENC_BTN_PIN);
  if (state == LOW && lastButtonState == HIGH){ //Inverted
    buttonPressed = 1;
    Serial.println("button");
    lastButtonState = state;
    return 1;
  }
  lastButtonState = state;
  return 0;
}

void updateDisplay(){
  screen.clearDisplay();

  screen.setCursor(0,2);
  screen.setTextSize(2);
  screen.printf("T:%.1fF", local_temp);

  screen.setTextSize(1);
  screen.setCursor(0, 20);
  screen.printf("Hum: %.1fF", local_humidity);

  // screen.drawFastVLine(70, 0, 64, SH110X_WHITE);

  if (controller.ctrl_loc == LOCAL_CTRL){
    screen.setTextSize(1);
    screen.setCursor(0, 35);
    screen.printf("SP: %.1fF", controller.cool_setpoint);
    screen.setCursor(0, 45);
    screen.print("Mode: ");
    screen.print(mode_to_str(controller.mode));
  }else if (controller.ctrl_loc == REMOTE_CTRL){
    screen.setTextSize(1);
    screen.setCursor(0, 35);
    screen.print("REMOTE CONTROL");
    screen.setCursor(0, 45);
    screen.print("Mode: ");
    screen.print(mode_to_str(controller.mode));
  }else{
       screen.setTextSize(1);
    screen.setCursor(0, 35);
    screen.print("MANUAL CONTROL");
    screen.setCursor(0, 45);
    screen.print("Mode: ");
    screen.print(mode_to_str(controller.mode));
  }

  if (buttonEditing){
    screen.setTextSize(1);
    screen.setCursor(70, 50);
    screen.print("EDITING");
  }

  screen.setCursor(0, 45);

  screen.display();
  
}

//======
//Main functions
//======
void setup() {
  Serial.begin(115200);
  Wire.begin();

  //Screen Init
  if (!screen.begin(SH1106_ADDR, true)) {
    Serial.println("SH1106 not found!");
    while (1) delay(10);
  }

  screen.clearDisplay();
  screen.setTextColor(SH110X_WHITE);
  screen.setTextSize(1);
  screen.setCursor(0, 0);
  screen.print("Connecting");
  screen.display();

  Serial.print("Wifi init");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    screen.print(".");
  }
  Serial.println("\nConnected, IP: " + WiFi.localIP().toString());
  screen.clearDisplay();
  screen.println("\nConnected, IP: " + WiFi.localIP().toString());

  tcpServer.begin();
  tcpServer.setNoDelay(true); 

  remoteServer.begin();
  remoteServer.setNoDelay(true);

  dht22.begin();
  if (!tmp_1.begin()) {
    Serial.println(F("Failed to find TMP117 chip"));
    screen.println(F("Failed to find TMP117 chip"));
    delay(2000);
    tmp_1_exists = false;
  }else{
    Serial.println(F("Found TMP117"));
    Serial.println(F("Found TMP117"));
  }

  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

  therm_setup(&controller, false, false, false, Relay_Pins[0], Relay_Pins[1],Relay_Pins[2]);

  for (int i = 0; i < 3; i++) {
    ledcAttach(LED_Pins[i], LED_PWM_FREQ, LED_PWM_RES);
  }

  for(int i=0; i<RelayN; i++){
    pinMode(Relay_Pins[i],OUTPUT);
  } 

  pinMode(ENC_BTN_PIN, INPUT);
  pinMode(ENC_A_PIN, INPUT_PULLUP);
  pinMode(ENC_B_PIN, INPUT_PULLUP);

  lastEncoderState = (digitalRead(ENC_A_PIN) << 1) | digitalRead(ENC_B_PIN);

  attachInterrupt(digitalPinToInterrupt(ENC_A_PIN), checkEncoder, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_B_PIN), checkEncoder, CHANGE);

  // ==== ZENOH: WiFi is up by this point, so open the session here.
  zenoh_setup();

}

void loop() {

  int64_t now = get_epoch_ms();
  
  process_tcp_commands(&controller);
  process_remote_commands(&controller, now);
  check_remote_watchdog(&controller, now);
  checkEncButton();

  if(buttonPressed){ // treating as flags in case need interupt later
    buttonPresTime = now;
    buttonPressed = 0;
  }

  if( (now - buttonPresTime <= EDIT_TIME) && (controller.ctrl_loc == LOCAL_CTRL) ){
    float val = (encoderCount-lastEncoderCount) * 0.05; 
    if (activePage == PAGE_TEMP){
      controller.cool_setpoint += val;
    }else if (activePage == PAGE_MODE){
      int i = 0;
    }
    buttonEditing = 1;
  }else{
    buttonEditing = 0;
  }

  lastEncoderCount = encoderCount;

  if (now - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = now;
    local_humidity = dht22.readHumidity();
    dht22_temp_f = (dht22.readTemperature() * 1.8) + 32;

    if (tmp_1_exists){
      if (tmp_1.dataReady()) {
        sensors_event_t tmp117_event;
        tmp_1.getEvent(&tmp117_event);
        tmp117_temp_f = (tmp117_event.temperature * 1.8) + 32;
        if (tmp117_event.temperature == 0.0f){
          tmp117_ok = 0; // bandaid, better error handling, also doesnt work
        }else{
          tmp117_ok = 1; 
        }
      }
    } 

    
    dht22_ok = !isnan(dht22_temp_f);
    if (dht22_ok && tmp117_ok) {
      local_temp = (dht22_temp_f + tmp117_temp_f) / 2.0f;
    } else if (tmp117_ok) {
      local_temp = tmp117_temp_f;  
    } else if (dht22_ok) {
      local_temp = dht22_temp_f;
    } else {
      local_temp = NAN;
    }

    // ==== ZENOH: publish the same fused values that just got computed,
    // once per SENSOR_INTERVAL — no point publishing faster than the
    // readings actually change.
    zenoh_publish_readings(local_temp, local_humidity);
  }


  if ((now>STARTUP_DELAY) && (now - lastScan >= SCAN_INTERVAL)){
    lastScan = now;
    last_err = therm_execute(&controller, local_temp);
  }
 
  if (now - lastLog >= LOG_INTERVAL) {
    lastLog = now;
    log_status(&controller, dht22_temp_f, tmp117_temp_f, local_temp, local_humidity, last_err);
  }

  if (now - lastLEDUpdate >= LED_UPDATE_INTERVAL) {
    lastLEDUpdate = now;
    rgb_pulse_t c = get_color_ctrl(&controller);
    update_led(c.r, c.g, c.b, c.freq);
  }

  updateDisplay();

}
