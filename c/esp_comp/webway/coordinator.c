#include "zenoh-pico.h"
#include "coordinator.h"
#include "esp_err.h"
#include "zenoh_setup.h"

#define KEY_RQST "collabw/global/requests"
#define KEY_RSP "collabw/global/responses"
#define KEY_PROD "collabw/global/producers"
#define KEY_CONS "collabw/global/consumers"

const char *TAG = "Collab Coordinator";

esp_err_t collabw_request_parse_type(const char* val_str, int val_len, collabw_request_t *req) {
    
    const char *del_1 = memchr(val_str, ' ', val_len);
    if (del_1 != NULL){
        return ESP_FAIL;
    }
    
    size_t type_field_len = (size_t)(del_1 - val_str);

    if (strncmp(val_str, "TELL", 4) == 0) {
        req->type = COLLABW_REQUEST_TELL;
    }
    else if (strncmp(val_str, "LINK", 4) == 0) {
        req->type = COLLABW_REQUEST_LINK;
    }
    else if (strncmp(val_str, "UNLINK", 6) == 0) {
        req->type = COLLABW_REQUEST_UNLINK;
    }else{
        return ESP_FAIL;
    }

    req->raw_len = (size_t) (val_len-*del_1);

    req->raw_string = (char *)val_str;


    return ESP_OK; 
    
}

// minimal parsing of request messages. subscribers share a task,
// so parse and store the request against the global channel request queue
void collabw_request_handler(z_loaned_sample_t *sample, void *arg) {

    // cast arguments as pointer to global channel struct
    collabw_global_channel_t* g_chnl = (collabw_global_channel_t *)arg;

    // z_view_string_t key_str;
    // z_keyexpr_as_view_string(z_sample_keyexpr(sample), &key_str);
    
    // extract payload string and store into normal string
    z_owned_string_t payload;
    z_bytes_to_string(z_sample_payload(sample), &payload);

    const char* val_str = z_string_data(z_loan(payload));
    int val_len = z_string_len(z_loan(payload));
    
    collabw_request_t req = {0};

    // attempt to parse the request, if ok, add to queue

    collabw_request_type_t req_type = collabw_request_parse_type(val_str, val_len, &req);
    if(req_type != COLLABW_REQUEST_UNKNOWN) {
        if (xQueueSend(g_chnl->request_queue, &req, 0) != pdTRUE) {
            ESP_LOGW(TAG, "Request queue full");
        }

    }else{
        ESP_LOGW(TAG, "Failed to parse request: %.*s", val_len, val_str);
    }

    z_string_drop(z_string_move(&payload));
}

esp_err_t collabw_coordinator_init(collabw_global_channel_t *g_chnl, z_main_ctx_t *ctx) {

    // initialize RTOS request queue
    g_chnl->request_queue = xQueueCreate(8, sizeof(collabw_request_t));
    
    // initialize subscriber on the global web request key
    z_view_keyexpr_t rqst_key;
    z_view_keyexpr_from_str(&rqst_key, KEY_RQST);

    z_owned_closure_sample_t rqst_callback;
    z_closure_sample(&rqst_callback, collabw_request_handler, NULL, &g_chnl);

    z_result_t res = z_declare_subscriber(z_loan(ctx->session),
                                    &g_chnl->requests,
                                    z_loan(rqst_key), 
                                    z_move(rqst_callback),
                                    NULL);
    if (res != Z_OK) {
        ESP_LOGE(TAG, "Failed to declare subscriber for key: %s", KEY_RQST);
        return ESP_FAIL;
    }

    return ESP_OK;
}