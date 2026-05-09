# GLx Tests

`fnq3_glx_logic_tests` covers renderer-independent GLx classification logic. It does not create an OpenGL context, include `code/renderer`, or require game assets.

The harness currently checks:

- GLSL material permutation key selection for RC-supported single-texture, multitexture, texmod, environment, depth-fragment, and fog shapes.
- Full prepared id Tech 3 stage-language keys for `rgbGen`, `alphaGen`, their wave functions, `tcGen`, ordered `tcMod` chains, `tcMod stretch` wave functions, detail stages, fog color adjustment, blend/depth/alpha-test state flags, dynamic-light, screen-map, and video-map cases, including proof that compact-key matches still produce distinct stage-language permutations.
- Rejection of unsupported multitexture combine modes.
- Stream material-gate behavior for the RC allowlist, including explicit multitexture and depth-fragment gates.
- The legacy shader collapse path not blocking compatible `depthFragment` base stages from becoming multitexture stages.
- Explicit dynamic-light, screen-map, and video-map stream gate behavior outside the RC allowlist.
- Explicit shadow-volume, beam, and fullscreen postprocess draw-array stream gate behavior outside the material-key system.
- RC runtime-sweep profiles enabling those state-only dynamic submission gates while keeping dynamic-light, screen-map, and video-map material gates off.
- The frozen RC/stress sweep profiles matching the runtime `r_glxProfile` table in `code/rendererglx/glx_module.cpp`.
- Hard proof-gate policy requiring reviewed screenshot baselines and compared performance baselines for `rc-proof`.
- The broad `r_glxStreamDrawKeyMode 2` developer escape hatch staying behind hard multitexture and depth-fragment gates.
- Capability version/extension parsing and tier selection.
- Dynamic-stream strategy selection across persistent, map-range, and orphan/subdata fallbacks.
- Static-world packet run classification and draw-policy gating.

`fnq3_glx_header_boundary` scans the pure GLx headers, the renderer-common GLx API/forwarding bridge, and the renderer facade. It fails if pure logic picks up legacy renderer includes, GL object typedefs, `qgl` references, renderer ABI types, or module/local implementation headers. It also keeps the bridge headers from growing a `tr_public.h`, `qgl`, GL typedef, or shutdown-enum dependency, and keeps `tr_glx_compat.h` from including back into `code/rendererglx`.

Build and run it with CMake:

```sh
cmake --build .tmp/cmake-glx --target fnq3_glx_logic_tests --config Debug
ctest --test-dir .tmp/cmake-glx -R "fnq3_glx_(logic|header_boundary)" --output-on-failure -C Debug
```
