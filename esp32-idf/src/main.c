#include "sdkconfig.h"

#include <string.h>
#include <math.h>
#include "time.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "driver/gpio.h"

#include "dht.h"
#include "thermostat.h"

#include "zenoh-pico.h"

// Wifi Vars
static const char* WIFI_ID = CONFIG_WIFI_SSID;
static const char* WIFI_PASS = CONFIG_WIFI_PASSWORD;

// NTP Vars   
static const char* NTP_SERVER = "pool.ntp.org";
static const int32_t GMT_OFFSET = -28800;
static const int32_t DLT_OFFSET = 3600;

// Pins
static const gpio_num_t PIN_LED_G = 16;
static const gpio_num_t PIN_LED_B = 17;
static const gpio_num_t PIN_LED_R = 18;
static const gpio_num_t PIN_DHT = 13;

// Cyclic task intervals (in milliseconds)
static const uint32_t INTVL_SENSORSCAN = 1000;
static const uint32_t INTVL_CTRLSCAN = 2000;
static const uint32_t INTVL_LOGGING = 15000;
static const uint32_t INTVL_DISPLAYUPDATE = 200;

// Global structs
static therm_ctrl_intlkd_t therm_ctrl;
static therm_sensor_t therm_dht;
static therm_sensor_t therm_tmp;

void app_main(void)
{
    while(1);
}