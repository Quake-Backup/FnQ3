# RTX Renderer Guide

RTX is FnQuake3's Vulkan ray-tracing renderer. It is a separate renderer
module and does not change demo, protocol, VM, or game-logic behavior.

The renderer uses a hybrid final frame, but native ray tracing is authoritative
for the eligible primary-view opaque world. Primary rays and closest-hit
shading own direct lighting, ray-tested shadow visibility, self-emissive
material appearance, bounded albedo-tinted analytic environment diffuse, and
ray-visibility-gated analytic-environment specular. RTX does not currently
trace scene-radiance reflections, full secondary diffuse bounces, or general
light transport from arbitrary emissive surfaces. Authored
`q3map_surfaceLight` compile metadata is handled separately through bounded
analytic RT emitters.

The Vulkan-derived raster path establishes compatible depth, provides a
complete fallback when fallback is permitted, and preserves the exact semantic
overlay for content not yet owned by RT: entities, weapons, sky, portals,
complex or animated shader stages, fogged and translucent surfaces, liquids,
particles, marks, flares, and UI.

## Requirements

Full ray tracing requires a Vulkan GPU and driver with buffer device address,
deferred host operations, acceleration structures, ray queries, and
ray-tracing pipelines. RTX also checks the required feature bits, limits,
descriptor capacity, and formats rather than relying on extension names alone.

If the requested feature set is unavailable, `rtx_rt_require 0` permits a safe
fallback inside the module. `rtx_rt_require 1` makes startup fail with an
actionable capability error and also fails closed if an eligible primary-view
RT pass cannot be completed; it never silently presents that frame as a
successful required-RT result.

## Selecting RTX

Use a modular build containing `fnquake3_rtx_<arch>` and restart video:

```cfg
seta cl_renderer "rtx"
seta rtx_rt_mode "2"
seta rtx_rt_require "0"
vid_restart
```

`rtx_rt_mode 0` disables RT, `1` requests the ray-query capability path while
retaining raster output, and `2` requests the ray-tracing pipeline.
`rtx_caps_report 1` prints a compact capability summary;
`rtx_caps_report 2` prints the verbose table. The `vkinfo` command reports the
active device and RT gating result.

For a stable starting profile:

```cfg
seta rtx_rt_quality_preset "3"
seta rtx_rt_dynamic_resolution "0"
seta rtx_rt_adaptive_budget "1"
seta rtx_rt_dynamic_blas "0"
seta rtx_rt_spatial_denoise "0"
seta rtx_rt_raster_reference "0"
seta rtx_rt_legacy_color_compat "1"
```

Quality presets run from `1` (low) through `4` (ultra); `0` uses individual
cvar values. Dynamic resolution and the four-extra-ray spatial filter remain
experimental and default off. Dynamic BLAS remains opt-in because heavy
dynamic-scene updates can cause device loss on some drivers.

`rtx_rt_raster_reference 0` is the normal RTX identity: native primary rays and
closest-hit shading own the eligible opaque-world result. Setting it to `1`
keeps authored raster scene color and lightmaps as a compatibility reference,
then applies bounded RT visibility and ray-visible analytic-environment
specular cues. It is useful for content whose original lightmap/material
balance matters more than native RT lighting, but it is not the renderer's
default visual identity.

`rtx_rt_legacy_color_compat` is deliberately separate. Its default value `1`
only applies the legacy `r_intensity` brightness scale to native RT output
before the shared final pass. Setting it to `0` disables that brightness
shaping; it does not switch primary-world ownership back to raster.

## Default Visual Features

The RTX defaults follow the Vulkan renderer's normal visible feature set:

- `r_hdr 1` requests RGBA16F storage for native RT shading, RT history, bloom,
  and hybrid composition. If the device lacks the required floating-point
  attachment, blend, sampling, transfer, or blit features, RTX reports the
  fallback and uses the effective SDR path. `r_hdrPrecision` controls SDR
  storage only; `r_tonemap`, `r_tonemapExposure`, the linear-to-sRGB output
  transform, and `r_gamma` own final presentation.
- `r_srgbTextures 1` decodes authored color textures as sRGB. Lightmaps, fog,
  data, and utility textures remain linear/data resources.
- Closest-hit albedo sampling selects an explicit mip from triangle world/UV
  area, texture extent, hit distance, camera FOV/output height, and incidence
  angle. The result is clamped to the available mip chain, avoiding forced
  LOD-zero shimmer without blurring Quake's high-frequency authored textures.
- `r_hudExcludePostProcess 1` applies world bloom before later 3D HUD scenes,
  keeping HUD elements sharp.
- `r_fogMode 1` uses analytic Quake III fog. `r_globalFog 1` permits optional
  depth-aware `maps/<map>.fog` atmosphere supplied by the active game.
- `r_depthFade 1` softens eligible translucent particle intersections.
- `r_staticLights 1` permits renderer-only `maps/<map>.lights.json` lights
  supplied by the active game. `r_staticLightMaxLights` limits how many are
  promoted into a scene.
- `rtx_rt_world_light_scale 0.35` promotes BSP compile-time light entities into
  native RT direct lights. Native mode uses those live lights rather than baked
  lightmap energy; raster-reference mode preserves the authored lightmap result.
- `r_surfaceLightProxies 1` converts used BSP surfaces carrying
  `q3map_surfaceLight` metadata into bounded point or linear analytic lights.
  RTX PVS-ranks at most `r_surfaceLightProxyMaxLights` (default `16`) into the
  native light buffer and traces their visibility with shadow rays. The raw
  compiler intensity affects bounded reach and selection only; it never
  multiplies RGB radiance directly. These lights are disabled in
  raster-reference mode to avoid adding them over baked lightmap energy.
- Used BSP sky shaders select their own `q3map_sun`, `q3map_sunExt`, or
  `q3map_sunExt2` direction and color. RTX converts the legacy q3map intensity
  unit to scene radiance at the RT boundary, then traces shadow visibility;
  shader registration order cannot leave a stale sun active for a later map.
- Enhanced liquids use the shared `r_liquid` controls and ripple feed described
  in the [liquid rendering guide](fnquake3/LIQUID_RENDERING.md).
- `r_picmipFilter 1` applies picmip to world textures while protecting models,
  sprites, icons, menus, UI, and fonts.

Active RT deliberately disables raster MSAA. RT reconstruction owns
anti-aliasing in this mode, and the semantic overlay uses the same
single-sample frame.

## Hybrid Limitations

`rtx_rt_dynamic_blas 0` is the stable default. Dynamic entities and effects
remain visible through the raster overlay, but do not participate in RT
visibility or cast RT shadows. With dynamic BLAS enabled, their geometry may
participate in ray visibility experimentally, but their visible pixels remain
raster-owned regardless of BLAS success.

Raster-overlay pixels are drawn after tracing and are not retroactively
ray-shadowed. Opaque overlay geometry may still be represented as a
shadow-ray occluder to avoid light leaks without transferring its primary
color to RT. Portals, mirrors, stereo eyes, cube-map faces, and other secondary
views intentionally use a complete raster fallback rather than sharing
incompatible RT history.

Native primary-color ownership is intentionally conservative. It currently
accepts static opaque shaders whose authored result is one base texture,
optionally modulated by a lightmap, without animation, texture transforms,
deformation, blending, alpha testing, or unusual depth behavior. More complex
shader-language semantics stay raster-owned rather than being approximated as
ordinary opaque RT materials.

`rtx_rt_reflection_strength` controls only glossy sampling of the analytic
sky/sun environment, and that contribution is accepted only when a glossy
visibility ray escapes scene geometry. It does not enable scene-radiance
reflection rays.

`rtx_rt_indirect_strength` scales an always-on, bounded, albedo-tinted analytic
environment diffuse term in native closest-hit shading. This keeps materials
legible where compiled Quake maps no longer retain enough source-light
transport for direct emitters alone; it does not import raster scene color or
baked lightmap lighting. `rtx_rt_indirect_bounce 1` adds one experimental
hemisphere visibility ray that only occlusion-refines that baseline with a
bounded floor. It is not a sampled radiance bounce or multi-bounce global
illumination.

Emissive materials can appear self-lit, but they do not generally illuminate
nearby geometry. The bounded `q3map_surfaceLight` proxy path is an
authored-content bridge, not arbitrary emissive radiance transport, and the
compile directive alone does not force the visible material to become
fullbright or shadow-immune.

Enhanced-liquid reflection and refraction preserve the Vulkan renderer's
screen-space scene-color treatment. They are not recursive RT reflection or
refraction rays.

RTX does not reproduce raster shadow maps or CSM, because ray visibility
provides the relevant shadow behavior. Optional Vulkan-only presentation
effects such as native HDR10 output, color-grading LUTs, CRT distortion,
motion blur, cel outlines, and extended screenshot metadata/watermarks are
outside the current RTX parity target.

## Build

RTX is part of the default three-renderer build. To build it alone as a module:

```sh
meson setup .tmp/build-rtx -Drenderers=rtx
meson compile -C .tmp/build-rtx
```

For a static client build:

```sh
meson setup .tmp/build-static-rtx -Drenderer-dlopen=false -Drenderer-default=rtx
meson compile -C .tmp/build-static-rtx
```

## Maintainer Validation

The focused smoke harness validates both the RTX module's raster fallback and
strict mode-2 hardware ray tracing. Its RT profile enables Vulkan validation,
HDR, bloom, depth fade, enhanced liquids, global fog, and static lights, then
captures `q3dm8` and `q3dm1`. Native surface-light proxies are explicitly
enabled in the profile. The RT profile also captures a q3dm1 albedo-debug
companion and verifies that high-frequency authored texture detail in a fixed
world-surface region remains correlated with the normally lit native RT image.
This catches material washout without requiring raster-like lighting.

The harness rejects missing RT activation/post-stack markers, missing or
structurally invalid screenshots, lost native material detail, excessive
near-white clipping, Vulkan validation errors, fatal errors, and device loss.
The launch line intentionally stays below Quake III's fixed startup-command
limit. A bounded lifecycle-sensitive subset (renderer mode/require policy,
validation, HDR/FBO/MSAA, logging, and window mode) is applied before the first
renderer initialization; the complete feature profile remains in the
generated config.

Run its deterministic tests and inspect a dry-run plan without retail assets or
a GPU:

```powershell
python tests/rtx_runtime_smoke_tests.py
python scripts/rtx_runtime_smoke.py --list-gates
python scripts/rtx_runtime_smoke.py --gate rtx-smoke --dry-run `
  --exe .tmp/rtx-gate-plans/fnquake3 `
  --basepath .tmp/rtx-gate-plans/basepath `
  --output-dir .tmp/rtx-gate-plans `
  --summary-markdown .tmp/rtx-gate-plans/rtx-smoke.md
```

Run the hardware gate with a built client and retail assets:

```powershell
python scripts/rtx_runtime_smoke.py --gate rtx-smoke `
  --exe <path-to-fnquake3> `
  --basepath <path-containing-retail-baseq3> `
  --output-dir .tmp/rtx-runtime-smoke `
  --summary-markdown .tmp/rtx-runtime-smoke/rtx-smoke.md
```

The `vulkan-verification` workflow builds modular and static VK and RTX
configurations, checks RTX shader/source contracts, generates dry-run VK/RTX
gate artifacts, and exposes the VK and `rtx-smoke` gates for manual execution
on self-hosted GPU runners.

## Troubleshooting

If RTX cannot initialize, capture `vkinfo`, the startup capability report, OS/GPU/driver details, and any `rtx_*` overrides. Use `cl_renderer vk` followed by `vid_restart` to return to Vulkan raster rendering.

Useful diagnostics include `rtx_debug_vk_validation 1`, `rtx_debug_framegraph 1`, `rtx_rt_perf_timing 1`, and `rtx_rt_debug_visualizer 1`. These are debugging controls and should normally remain disabled.

Maintainers should use the
[RTX parity contract](fnquake3/RTX_PARITY.md) for the exact Vulkan comparison
surface, implemented action plan, intentional exclusions, validation commands,
and remaining hardware promotion matrix.
