#pragma once
#include "zenoh-pico.h"
#include "zenoh_setup.h"


// internal representation only, request messages stay in plain text
typedef enum{
    COLLABW_REQUEST_UNKNOWN,
    COLLABW_REQUEST_TELL,
    COLLABW_REQUEST_LINK,
    COLLABW_REQUEST_UNLINK

} collabw_request_type_t;

typedef enum{
    COLLABW_FLAG_ECHO_CONSUMERS = 0x01,
    COLLABW_FLAG_ECHO_PRODUCERS = 0x02
} collabw_echo_flag_field_t;

typedef enum{
    COLLABW_FLAG_LINK_OVERWRITE = 0x01
} collabw_link_flag_field_t;

typedef struct {
    z_owned_subscriber_t requests;
    z_owned_publisher_t responses;
    z_owned_publisher_t producers;
    z_owned_publisher_t consumers;
    QueueHandle_t request_queue;

} collabw_global_channel_t;


typedef struct {
    z_owned_keyexpr_t key_A;
    z_owned_keyexpr_t key_B;
    uint8_t flag_field;
    uint32_t web_uuid;
    uint32_t link_uuid;
} collabw_link_request_t;

typedef struct {
    z_owned_keyexpr_t key_match;
    uint8_t flag_field;
} collabw_echo_request_t;

// request as it is in queue
typedef struct {
    collabw_request_type_t type;
    char *raw_string;
    size_t raw_len;
} collabw_request_t;

typedef struct{
    z_owned_keyexpr_t signal_key;
    z_owned_string_t signal_type;
    bool is_producer;
} collabw_response_t;




esp_err_t collabw_coordinator_init(collabw_global_channel_t *g_chnl, z_main_ctx_t *ctx);
