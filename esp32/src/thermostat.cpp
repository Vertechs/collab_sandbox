#include "thermostat.h"
#include "esp_err.h"
#include "stdbool.h"
#include "sys/time.h"
#include <Arduino.h>
#include <math.h>

int64_t get_epoch_ms(){
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

timer_state sw_timer_eval(sw_timer *timer, bool enabled){
  if (enabled){

    int64_t now = get_epoch_ms();

    if (!timer->started){
      timer->started = true;
      timer->start_time = now;
    }

    if (timer->accum < timer->preset){ // stop recalculating once timer is done, will show some overrun if not called on the millisecond
      timer->accum = now - timer->start_time;
    }
    timer->last_state = timer->accum >= timer->preset ? TIMER_DONE : TIMER_TIMING;

  }else{

    timer->accum = 0;
    timer->started = false;
    timer->last_state = TIMER_DISABLED;
    
  }
  return timer->last_state;
}

esp_err_t guarded_output_set(guarded_output *pin, bool cmd){
  if (cmd==pin->state){
    return ESP_OK;
  }

  int64_t now = get_epoch_ms();

  if (cmd){
    if ((now - pin->stop_ms) < pin->min_off_ms){
      return ESP_ERR_NOT_ALLOWED;
    }else{
      pin->start_ms = now;
      pin->state = true;
      digitalWrite(pin->pin_num, !pin->inverted);
    }
  }else{
    if ((now - pin->start_ms) < pin->min_on_ms){
      return ESP_ERR_NOT_ALLOWED;
    }else{
      pin->stop_ms = now;
      pin->state = false;
      digitalWrite(pin->pin_num, pin->inverted);
    }
  }
  return ESP_OK;
  
}


esp_err_t therm_setup(therm_ctrl_intlkd_t *therm, bool invert_fan, bool invert_sys, bool invert_mode, int fan_num, int sys_num, int mode_num){
  therm->fan_out.inverted = invert_fan;
  therm->system_out.inverted = invert_sys;
  therm->mode_out.inverted = invert_mode;

  therm->fan_out.pin_num = fan_num;
  therm->system_out.pin_num = sys_num;
  therm->mode_out.pin_num = mode_num;

  pinMode(therm->fan_out.pin_num, OUTPUT);
  pinMode(therm->system_out.pin_num, OUTPUT);
  pinMode(therm->mode_out.pin_num, OUTPUT);

  digitalWrite(therm->fan_out.pin_num, therm->fan_out.inverted);
  digitalWrite(therm->system_out.pin_num, therm->system_out.inverted);
  digitalWrite(therm->mode_out.pin_num, therm->mode_out.inverted);

  int64_t now = get_epoch_ms();

  // setup guarded outputs
  therm->fan_out.start_ms = now;
  therm->fan_out.stop_ms = now;
  therm->system_out.start_ms = now;
  therm->system_out.stop_ms = now;
  therm->mode_out.start_ms = now;
  therm->mode_out.stop_ms = now;

  //TODO setup defaults file?
  therm->fan_out.min_on_ms = 0.5*60*1000;
  therm->fan_out.min_off_ms = 0.5*60*1000;
  therm->system_out.min_on_ms = 1*60*1000;
  therm->system_out.min_off_ms = 5*60*1000;
  therm->mode_out.min_on_ms = 5*60*1000;
  therm->mode_out.min_off_ms = 5*60*1000;

  // ensure no pins change state after a reboot
  therm->fan_out.start_ms = now;
  therm->fan_out.stop_ms = now;
  therm->system_out.start_ms = now;
  therm->system_out.stop_ms = now;
  therm->mode_out.start_ms = now;
  therm->mode_out.stop_ms = now;

  // set default time delays
  therm->cool_on_delay.preset = 5*60*1000;
  therm->cool_off_delay.preset = 5*60*1000;
  therm->heat_on_delay.preset = 10*60*1000;
  therm->heat_off_delay.preset = 10*60*1000;
  therm->fan_pre_run_delay.preset = 1*60*1000;
  therm->fan_post_run_delay.preset = 3*60*1000;

  therm->fan_post_run_delay.accum = therm->fan_post_run_delay.preset+1000;

  // set default setpoints
  therm->cool_setpoint = DEF_COOL_SP;
  therm->cool_deadband = DEF_COOL_DB;
  therm->heat_setpoint = DEF_HEAT_SP;
  therm->heat_deadband = DEF_HEAT_DB;

  therm->ctrl_loc = LOCAL_CTRL;
  therm->mode = THERM_OFF;

  return ESP_OK;
}


esp_err_t therm_execute(therm_ctrl_intlkd_t *therm, float local_temp){

  // check permissives, turn off outputs and exit early if needed
  // TODO
  bool perm = (therm->cool_setpoint-therm->cool_deadband) > (therm->heat_setpoint+therm->heat_deadband);
  perm = perm && !isnan(local_temp);
  if (!perm){
    therm->mode = THERM_OFF;

    // TODO add graceful shutdown logic, and permissive lockout
    guarded_output_set(&therm->fan_out, false);
    guarded_output_set(&therm->system_out, false);

    return ESP_ERR_NOT_ALLOWED;
  }

  // temporary state variables to capture guarded input states
  esp_err_t fan_out_st = ESP_OK;
  esp_err_t sys_out_st = ESP_OK;
  esp_err_t mode_out_st = ESP_OK;

  // main mode logic, with delay timers
  if (therm->ctrl_loc == LOCAL_CTRL){

    // enter and exist mode timers
    timer_state cool_on_tm = sw_timer_eval(&therm->cool_on_delay, local_temp > therm->cool_setpoint + therm->cool_deadband);
    timer_state cool_off_tm = sw_timer_eval(&therm->cool_off_delay, local_temp < therm->cool_setpoint - therm->cool_deadband);

    timer_state heat_on_tm = sw_timer_eval(&therm->heat_on_delay, local_temp < therm->heat_setpoint - therm->heat_deadband);
    timer_state heat_off_tm = sw_timer_eval(&therm->heat_off_delay, local_temp > therm->heat_setpoint + therm->heat_deadband);

    // decide current mode
    if ((therm->mode == THERM_OFF) || (therm->mode == THERM_CIRC)){
      if (cool_on_tm == TIMER_DONE){
        therm->mode = THERM_COOL;
      }else if (heat_on_tm == TIMER_DONE){
        therm->mode = THERM_HEAT;
      }else{
        therm->mode = THERM_OFF; // fall back to IDLE if circ was active
      }
    }else if (therm->mode == THERM_COOL){
      if (cool_off_tm == TIMER_DONE){
        therm->mode = THERM_OFF;
      }
    }else if (therm->mode == THERM_HEAT){
      if (heat_off_tm == TIMER_DONE){
        therm->mode = THERM_OFF;
      }
    }else{
      therm->mode = THERM_OFF; // default to IDLE if invalid mode is set
    }

  }else if (therm->ctrl_loc == REMOTE_CTRL){
    // set mode according to external command
    therm->mode = therm->mode_cmd;

  }else{
    therm->mode = THERM_OFF;
  }

  // fan pre and post run time timers
  timer_state fan_on_tm = sw_timer_eval(&therm->fan_pre_run_delay, (therm->mode==THERM_COOL || therm->mode==THERM_HEAT || therm->mode==THERM_CIRC) );
  timer_state fan_off_tm = sw_timer_eval(&therm->fan_post_run_delay, (therm->mode==THERM_OFF));

  // set outputs according to mode
  if ((fan_on_tm != TIMER_DISABLED) || (fan_off_tm == TIMER_TIMING)){
    fan_out_st = guarded_output_set(&therm->fan_out, true);
  }else{
    fan_out_st = guarded_output_set(&therm->fan_out, false);
  }

  if (( (therm->mode == THERM_HEAT) || (therm->mode == THERM_COOL) ) && (fan_on_tm == TIMER_DONE) ){
    sys_out_st = guarded_output_set(&therm->system_out, true);
  }else{
    sys_out_st = guarded_output_set(&therm->system_out, false);
  }

  // never switch modes if system is running
  if (therm->system_out.state == 0){
    // normally closed contact goes to cooling call
    mode_out_st = guarded_output_set(&therm->mode_out, therm->mode==THERM_HEAT);
  }

  if (fan_out_st + sys_out_st + mode_out_st){
    return ESP_ERR_NOT_ALLOWED;
  }else{
    return ESP_OK;
  }

}