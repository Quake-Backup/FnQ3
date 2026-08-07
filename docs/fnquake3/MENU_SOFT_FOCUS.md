# In-Game Menu Soft Focus

## Scope

While an in-game menu owns the screen, FnQuake3 replaces the frame behind it with a soft-focus copy of itself, so the menu reads as the foreground instead of competing with a sharp, still-animating scene. The effect exists only while a menu is open: gameplay is never softened, and nothing about the frame the player shoots into changes.

It touches no BSP data, collision, visibility, prediction, snapshots, protocol data, demo data, or VM/native-module interfaces. It is a pure post-process over the finished frame, so enabling it cannot change how a server evaluates a client.

This replaces the earlier `cl_menuDepthOfField` effect, which was implemented only for the OpenGL lineage, was a no-op on both Vulkan backends, and failed silently whenever it declined. That cvar and its `cl_menuDepthOfFieldTime` companion are gone; a config still setting them will simply have two unknown cvars.

## Cvar

| Cvar | Default | Meaning |
| --- | --- | --- |
| `cl_menuBlur` | `1` | `0` leaves the scene sharp. `0..1` scales both the blur radius and how far the softened copy replaces the sharp frame. |

One cvar gates the whole feature. The fade in and out is a fixed 140 ms and is not configurable: shorter reads as a flicker when a menu is toggled, longer starts to feel like input lag on the menu itself.

Because strength scales radius *and* composite weight together, a partial value is a gently softened frame rather than a cross-fade between a sharp and a blurred copy of the same image, which would read as a ghosted double exposure.

## Trigger

The client owns the decision, in `SCR_DrawScreenField`. The effect is requested when all of the following hold:

- `KEYCATCH_UI` is set and a UI module is loaded;
- the menu is not fullscreen — a fullscreen menu has no scene behind it to soften;
- `cls.state == CA_ACTIVE` — the connect and level-loading screens are not in-game menus.

The request is issued after the scene *and* the cgame HUD have been drawn and before `UI_REFRESH`, so the HUD is softened along with the world and only the menu itself stays sharp.

`SCR_UpdateMenuBlurStrength` ramps toward the requested strength on wall-clock time rather than per frame, so the pull into focus takes the same 140 ms at 60 and at 250 fps. A negative `cls.realtime` delta is a timer reset and a delta over a second is a hitch or a restored window; neither counts as elapsed fade time, and a discarded delta holds the current strength rather than snapping to the target. A non-finite `cl_menuBlur` value is rejected before `Com_Clamp` sees it, because `Com_Clamp` is comparison based and would let a NaN through, latching the ramp for the rest of the session.

### What is deliberately not softened

**`KEYCATCH_CGAME` overlays** — the scoreboard and similar — stay sharp. They are drawn over live gameplay the player is still reading, and cgame draws the scene, the HUD, and its overlays in a single `CG_DRAW_ACTIVE_FRAME` call, so a request queued after it would soften the overlay itself rather than the frame behind it. That needs a cgame-side hook that does not exist.

**The connection dialog and the level-loading screen** are 2D-only frames. The OpenGL backend gates the composite on `backEnd.doneSurfaces` — "a 3D pass has run this frame" — because that is its only signal that the render target holds something this composite may read back.

**The console** is the one layer that finishes the frame's own post-processing, calling `re.FinishBloom` from inside `Con_DrawConsole`. Issuing the request before that leaves the console drawing with the descriptor sets bloom's blend pass bound, so it does not appear at all; issuing it after leaves the Vulkan backends in a pass the pyramid does not sample. Either ordering also composites over live gameplay for the 140 ms the request takes to fade out after the console closes, which reads as the HUD briefly losing opacity for no reason the player can see.

## Sampling plan

`code/renderercommon/tr_menu_blur.h` owns the plan. The three renderer backends drive it rather than each inventing a blur, which is what keeps them looking the same.

The plan is a small Gaussian pyramid, not one wide kernel:

1. The finished frame is box-downsampled to 1/2 and then to 1/4. Going straight to 1/4 in a single bilinear step discards three of every four texels, and *which* three changes as the scene animates, so the backdrop crawls. Two exact halvings average every texel instead. On every backend the halving is a plain linear resample, which at an exact 2:1 reduction lands each destination texel centre between four source texels and therefore averages all of them.
2. 1/4 resolution carries four separable horizontal+vertical Gaussian iterations. A texel of spacing there covers four screen pixels, so a wide blur needs few passes.
3. Per-pass sigmas grow as 1:2:3:4 and combine in quadrature to the requested total. The tight first pass removes the high frequencies that would otherwise show the later, sparser taps as banding; the later passes run on already-smooth data, where wider gaps cost nothing.
4. The level is bilinearly resampled back to full resolution and composited with the plan's alpha.

Total sigma is `MENU_BLUR_SIGMA_FRACTION` (1.3%) of render-target *height*, so the softness covers the same share of the screen at 720p and at 4K, and width does not enter it. The pass count is constant, so a fade cannot pop as the ramp crosses a threshold.

### Why the backends exchange sigma, not offsets

The kernels differ. The OpenGL lineage iterates the existing 6-tap binomial ARB program (`BLUR2_FRAGMENT`); Vulkan and RTX iterate the 3-tap linear-sampling kernel that emulates a 5-tap binomial. Their unit-spacing variances are tabulated as `MENU_BLUR_KERNEL_VARIANCE_BINOMIAL6` and `MENU_BLUR_KERNEL_VARIANCE_LINEAR3`, and each backend converts the plan's per-pass sigma into its own tap spacing with `R_MenuBlur_TapSpacing`. Matching sigma is what makes the renderers agree; matching tap offsets would not.

A plan is reported disabled — never an error — for a non-positive or non-finite strength, a strength below the visible-composite floor, a non-positive target size, or a target too small to hold a quarter-resolution level. Every backend treats a disabled plan as "leave the finished frame alone".

## Backends

The effect samples the finished frame, so it cannot run from the frontend. Each renderer queues an `RC_MENU_BLUR` command that executes in draw order and calls `RB_EndSurface` first, so queued geometry has landed on the target before it is read back.

### OpenGL lineage (`code/renderer`)

`FBO_MenuBlur` allocates three framebuffers — one half-resolution step and a ping-pong pair at the level — sized from the plan and rebuilt when the render target changes. The two halvings are `glBlitFramebuffer` with `GL_LINEAR`; the iterations reuse the ARB blur program through `ARB_BlurParams`, which gained a spacing argument for this (bloom passes pass `1.0` and are unchanged). The composite is a fixed-function modulated quad whose vertex alpha carries the strength.

Two ordering constraints are load-bearing and easy to undo by accident:

- The multisample resolve (`FBO_BlitMS`) is consumed only after every decline has been passed. Consuming it earlier disarms the frame's only resolve *and* switches the draw target, so a later decline strands the rest of the frame in a buffer that is never blitted.
- A failed pyramid allocation rebinds the caller's framebuffer before returning. `FBO_Create` and `FBO_Clean` both leave framebuffer 0 bound, so without that every later UI draw lands in the back buffer, where `FBO_PostProcess` erases it.

### Vulkan and RTX (`code/renderervk`, `code/rendererrtx`)

Both use one new fragment shader, `menu_blur.frag`. Its tap offset is a push constant, so a zero offset collapses the three taps onto one coordinate — the weights still sum to one — and the same shader becomes the plain bilinear resample the downsample steps and the composite need. The pyramid therefore needs no copy shader of its own.

Three attachments, one render pass, three framebuffers, three descriptors, and three pipelines are created. One render pass object serves all three targets because render-pass compatibility depends on attachment format and sample count, not extent; three *pipelines* are still needed because viewport and scissor are baked into a pipeline in this codebase. `VK_NUM_MENU_BLUR_IMAGES` is budgeted into both `MAX_ATTACHMENTS_IN_POOL` and the combined-image-sampler descriptor pool.

The pyramid samples the scene through its own descriptor, `menu_blur_source_descriptor`, rather than through `vk.color_descriptor`. The latter is built with `vk.blitFilter`, which is `GL_NEAREST` unless supersampling is on, and point-sampling the first 2:1 reduction keeps one texel in four — reintroducing exactly the backdrop crawl the two-step pyramid exists to avoid. The liquid snapshot already carries a private linear view of the scene for the same reason.

Two pieces of state have to be restored before returning, and both are load-bearing rather than tidiness:

- `vk.cmd->last_pipeline` is nulled. The composite binds descriptor set 0 through the post-process pipeline layout, and binding through a layout incompatible with the material layout disturbs the sets bound for it. Nulling the cache is what forces the next draw to rebind them; handing the frame's pipeline back instead lets that draw proceed with disturbed sets.
- `vk_update_mvp( NULL )` re-pushes the MVP. The same layout incompatibility leaves that push constant undefined, and this is the only post-process detour that runs while `backEnd.projection2D` is already set, so the next `RB_StretchPic` skips `RB_SetGL2D` and nothing else would restore it.

#### Frame liveness, not a sticky index

`vk.renderPassIndex` is sticky state, not a recording flag: `vk_end_render_pass` deliberately leaves it set, and `vk_end_frame` re-arms it *after* `qvkEndCommandBuffer` and `qvkQueueSubmit`. So it can read a live-looking value in exactly the state where recording anything is undefined. Two mid-client-frame drains produce that state: the one level of re-entrant `SCR_UpdateScreen` the client permits, and `R_IssuePendingRenderCommands`. Either ends and submits the command buffer mid-frame, and ending a render pass on a dead command buffer faults the device inside the ICD.

`vk_menu_blur` therefore tests `vk.frame_count` — and, on `renderervk`, the recording pass itself — which is the precondition `vk_capture_liquid_scene` already uses for the same end-detour-resume trick.

#### Which pass is resumed

`RB_StretchPic` runs `vk_bloom()` on the cgame HUD's first 2D quad, and bloom finishes by entering the post-bloom pass with nothing to put the index back. `r_bloom` defaults to `1` on both Vulkan backends, so by the time `RC_MENU_BLUR` executes the frame is normally in `RENDER_PASS_POST_BLOOM`. A guard that accepted only `RENDER_PASS_MAIN` would leave the whole effect inert at shipped defaults.

- `renderervk` records which pass it interrupted and resumes that one, because the index selects which pipeline variant every later HUD draw uses. One composite pipeline serves both, because `main_load` and `post_bloom` are built from the same attachment description and differ only in load/store ops, which render-pass compatibility ignores.
- `rendererrtx` has no `main_load`; `post_bloom` *is* its load-op-LOAD view of the main framebuffer, and it is where `vk_draw_global_fog` already resumes. The composite is built against it, and the effect declines rather than falling back to a clearing pass when it was never created.

The Vulkan attachments are allocated unconditionally whenever the FBO path is active, not gated on `cl_menuBlur`. The attachment pool is fixed-size and populated at renderer init, where the renderer cannot usefully consult a client cvar the player may change at any moment. The cost is roughly 3 MB at 1080p and 12 MB at 4K.

Both SPIR-V blobs are checked in beside the shader source in `shaders/spirv/shader_data.c`. `renderervk` uses the `bin2hex` layout its `compile.bat` produces; `rendererrtx` regenerates through `code/rendererrtx/shaders/build_shaders.py`, which also refreshes `shader_reflection.json`.

## Declining

Every backend reports why it declined, once per distinct reason, at `PRINT_DEVELOPER`. Reasons are configuration rather than failure: no framebuffer path, pyramid not allocated, pipelines not created, no live scene pass, or a pyramid that no longer matches the render target. This is a deliberate response to the predecessor effect, which failed silently and so made an unsupported configuration indistinguishable from a disabled cvar.

The effect requires the framebuffer post-processing path. With `r_fbo 0` there is no sampleable copy of the finished frame and the menu stays sharp.

## Validation

`tests/menu_blur_tests.cpp` covers the plan: inert disabled plans for every rejected input including NaN strength and undersized targets; two halvings with truncation that never collapses to zero; total sigma tracking target height and not width; the 1:2:3:4 ramp; strength scaling sigma and alpha together with a constant pass count and clamping above 1; tap-spacing conversion round-tripping through each kernel variance and collapsing to zero on degenerate input; and the property that both kernels reach the same total sigma from the same plan.

`tests/menu_blur_source_tests.py` gates the structure: that all three backends include the shared header and call both plan functions; that each passes its own kernel variance and not the other's; that a single archived cvar gates the effect and the depth-of-field path is gone from every file that referenced it; that the trigger excludes fullscreen menus and non-active states and consults no `KEYCATCH_CGAME`; that exactly one layer is requested with no client-side `re.FinishBloom` crept back in; that the GL path performs exactly two linear blits and resolves multisample only after every decline; that both Vulkan backends test frame liveness rather than the sticky index, sample the first halving through the private linear descriptor, resume their own load pass, restore the MVP and the pipeline cache, and allocate, budget, and release every object they create; that the shader's weights and tap positions still match the tabulated kernel variance; and that the two Vulkan shader sources are byte-identical.

Runtime promotion still needs a windowed retail-asset check on each renderer: open an in-game menu during live play and confirm the scene and HUD soften while the menu stays sharp, that the fade is smooth in both directions, that `cl_menuBlur 0` leaves the frame untouched, and that intermediate values look softened rather than double-exposed. Confirm too that the layers deliberately left out stay out: connecting to a server and dropping the console during live play must both leave the frame completely untouched. `r_fbo 0`, `r_bloom 0`, and a `vid_restart` with the menu open are the configuration cases worth checking explicitly.
