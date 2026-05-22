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
- `[x]` GLx and Vulkan render planned dlight atlas tiles with opaque world
  `SF_FACE`, `SF_GRID`, and `SF_TRIANGLES` casters from existing lit-surface
  lists.
- `[x]` `r_dlightTest` injects repeatable test dynamic lights from the renderer.
- `[x]` `scripts/dlight_shadow_test.py` generates GLx/Vulkan shadow test
  launches, manifests, dry-runs, and optional RenderDoc wrapping.
- `[x]` `r_dlightShadowDebug 1` reports planning counters plus atlas render
  counters: `render lights`, `faces`, and `surfs`.
- `[ ]` Lighting does not yet sample the atlas. The visible shadowing path still
  uses the temporary screen-space fallback.
- `[ ]` Brush-model casters are not rendered into the atlas yet.
- `[ ]` Entity-model casters are not rendered into the atlas yet.
- `[ ]` Per-face caster culling is not implemented yet.
- `[ ]` PCF/filtering and CSM work have not started.

Next milestone: replace the screen-space fallback with initial hard shadow-map
sampling from the atlas, while preserving the world-caster render path for
RenderDoc inspection.

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
- `[ ]` Add brush-model caster collection.
- `[ ]` Add entity-model caster collection.
- `[ ]` Add conservative per-face culling against point-light cube faces.
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
- `[ ]` Avoid rendering empty faces.
- `[ ]` Add slope/normal-aware depth bias for the atlas render path.

### Phase 5: Sampling And Filtering

- `[ ]` Replace the screen-space fallback with real shadow-map sampling.
- `[ ]` Start with hard shadows and a stable depth bias.
- `[ ]` Add per-light atlas tile lookup and cube-face selection in GLx.
- `[ ]` Add per-light atlas tile lookup and cube-face selection in Vulkan.
- `[ ]` Add 2x2 PCF.
- `[ ]` Add a small rotated or poisson-style PCF kernel.
- `[ ]` Tune normal/slope bias and receiver bias to reduce acne without
  peter-panning.
- `[ ]` Make filtering selectable without changing compatibility defaults.

### Phase 6: Efficiency

- `[ ]` Cache shadow maps for static lights when the light, view relevance, and
  caster set allow it.
- `[ ]` Avoid rendering empty faces and low-value lights under load.
- `[ ]` Batch shadow-map draws by shader/material state where renderer
  architecture allows it.
- `[x]` Track planned light count, face count, and submitted caster surface
  count.
- `[ ]` Track atlas fill, shadow draw counts, and GPU time.

### Phase 7: Directional Shadows And CSM

- `[x]` Treat cascaded shadow maps as a separate directional-light feature.
- `[ ]` Define cascade split policy, texel snapping, and stable light-space
  bounds.
- `[ ]` Share filtering, bias, visualization, and RenderDoc validation utilities
  with dlight shadows where practical.
- `[ ]` Keep CSM cvars and defaults separate from dlight shadow cvars.

### Phase 8: Release Evidence

- `[ ]` Add dlight shadow scenes to GLx and Vulkan runtime sweeps.
- `[ ]` Capture screenshots and logs for world geometry, brush models, entities,
  alpha-tested surfaces, portals/mirrors, and stress-light budgets.
- `[ ]` Require both renderers to pass build, shader, screenshot, and RenderDoc
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
  `dlight shadow atlas render pass`, clears the atlas depth, and attempts six
  atlas tiles using the reported `render lights`, `faces`, and `surfs` counters
  from `r_dlightShadowDebug 1`.
- `[ ]` After Phase 5: confirm lighting passes bind the atlas, use the intended
  tile, and sample the expected filter kernel.

Build and script evidence:

- `[x]` `meson compile -C .tmp\meson-dlight fnquake3_glx_x86_64
  fnquake3_vulkan_x86_64` passed on May 22, 2026.
- `[x]` `python -m py_compile scripts\dlight_shadow_test.py` passed on
  May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer vulkan --dry-run`
  passed on May 22, 2026.
- `[x]` `python scripts\dlight_shadow_test.py --renderer glx --dry-run`
  passed on May 22, 2026.

## Maintenance Rule

Every shadow-map implementation step must update this document's current
snapshot, checklists, next milestone, and testing notes in the same change. If a
step intentionally defers part of the roadmap, record the deferral here instead
of leaving it only in chat or commit notes.
