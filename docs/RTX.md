# RTX Renderer Guide

RTX is FnQuake3's Vulkan ray-tracing renderer. It is a separate renderer module and does not change demo, protocol, VM, or game logic behavior.

## Requirements

Full ray tracing requires a Vulkan GPU and driver with buffer device address, deferred host operations, acceleration structures, ray queries, and ray-tracing pipelines. If the requested feature set is unavailable, `rtx_rt_require 0` permits a safe fallback inside the module; `rtx_rt_require 1` makes startup fail with an actionable capability error.

## Selecting RTX

Use a modular build containing `fnquake3_rtx_<arch>` and restart video:

```cfg
seta cl_renderer "rtx"
seta rtx_rt_mode "2"
seta rtx_rt_require "0"
vid_restart
```

`rtx_rt_mode 0` disables RT, `1` requests ray-query support, and `2` requests the ray-tracing pipeline. `rtx_caps_report 1` prints a compact capability summary; `rtx_caps_report 2` prints the verbose table. The `vkinfo` command reports the active device and RT gating result.

For a stable starting profile:

```cfg
seta rtx_rt_quality_preset "3"
seta rtx_rt_dynamic_resolution "1"
seta rtx_rt_adaptive_budget "1"
seta rtx_rt_dynamic_blas "0"
```

Quality presets run from `1` (low) through `4` (ultra); `0` uses individual cvar values. Dynamic BLAS remains opt-in because heavy dynamic-scene updates can cause device loss on some drivers.

## Build

RTX is part of the default three-renderer build. To build it alone as a module:

```sh
meson setup meson/build-rtx -Drenderers=rtx
meson compile -C meson/build-rtx
```

For a static client build:

```sh
meson setup meson/build-rtx-static -Drenderer-dlopen=false -Drenderer-default=rtx
meson compile -C meson/build-rtx-static
```

## Troubleshooting

If RTX cannot initialize, capture `vkinfo`, the startup capability report, OS/GPU/driver details, and any `rtx_*` overrides. Use `cl_renderer vk` followed by `vid_restart` to return to Vulkan raster rendering.

Useful diagnostics include `rtx_debug_vk_validation 1`, `rtx_debug_framegraph 1`, `rtx_rt_perf_timing 1`, and `rtx_rt_debug_visualizer 1`. These are debugging controls and should normally remain disabled.
