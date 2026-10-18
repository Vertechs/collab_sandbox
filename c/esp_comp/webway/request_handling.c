// sp_err_t collabw_parse_request(const char* val_str, int val_len, collabw_request_t *req) {
//     // parse request string, delimited by commas
//     // request string always 4 characters or more
//     if (val_len < 4){
//         return ESP_FAIL;
//     }

//     // extract request type
//     // const char *del_1 = memchr(val_str, ',', val_len);
//     // if (!del_1){
//     //     return ESP_FAIL;
//     // }
//     // size_t type_field_len = (size_t)(del_1 - val_str);

//     // if (strncmp(val_str, "TELL", 4) == 0) {
//     //     req->type = COLLABW_REQUEST_TELL;
//     // }
//     // else if (strncmp(val_str, "LINK", 4) == 0) {
//     //     req->type = COLLABW_REQUEST_LINK;
//     // }
//     // else if (strncmp(val_str, "UNLINK", 6) == 0) {
//     //     req->type = COLLABW_REQUEST_UNLINK;
//     // }
//     // else{
//     //     return ESP_FAIL;
//     // }

//     // walk flag option characters and fill flag field
//     const char *del_2 = memchr(del_1 + 1, ',', val_len - (size_t)(del_1 - val_str));
//     if (!del_2){
//         return ESP_FAIL;
//     }
//     else if (del_2 == del_1 + 1) {
//         req->flag_field = 0x00;
//     }
//     else{
//         for (const char *p = del_1 + 1; p < del_2; p++) {
//             switch (*p) {
//                 case 'C':
//                     req->flag_field |= COLLABW_FLAG_ECHO_CONSUMERS;
//                     break;
//                 case 'P':
//                     req->flag_field |= COLLABW_FLAG_ECHO_PRODUCERS;
//                     break;
//                 default:
//                     return ESP_FAIL;
//             }
//         }   
//     }

//     if (req->type == COLLABW_REQUEST_LINK)||(req->type == COLLABW_REQUEST_UNLINK) {

//     return ESP_OK;
// }