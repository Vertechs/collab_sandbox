#include "time.h"
#include "esp_err.h"
#include "stdbool.h"

#define DEF_COOL_SP 78.0
#define DEF_COOL_DB 1.2
#define DEF_HEAT_SP 64.0
#define DEF_HEAT_DB 2.0

//===========
// Enums
typedef enum{
  TIMER_DISABLED = 0x00,
  TIMER_TIMING = 0x01,
  TIMER_DONE = 0x02
} timer_state;

typedef enum{
  LOCAL_CTRL = 0x00,
  REMOTE_CTRL = 0x01,
  MANUAL_CTRL = 0x02
}mode_locrem;

typedef enum{
  THERM_OFF = 0x00,
  THERM_CIRC = 0x01,
  THERM_COOL = 0x02,
  THERM_HEAT = 0x03
}mode_HVAC;

//==========
// structs
typedef struct{
  int64_t preset;
  int64_t accum;
  int64_t start_time;
  bool started;
  timer_state last_state; // allow access to last updated state without evaluation
}sw_timer;

typedef struct{
  int64_t start_ms;
  int64_t stop_ms;
  int64_t min_on_ms;
  int64_t min_off_ms;
  bool state;
  int pin_num;
  bool inverted;
} guarded_output;

typedef struct{
  guarded_output fan_out;
  guarded_output system_out;
  guarded_output mode_out;

  mode_locrem ctrl_loc;
  mode_HVAC mode;
  mode_HVAC mode_cmd;

  float cool_setpoint;
  float cool_deadband;

  float heat_setpoint;
  float heat_deadband;

  sw_timer cool_on_delay;
  sw_timer cool_off_delay;
  sw_timer heat_on_delay;
  sw_timer heat_off_delay;
  sw_timer fan_pre_run_delay;
  sw_timer fan_post_run_delay;

}therm_ctrl_intlkd_t;

//=======
// functions
timer_state sw_timer_eval(sw_timer *timer, bool enabled);

int64_t get_epoch_ms(void);

esp_err_t guarded_output_set(guarded_output *pin, bool cmd);

esp_err_t deadband_controller_eval(float pv);

esp_err_t therm_setup(therm_ctrl_intlkd_t *therm, bool invert_fan, bool invert_sys, bool invert_mode, int fan_num, int sys_num, int mode_num);

esp_err_t therm_execute(therm_ctrl_intlkd_t *therm, float local_temp);