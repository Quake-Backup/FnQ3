# GLx Tests

`fnq3_glx_logic_tests` covers renderer-independent GLx classification logic. It does not create an OpenGL context, include `code/renderer`, or require game assets.

The harness currently checks:

- GLSL material permutation key selection for RC-supported single-texture, multitexture, texmod, environment, and fog shapes.
- Dynamic-light, screen-map, and video-map material flags staying gate-only rather than expanding the shader permutation table.
- Rejection of unsupported multitexture combine modes.
- Stream material-gate behavior for the RC allowlist.
- Explicit dynamic-light, screen-map, and video-map stream gate behavior outside the RC allowlist.
- Explicit stencil shadow-volume stream gate behavior outside the material-key system.
- Explicit immediate beam draw-array stream gate behavior outside the material-key system.
- Explicit fullscreen postprocess draw-array stream gate behavior outside the material-key system.
- The broad `r_glxStreamDrawKeyMode 2` developer escape hatch.
- Capability version/extension parsing and tier selection.
- Dynamic-stream strategy selection across persistent, map-range, and orphan/subdata fallbacks.
- Static-world packet run classification and draw-policy gating.

`fnq3_glx_header_boundary` scans the pure GLx headers and the public GLx module bridge header. It fails if pure logic picks up legacy renderer includes, GL object typedefs, `qgl` references, renderer ABI types, or module/local implementation headers. It also keeps `glx_module.h` from growing a `tr_public.h`, `qgl`, GL typedef, or shutdown-enum dependency.

Build and run it with CMake:

```sh
cmake --build .tmp/cmake-glx --target fnq3_glx_logic_tests --config Debug
ctest --test-dir .tmp/cmake-glx -R "fnq3_glx_(logic|header_boundary)" --output-on-failure -C Debug
```
