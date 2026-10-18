#include "wifi_setup.h"
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_check.h"
#include "nvs_flash.h"
#include "lwip/ip4_addr.h"
#include "esp_timer.h"

#define WIFI_RETRY_MIN_MS 1000
#define WIFI_RETRY_MAX_MS 30000
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

// logger 
static const char *TAG = "Wifi Setup";

// globals
static EventGroupHandle_t s_wifi_event_group;
static esp_timer_handle_t s_wifi_reconnect_timer;
static uint32_t s_backoff_time_ms = WIFI_RETRY_MIN_MS;
static int s_retry_num = 0;
static char s_ip_str[16] = {0};

static void wifi_reconnect_timer_handler(void *arg){
    esp_wifi_connect();
}

static void wifi_event_handler(void *arg, 
                                esp_event_base_t event_base, 
                                int32_t event_id, 
                                void *event_data){
    // run on station start                      
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    // run when connected
    }else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_CONNECTED){
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    // run when disconnected
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED){
        s_ip_str[0] = '\0'; //Null IP string
        if (s_retry_num == 0){
            // first retry, try immediately
            s_retry_num++;
            esp_wifi_connect();
        } else {
            // subsequent retries, increase delay between
            esp_timer_start_once(s_wifi_reconnect_timer, s_backoff_time_ms * 1000);
            s_backoff_time_ms = s_backoff_time_ms * 2 > WIFI_RETRY_MAX_MS ? WIFI_RETRY_MAX_MS : s_backoff_time_ms * 2;
            s_retry_num++;
        }
    // run when IP is obtained
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        snprintf(s_ip_str, sizeof(s_ip_str), IPSTR, IP2STR(&event->ip_info.ip));
        ESP_LOGI(TAG, "Connected! IP: %s", s_ip_str);
        s_retry_num = 0;
        s_backoff_time_ms = WIFI_RETRY_MIN_MS;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

esp_err_t wifi_setup(const char *ssid, const char *password){
    //TODO: Improve wifi error handling
    const esp_timer_create_args_t targs = {
        .callback = wifi_reconnect_timer_handler,
        .name = "wifi_reconnect",
    };
    
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_RETURN_ON_ERROR(err, TAG, "nvs init failed");

    s_wifi_event_group = xEventGroupCreate();

    ESP_RETURN_ON_ERROR(esp_netif_init(), TAG, "Failed to initialize network interface");

    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), TAG, "Failed to create default event loop");

    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&cfg), TAG, "Failed to initialize WiFi");

    esp_event_handler_instance_t instance_any_id;
    ESP_RETURN_ON_ERROR(esp_event_handler_instance_register(
        WIFI_EVENT,
        ESP_EVENT_ANY_ID,
        &wifi_event_handler,
        NULL,
        &instance_any_id
    ), TAG, "Failed to register WiFi event handler");

    esp_event_handler_instance_t instance_ip_event;
    ESP_RETURN_ON_ERROR(esp_event_handler_instance_register(
        IP_EVENT,
        IP_EVENT_STA_GOT_IP,
        &wifi_event_handler,
        NULL,
        &instance_ip_event
    ), TAG, "Failed to register IP event handler");

    wifi_config_t wifi_config = { 0 };
    strlcpy((char *)wifi_config.sta.ssid, ssid, sizeof(wifi_config.sta.ssid));
    strlcpy((char *)wifi_config.sta.password, password, sizeof(wifi_config.sta.password));
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "Failed to set WiFi mode");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &wifi_config), TAG, "Failed to set WiFi config");
    // Disable sleep - needed by Zenoh
    ESP_RETURN_ON_ERROR(esp_wifi_set_ps(WIFI_PS_NONE), TAG, "Failed to disable WiFi power save");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "Failed to start WiFi");

    ESP_LOGI(TAG, "Connecting to %s", ssid);

    EventBits_t bits = xEventGroupWaitBits(
        s_wifi_event_group, 
        WIFI_CONNECTED_BIT | WIFI_FAIL_BIT, 
        pdTRUE, pdFALSE, portMAX_DELAY);

    // REMOVE, keep registered in case of disconnect
    // esp_event_handler_instance_unregister(IP_EVENT, IP_EVENT_STA_GOT_IP, instance_ip_event);
    // esp_event_handler_instance_unregister(WIFI_EVENT, ESP_EVENT_ANY_ID, instance_any_id);
    // vEventGroupDelete(s_wifi_event_group);

    return (bits & WIFI_CONNECTED_BIT) ? ESP_OK : ESP_FAIL;
    
}

const char *wifi_get_ip(void){
    return (s_ip_str[0] != '\0') ? s_ip_str : NULL;
}