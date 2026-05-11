# GLx Proof Corpus

## Purpose

The GLx proof corpus is the single scene list used by RC gate dry runs, runtime sweep manifests, screenshot baseline keys, timedemo performance baselines, CI gate-plan artifacts, and release package metadata.

`scripts/glx_runtime_sweep.py` owns the machine-readable corpus. This document is the maintainer-facing description of the same corpus and must stay in sync with `GLX_PROOF_CORPUS_VERSION`.

Current corpus version: `2026-05-11-post-proof-v1`.

Current parity suite version: `2026-05-11-post-v1`.

## Scene Sets

| Gate | Corpus scenes | Required coverage |
|---|---|---|
| `rc-smoke` | `stock-q3dm1-hud` | Retail stock map, UI/HUD-sensitive renderer switching, screenshots, diagnostics, frame-counter samples. |
| `rc-parity` | `stock-q3dm1-hud`, `stock-q3dm17-open`, `timedemo-demo1` | Retail stock screenshots, HUD-sensitive coverage, bloom-tagged output, stock-map/lightmap `worldProofEvidence`, and legacy OpenGL versus GLx timedemo comparison. |
| `rc-proof` | `stock-q3dm1-hud`, `stock-q3dm17-open`, `stock-q3dm6-geometry`, `stock-q3dm11-shader`, `stock-q3dm15-fog`, `timedemo-demo1` | Retail screenshot, demo playback, HUD, shadow, bloom, cel-shading, fog, tone-map/color-grade, world/static/lightmap/fog `worldProofEvidence`, material/tcgen `materialProofEvidence`, entity/weapon/dynamic-light/planar-shadow `dynamicProofEvidence`, greyscale/render-scale `postProofEvidence`, screenshot-baseline, and performance-baseline proof. |
| `rc-stress` | `stock-q3dm1-hud`, `stock-q3dm17-open`, `stock-q3dm6-geometry`, `stock-q3dm11-shader`, `stock-q3dm15-fog`, `modern-fnq3glx-heavy01`, `modern-fnq3glx-shader01`, `modern-fnq3glx-fog01`, `timedemo-demo1`, `timedemo-fnq3glx-particles01` | Full retail proof set plus staged modern-map, high-geometry, shader-heavy, fog-heavy, animated-image, vector-tcgen, screen-map, video-map, tone-map/color-grade, particle-heavy-demo, world/static/fog proof, material proof, dynamic-scene proof for particles/polys/marks/beams, postprocess proof, and performance stress coverage. |

## Parity Suites

`rc-proof` and `rc-stress` require the named parity suites below. Each suite has a fixed scene list and, where needed, fixed cvar overrides emitted by the sweep config before the selected map loads. The suite names and scene IDs are stored in `scripts/glx_runtime_sweep.py`, embedded into gate manifests, and revalidated by release proof checks.

| Suite ID | Artifact | Scene IDs | Required tags | Suite cvars |
|---|---|---|---|---|
| `screenshot` | screenshot | `stock-q3dm1-hud`, `stock-q3dm17-open`, `stock-q3dm6-geometry`, `stock-q3dm11-shader`, `stock-q3dm15-fog` | `screenshot-parity` | none |
| `demo-playback` | timedemo | `timedemo-demo1` | `demo-playback-parity`, `stock-demo` | none |
| `hud` | screenshot | `stock-q3dm1-hud` | `hud-parity`, `ui-hud-sensitive` | none |
| `shadow` | screenshot | `stock-q3dm6-geometry` | `shadow-parity` | `cg_shadows=2` |
| `bloom` | screenshot | `stock-q3dm17-open` | `bloom-parity` | none; the RC profile enables final-pass bloom |
| `cel-shading` | screenshot | `stock-q3dm11-shader` | `cel-shading-parity`, `outline-parity` | `r_celShading=1`, `r_celOutline=1`, `r_celShadingSteps=4` |
| `greyscale` | screenshot | `stock-q3dm1-hud` | `greyscale-proof` | `r_fbo=1`, `r_greyscale=1` |
| `render-scale` | screenshot | `stock-q3dm17-open` | `render-scale-proof` | `r_fbo=1`, `r_renderScale=1`, `r_renderWidth=512`, `r_renderHeight=384` |

## Scenes

| Scene ID | Kind | Target | Asset tier | Tags |
|---|---|---|---|---|
| `stock-q3dm1-hud` | map | `q3dm1` | `retail-baseq3` | `stock-map`, `baseline-map`, `ui-hud-sensitive`, `screenshot-parity`, `hud-parity`, `lightmap`, `tcgen-lightmap`, `dynamic-entity`, `weapon-model`, `greyscale-proof` |
| `stock-q3dm17-open` | map | `q3dm17` | `retail-baseq3` | `stock-map`, `open-map`, `shader-heavy`, `sky`, `screenshot-parity`, `bloom-parity`, `tone-map-proof`, `render-scale-proof` |
| `stock-q3dm6-geometry` | map | `q3dm6` | `retail-baseq3` | `stock-map`, `high-geometry`, `large-map`, `screenshot-parity`, `shadow-parity`, `performance-comparison`, `dynamic-entity`, `planar-shadow` |
| `stock-q3dm11-shader` | map | `q3dm11` | `retail-baseq3` | `stock-map`, `shader-heavy`, `material-stage`, `tcgen-environment`, `screenshot-parity`, `cel-shading-parity`, `outline-parity`, `color-grade-proof`, `tone-map-proof`, `dynamic-entity` |
| `stock-q3dm15-fog` | map | `q3dm15` | `retail-baseq3` | `stock-map`, `fog-heavy`, `visibility`, `tcgen-fog`, `screenshot-parity`, `color-grade-proof` |
| `modern-fnq3glx-heavy01` | map | `fnq3_glx_heavy01` | `glx-proof-corpus` | `modern-map`, `high-geometry`, `large-map`, `screenshot-parity`, `performance-comparison` |
| `modern-fnq3glx-shader01` | map | `fnq3_glx_shader01` | `glx-proof-corpus` | `modern-map`, `shader-heavy`, `material-stage`, `animated-image`, `tcgen-vector`, `screen-map`, `video-map`, `screenshot-parity`, `cel-shading-parity`, `outline-parity` |
| `modern-fnq3glx-fog01` | map | `fnq3_glx_fog01` | `glx-proof-corpus` | `modern-map`, `fog-heavy`, `visibility`, `screenshot-parity` |
| `timedemo-demo1` | demo | `demo1` | `retail-baseq3` | `stock-demo`, `demo-playback-parity`, `performance-comparison`, `dynamic-entity`, `dynamic-light` |
| `timedemo-fnq3glx-particles01` | demo | `fnq3_glx_particles01` | `glx-proof-corpus` | `particle-heavy-demo`, `demo-playback-parity`, `modern-map`, `performance-comparison`, `particle`, `transient-poly`, `mark-decal`, `beam`, `dynamic-light` |

## Artifact Contract

Every named gate manifest includes a `proofCorpus` object with the corpus version, document path, selected scene IDs, selected tags, gate-required tags, parity suite version, selected parity suite IDs, and the versioned suite records. Screenshot entries carry the selected corpus scene IDs, tags, parity suite IDs, and suite cvars for their map target. Performance-baseline JSON written by the sweep embeds the same `proofCorpus` object so future comparisons can prove they were generated from the same content contract.

CI dry-run gate artifacts run `--list-corpus`, generate manifests and Markdown summaries from the same script-owned scene sets, and upload this document beside those artifacts. Release packaging includes this document in each archive and writes `glx_proof_corpus` metadata into `.install/release-manifest.json`.

The `retail-baseq3` tier must remain runnable with retail Quake III Arena assets. The `glx-proof-corpus` tier is reserved for staged project stress content and is required by `rc-stress`; keep those scene IDs stable once corresponding assets or demos are published.
