#pragma once
#include "zenoh-pico.h"
#include "esp_err.h"

typedef struct{
    z_owned_config_t config;
    z_owned_session_t session;
} z_main_ctx_t;

esp_err_t zenoh_setup(z_main_ctx_t *ctx, const char *ip_addr);
esp_err_t zenoh_reinit(z_main_ctx_t *ctx);
esp_err_t zenoh_close(z_main_ctx_t *ctx);
