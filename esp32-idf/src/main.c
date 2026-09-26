// Vibe-coded test: read DHT22 on pin 13 (bit-banged, no Arduino libs),
// publish over Zenoh in peer mode. Pure ESP-IDF.
//
// TBD before running:
//   - WIFI_SSID / WIFI_PASS
//   - ZENOH_KEY

#include <string.h>
#include <math.h>

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

#include "zenoh-pico.h"

static const char *TAG = "dht_zenoh_test";

#define DHT_GPIO        GPIO_NUM_13

#define WIFI_SSID       "Hello There"   // TBD
#define WIFI_PASS       "FishTreeCatLamp"   // TBD

#define ZENOH_MODE      "peer"
#define ZENOH_LOCATOR   "tcp/10.0.0.33:7447"
#define ZENOH_KEY       "esp_test/temp1"   // TBD

static EventGroupHandle_t s_wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0

static z_owned_session_t s_session;
static z_owned_publisher_t s_pub;

// ---------------------------------------------------------------------
// DHT22 bit-banged driver
// ---------------------------------------------------------------------
 
// Waits until the pin reads `level`, up to `timeout_us`.
// Returns elapsed microseconds, or -1 on timeout.
static int wait_for_level(gpio_num_t pin, int level, int timeout_us) {
    int64_t start = esp_timer_get_time();
    while (gpio_get_level(pin) != level) {
        if ((esp_timer_get_time() - start) > timeout_us) {
            return -1;
        }
    }
    return (int)(esp_timer_get_time() - start);
}
 
// Reads temperature (C) and humidity (%) from a DHT22 on `pin`.
// Returns 0 on success, negative on failure.
static int dht22_read(gpio_num_t pin, float *temp_c, float *humidity) {
    uint8_t data[5] = {0};
 
    // Send start signal: pull low ~1.5ms, then release and let the
    // external pull-up bring the line high.
    gpio_set_direction(pin, GPIO_MODE_OUTPUT);
    gpio_set_level(pin, 0);
    esp_rom_delay_us(1500);
    gpio_set_level(pin, 1);
    esp_rom_delay_us(30);
    gpio_set_direction(pin, GPIO_MODE_INPUT);
 
    // Sensor response: low ~80us, then high ~80us.
    if (wait_for_level(pin, 0, 100) < 0) return -1;
    if (wait_for_level(pin, 1, 100) < 0) return -2;
    if (wait_for_level(pin, 0, 100) < 0) return -3;
 
    // 40 data bits. Each bit starts with a ~50us low, followed by a
    // high whose length encodes 0 (~26-28us) or 1 (~70us).
    for (int i = 0; i < 40; i++) {
        if (wait_for_level(pin, 1, 100) < 0) return -4;
        int high_us = wait_for_level(pin, 0, 100);
        if (high_us < 0) return -5;
 
        uint8_t bit = (high_us > 40) ? 1 : 0;
        data[i / 8] <<= 1;
        data[i / 8] |= bit;
    }
 
    uint8_t checksum = (uint8_t)(data[0] + data[1] + data[2] + data[3]);
    if (checksum != data[4]) {
        ESP_LOGW(TAG, "DHT22 checksum mismatch");
        return -6;
    }
 
    int16_t raw_humidity = (int16_t)((data[0] << 8) | data[1]);
    int16_t raw_temp = (int16_t)(((data[2] & 0x7F) << 8) | data[3]);
 
    *humidity = raw_humidity / 10.0f;
    *temp_c = raw_temp / 10.0f;
    if (data[2] & 0x80) {
        *temp_c = -(*temp_c);
    }
 
    return 0;
}
 
// ---------------------------------------------------------------------
// Wi-Fi (station mode, needed for Zenoh's UDP transport)
// ---------------------------------------------------------------------
 
static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                                int32_t event_id, void *event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "Wi-Fi disconnected, retrying");
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}
 
static void wifi_init_sta(void) {
    s_wifi_event_group = xEventGroupCreate();
 
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
 
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
 
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL));
 
    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
        },
    };
 
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
 
    ESP_LOGI(TAG, "Waiting for Wi-Fi connection...");
    xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT, pdFALSE, pdTRUE, portMAX_DELAY);
    ESP_LOGI(TAG, "Wi-Fi connected");
}
 
// ---------------------------------------------------------------------
// Zenoh
// ---------------------------------------------------------------------
 
static void zenoh_publish(float temp_c, float humidity) {
    char payload[64];
    int len = snprintf(payload, sizeof(payload),
                        "{\"temp_c\":%.2f,\"humidity\":%.2f}",
                        temp_c, humidity);
 
    z_owned_bytes_t z_payload;
    z_bytes_copy_from_buf(&z_payload, (const uint8_t *)payload, (size_t)len);
 
    z_publisher_put_options_t options;
    z_publisher_put_options_default(&options);
    if (z_publisher_put(z_loan(s_pub), z_move(z_payload), &options) < 0) {
        ESP_LOGW(TAG, "Zenoh publish failed");
    }
}
 
static void zenoh_init(void) {
    z_owned_config_t config;
    z_config_default(&config);
    zp_config_insert(z_loan_mut(config), Z_CONFIG_MODE_KEY, ZENOH_MODE);
    if (strlen(ZENOH_LOCATOR) > 0) {
        zp_config_insert(z_loan_mut(config), Z_CONFIG_CONNECT_KEY, ZENOH_LOCATOR);
    }
 
    int8_t open_err = z_open(&s_session, z_move(config), NULL);
    if (open_err < 0) {
        // Print the actual code instead of just "failed" — with
        // ZENOH_LOCATOR blank, peer mode relies on UDP multicast
        // scouting, which needs both zenoh-pico built with multicast
        // scouting support and lwIP's IGMP/multicast enabled in
        // sdkconfig. If those aren't set up, this is where it'll fail.
        ESP_LOGE(TAG, "Zenoh session open failed (err=%d)", open_err);
        abort();
    }
 
    if (zp_start_read_task(z_loan_mut(s_session), NULL) < 0 ||
        zp_start_lease_task(z_loan_mut(s_session), NULL) < 0) {
        ESP_LOGE(TAG, "Zenoh background tasks failed to start");
        abort();
    }
 
    z_view_keyexpr_t ke;
    z_view_keyexpr_from_str(&ke, ZENOH_KEY);
 
    if (z_declare_publisher(z_loan(s_session), &s_pub, z_loan(ke), NULL) < 0) {
        ESP_LOGE(TAG, "Zenoh publisher declare failed");
        abort();
    }
 
    ESP_LOGI(TAG, "Zenoh ready in peer mode");
}
 
// ---------------------------------------------------------------------
// app_main
// ---------------------------------------------------------------------
 
// Wi-Fi init + Zenoh session/socket setup together need more stack than
// the default "main" task gets (CONFIG_ESP_MAIN_TASK_STACK_SIZE is only
// ~3.5-4KB out of the box) — that combination is what stack-overflowed.
// Rather than depend on a menuconfig change, do the real work in its own
// task with a stack sized for it, and keep app_main() minimal.
static void app_task(void *arg) {
    (void)arg;
 
    wifi_init_sta();
    zenoh_init();
 
    while (1) {
        float temp_c = NAN, humidity = NAN;
        int err = dht22_read(DHT_GPIO, &temp_c, &humidity);
 
        if (err != 0) {
            ESP_LOGW(TAG, "DHT22 read failed (err=%d)", err);
        } else {
            ESP_LOGI(TAG, "temp_c=%.2f humidity=%.2f", temp_c, humidity);
            zenoh_publish(temp_c, humidity);
        }
 
        // DHT22 needs >=2s between reads.
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}
 
void app_main(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
 
    // 8KB stack; bump further if you add more to app_task and see this again.
    xTaskCreate(app_task, "app_task", 8192, NULL, 5, NULL);
}
 