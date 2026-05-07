# GLx Renderer Architecture Note

## Status

GLx is an experimental renderer module under active development. It is build-gated with `USE_GLX` and is not the default renderer.

## Decision

GLx keeps FnQuake3's existing renderer ABI intact:

- `REF_API_VERSION` stays at 8.
- `GetRefAPI` remains the only exported renderer entry point.
- The engine continues to communicate through `refimport_t` and `refexport_t`.
- `cl_renderer glx` loads a separate modular renderer named `fnquake3_glx_<arch>`.

The first implementation slice deliberately reuses the compatibility-proven OpenGL renderer as the rendering baseline and compiles it with `RENDERER_GLX`. GLx-specific code lives in `code/rendererglx/` and starts with capability detection, debug callback wiring, timer-query profiling, static-world cache telemetry, dynamic-stream strategy selection, and build-system integration.

## Capability Floor

The long-term GLx floor is shader-based OpenGL 2.1 with GLSL 1.20. Fixed-function fallback is not a goal for new GLx internals. Hardware below that line may continue to rely on legacy renderer paths while they exist.

GLx records one capability tier at OpenGL initialization:

- `compat`: OpenGL 2.1+ baseline.
- `core`: OpenGL 3.3+ or the equivalent map-buffer, UBO, and instancing feature set.
- `advanced`: persistent buffer storage, sync objects, and multi-draw indirect are available.

Hot renderer paths should consume this one-time tier decision instead of scattering extension checks through draw submission.

## Current Foundation

The bootstrap modules currently provide:

- `renderer_switch <renderer> [fast|keep_window|full]` in dynamic-renderer builds for runtime renderer reload/switch testing through the same lifecycle as `vid_restart`.
- `glxinfo` / `glxcaps` command output.
- `glxmaterial` command output for GLSL material program readiness, compile/link/precache failures, cache hits, bind counts, and the last material request.
- `glxpostprocess` command output for FBO readiness, internal render target sizing, HDR/render-scale state, final gamma output, bloom chain creation, bloom pass mode, and screen-map/MSAA/SSAA blits.
- `glxstaticworld [limit]`, `glxstaticworld hot [limit]`, `glxstaticworld commands [limit]`, and `glxstaticworld spans [limit]` command output for static-world cache, arena, queue, packet item ranges, draw-range inspection, packet heat ranking, indirect command inspection, and MDI span diagnostics.
- `glxstreamtest` developer command for exercising one dynamic stream reservation/upload/commit without changing scene rendering.
- `r_glxDebug` and `r_glxDebugVerbose` cvars for KHR_debug callback setup when the driver exposes it.
- `r_glxDebugGroups` for optional KHR_debug groups around GLx-observed shader batch submission.
- `r_glxGpuTiming` for non-blocking backend GPU timing with timer queries when supported.
- `r_glxPostProcessDebug` for optional logging of GLx-observed FBO, render-scale, gamma, and bloom parity events.
- `r_glxWorldRenderer` for enabling the compatibility-first GLx static world renderer bundle with per-draw fallback.
- `r_glxStaticWorldArena` for developer-only GLx-owned uploads of the packed legacy static world VBO/IBO payload.
- `r_glxStaticWorldArenaDraw` for developer-only binding of the GLx-owned static arena during legacy VBO draws.
- `r_glxStaticWorldDraw` for developer-only GLx submission of legacy-prepared static device-index runs.
- `r_glxStaticWorldSoftDraw` for routing static-world CPU-index fallback runs through the GLx dispatcher.
- `r_glxStaticWorldDrawPolicy` for restricting experimental GLx static draws to `full`, `contained`, or `all` packet ranges.
- `r_glxStaticWorldMultiDraw` for developer-only batching of same-state static device-index runs with `glMultiDrawElements`.
- `r_glxStaticWorldIndirectBuffer` for developer-only upload of the static packet command manifest into a GL-owned indirect command buffer without drawing from it yet.
- `r_glxStaticWorldIndirectDraw` for developer-only submission of full manifest-packet static draws through `glDrawElementsIndirect` when the command buffer is ready.
- `r_glxStaticWorldMultiDrawIndirect` for developer-only submission of contiguous full-packet static command spans through `glMultiDrawElementsIndirect`.
- `r_glxStaticWorldMultiDrawIndirectCompact` for developer-only upload of compact visible full-packet command batches when static command-buffer slots are not adjacent or not uploaded.
- `r_glxStaticWorldMultiDrawIndirectSpans` for developer-only splitting of filtered static batches into ordered MDI and fallback multidraw spans.
- `r_glxStreamMode` and `r_glxStreamMegabytes` for selecting and allocating the transient geometry stream ring.
- `r_glxStreamTess` for developer-only shadow uploads of legacy tessellation payloads through the GLx stream ring.
- `r_glxStreamDraw` for an experimental opt-in streamed draw path for eligible generic shader stages.
- `r_glxStreamDrawKeyMode` for narrowing or widening the streamed draw material-key allowlist during experiments.
- `r_glxStreamDrawMultitexture` for separately opting eligible fixed-function multitexture stages into the streamed draw experiment.
- `r_glxStreamDrawFog` for separately opting fog-only passes into the streamed draw experiment.
- `r_glxStreamDrawDepthFragment` for separately opting eligible depth-fragment stages into the streamed draw experiment.
- `r_glxMaterialRenderer` for using the independent GLSL material program path on streamed GLx draws when the driver can compile the complete compatibility shader set.
- `r_glxMaterialPrecache` for compiling every supported GLx material permutation at OpenGL startup so shader failures fall back before the first draw.
- `r_glxMaterialDebug` for material shader diagnostics, with level `2` dumping failed GLSL source.
- `r_speeds 7` output for GLx capability, backend timer, shader-batch counts, draw counts, postprocess/FBO/bloom counters, stream readiness/upload counters, static-world cache counters, packet lookup counters, and indirect-buffer readiness.
- Static-world VBO cache, packet-manifest, and queue-split accounting, shader-batch telemetry, and material-stage key telemetry from the existing OpenGL renderer paths.

This preserves compatibility while creating the measurement and capability surface needed for later GLx-only work.

## Implementation Map

The current C++ boundary is intentionally small and split by ownership:

- `glx_caps.*`: one-time OpenGL version, extension, feature, and capability-tier detection.
- `glx_debug.*`: KHR_debug callback, object labels, debug groups, and debug-output filtering.
- `glx_profiler.*`: backend frame counters, rotating timer-query collection, shader-batch/material telemetry, and draw-call/index counters.
- `glx_postprocess.*`: compatibility FBO lifecycle telemetry, render-scale/resolve counters, final gamma result tracking, and bloom parity accounting for the shared OpenGL postprocess path.
- `glx_static_world.*`: static BSP/VBO cache accounting, GLx-owned packet manifest snapshots, optional static arena uploads/draw binding, optional GLx device-run submission, and prepared-queue split telemetry.
- `glx_stream.*`: dynamic stream policy selection, buffer lifecycle, reservation/upload/commit API, and counters for persistent-map, map-range, or orphan/subdata paths.
- `glx_module.*`: the C ABI bridge used by the legacy renderer hooks.

`r_glxStreamMode auto` selects `persistent-map` only when buffer storage and sync objects are present, falls back to `map-range` when available, and otherwise uses the portable orphan/subdata path. Forced modes fall back rather than failing renderer initialization. The stream ring is allocated during OpenGL initialization and now exposes reserve/upload-at/commit primitives so one draw can safely upload several attribute ranges inside one contiguous reservation. When sync objects are available, frames that touched the stream insert a GL fence and the next stream reservation waits before reusing the reset frame range. Same-frame stream wraps are rejected instead of reusing the beginning of the ring while earlier draws from that frame may still be in flight; the caller falls back to the legacy draw path and the reject is counted separately from ordinary wraps. Scene draw submission still uses the legacy client-array path by default.

`r_glxStreamTess 1` enables shadow uploads from `RB_EndSurface`: after the legacy stage iterator has drawn a non-VBO tessellation batch, GLx uploads the batch's vertex and index payloads through the selected stream strategy and records upload pressure. The uploaded data is not used for drawing yet, so this mode is for development telemetry rather than visual parity testing.

`r_glxStreamDraw 1` enables the first guarded streamed draw experiment. By default only generic, single-texture, non-depth-fragment shader stages are eligible. The legacy renderer still computes colors, texcoords, state bits, texture binding, fog, dynamic lights, and fallback behavior; GLx uploads the already-computed xyz/color/texcoord arrays and index list into one stream reservation, binds that buffer for vertex and element arrays, draws from stream offsets, then restores the legacy CPU vertex/color/texcoord pointers. If any stream reservation or upload fails, the stage falls back to the existing `R_DrawElements` path.

`r_glxStreamDrawMultitexture 1` additionally allows eligible fixed-function multitexture stages through the same stream path. In that mode GLx uploads both texture coordinate bundles, binds both client texture-coordinate arrays from the stream buffer, and then restores the legacy unit-0 and unit-1 pointers. This is separately gated because it touches more GL client state and should be parity-tested independently from the single-texture path.

`r_glxStreamDrawFog 1` additionally allows the classic fog overlay pass to draw from the stream ring. The legacy renderer still computes fog colors, fog texture coordinates, texture binding, blend state, and depth-function selection; GLx only uploads the prepared xyz/color/fog-texcoord arrays plus indexes, draws from stream offsets, and restores the previous array and element buffer bindings before returning. This is separately gated because fog is a compatibility-visible overlay and should be checked independently from normal material stages.

`r_glxStreamDrawDepthFragment 1` additionally allows eligible single-texture `depthFragment` shader stages through the stream path. GLx uploads the prepared stage arrays once, issues the normal draw from stream offsets, then mirrors the legacy second pass by forcing depth writes, enabling the existing ARB sprite fragment program, and drawing the same streamed indexes again before restoring buffer and client-array state. This is separately gated because it changes a two-draw compatibility path and should be parity-tested independently from plain material stages.

`r_glxMaterialRenderer 1` makes streamed GLx draws bind GLSL material programs instead of relying on fixed-function texture combiners for the supported compatibility-stage shapes. The first material slice covers single-texture, fixed-function multitexture modulate/add/replace/decal, and fog-only stream passes. Texture coordinate generation, texmods, colors, state bits, alpha test, texture binding, and fallback ordering still come from the legacy renderer before GLx uploads the already-computed arrays, keeping the shader layer small while parity is measured. Startup precache compiles the whole supported set by default; if any program fails to compile or link, the material path reports `not-ready` and the stream draw caller falls back to the legacy path instead of discovering the failure mid-frame.

Postprocess parity is implemented by keeping the compatibility-proven OpenGL FBO and ARB-program postprocess path as the GLx baseline instead of introducing a second bloom algorithm. Under `RENDERER_GLX`, that shared path now reports FBO init/shutdown state, internal render/capture/window dimensions, HDR precision mode, internal render scaling, MSAA resolve blits, supersample capture blits, screen-map copies, final gamma output mode, minimized/screenshot fallback output, bloom chain allocation, and bloom execution. The counters distinguish `r_bloom 1` pre-final bloom from `r_bloom 2` final-pass bloom, record requested versus effective `r_bloom_passes`, and retain the active `r_bloom_blend_base`, `r_bloom_filter_size`, `r_bloom_threshold_mode`, `r_bloom_modulate`, `r_bloom_intensity`, and `r_bloom_reflection` values. This preserves the documented OpenGL bloom surface while making GLx failures visible through `glxpostprocess`, `glxinfo`, and `r_speeds 7`.

## Runtime Switching and Sweep Harness

Dynamic renderer builds now expose `renderer_switch <renderer> [fast|keep_window|full]`. It validates the renderer name, force-updates `cl_renderer`, and restarts the video subsystem through the existing `CL_Vid_Restart` path. A changed renderer still causes `CL_ShutdownRef` to unload the active renderer DLL, so switching exercises the same teardown, context/window handling, renderer registration, VM restart, screenshot, and cgame recovery behavior that manual `cl_renderer` plus `vid_restart` testing depends on.

`scripts/glx_runtime_sweep.py` automates the compatibility smoke pass that GLx needs before promotion. It writes generated configs under an isolated `.tmp/runtime-sweeps/<run-id>/home` fs_homepath, launches a built client with a selected renderer sequence, loads maps, switches renderers in-process, captures named PNG screenshots, runs GLx diagnostics after GLx captures, and records a JSON manifest plus logs. Demo sweeps run each selected renderer in its own timedemo process and rely on `nextdemo "quit"` so completed demos terminate cleanly.

Typical local run from the repository root:

```sh
python scripts/glx_runtime_sweep.py --exe code/win32/msvc2017/output/fnquake3.glx.x64.exe --basepath code/win32/msvc2017/output --renderers opengl,glx --switch-sequence opengl,glx,opengl,glx --maps q3dm1 --demos demo1
```

Use `--profile baseline` for a conservative renderer-switch check, `--profile glx-parity` for the current world/material/bloom parity surface, or `--profile glx-stress` to include the indirect static-world paths. `--dry-run` writes the configs and manifest without launching the engine, which is useful on machines without retail assets installed. VS Code also has a `Release: Runtime Sweep x64 GLx` task that builds the x64 GLx client and runs the default `q3dm1` screenshot switch sweep.

`r_glxStreamDrawKeyMode` controls the material-key allowlist used after the hard eligibility checks:

- `0`: plain keys only, rejecting texmods and special dynamic bundles.
- `1`: computed keys, allowing texmods while still rejecting video, screen-map, dynamic-light, and environment cases.
- `2`: all currently eligible single-texture generic stages.

Stream draw counters report accepted/rejected material keys and skip reasons for ineligible stages, including missing buffer binding support, multitexture, depth-fragment gating, missing texcoords, empty batches, material-key rejection, and fog-gate rejection. They also split out second-texture-coordinate upload pressure, multitexture draw count, fog draw count, and depth-fragment streamed stage count.

Draw telemetry is recorded from the existing renderer hot paths: client-array draws through `R_DrawElements`, static-world device-index VBO draws, and static-world soft-index VBO draws. Material-stage telemetry is recorded from the generic and VBO stage iterators before each legacy pass binds state and submits indexes. It tracks fixed-function state bits, color/alpha generators, texture coordinate generators, texmod counts, multitexture, depth-fragment, blend, alpha-test, depth-write, lightmap, animated-image, video, screen-map, dynamic-light, and environment flags, plus a small fixed hot-key table by index pressure. `r_glxDebugGroups 1` wraps shader batches in KHR_debug groups when the extension functions are available, which helps external GL debuggers correlate driver output with id Tech 3 shader names.

Shader-batch telemetry is recorded at `RB_EndSurface` before the existing stage iterator runs. It tracks batch count, vertex/index pressure, total stage passes, pass-count histogram, sort histogram, fog/multitexture/polygon-offset flags, VBO vs generic batches, largest batch, and a small fixed top-shader table by index pressure. Material-stage telemetry complements that batch view with per-pass keys so later streamed draw and GLSL permutation work can target the most common compatibility shapes first.

Static-world packet telemetry is recorded when the legacy VBO builder has packed static BSP surfaces by shader at map load. GLx now snapshots one packet per sorted shader group with shader name, sort, surface/vertex/index pressure, packed vertex/index offsets and byte spans, stage-pass count, and batch flags. It also derives one `DrawElementsIndirect`-shaped command record per valid packet, including index count and first-index offset, while reporting invalid or misaligned packet records separately. Packet output includes the compact command index so packet-owned submission can move from a manifest packet to a command-buffer slot deterministically. `r_glxStaticWorldIndirectBuffer 1` uploads the compact valid-command list into a `GL_DRAW_INDIRECT_BUFFER` when the driver exposes draw-indirect support, preserving the previous binding and labeling the buffer for GL debuggers.

`r_glxWorldRenderer 1` enables the parity-oriented static-world GLx bundle. It implies static arena upload, arena binding, device-index run dispatch, ordered multidraw batching when available, soft-index dispatch, and an effective `all` draw policy for device runs. The compatibility renderer still owns world visibility, shader sorting, stage iteration, fog setup, texture binding, ARB program setup, debug overlays, and fallback order; GLx owns the buffer/draw submission edge and returns to the legacy path for any unsupported draw. This is the intended switch for whole-world parity testing because it avoids needing to hand-compose the lower-level experimental cvars. It requires the static VBO world cache, so use it with `r_vbo 1` before map load or `vid_restart`.

`r_glxStaticWorldArena 1` additionally uploads the already-packed legacy static world vertex and index payloads into GLx-owned buffer objects after the legacy VBO upload succeeds. This does not draw anything by itself and it does not replace `VBO_world_data` / `VBO_world_indexes`; it is a developer-only ownership bridge so GLx can validate buffer lifetime, memory pressure, and binding preservation before any static-world draw takeover. It is implied by `r_glxWorldRenderer`.

`r_glxStaticWorldArenaDraw 1` lets the existing legacy VBO stage iterator bind the GLx-owned static arena buffers when they are available. Shader state, sort order, queue preparation, and draw calls still use the compatibility renderer path; only the bound vertex/index buffer object handles change. If the arena is not ready, GLx reports a draw skip and the bind helpers keep using the legacy buffers. It is implied by `r_glxWorldRenderer`.

Static-world queue telemetry now classifies every prepared device-index run against the packet manifest before any experimental draw cvar is considered. GLx builds a fixed item-index-to-packet lookup while recording the manifest, uses it for the common first/last item range classification path, and falls back to byte-span scanning when a range is missing, overflowing, or inconsistent. It also measures how visible full-packet runs line up with the compact indirect command buffer: contiguous command runs, command count, covered indexes, breaks, and largest adjacent command run are reported for both the last queue and cumulative totals. `glxstaticworld` and `r_speeds 7` report full-packet, partial-packet, miss, item-mismatch, lookup-hit, lookup-fallback, and indirect-command adjacency counts so the next packet-level draw work can be guided by real visibility behavior instead of assumptions. The packet list also accumulates per-packet queue and draw heat (`q` full/partial runs, `d` full/partial draws, and manifest-owned draw indexes), while `glxstaticworld hot [limit]` ranks packets by weighted queue/draw pressure to identify stable candidates for later packet-level submission.

`r_glxStaticWorldDraw 1` routes static-world device-index VBO runs through the GLx static draw dispatcher after the legacy renderer has prepared queue runs and bound the stage state. The dispatcher validates each submitted byte range and queued item range against the GLx static packet manifest, records full-packet, partial-packet, miss, item-mismatch, and arena-vs-legacy-buffer counters, issues the same `glDrawElements` call, and returns control to the VBO iterator for later shader stages. If disabled or rejected, the original VBO draw call remains the fallback path. It is implied by `r_glxWorldRenderer`.

`r_glxStaticWorldSoftDraw 1` routes the short-run CPU-index fallback path through GLx as well. These draws intentionally do not use packet substitution because the software index buffer can contain a stitched list of visible items; GLx submits the same client index span that the legacy VBO path would have submitted and reports soft-draw call/index/fallback counters. It is implied by `r_glxWorldRenderer`.

`r_glxStaticWorldDrawPolicy` defaults to `full`, which means GLx only submits runs that exactly match one manifest packet. For full-packet runs, GLx issues the draw from its own manifest packet offset and index count rather than the legacy run fields, so the static-world handoff is now packet-owned while still protected by legacy queue validation. `contained` also allows partial visibility ranges that remain inside a packet, while `all` submits any valid legacy device run and is mainly useful for parity and broad dispatcher comparisons. `r_glxWorldRenderer` uses an effective `all` policy. Policy skips are counted separately from GL function or validation fallbacks.

`r_glxStaticWorldIndirectDraw 1` lets the single-run GLx dispatcher submit full manifest-packet static draws with `glDrawElementsIndirect` when `r_glxStaticWorldIndirectBuffer` has successfully uploaded the command buffer. It is stricter than the normal GLx static draw dispatcher: partial packet runs, item mismatches, missing command slots, missing function pointers, or GL errors fall back to the existing manifest-owned `glDrawElements` path. The draw-indirect binding is restored around each experimental submission.

`r_glxStaticWorldMultiDraw 1` lets GLx collapse eligible same-state static device-index runs from one VBO queue into one or more `glMultiDrawElements` calls when the driver exposes it. Each run carries its original VBO item range so GLx can classify whether visibility produced complete shader packets or partial packet runs. Multidraw is now filtered instead of all-or-nothing: GLx marks only the runs it actually submits, and the VBO iterator keeps rendering the remaining runs through the single-run GLx dispatcher or the original per-run `glDrawElements` loop. Non-eligible runs are treated as order barriers: GLx flushes any pending eligible batch before the barrier and leaves that barrier plus later runs to the legacy loop, so the experimental filtered path cannot move a later fast-path draw ahead of an earlier fallback draw. With broader policies such as `contained` or `all`, partial-but-allowed runs can still stay inside the ordered GLx span walker. It is implied by `r_glxWorldRenderer`.

`r_glxStaticWorldMultiDrawIndirect 1` adds an even narrower filtered-batch path on top of `r_glxStaticWorldMultiDraw`: if every run in a flushed filtered batch is a full manifest packet and those packets map to adjacent command-buffer slots, GLx submits that batch with one `glMultiDrawElementsIndirect` call. If the batch is partial, missing a command, non-adjacent, unsupported, or hits a GL error, GLx falls back to the existing `glMultiDrawElements` filtered batch without changing the draw order.

`r_glxStaticWorldMultiDrawIndirectCompact 1` lets that same MDI gate upload a compact per-batch command list for full manifest packets that are visible in a non-adjacent order, or when the static command buffer was not uploaded. This preserves the VBO queue order by copying only the selected packet commands into a small `GL_DRAW_INDIRECT_BUFFER` immediately before the call. The compact command buffer is reused when possible: after an initial `glBufferData` allocation, later batches use `glBufferSubData` if the driver exposes it and the existing scratch capacity is large enough. When KHR_debug object labels are available, the lazily-created compact command buffer is labeled after the filtered submission path observes it. It remains separately gated because it trades fewer draw calls for per-batch command-buffer uploads and needs real-map telemetry before becoming a preferred path.

`r_glxStaticWorldMultiDrawIndirectSpans 1` lets GLx split one filtered static multidraw batch into ordered spans before submission. Consecutive full-manifest spans try the MDI path, while consecutive non-manifest spans use the existing `glMultiDrawElements` fallback; if no useful span is found, GLx keeps the original whole-batch filtered multidraw behavior. This is useful with broader draw policies such as `contained` or `all`, where one partial packet should not prevent neighboring full-packet spans from exercising the indirect path. One-run outer spans are now submitted immediately in queue order instead of being deferred to the caller's later per-run fallback loop. When compact MDI is disabled but the static indirect command buffer is ready, full-manifest spans can also split into adjacent command subspans. Singleton command gaps are submitted in order through the existing `r_glxStaticWorldIndirectDraw` single-draw path when it is enabled and ready, otherwise as ordinary GLx single draws, then neighboring adjacent command spans can still use MDI without perturbing the original visible order. The MDI submitter now refuses the path unless the one-time GLx capability table advertises multi-draw-indirect support, rather than trusting function-pointer presence alone.

The MDI counters intentionally split rejection reasons into unsupported/missing command-buffer state, short batches, non-manifest packet runs, missing command slots, non-contiguous command spans, compact upload failures, and GL errors. They also remember the most recent rejection reason, rejected run/index pressure, rejected command slot, last outer span shape, largest outer span split, how many one-run spans were submitted directly or through single-run indirect draws, and the concrete command ranges from the most recent visible queue. `glxstaticworld spans [limit]` prints this focused view so real-map tuning can distinguish capability gaps, visibility-order gaps, compact-upload pressure, and actual GL failures without stepping through the renderer.

The MDI diagnostics also remember the last successful source (`static` command buffer or compact upload), last run/index pressure, first static command slot when applicable, largest index span, and the last command-subspan split shape. This makes runtime tuning possible from `glxstaticworld` or `r_speeds 7` without stepping through the renderer.

Static-world queue telemetry is recorded after the legacy VBO queue sorter has grouped visible static surfaces for a shader batch. It tracks total prepared queues, last queued item/index pressure, device-index run count, soft-index fallback pressure, and largest contiguous device-index run. This measures the exact legacy split that a future GLx-owned static arena or indirect draw path must preserve before replacing it.

## Next Implementation Slices

Near-term GLx work should stay inside the renderer boundary:

1. Extend the GLx static-world dispatcher from device-run and multidraw submission toward packet-level static batch submission while preserving id Tech 3 shader sort and stage behavior.
2. Expand `r_glxStreamDraw` from generic, fog, and depth-fragment passes toward other selected special cases after the current streamed draw paths have parity coverage.
3. Split the streamed draw prototype into explicit material-key allowlists once enough telemetry identifies the safest high-volume stage shapes.
4. Introduce GLSL material permutations only after the compatibility baseline and static-world cache measurements are stable.
5. Promote `glx` in user-facing docs only after it survives renderer switching, demo/screenshot regression checks, and display-parity visual review.
