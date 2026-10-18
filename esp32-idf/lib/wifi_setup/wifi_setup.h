#pragma once
#include "esp_err.h"

esp_err_t wifi_setup(const char *ssid, const char *password);
const char *wifi_get_ip(void);