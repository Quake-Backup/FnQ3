# Audio Tests

`fnq3_audio_loopback_tests` is a deterministic OpenAL Soft loopback harness for the modern audio backend work. It uses `ALC_SOFT_loopback` to render into an in-memory stereo float buffer, so it does not need a real playback device or game assets.

`fnq3_audio_zone_tests` exercises the engine-independent `.azb` runtime parser and selection helper with synthetic sidecars. It covers version 1 compatibility defaults, version 2 material/flag/portal metadata, priority and smaller-volume selection, portal blend bounds, and invalid sidecar rejection.

`fnq3_audio_recovery_tests` exercises the OpenAL device recovery policy without needing real hardware disconnects. It covers poll timing, retry suppression, one-shot disconnect/reconnect messages, disabled auto-recovery behavior, successful recovery reset, refresh-query failure behavior, and manual force/skip decisions.

The harness currently checks:

- OpenAL library and loopback availability.
- HRTF status reporting and mode switching when `ALC_SOFT_HRTF` is present.
- Inverse-clamped distance attenuation.
- Stereo, quad, 5.1, 6.1, and 7.1 direct-channel routing when the runtime supports those layouts.
- Optional UHJ and B-Format buffer acceptance when the runtime exposes those extensions.
- Idle loopback silence.
- EFX low-pass, high-pass, and band-pass filter behavior when `ALC_EXT_EFX` is present.

Build and run it with CMake:

```sh
cmake --build .tmp/cmake-check --target fnq3_audio_zone_tests fnq3_audio_recovery_tests fnq3_audio_loopback_tests --config Release
ctest --test-dir .tmp/cmake-check -R "fnq3_audio_(zones|recovery|loopback)" --output-on-failure -C Release
```

The loopback test exits with code `77` when OpenAL or `ALC_SOFT_loopback` is unavailable. CTest treats that as a skip. The zone runtime and recovery policy tests do not require OpenAL.
