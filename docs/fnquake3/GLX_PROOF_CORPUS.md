# GLx Proof Corpus

## Purpose

The GLx proof corpus is the single scene list used by RC gate dry runs, runtime sweep manifests, screenshot baseline keys, timedemo performance baselines, CI gate-plan artifacts, and release package metadata.

`scripts/glx_runtime_sweep.py` owns the machine-readable corpus. This document is the maintainer-facing description of the same corpus and must stay in sync with `GLX_PROOF_CORPUS_VERSION`.

Current corpus version: `2026-05-09-task-o`.

## Scene Sets

| Gate | Corpus scenes | Required coverage |
|---|---|---|
| `rc-smoke` | `stock-q3dm1-hud` | Retail stock map, UI/HUD-sensitive renderer switching, screenshots, diagnostics, frame-counter samples. |
| `rc-parity` | `stock-q3dm1-hud`, `stock-q3dm17-open`, `timedemo-demo1` | Retail stock screenshots plus legacy OpenGL versus GLx timedemo comparison. |
| `rc-proof` | `stock-q3dm1-hud`, `stock-q3dm17-open`, `stock-q3dm6-geometry`, `stock-q3dm11-shader`, `stock-q3dm15-fog`, `timedemo-demo1` | Retail stock, high-geometry, shader-heavy, fog-sensitive, UI/HUD-sensitive, screenshot-baseline, and performance-baseline proof. |
| `rc-stress` | `stock-q3dm1-hud`, `stock-q3dm17-open`, `stock-q3dm6-geometry`, `stock-q3dm11-shader`, `stock-q3dm15-fog`, `modern-fnq3glx-heavy01`, `modern-fnq3glx-shader01`, `modern-fnq3glx-fog01`, `timedemo-demo1`, `timedemo-fnq3glx-particles01` | Full retail proof set plus staged modern-map, high-geometry, shader-heavy, fog-heavy, particle-heavy-demo, and performance stress coverage. |

## Scenes

| Scene ID | Kind | Target | Asset tier | Tags |
|---|---|---|---|---|
| `stock-q3dm1-hud` | map | `q3dm1` | `retail-baseq3` | `stock-map`, `baseline-map`, `ui-hud-sensitive`, `lightmap` |
| `stock-q3dm17-open` | map | `q3dm17` | `retail-baseq3` | `stock-map`, `open-map`, `shader-heavy`, `sky` |
| `stock-q3dm6-geometry` | map | `q3dm6` | `retail-baseq3` | `stock-map`, `high-geometry`, `large-map`, `performance-comparison` |
| `stock-q3dm11-shader` | map | `q3dm11` | `retail-baseq3` | `stock-map`, `shader-heavy`, `material-stage` |
| `stock-q3dm15-fog` | map | `q3dm15` | `retail-baseq3` | `stock-map`, `fog-heavy`, `visibility` |
| `modern-fnq3glx-heavy01` | map | `fnq3_glx_heavy01` | `glx-proof-corpus` | `modern-map`, `high-geometry`, `large-map`, `performance-comparison` |
| `modern-fnq3glx-shader01` | map | `fnq3_glx_shader01` | `glx-proof-corpus` | `modern-map`, `shader-heavy`, `material-stage` |
| `modern-fnq3glx-fog01` | map | `fnq3_glx_fog01` | `glx-proof-corpus` | `modern-map`, `fog-heavy`, `visibility` |
| `timedemo-demo1` | demo | `demo1` | `retail-baseq3` | `stock-demo`, `performance-comparison` |
| `timedemo-fnq3glx-particles01` | demo | `fnq3_glx_particles01` | `glx-proof-corpus` | `particle-heavy-demo`, `modern-map`, `performance-comparison` |

## Artifact Contract

Every named gate manifest includes a `proofCorpus` object with the corpus version, document path, selected scene IDs, selected tags, and gate-required tags. Screenshot entries carry the selected corpus scene IDs and tags for their map target. Performance-baseline JSON written by the sweep embeds the same `proofCorpus` object so future comparisons can prove they were generated from the same content contract.

CI dry-run gate artifacts run `--list-corpus`, generate manifests and Markdown summaries from the same script-owned scene sets, and upload this document beside those artifacts. Release packaging includes this document in each archive and writes `glx_proof_corpus` metadata into `.install/release-manifest.json`.

The `retail-baseq3` tier must remain runnable with retail Quake III Arena assets. The `glx-proof-corpus` tier is reserved for staged project stress content and is required by `rc-stress`; keep those scene IDs stable once corresponding assets or demos are published.
