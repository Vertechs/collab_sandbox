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


#include "wifi_setup.h"
#include "dht.h"
#include "thermostat.h"

#include "zenoh-pico.h"
#include "zenoh_setup.h"

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
static z_main_ctx_t zenoh_ctx;

// Logger
static const char *TAG = "MAIN";

void log_performance(void){
    ESP_LOGI(TAG, "Free heap size: %d", xPortGetFreeHeapSize());
    ESP_LOGI(TAG, "Execution time: %d", xTaskGetTickCount());
}


void app_main(void)
{
    // Init NVS for wifi driver, abort if re-init fails or other error
    // REMOVE, do this in wifi setup now
    // esp_err_t err_catch = nvs_flash_init();
    // if (err_catch == ESP_ERR_NVS_NO_FREE_PAGES || err_catch == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    //     ESP_ERROR_CHECK(nvs_flash_erase());
    //     ESP_ERROR_CHECK(nvs_flash_init());
    // }
    // ESP_ERROR_CHECK(err_catch);
    
    // fall back to local control if wifi init fails
    // TODO handle re-try timer
    esp_err_t err_catch = wifi_setup(WIFI_ID, WIFI_PASS);
    if (err_catch != ESP_OK) {
        ESP_LOGE(TAG, "WiFi setup failed");
    }

    // TODO, why is this delay here
    vTaskDelay(500 / portTICK_PERIOD_MS);

    if (wifi_get_ip() != NULL) {
        if(zenoh_setup(&zenoh_ctx, wifi_get_ip()) != ESP_OK) {
            ESP_LOGE(TAG, "Zenoh setup failed");
        }
    }

    

}