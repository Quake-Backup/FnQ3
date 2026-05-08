# GLx Tests

`fnq3_glx_logic_tests` covers renderer-independent GLx classification logic. It does not create an OpenGL context or require game assets.

The harness currently checks:

- GLSL material permutation key selection for RC-supported single-texture, multitexture, texmod, environment, and fog shapes.
- Rejection of unsupported multitexture combine modes.
- Stream material-gate behavior for the RC allowlist.
- The broad `r_glxStreamDrawKeyMode 2` developer escape hatch.
- Capability version/extension parsing and tier selection.
- Dynamic-stream strategy selection across persistent, map-range, and orphan/subdata fallbacks.
- Static-world packet run classification and draw-policy gating.

Build and run it with CMake:

```sh
cmake --build .tmp/cmake-glx --target fnq3_glx_logic_tests --config Debug
ctest --test-dir .tmp/cmake-glx -R fnq3_glx_logic --output-on-failure -C Debug
```
