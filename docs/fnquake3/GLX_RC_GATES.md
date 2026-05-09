# GLx Release Candidate Gates

## Status

This document freezes the initial GLx release-candidate target. GLx remains experimental until the blocking gates here pass on the blocking runtime matrix and the captured artifacts have been reviewed.

The gates are intentionally conservative. They prove that GLx can load through the existing renderer ABI, survive renderer switching and `vid_restart`-equivalent paths, preserve the current OpenGL display surface, and stay close enough to the legacy OpenGL renderer to justify the next ownership work. They are not permission to remove `opengl` or `opengl2`.

The final renderer replacement contract is [GLX_FINAL_CONTRACT.md](GLX_FINAL_CONTRACT.md). The gates in this document validate the transitional RC surface; they do not satisfy the final five-tier, GLx-owned draw, scene-linear color, and full feature-closure requirements by themselves.

## Blocking Runtime Matrix

The first GLx RC requires runtime evidence on:

- Windows 10 or newer, x64, dynamic renderer build, retail `baseq3` assets.
- Linux x86_64, Mesa or vendor OpenGL driver, dynamic renderer build, retail `baseq3` assets.

Every blocking RC run must expose at least the `GL2X` product tier: OpenGL 2.x with GLSL-era program support. `GL12` exists as the final fixed-function compatibility floor, but the current conservative RC profile still exercises the programmable migration surface. `GL3X`, `GL41`, and `GL46` features are optional accelerators for this RC gate. Missing persistent mapping, sync objects, multidraw, indirect draw, direct-state-access, or debug-output support must select a fallback path rather than fail renderer initialization. A `GL2X` run must report the `GL2X programmable executor` contract: stream uploads, the GLSL material compiler, postprocess-lite behavior, common material coverage, dynamic entities, lightmaps, multitexture, fog, sprites, beams, screenshots, and demos are supported, while modern post-chain and scene-linear output are not required.

`GL12` is not a blocking RC profile target, but its diagnostics are still structured. A GL12 run must report the `GL12 fixed-function executor` contract, client-memory draw support, and the fixed-function coverage line for lightmaps, multitexture, fog, sprites, beams, dynamic lights, stencil shadows when available, screenshots, and demos. It must also report stream uploads, the GLSL material compiler, and the modern post chain as unavailable on that tier.

`GL3X` is likewise structured even though it is an accelerator for the conservative RC gate. A GL3X run must report the `GL3X performance executor` contract: FBO postprocess, UBO-style frame/object constants, timer queries, sync-aware uploads, static buffer ownership, dynamic buffer ownership, modern post-chain, scene-linear output, screenshots, and demos are supported, while persistent mapped uploads, indirect submission requirements, and direct state access requirements are not mandatory on that tier.

`GL41` runs must report the `GL41 mac-modern executor` contract. That line proves the macOS ceiling tier is treated as a supported modern product target, with FBO postprocess, UBO-style constants, timer queries, sync-aware uploads, static/dynamic buffer ownership, scene-linear post, high-quality SDR, optional hardware HDR output, screenshots, and demos. The paired GL4+ requirements line must keep debug output, buffer storage, direct state access, multi-draw indirect, and persistent uploads marked as non-required.

`GL46` runs must report the `GL46 high-end executor` contract. That line proves persistent uploads, buffer-storage upload policy, sync-heavy streaming, DSA, MDI, aggressive static-world submission, detailed GPU counters, hardware HDR output, screenshots, and demos are all part of the high-end tier. The compact `glx: GL46 high-end ...` line records persistent-upload, DSA-product, MDI-product, aggressive-static, backend GPU query, and static-world MDI counters so the tier can be compared against lower paths.

Nightly packaging should continue to build GLx wherever the repository already enables `USE_GLX`, including Windows x86, macOS, Linux aarch64, and other packaged targets. Those platforms need at least manual smoke coverage before GLx becomes the default or `opengl` becomes an alias, but they are not blockers for the first conservative RC unless maintainers add stable GPU runners for them.

## Canonical Gate Presets

`scripts/glx_runtime_sweep.py` owns the machine-readable gate presets. Use `--list-gates` to print the current script view.

| Gate | Purpose | Profile | Scene Set | Automated Floor |
|---|---|---|---|---|
| `rc-smoke` | Renderer lifecycle smoke: module load, map load, repeated in-process renderer switches, screenshots, and GLx diagnostics. | `baseline` | `q3dm1` | All runs pass and all expected screenshots are written. |
| `rc-parity` | Blocking conservative RC gate for world, ordered packet-batch static spans, stream paths including CPU-computed texmods, environment coordinates, state-only dynamic-scene draw arrays, material, bloom, and GPU-timing paths. | `glx-parity` / `r_glxProfile rc` | `q3dm1`, `q3dm17`, `demo1` | All runs pass, all screenshots are written, and GLx timedemo FPS is at least 90% of `opengl` on the same machine and demo. |
| `rc-proof` | Blocking proof gate for the RC surface, requiring reviewed screenshot baselines and an approved performance baseline in addition to the `rc-parity` checks. | `glx-parity` / `r_glxProfile rc` | `q3dm1`, `q3dm17`, `demo1` | All parity checks pass, every screenshot compares within threshold, and aggregate performance counters stay within the approved baseline growth budget. |
| `rc-stress` | Developer stress gate for indirect static-world paths before any advanced GLx path becomes a default. | `glx-stress` / `r_glxProfile stress` | `q3dm1`, `q3dm17`, `demo1` | All runs pass, screenshots are written, and timedemo metrics are captured. |

The initial scene set is deliberately small and stock-data friendly. It may grow as bugs are found, but it should not shrink during an RC cycle.

The profile names are not just documentation labels. `glx-parity` and `glx-ownership` launch GLx with `r_glxProfile rc`, and `glx-stress` launches GLx with `r_glxProfile stress`, so startup-sensitive resources are built under the same profile that `glxprofile status` reports in the renderer. `glx-ownership` uses the RC cvar surface plus `r_glxRequireOwnership 1`, rejecting legacy-delegation draw submissions and turning any attempted delegation into a blocking diagnostic failure.

## Frozen RC Profile

The conservative RC profile is frozen as a cvar contract between the runtime renderer and the sweep harness. `code/rendererglx/glx_module.cpp` owns the `r_glxProfile rc` table, while `scripts/glx_runtime_sweep.py` owns the `glx-parity` launch profile. `tests/glx/glx_runtime_sweep_tests.py` parses the runtime table and fails if the script profile drifts from it.

Use `python scripts/glx_runtime_sweep.py --list-profiles` to print the exact profile values used by sweeps. The RC profile enables the compatibility-first GLx world renderer, guarded stream draw, material renderer/precache, packet-batch static spans, final-pass bloom parity, GPU timing, and the state-only shadow/beam/postprocess dynamic draw-array submissions. It intentionally keeps dynamic-light/screen-map/video-map material gates and indirect static-world submission off; those stay in the stress profile or explicit developer overrides until their gates have evidence.

## Exit Criteria

A GLx RC candidate must meet all of these conditions:

- `rc-smoke`, `rc-parity`, and `rc-proof` pass on every blocking runtime platform.
- The generated manifest, logs, screenshots, screenshot diffs, Markdown summary, timedemo metrics, and performance comparisons are archived with the candidate build.
- The GLx timedemo result is at least 90% of the legacy `opengl` timedemo result for each required demo on the same machine. A lower result needs a tracked waiver with the measured cause.
- Manual screenshot review finds no unexplained drift in world visibility, sky, fog, lightmaps, weapon placement, marks/decals, particles, HUD/2D, bloom, gamma, or final output size.
- GLx diagnostic output shows no shader compile/link failures, material path `not-ready` state, GL errors, postprocess fallback output, streamed dynamic-scene fallback growth, or unexpected loss of the static-world/stream fallback guarantees.
- `renderer_switch opengl,glx,opengl,glx` loops do not leak state, fail screenshot capture, lose the cgame/UI, or leave the next renderer in a partially initialized state.
- `rc-stress` is clean before indirect static-world or other advanced GLx paths are promoted to default behavior.

Failing any blocking criterion keeps GLx experimental. The fix may be renderer code, a narrower default GLx profile, a documented waiver, or a larger test corpus, but it should not be a silent default promotion.

## Typical Commands

From the repository root:

```sh
python scripts/glx_runtime_sweep.py --list-gates
python scripts/glx_runtime_sweep.py --list-profiles
python scripts/glx_runtime_sweep.py --gate rc-smoke --exe path/to/fnquake3.glx.x64.exe --basepath path/to/game/root
python scripts/glx_runtime_sweep.py --gate rc-parity --exe path/to/fnquake3.glx.x64.exe --basepath path/to/game/root
python scripts/glx_runtime_sweep.py --gate rc-proof --exe path/to/fnquake3.glx.x64.exe --basepath path/to/game/root --proof-dir .tmp/glx-proof/windows-x64
python scripts/glx_runtime_sweep.py --gate rc-stress --exe path/to/fnquake3.glx.x64.exe --basepath path/to/game/root
```

Use `--dry-run` to generate the configs and manifest without requiring a built executable or retail assets. Dry runs are useful for reviewing the expanded cvars, startup cvars, maps, demos, and commands, but they do not count as gate evidence.

## Screenshot Baselines

The sweep can compare captured PNG screenshots against an approved baseline directory without external Python packages. Baseline filenames use stable screenshot keys derived from the profile, map, switch round, switch step, and renderer, while the live capture filenames keep the unique run id.

To deliberately approve a new local baseline set:

```sh
python scripts/glx_runtime_sweep.py --gate rc-parity --exe path/to/fnquake3.glx.x64.exe --basepath path/to/game/root --screenshot-baseline-dir .tmp/glx-baselines/windows-x64 --approve-screenshot-baselines
```

To compare a candidate run against that baseline and write difference PNGs:

```sh
python scripts/glx_runtime_sweep.py --gate rc-parity --exe path/to/fnquake3.glx.x64.exe --basepath path/to/game/root --screenshot-baseline-dir .tmp/glx-baselines/windows-x64 --screenshot-diff-dir .tmp/glx-diffs/windows-x64 --screenshot-max-rms 2.0 --screenshot-max-pixel-ratio 0.005
```

The initial thresholds are intentionally tight and should be adjusted only with reviewed evidence. Missing baselines or failed comparisons fail a non-dry-run gate when a baseline directory is supplied.

For hard RC proof, prefer `--gate rc-proof --proof-dir <dir>`. The proof directory defaults screenshot baselines to `<dir>/screenshots`, performance baselines to `<dir>/performance-baseline.json`, screenshot diffs to the run artifact directory, and the Markdown summary to the run artifact directory. `rc-proof` rejects baseline-approval mode before launching runtime work; approve refreshed visual and performance baselines in a separate reviewed `rc-parity` run before using them as proof inputs.

## Diagnostic Gate Analysis

Non-dry-run gate manifests now include structured analysis of the GLx diagnostic commands emitted during screenshot sweeps. The analyzer reads the `glxmaterial`, `glxpostprocess`, and `glxstaticworld`/stream sections from the run log and fails the gate on release-blocking renderer states:

- material renderer enabled but not ready under the RC/stress profiles;
- material compile, link, precache, bind, not-ready, or program-limit failures;
- requested FBO output that is not ready, FBO init failures, bloom create failures, bloom pass failures, or minimized final output;
- dynamic stream readiness loss under the RC/stress profiles, sync/upload/reservation failures, same-frame wrap rejects, streamed draw fallbacks, material-program stream skips, or high-risk dynamic-light/screen-map/video-map material stream draws;
- static-world renderer or packet batching disabled under the RC/stress profiles, static arena/indirect-buffer failures, or static-world GL errors.
- a `GL12` diagnostic that does not expose the fixed-function executor contract or that claims stream uploads, the GLSL material compiler, or the modern post chain are supported on the GL12 tier.
- a `GL2X` diagnostic that does not expose the programmable executor contract or that treats persistent/modern post/HDR requirements as mandatory on the GL2X tier.
- a `GL3X` diagnostic that does not expose the performance executor contract, omits FBO/UBO/timer/sync/static-buffer/dynamic-buffer ownership, or treats GL4-only persistent upload, indirect submission, or DSA requirements as mandatory on the GL3X tier.
- a `GL41` diagnostic that does not expose the mac-modern executor contract, omits the modern macOS ceiling feature surface, or treats GL4.3 debug output, GL4.4 buffer storage, GL4.5 DSA, MDI, or persistent uploads as mandatory on the GL41 tier.
- a `GL46` diagnostic that does not expose the high-end executor contract or omits persistent uploads, buffer storage uploads, sync-heavy streaming, DSA, MDI, aggressive static-world submission, detailed GPU counters, hardware HDR output, or the required high-end driver feature requirements.

The analyzer also records `glx: ownership legacy delegation ...` diagnostics. Transitional RC gates keep those counters as review evidence, while the ownership-proof `glx-ownership` profile fails when any legacy draw delegation remains.

Ordinary compatibility counters, unsupported capability fallbacks, packet-shape data, skipped material keys, and other tuning metrics remain in the manifest and Markdown summary for review, but they are not treated as blocking failures by themselves.

## Performance Samples

During GLx screenshot captures the sweep briefly enables `r_speeds 7`, waits a small number of frames, captures the screenshot, and disables `r_speeds` again. The compact `glx:` frame-counter lines are parsed into the manifest and Markdown summary as performance samples. They include the five-value product tier, locked pass-schedule text/hash, draw/index pressure, stream strategy/readiness, backend GPU timer text, material renderer failure counts, postprocess output state, stream draw pressure, material-shape stream draw counts, state-only dynamic stream draw counts, and static-world draw/MDI counters.

Named RC gates require at least one GLx frame-counter sample in a non-dry-run screenshot sweep. `--perf-sample-wait` controls the number of frames sampled around each GLx capture, and `--no-perf-samples` is available only for focused local experiments that should not count as RC gate evidence.

Named gates also apply a built-in performance budget to the aggregate sample maxima. The default budget blocks stream rejects, material shader failures, material bind/precache failures, streamed/static draw fallbacks, high-risk dynamic-light/screen-map/video-map material stream draws, and static MDI errors from silently entering RC evidence. For local experiments use `--no-performance-budget`; for runner-specific limits add a JSON file with `--performance-budget`:

```json
{
  "max": {
    "streamDrawFallbacks": 0,
    "staticDrawFallbacks": 0
  },
  "min": {
    "sampleCount": 1
  }
}
```

Performance baselines are separate from hard budgets. Approve a reviewed aggregate sample with `--performance-baseline path/to/glx-performance.json --approve-performance-baseline`, then compare future candidates with `--performance-baseline path/to/glx-performance.json`. Counter growth is checked for draw/index pressure, stream pressure, material-shape and state-only stream draw counts, fallback counters, and static-world counters; `--performance-max-growth-ratio` defaults to 20%. `rc-proof` requires a compared performance baseline rather than an approval run.

## Automated Verification

`.github/workflows/glx-verification.yml` provides the first renderer-focused automation surface for these gates:

- `GLx logic and boundary tests` builds the deterministic `fnq3_glx_logic_tests` target on hosted Ubuntu, then runs both the pure logic tests and the GLx header-boundary scan through CTest.
- `GLx RC gate plans` runs every named gate in `--dry-run` mode, writes the generated configs/manifests/Markdown summaries under `.tmp/glx-gate-plans`, runs the sweep image/diagnostic/performance unit tests, and uploads the gate-plan artifacts. This catches drift between the documented gates and the script-owned cvar/scene presets without requiring retail assets.
- `GLx runtime sweep` is a manual `workflow_dispatch` job for self-hosted GPU runners labeled for GLx validation. It requires a built client executable and a retail `baseq3` basepath, accepts `proof_dir` for hard proof runs, preserves the screenshot threshold and performance-growth inputs whether baselines are explicit or proof-derived, can optionally approve or compare screenshot and performance baselines, accepts an extra performance budget file, writes a Markdown summary, and uploads the full sweep output for review.

The pure logic target intentionally covers GLx decisions that do not need a driver: capability-tier and extension parsing, stream strategy fallback selection, material-key allowlists, static-world packet classification, and static draw-policy gating. Runtime sweeps remain responsible for the parts that require a real OpenGL context, retail assets, and screenshots.

Hosted dry-run gate artifacts are planning evidence only. Blocking RC evidence still requires non-dry-run runtime artifacts from the blocking Windows and Linux matrix.

## Promotion Boundary

Passing these gates is the start of promotion review, not the end of deprecation. `opengl` should only become a migration alias to GLx after RC evidence is reviewed, migration notes are written, and a rollback path remains available. `opengl2` should move behind a legacy build flag before either legacy OpenGL renderer is removed.
