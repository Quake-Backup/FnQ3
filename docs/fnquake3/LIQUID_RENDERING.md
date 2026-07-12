# Liquid Rendering

## Scope

FnQuake3's enhanced liquid path is an opt-in renderer extension for existing idTech3 liquid shaders. It adds warped sampling of a same-frame scene-color snapshot, a bounded Fresnel sheen, and visual ripple impulses without changing BSP data, collision, snapshots, prediction, protocols, demos, or VM-visible gameplay. With `r_liquidReflections 0` and `r_liquidRipples 0`, the renderer follows the authored liquid path alone.

This is deliberately a scene-color refraction effect with a procedural Fresnel sheen rather than a planar reflection renderer, depth-ray-marched screen-space reflection (SSR), or gameplay fluid simulation. That choice gives the OpenGL-lineage and Vulkan renderers a useful liquid upgrade with one private scaled color copy and no second world traversal, PVS calculation, reflected entity submission, depth-ray hit search, or clip-plane pass. The Fresnel sheen never resamples scene color: re-projecting the current camera image after the authored water stages is geometrically wrong and produces unstable feedback-like smearing.

## Capture And Refraction Architecture

The renderer backends follow the same pass contract:

1. Classify a surface from the original and effective shader's existing contents flags. Keeping both means a visual `remapShader` cannot accidentally discard the original `surfaceparm water`. Mode `1` accepts `CONTENTS_WATER`; mode `2` also accepts `CONTENTS_SLIME` and `CONTENTS_LAVA`. A texture name, stage image, or use of the legacy `$screenMap` image does not qualify a shader by itself.
2. Require at least one authored unfogged pass and a sort at or after `SS_FOG`. FnQuake3 inserts deferred opaque lighting at `SS_FOG`; custom sort classes before that boundary cannot be captured without changing their established draw order, so they intentionally retain the authored path only. Alpha-tested stages, depth-fade or line-mode stages, disabled depth tests, and equal-only depth tests are also left authored because the synthetic geometry pass cannot reproduce their pixel coverage safely.
3. Look ahead for any qualifying liquid, then capture once at the deterministic `SS_FOG` boundary after deferred opaque lighting and the world outline, before fog, underwater, and regular transparent batches. `r_liquidReflectionScale` controls both dimensions and is resolved when renderer resources are created. This resource is independent of the legacy `$screenMap` target and its separate rerender path.
4. Restore or resume the main world pass and draw the warped scene snapshot onto the deformed liquid face before any authored stage. `r_liquidRefraction` controls this base pass. Every transparent authored stage then scrolls, tints, and blends over an already-refracted view of the completed scene behind the face.
5. Draw every authored stage normally, then add a bounded material-coloured sheen weighted by the view-angle Fresnel term. Water uses the full material scale; slime and lava are intentionally weaker. This pass does not sample the scene snapshot and therefore cannot paste the background back over the completed authored material.

The fixed capture boundary is important to idTech3's sorted renderer. It avoids sampling a render target while it is still bound for writing, includes deferred opaque contributions, and prevents the first liquid shader's chosen sort from changing which transparent work is baked into the snapshot. Because deferred lighting lands at `SS_FOG`, earlier `SS_DECAL`, `SS_SEE_THROUGH`, and `SS_BANNER` work is also present; this is a stable ordering compromise rather than a claim that the texture is strictly opaque-only. The snapshot is then stable for all enhanced liquids in that view. Fog, underwater, and regular transparent surfaces sorted after the capture are necessarily absent from the refraction.

The feature is skipped when a safe main-view snapshot is not available, including non-world UI/model scenes and special view paths such as portals, stereo rendering, or cubemap screenshot capture. The authored shader remains the fallback; failure to capture must never make a liquid disappear.

## Backend Paths And Parity

The OpenGL-lineage renderer owns a dedicated `liquidScreenBuffer`; `FBO_CopyLiquidScreen` linearly copies the active main FBO into that scaled private texture. It never aliases the historical `$screenMap` buffer. On the GLx GL2+ tier, a GLSL 1.20 liquid program evaluates pixel-scaled ambient waves and ripple rings per fragment and streams the current deformed positions, normals, and indices when necessary. The GL12 compatibility tier, or a GLx shader/stream allocation failure, uses a conservative CPU/projective fallback with projective coordinates evaluated per vertex.

Vulkan ends the active main pass on demand, resolves it when required, linearly downsamples through a dedicated source sampler into its private scaled `liquidSnapshot` attachment, and resumes through the load-preserving main pass. A dedicated liquid vertex/fragment pipeline samples that attachment for the refraction underlay and emits the non-sampling Fresnel sheen after authored stages.

The GLx GL2+ and Vulkan paths both evaluate the liquid function per fragment. The GL12 fallback evaluates the distortion and alpha at tessellated vertices and projectively interpolates the result, so it is expected to look smoother and less locally detailed. All paths share the same cvar surface, contents classification, material-strength policy, impulse limits, and lifetime constants through `renderercommon/tr_liquid.h`; texture filtering, precision, and fallback interpolation mean that parity is visual rather than pixel-for-pixel.

The seven public controls are:

- `r_liquidReflections` (`0`, latched): `0` authored liquids only, `1` water, `2` water/slime/lava.
- `r_liquidReflectionScale` (`0.5`, latched): per-axis snapshot scale in the range `0.125..1.0`.
- `r_liquidRefraction` (`0.65`): opacity of warped scene color behind authored stages in the range `0.0..1.0`.
- `r_liquidWarp` (`0.012`): ambient strength in the range `0.0..0.05`, mapped to a resolution-independent `0..8` pixel displacement so existing archived values remain valid.
- `r_liquidFresnel` (`0.65`): material-coloured grazing-angle sheen strength in the range `0.0..1.0`.
- `r_liquidRipples` (`0`): enables client-fed visual impulses.
- `r_liquidRippleStrength` (`1.0`): impulse amplitude multiplier in the range `0.0..2.0`.

`r_liquidReflections` and `r_liquidReflectionScale` are latched because the scaled target and backend pipeline resources are established at renderer initialization. Both require `r_fbo 1` and `vid_restart`. The remaining controls are runtime tuning values.

The `r_liquidReflections` name is retained as the compatibility master/material selector. It no longer means that the renderer reuses the current camera image as a fake reflection; doing so was the source of the invalid post-stage feedback path.

## Client Visual Impulse Feed

When both the master mode and ripple toggle are active, the engine-side client observes already available rendered entity and local-view motion. It classifies stable `ET_PLAYER` and `ET_MISSILE` positions, samples collision contents, finds liquid entry and exit boundaries, detects fast missile traversals whose two sampled endpoints are both dry, and emits periodic near-surface wakes while an entity moves through a liquid. Sampling rejects implausible motion, teleports, stale gaps, repeated stereo-frame samples, and invalid origins so snapshot discontinuities do not create giant rings.

Impulses cross the renderer export boundary as `liquidInteraction_t` records containing origin, initial radius, strength, time, and player/projectile source. They do not enter `entityState_t`, `playerState_t`, the cgame VM trap ABI, or network snapshots. Each renderer retains at most 16 recent records, coalesces near-duplicate events, supplies at most eight active impulses to a view, and expires each record after 2.4 seconds. The overlay expands and fades those records analytically; there is no persistent height field.

`AddLiquidInteractionToScene` is nevertheless part of the engine-to-renderer module ABI. Changes to that export or to the shared record layout require a coordinated `REF_API_VERSION` update and matching OpenGL-lineage and Vulkan modules; they must not be exposed by repurposing a cgame VM trap or network field.

This separation is a compatibility requirement. A demo can produce local visual ripples from its replayed player and missile motion when viewed with the option enabled, but the impulses are not recorded in the demo and cannot influence playback, prediction, movement, weapon traces, damage, or authoritative state. Mods require no new asset or game-code support and receive classic behavior when the option is disabled.

## Cost And Screen-Space Limits

The dominant fixed cost is one linearly filtered copy into the dedicated liquid snapshot in a view that contains an eligible liquid. Pixel count and approximate copy bandwidth scale quadratically with `r_liquidReflectionScale`: the default `0.5` target contains about 25% as many pixels as a full-size target. Refraction and the inexpensive non-sampling sheen add two blended liquid draws; they do not render the world twice or invoke the legacy `$screenMap` rerender. Setting `r_liquidRefraction 0` skips both the snapshot capture and first draw while still allowing the independent sheen; setting `r_liquidFresnel 0` skips the sheen. Both paths preserve destination alpha. GLx uses transient streamed geometry for the programmable liquid passes because the positions and normals are consumed by the current view's shader evaluation.

The snapshot has no information beyond the current captured color buffer. The implementation does not sample scene depth or ray-march reflection directions, so it cannot recover off-screen, behind-camera, or occluded geometry; reject a sample using depth; reveal objects covered by foreground pixels; or include transparent work submitted later. Warp is expressed in pixels and fades to zero near screen edges to bound clamp smearing. The result is artistic same-frame refraction plus a procedural sheen, not true SSR or a geometrically correct mirror. The impulse rings add an independent pixel displacement: they do not move vertices, conserve volume, flow downhill, or interact physically with collision geometry.

These constraints are preferable to silently changing the meaning of retail shader stages. Authored `tcMod`, blend, deform, fog, and texture animation remain the base appearance, and the optional overlay either augments that appearance or cleanly drops out.

## Future Directions

Future work should preserve the current underlay and sheen as the compatibility and low-cost tier. Plausible higher tiers include:

- A depth-aware refraction or short screen-space reflection march, with thickness rejection, edge fading, and a strict fallback when depth sampling is unavailable.
- Budgeted planar reflection probes for a small number of dominant water planes, with reflected-view PVS and entity submission kept outside demo or gameplay state.
- Optional authored liquid material hints for normal scale, tint, roughness, or an explicit opt-out, added without reinterpreting existing Quake III shader scripts.
- A small renderer-local height field for richer wake propagation and projectile splashes. Inputs must remain visual records, simulation bounds must be deterministic and capped, and no result may feed collision or game logic.
- Temporal stabilization for the screen-space sample, provided camera cuts, portals, stereo views, and demo seeks invalidate history conservatively.

Any higher tier should remain default-off until GLx/Vulkan visual parity, failure fallback, retail map coverage, demo seeking, and performance budgets have been validated.
