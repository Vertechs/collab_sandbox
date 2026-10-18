#include "zenoh_setup.h"
#include "zenoh-pico.h"
#include "wifi_setup.h"
#include "esp_err.h"

// Zenoh session defaults
#define ZENOH_MODE "peer"
#define ZENOH_MULTICAST_LOCATOR "udp/224.0.0.225:7447"

// Logger
static const char *TAG = "Zenoh Setup";

esp_err_t zenoh_setup(z_main_ctx_t *ctx, const char *ip_addr){

    z_internal_null(&ctx->config);
    z_internal_null(&ctx->session);
    z_config_default(&ctx->config);

    zp_config_insert(z_config_loan_mut(&ctx->config), Z_CONFIG_MODE_KEY, ZENOH_MODE);
    zp_config_insert(z_config_loan_mut(&ctx->config), Z_CONFIG_MULTICAST_LOCATOR_KEY, ZENOH_MULTICAST_LOCATOR);

    char listen_locator[48];
    snprintf(listen_locator, sizeof(listen_locator), "tcp/%s:7447", ip_addr);
    // TODO build unicast links?
    //zp_config_insert(z_config_loan_mut(&ctx->config), Z_CONFIG_LISTEN_KEY, listen_locator);

    ESP_LOGI(TAG, "Opening session: mode=%s, multicast_locator=%s, listen_key=%s", 
        ZENOH_MODE, ZENOH_MULTICAST_LOCATOR, listen_locator);

    z_result_t err_catch = z_open(&ctx->session, z_config_move(&ctx->config), NULL);
    if (err_catch != Z_OK) {
        ESP_LOGE(TAG, "Failed to open Zenoh session, err:%d", err_catch);
        return ESP_FAIL;
    }

    return ESP_OK;

}
esp_err_t zenoh_reinit(z_main_ctx_t *ctx){
    return ESP_ERR_NOT_ALLOWED;
}

esp_err_t zenoh_close(z_main_ctx_t *ctx)
{
    if(!z_internal_session_check(&ctx->session)){
        ESP_LOGE(TAG, "Attempted to close session that is not open");
        return ESP_FAIL;
    }
    z_close(z_session_loan_mut(&ctx->session),NULL);
    z_drop(z_session_move(&ctx->session));
    return ESP_OK;
}   