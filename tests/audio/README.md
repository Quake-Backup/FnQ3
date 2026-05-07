# Audio Loopback Tests

`fnq3_audio_loopback_tests` is a deterministic OpenAL Soft loopback harness for the modern audio backend work. It uses `ALC_SOFT_loopback` to render into an in-memory stereo float buffer, so it does not need a real playback device or game assets.

The harness currently checks:

- OpenAL library and loopback availability.
- HRTF status reporting when `ALC_SOFT_HRTF` is present.
- Inverse-clamped distance attenuation.
- Stereo buffer channel isolation.
- Idle loopback silence.
- EFX low-pass, high-pass, and band-pass filter behavior when `ALC_EXT_EFX` is present.

Build and run it with CMake:

```sh
cmake --build .tmp/cmake-check --target fnq3_audio_loopback_tests --config Release
ctest --test-dir .tmp/cmake-check -R fnq3_audio_loopback --output-on-failure -C Release
```

The test exits with code `77` when OpenAL or `ALC_SOFT_loopback` is unavailable. CTest treats that as a skip.
