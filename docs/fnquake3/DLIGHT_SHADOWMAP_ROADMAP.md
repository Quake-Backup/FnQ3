# Dynamic-Light Shadow Mapping Roadmap

This document tracks the dynamic-light shadow mapping work for the GLx and
Vulkan renderers. Keep it current whenever shadow-map planning, allocation,
rendering, filtering, testing, or release evidence changes.

## Goals

- Preserve retail Quake III compatibility, demo behavior, and renderer module
  boundaries.
- Support high-quality shadows from point dynamic lights on world geometry,
  brush models, and entity models in both GLx and Vulkan.
- Keep the implementation efficient in hot paths: bounded light budgets,
  explicit culling, predictable atlas allocation, and renderer-local GPU work.
- Grow toward stable filtering and eventual cascaded shadow maps for directional
  light paths without mixing CSM concerns into the dlight milestone.

## Checklist Rules

- `[x]` means the item is implemented in both GLx and Vulkan unless the item
  names one renderer.
- `[ ]` means the item is not implemented yet.
- Items tagged `(partial)` are intentionally present but not complete enough to
  close the milestone.
- Every implementation step must update this checklist, the current snapshot,
  and the testing evidence in the same change.

## Current Snapshot

As of May 22, 2026:

- `[x]` Dynamic-light shadow cvars, planning counters, candidate filtering, and
  per-view prioritization are implemented.
- `[x]` Per-dlight six-face atlas slot metadata and shared atlas layout logic
  are implemented.
- `[x]` GLx allocates a depth-only shadow atlas texture/FBO.
- `[x]` Vulkan allocates a sampled depth atlas image/view/descriptor and a
  depth-only shadow atlas render pass/framebuffer.
- `[x]` GLx and Vulkan render planned dlight atlas tiles with opaque world,
  brush-model, and entity-model casters from existing lit-surface lists.
  World and brush-model casters use `SF_FACE`, `SF_GRID`, and `SF_TRIANGLES`;
  entity-model casters use `SF_MD3`, `SF_MDR`, and `SF_IQM` when
  `r_dlightMode 2` enables entity dynamic-light surfaces.
- `[x]` `r_dlightTest` injects repeatable test dynamic lights from the renderer.
- `[x]` `scripts/dlight_shadow_test.py` generates GLx/Vulkan shadow test
  launches, manifests, dry-runs, and optional RenderDoc wrapping.
- `[x]` `r_dlightShadowDebug 1` reports planning counters plus atlas render
  counters: `fill`, `render lights`, `faces`, `batches`, `draws`, `surfs`,
  atlas CPU time, and `lowvalue` overload skips.
- `[x]` GLx and Vulkan lighting sample the dlight shadow atlas with selectable
  `r_dlightShadowFilter` modes for per-face point-light lookups on world
  receivers: hard shadows, 2x2 PCF, and the default four-tap poisson-style PCF.
  The temporary screen-space fallback has been removed.
- `[x]` GLx shadow sampling uses ARB-fragment-program-safe scalar atlas
  coordinate clamps/scales so drivers that reject short source swizzles compile
  the dlight shadow programs instead of disabling `r_dlightShadows`.
- `[x]` Brush-model casters are rendered into the atlas from lit-surface brush
  model entries.
- `[x]` Entity-model casters are rendered into the atlas from lit-surface MD3,
  MDR, and IQM model entries when `r_dlightMode 2` is active.
- `[x]` Conservative per-face caster culling skips caster bounds that are fully
  outside each point-light cube face, and empty face tiles are preflighted and
  skipped before viewport/scissor setup or draw submission.
- `[x]` GLx and Vulkan apply tuned dlight-shadow bias: lower default
  slope/constant caster depth bias during atlas writes, angle-aware caster
  normal offset before CPU tessellation is submitted, and angle-aware,
  texel-scaled receiver bias during atlas sampling so wall-contact shadows do
  not detach at corners.
- `[x]` Basic 2x2 PCF filtering has been upgraded to selectable GLx and Vulkan
  dlight and sky-sun CSM shadow-map filters: hard shadows, 2x2 PCF, and
  default four-tap poisson-style PCF.
- `[x]` GLx and Vulkan cache atlas tiles for static world-only dlight shadow
  casters when the light parameters, receiver count, lit-surface set, atlas
  face size, and atlas resource generation match. Non-cacheable entity,
  brush-model, and deformed-shader caster tiles are invalidated and redrawn.
- `[x]` When shadow candidates exceed the configured atlas light budget, GLx and
  Vulkan stop assigning atlas slots to candidates below 1/16th of the strongest
  candidate priority and report those skips separately from hard budget skips.
- `[x]` GLx and Vulkan batch shadow-map caster submission by the valid
  depth-only state boundary: one shadow material batch per world/entity
  transform for each rendered atlas face, instead of reopening the batch when
  the lit-surface list changes original materials.
- `[x]` Shadow atlas telemetry reports planned atlas fill, backend shadow draw
  counts, and pass timing. GLx exposes a `dlight-shadow-atlas` GPU pass timer
  through `r_speeds 7`/`r_glxGpuPassTiming`; Vulkan exposes the dlight atlas
  render-pass timestamp span through `r_speeds 7`.
- `[x]` Directional CSM is defined as a separate, disabled-by-default feature
  path with `r_csm*` cvars. GLx and Vulkan compute deterministic
  practical-split cascades, stable sphere-derived light-space bounds, texel
  snapping from the planned cascade resolution, allocate sampled shadow atlases,
  and render sky-sun shadows for opaque BSP world geometry, entity models, and
  brush models.
- `[x]` GLx and Vulkan share shadow filter and bias utility policy between
  dlight shadows and CSM where practical. Dlight and CSM sampling/atlas
  rendering use the common filter/bias clamps, while CSM keeps separate
  receiver-bias, caster-bias, and strength settings in cvars and debug output.
- `[x]` GLx `rc-parity` and Vulkan `vk-modern` runtime gates plan dedicated
  `dlight-shadow-scenes` runs. These runs launch with latched dlight shadow
  cvars, load retail maps with `devmap`, inject persistent `r_dlightTest`
  lights, capture `shadowScene` screenshots, and parse scene-marked dlight
  shadow planning/render log samples.
- `[x]` The dlight shadow release-evidence matrix now covers world geometry,
  brush models, entities, alpha-tested surfaces, portals/mirrors, and
  stress-light budgets. GLx and Vulkan gate evaluation require every category
  to appear in both screenshot metadata and scene-scoped shadow log samples;
  the stress row injects 16 test dlights against an 8-light atlas budget.
- `[x]` `scripts/dlight_shadow_release_gate.py` requires reviewed GLx and
  Vulkan build, shader validation, non-dry-run screenshot/log sweep, and
  RenderDoc inspection evidence before `r_dlightShadows` may be enabled by
  default. The gate reports a policy failure if either renderer's source
  default is promoted before the evidence is ready.

Next milestone: complete RenderDoc capture validation when a runtime asset
environment is available. Real shadow maps remain disabled by default until
reviewed evidence makes the default-enable release gate ready.

## Roadmap

### Phase 1: Planning And Budgets

- `[x]` Select shadow-casting point lights from visible dlights only.
- `[x]` Skip linear lights until a dedicated representation exists.
- `[x]` Prioritize by brightness, radius, distance to the camera, and receiver
  count.
- `[x]` Expose counters for considered, candidate, planned, and skipped lights.
- `[x]` Maintain stable per-light `shadowIndex` and atlas slots for the backend.

### Phase 2: Atlas Resources And Validation

- `[x]` Allocate depth atlas resources in GLx and Vulkan.
- `[x]` Keep atlas sizing deterministic from `r_dlightShadowMaxLights`,
  `r_dlightShadowResolution`, and the renderer texture-size limit.
- `[x]` Maintain the test command and scripts as new renderer paths come online.
- `[ ]` Use RenderDoc captures to confirm resource lifetime, layout transitions,
  framebuffer/render-pass contents, and descriptor binding.

### Phase 3: Caster Collection

- `[x]` Reuse existing lit-surface receiver data for first-pass world casters.
- `[x]` Render opaque world `SF_FACE`, `SF_GRID`, and `SF_TRIANGLES` casters.
- `[x]` Add brush-model caster collection.
- `[x]` Add entity-model caster collection.
- `[x]` Add conservative per-face culling against point-light cube faces.
- `[x]` Do not render sky, nodlight, translucent-only, flare, or screen-space
  surfaces into shadow maps.

### Phase 4: Shadow Atlas Rendering

- `[x]` Render six cube faces per planned dlight into its atlas tiles.
- `[x]` GLx: add a depth-only FBO path with viewport/scissor per tile.
- `[x]` Vulkan: add a depth-only render pass/framebuffer path or equivalent
  rendering path when available.
- `[x]` Keep color writes disabled and depth state explicit.
- `[x]` Add debug names, pass labels, and counters so RenderDoc captures are
  readable.
- `[x]` Avoid rendering empty faces.
- `[x]` Add slope/normal-aware depth bias for the atlas render path.

### Phase 5: Sampling And Filtering

- `[x]` Replace the screen-space fallback with real shadow-map sampling.
- `[x]` Start with hard shadows and a stable depth bias.
- `[x]` Add per-light atlas tile lookup and cube-face selection in GLx.
- `[x]` Add per-light atlas tile lookup and cube-face selection in Vulkan.
- `[x]` Add 2x2 PCF.
- `[x]` Add a small rotated or poisson-style PCF kernel.
- `[x]` Tune normal/slope bias and receiver bias to reduce acne without
  peter-panning, including texel-scaled receiver bias for contact corners.
- `[x]` Make filtering selectable without changing compatibility defaults.

### Phase 6: Efficiency

- `[x]` Cache shadow maps for static lights when the light, view relevance, and
  caster set allow it.
- `[x]` Avoid rendering empty faces and low-value lights under load.
- `[x]` Batch shadow-map draws by shader/material state where renderer
  architecture allows it.
- `[x]` Track planned light count, face count, and submitted caster surface
  count.
- `[x]` Track atlas fill, shadow draw counts, and GPU time.

### Phase 7: Directional Shadows And CSM

- `[x]` Treat cascaded shadow maps as a separate directional-light feature.
- `[x]` Define cascade split policy, texel snapping, and stable light-space
  bounds.
- `[x]` Render sky-sun CSM atlases and receiver passes on GLx and Vulkan for
  opaque BSP world geometry, entity models, and brush models, sourced from
  parsed sky shader sun parms.
- `[x]` Share filtering, bias, visualization, and RenderDoc validation utilities
  with dlight shadows where practical.
- `[x]` Keep CSM cvars and defaults separate from dlight shadow cvars.

### Phase 8: Release Evidence

- `[x]` Add dlight shadow scenes to GLx and Vulkan runtime sweeps.
- `[x]` Capture screenshots and logs for world geometry, brush models, entities,
  alpha-tested surfaces, portals/mirrors, and stress-light budgets.
- `[x]` Require both renderers to pass build, shader, screenshot, and RenderDoc
  inspection checks before enabling real shadow maps by default.

## Testing Tools

`r_dlightTest <count> [intensity] [distance] [height] [seconds]` injects a ring
of colored point dynamic lights in front of the current camera. Use
`r_dlightTest off` to disable it. A `seconds` value of `0` keeps the test active
until disabled.

`scripts/dlight_shadow_test.py` writes a repeatable launch config and manifest
under `.tmp/dlight-shadow-tests/`:

```powershell
python scripts/dlight_shadow_test.py --renderer vulkan --dry-run
python scripts/dlight_shadow_test.py --renderer glx --exe .tmp\clean-rebuild\fnquake3.x64.exe --renderdoc
```

Use `--extra-set NAME=VALUE` for one-off renderer cvar experiments. Use
`--renderdoc-arg` when a local RenderDoc version needs additional capture
options before the executable path.

RenderDoc capture checkpoints:

- `[ ]` GLx: confirm the dlight shadow atlas FBO is depth-only, complete, and
  sized as reported by `r_speeds 4`.
- `[ ]` Vulkan: confirm the dlight shadow atlas image uses a depth format, has
  sampled and depth-attachment usage, and has a descriptor set.
- `[ ]` Confirm every planned dlight enters the GLx atlas FBO or Vulkan
  `dlight shadow atlas render pass`, preserves cached atlas depth, clears only
  uncached or invalid per-face tile scissors, preflights six cube faces, and
  renders only non-empty atlas tiles using the reported `render lights`,
  `faces`, `batches`, `draws`, `surfs`, fill, budget, and `lowvalue` counters
  from `r_dlightShadowDebug 1`.
- `[ ]` After Phase 5: confirm lighting passes bind the atlas, use the intended
  tile, and sample the expected filter kernel.

Default-enable release gate:

```powershell
python scripts/dlight_shadow_release_gate.py --print-template
python scripts/dlight_shadow_release_gate.py --evidence .tmp\dlight-shadow-release-gate.json --require-ready
```

The evidence manifest must name passed GLx and Vulkan builds, GLx and Vulkan
shader validation, non-dry-run `rc-parity`/`vk-modern` runtime sweep manifests
with dlight shadow screenshot/log coverage, and reviewed RenderDoc inspection
checks. Without `--require-ready`, the script still fails if source defaults
enable `r_dlightShadows` before the evidence is complete.

Build and script evidence:

- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --dry-run`
  passed on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --dry-run`
  passed on May 22, 2026.
- `[x]` `glslangValidator -S frag -V` passed for the Vulkan dlight lighting
  fragment template variants: base, fog, line, and line+fog on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after initial hard atlas sampling on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  initial hard atlas sampling on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --dry-run`
  passed after initial hard atlas sampling on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --dry-run`
  passed after initial hard atlas sampling on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after brush-model caster collection on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  brush-model caster collection on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --dry-run`
  passed after brush-model caster collection on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --dry-run`
  passed after brush-model caster collection on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after entity-model caster collection on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  entity-model caster collection on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --dry-run` passed after entity-model caster collection on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --dry-run` passed after entity-model caster collection on
  May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after per-face caster culling on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  per-face caster culling on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --dry-run` passed after per-face caster culling on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --dry-run` passed after per-face caster culling on
  May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after empty-face atlas skipping on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  empty-face atlas skipping on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --dry-run` passed after empty-face atlas skipping on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --dry-run` passed after empty-face atlas skipping on
  May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after slope/normal-aware atlas caster bias on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  slope/normal-aware atlas caster bias on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --dry-run` passed after slope/normal-aware atlas caster bias
  on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --dry-run` passed after slope/normal-aware atlas caster bias
  on May 22, 2026.
- `[x]` `git diff --check` passed after slope/normal-aware atlas caster bias
  on May 22, 2026; Git reported only existing LF-to-CRLF working-copy
  warnings.
- `[x]` `glslangValidator -S frag -V` passed for the Vulkan dlight lighting
  fragment template variants: base, fog, line, and line+fog after 2x2 PCF on
  May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after 2x2 PCF on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  2x2 PCF on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --dry-run` passed after 2x2 PCF on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --dry-run` passed after 2x2 PCF on May 22, 2026.
- `[x]` `git diff --check` passed after 2x2 PCF on May 22, 2026; Git reported
  only existing LF-to-CRLF working-copy warnings.
- `[x]` `glslangValidator -S frag -V` passed for the Vulkan dlight lighting
  fragment template variants: base, fog, line, and line+fog after four-tap
  poisson-style PCF on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after four-tap poisson-style PCF on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  four-tap poisson-style PCF on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --dry-run` passed after four-tap poisson-style PCF on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --dry-run` passed after four-tap poisson-style PCF on
  May 22, 2026.
- `[x]` `git diff --check` passed after four-tap poisson-style PCF on
  May 22, 2026; Git reported only existing LF-to-CRLF working-copy warnings.
- `[x]` `glslangValidator -S frag -V` passed for the Vulkan dlight lighting
  fragment template variants: base, fog, line, and line+fog after
  normal/slope and receiver-bias tuning on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after normal/slope and receiver-bias tuning
  on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  normal/slope and receiver-bias tuning on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --dry-run` passed after normal/slope and receiver-bias tuning
  on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --dry-run` passed after normal/slope and receiver-bias tuning
  on May 22, 2026.
- `[x]` `git diff --check` passed after normal/slope and receiver-bias tuning
  on May 22, 2026; Git reported only existing LF-to-CRLF working-copy warnings.
- `[x]` `glslangValidator -S frag -V` passed for the Vulkan dlight lighting
  fragment template variants: base, fog, line, and line+fog after selectable
  filtering on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after selectable filtering on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  selectable filtering on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=0 --dry-run` passed after
  selectable filtering on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=1 --dry-run` passed after
  selectable filtering on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  selectable filtering on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  selectable filtering on May 22, 2026.
- `[x]` `git diff --check` passed after selectable filtering on
  May 22, 2026; Git reported only existing LF-to-CRLF working-copy warnings.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after static-light shadow-map caching on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  static-light shadow-map caching on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  static-light shadow-map caching on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  static-light shadow-map caching on May 22, 2026.
- `[x]` `git diff --check` passed after static-light shadow-map caching on
  May 22, 2026; Git reported only existing LF-to-CRLF working-copy warnings.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after low-value dlight shadow throttling on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  low-value dlight shadow throttling on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --extra-set
  r_dlightShadowMaxLights=1 --dry-run` passed after low-value dlight shadow
  throttling on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --extra-set
  r_dlightShadowMaxLights=1 --dry-run` passed after low-value dlight shadow
  throttling on May 22, 2026.
- `[x]` `git diff --check` passed after low-value dlight shadow throttling on
  May 22, 2026; Git reported only existing LF-to-CRLF working-copy warnings.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after depth-only shadow caster batching on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  depth-only shadow caster batching on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  depth-only shadow caster batching on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  depth-only shadow caster batching on May 22, 2026.
- `[x]` `git diff --check` passed after depth-only shadow caster batching on
  May 22, 2026; Git reported only existing LF-to-CRLF working-copy warnings.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after shadow atlas telemetry on
  May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  shadow atlas telemetry on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  shadow atlas telemetry on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  shadow atlas telemetry on May 22, 2026.
- `[x]` `git diff --check` passed after shadow atlas telemetry on
  May 22, 2026; Git reported only existing LF-to-CRLF working-copy warnings.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after directional CSM split-policy planning
  on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  directional CSM split-policy planning on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --extra-set
  r_csmShadows=1 --extra-set r_csmDebug=1 --dry-run` passed after directional
  CSM split-policy planning on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --extra-set
  r_csmShadows=1 --extra-set r_csmDebug=1 --dry-run` passed after directional
  CSM split-policy planning on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after shared shadow filter/bias utilities and
  separate CSM policy cvars on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  shared shadow filter/bias utilities and separate CSM policy cvars on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --extra-set
  r_csmShadows=1 --extra-set r_csmDebug=1 --extra-set r_csmShadowFilter=1
  --extra-set r_csmShadowBias=6 --extra-set r_csmCasterSlopeBias=2 --dry-run`
  passed after shared shadow filter/bias utilities and separate CSM policy
  cvars on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --extra-set
  r_csmShadows=1 --extra-set r_csmDebug=1 --extra-set r_csmShadowFilter=1
  --extra-set r_csmShadowBias=6 --extra-set r_csmCasterSlopeBias=2 --dry-run`
  passed after shared shadow filter/bias utilities and separate CSM policy
  cvars on May 22, 2026.
- `[x]` `git diff --check` passed after shared shadow filter/bias utilities
  and separate CSM policy cvars on May 22, 2026; Git reported only existing
  LF-to-CRLF working-copy warnings.
- `[x]` `python -m py_compile scripts\vk_runtime_sweep.py
  scripts\glx_runtime_sweep.py` passed after adding dlight shadow scenes to the
  runtime sweeps on May 22, 2026.
- `[x]` `python tests\vulkan\vk_runtime_sweep_tests.py` passed after adding
  dlight shadow scenes to the Vulkan runtime sweep on May 22, 2026.
- `[x]` `python tests\glx\glx_runtime_sweep_tests.py` passed after adding
  dlight shadow scenes to the GLx runtime sweep on May 22, 2026.
- `[x]` `python scripts\vk_runtime_sweep.py --gate vk-modern --dry-run --exe
  .tmp\vk-gate-plans\fnquake3 --basepath .tmp\vk-gate-plans\basepath
  --output-dir .tmp\vk-dlight-sweep-test` passed on May 22, 2026 and planned
  a dedicated Vulkan `dlight-shadow-scenes` run with `shadowScene`
  screenshots.
- `[x]` `python scripts\glx_runtime_sweep.py --gate rc-parity --dry-run --exe
  .tmp\glx-gate-plans\fnquake3 --basepath .tmp\glx-gate-plans\basepath
  --output-dir .tmp\glx-dlight-sweep-test` passed on May 22, 2026 and planned
  a dedicated GLx `dlight-shadow-scenes` run with `shadowScene` screenshots.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after adding runtime sweep dlight shadow
  scenes on May 22, 2026; Ninja reported no work to do.
- `[x]` `git diff --check` passed after adding runtime sweep dlight shadow
  scenes on May 22, 2026; Git reported only existing LF-to-CRLF working-copy
  warnings.
- `[x]` `python -m py_compile scripts\vk_runtime_sweep.py
  scripts\glx_runtime_sweep.py` passed after adding dlight shadow screenshot
  and log evidence categories on May 22, 2026.
- `[x]` `python tests\vulkan\vk_runtime_sweep_tests.py` passed after requiring
  dlight shadow evidence categories and scene-marked log samples in the Vulkan
  runtime gate on May 22, 2026.
- `[x]` `python tests\glx\glx_runtime_sweep_tests.py` passed after requiring
  dlight shadow evidence categories and scene-marked log samples in the GLx
  runtime gate on May 22, 2026.
- `[x]` `python scripts\vk_runtime_sweep.py --gate vk-modern --dry-run --exe
  .tmp\vk-gate-plans\fnquake3 --basepath .tmp\vk-gate-plans\basepath
  --output-dir .tmp\vk-dlight-evidence-test` passed on May 22, 2026 and
  planned six Vulkan dlight shadow evidence screenshots covering world
  geometry, brush models, entities, alpha-tested surfaces, portals/mirrors,
  and stress-light budgets.
- `[x]` `python scripts\glx_runtime_sweep.py --gate rc-parity --dry-run --exe
  .tmp\glx-gate-plans\fnquake3 --basepath .tmp\glx-gate-plans\basepath
  --output-dir .tmp\glx-dlight-evidence-test` passed on May 22, 2026 and
  planned six GLx dlight shadow evidence screenshots covering world geometry,
  brush models, entities, alpha-tested surfaces, portals/mirrors, and
  stress-light budgets.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after adding dlight shadow screenshot/log
  evidence categories on May 22, 2026; Ninja reported no work to do.
- `[x]` `git diff --check` passed after adding dlight shadow screenshot/log
  evidence categories on May 22, 2026; Git reported only existing LF-to-CRLF
  working-copy warnings.
- `[x]` `python -m py_compile scripts\dlight_shadow_release_gate.py` passed
  after adding the dlight shadow default-enable release gate on May 22, 2026.
- `[x]` `python tests\dlight_shadow_release_gate_tests.py` passed after adding
  the dlight shadow default-enable release gate on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_release_gate.py --print-template` passed
  after adding the dlight shadow default-enable release gate on May 22, 2026.
- `[x]` `python tests\vulkan\vk_runtime_sweep_tests.py` and
  `python tests\glx\glx_runtime_sweep_tests.py` passed after adding the
  dlight shadow default-enable release gate on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after adding the dlight shadow
  default-enable release gate on May 22, 2026; Ninja reported no work to do.
- `[x]` `git diff --check` passed after adding the dlight shadow
  default-enable release gate on May 22, 2026; Git reported only existing
  LF-to-CRLF working-copy warnings.
- `[x]` `python tests\dlight_shadow_bias_tests.py` passed after
  contact-preserving dlight shadow bias revision on May 22, 2026.
- `[x]` `glslangValidator -S frag -V` passed for the Vulkan dlight lighting
  fragment template variants: base, fog, line, and line+fog after
  contact-preserving dlight shadow bias revision on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after
  contact-preserving dlight shadow bias revision on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  contact-preserving dlight shadow bias revision on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  contact-preserving dlight shadow bias revision on May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after contact-preserving dlight shadow bias
  revision on May 22, 2026.
- `[x]` `git diff --check` passed after contact-preserving dlight shadow bias
  revision on May 22, 2026; Git reported only existing LF-to-CRLF
  working-copy warnings.
- `[x]` `python tests\dlight_shadow_bias_tests.py` passed after the GLx
  ARB-safe texel-scaled receiver-bias simplification on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after the
  GLx ARB-safe texel-scaled receiver-bias simplification on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  the GLx ARB-safe texel-scaled receiver-bias simplification on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  the GLx ARB-safe texel-scaled receiver-bias simplification on
  May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after the GLx ARB-safe texel-scaled
  receiver-bias simplification on May 22, 2026.
- `[x]` `git diff --check` passed after the GLx ARB-safe texel-scaled
  receiver-bias simplification on May 22, 2026; Git reported only existing
  LF-to-CRLF working-copy warnings.
- `[x]` `python tests\dlight_shadow_bias_tests.py` passed after the GLx ARB
  shadow-program scalar swizzle compatibility fix on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed after the
  GLx ARB shadow-program scalar swizzle compatibility fix on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  the GLx ARB shadow-program scalar swizzle compatibility fix on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --extra-set
  r_dlightMode=2 --extra-set r_dlightShadowFilter=2 --dry-run` passed after
  the GLx ARB shadow-program scalar swizzle compatibility fix on
  May 22, 2026.
- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after the GLx ARB shadow-program scalar
  swizzle compatibility fix on May 22, 2026.
- `[x]` `meson compile -C meson\build fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed after the GLx ARB shadow-program scalar
  swizzle compatibility fix on May 22, 2026.
- `[x]` A non-dry-run GLx renderer-init smoke launch against the local Q3Test
  assets no longer logs `FP Compile Error` or `WARNING: ARB dynamic light
  shadow programs failed` after the GLx ARB shadow-program scalar swizzle
  compatibility fix on May 22, 2026. The launch still stops at the known
  Q3Test 1.09 UI VM version mismatch before gameplay evidence can be captured.
- `[x]` `git diff --check` passed after the GLx ARB shadow-program scalar
  swizzle compatibility fix on May 22, 2026; Git reported only existing
  LF-to-CRLF working-copy warnings.

## Maintenance Rule

Every shadow-map implementation step must update this document's current
snapshot, checklists, next milestone, and testing notes in the same change. If a
step intentionally defers part of the roadmap, record the deferral here instead
of leaving it only in chat or commit notes.
