# ESP32 firmware — ESP-IDF (in progress)

Sibling to `../esp32/` (the Arduino/PlatformIO version), which stays as
a working reference while this one gets ported over piece by piece.

Build/upload the same way as `esp32/`:

    pio run
    pio run -t upload
    pio device monitor

Porting notes:
- Entry point is `app_main()` in `src/main.c`, not `setup()`/`loop()`.
- No Arduino, no Adafruit libraries — sensor/display/relay drivers need
  ESP-IDF-native equivalents (`i2c_master_*`, `gpio_*`, `ledc_*`) or a
  driver written from scratch. Port and verify one peripheral at a time
  against the working Arduino version in `../esp32/` rather than all at
  once.
- Zenoh integration is not set up yet — check whether zenoh-pico is
  published to the ESP-IDF Component Registry before assuming the same
  git-URL approach from the Arduino version carries over unchanged.
