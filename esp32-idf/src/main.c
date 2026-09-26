#include <string.h>
#include <math.h>
#include "time.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_rom_sys.h"     // esp_rom_delay_us
#include "esp_timer.h"       // esp_timer_get_time
#include "nvs_flash.h"
#include "driver/gpio.h"

//#include "dht.h"

#include "zenoh-pico.h"

// Wifi Vars
const char* WIFI_ID = "Hello There";
const char* WIFI_PASS = "FishTreeCatLamp";

// NTP Vars   
const char* NTP_SERVER = "pool.ntp.org";
const long GMT_OFFSET = -28800;
const int DLT_OFFSET = 3600;

// Pins
const int LED_PIN_G = 16;
const int LED_PIN_B = 17;
const int LED_PIN_R = 18;

const int PIN_DHT = 13;

const int INTVL_SENSORSCAN = 1000;
const int INTVL_CTRLSCAN = 2000;
const int INTVL_LOGGING = 15000;
const int INTVL_DISPLAYUPDATE = 200;

