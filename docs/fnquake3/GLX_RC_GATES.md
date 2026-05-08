# GLx Release Candidate Gates

## Status

This document freezes the initial GLx release-candidate target. GLx remains experimental until the blocking gates here pass on the blocking runtime matrix and the captured artifacts have been reviewed.

The gates are intentionally conservative. They prove that GLx can load through the existing renderer ABI, survive renderer switching and `vid_restart`-equivalent paths, preserve the current OpenGL display surface, and stay close enough to the legacy OpenGL renderer to justify the next ownership work. They are not permission to remove `opengl` or `opengl2`.

## Blocking Runtime Matrix

The first GLx RC requires runtime evidence on:

- Windows 10 or newer, x64, dynamic renderer build, retail `baseq3` assets.
- Linux x86_64, Mesa or vendor OpenGL driver, dynamic renderer build, retail `baseq3` assets.

Every blocking run must expose at least the GLx compatibility floor: OpenGL 2.1 with GLSL 1.20. Core-tier and advanced-tier features are optional accelerators. Missing persistent mapping, sync objects, multidraw, indirect draw, or debug-output support must select a fallback path rather than fail renderer initialization.

Nightly packaging should continue to build GLx wherever the repository already enables `USE_GLX`, including Windows x86, macOS, Linux aarch64, and other packaged targets. Those platforms need at least manual smoke coverage before GLx becomes the default or `opengl` becomes an alias, but they are not blockers for the first conservative RC unless maintainers add stable GPU runners for them.

## Canonical Gate Presets

`scripts/glx_runtime_sweep.py` owns the machine-readable gate presets. Use `--list-gates` to print the current script view.

| Gate | Purpose | Profile | Scene Set | Automated Floor |
|---|---|---|---|---|
| `rc-smoke` | Renderer lifecycle smoke: module load, map load, repeated in-process renderer switches, screenshots, and GLx diagnostics. | `baseline` | `q3dm1` | All runs pass and all expected screenshots are written. |
| `rc-parity` | Blocking conservative RC gate for world, ordered packet-batch static spans, stream paths including CPU-computed texmods and environment coordinates, material, bloom, and GPU-timing paths. | `glx-parity` / `r_glxProfile rc` | `q3dm1`, `q3dm17`, `demo1` | All runs pass, all screenshots are written, and GLx timedemo FPS is at least 90% of `opengl` on the same machine and demo. |
| `rc-stress` | Developer stress gate for indirect static-world paths before any advanced GLx path becomes a default. | `glx-stress` / `r_glxProfile stress` | `q3dm1`, `q3dm17`, `demo1` | All runs pass, screenshots are written, and timedemo metrics are captured. |

The initial scene set is deliberately small and stock-data friendly. It may grow as bugs are found, but it should not shrink during an RC cycle.

The profile names are not just documentation labels. `glx-parity` launches GLx with `r_glxProfile rc`, and `glx-stress` launches GLx with `r_glxProfile stress`, so startup-sensitive resources are built under the same profile that `glxprofile status` reports in the renderer.

## Exit Criteria

A GLx RC candidate must meet all of these conditions:

- `rc-smoke` and `rc-parity` pass on every blocking runtime platform.
- The generated manifest, logs, screenshots, and timedemo metrics are archived with the candidate build.
- The GLx timedemo result is at least 90% of the legacy `opengl` timedemo result for each required demo on the same machine. A lower result needs a tracked waiver with the measured cause.
- Manual screenshot review finds no unexplained drift in world visibility, sky, fog, lightmaps, weapon placement, marks/decals, particles, HUD/2D, bloom, gamma, or final output size.
- GLx diagnostic output shows no shader compile/link failures, material path `not-ready` state, GL errors, postprocess fallback output, or unexpected loss of the static-world/stream fallback guarantees.
- `renderer_switch opengl,glx,opengl,glx` loops do not leak state, fail screenshot capture, lose the cgame/UI, or leave the next renderer in a partially initialized state.
- `rc-stress` is clean before indirect static-world or other advanced GLx paths are promoted to default behavior.

Failing any blocking criterion keeps GLx experimental. The fix may be renderer code, a narrower default GLx profile, a documented waiver, or a larger test corpus, but it should not be a silent default promotion.

## Typical Commands

From the repository root:

```sh
python scripts/glx_runtime_sweep.py --list-gates
python scripts/glx_runtime_sweep.py --gate rc-smoke --exe path/to/fnquake3.glx.x64.exe --basepath path/to/game/root
python scripts/glx_runtime_sweep.py --gate rc-parity --exe path/to/fnquake3.glx.x64.exe --basepath path/to/game/root
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

## Diagnostic Gate Analysis

Non-dry-run gate manifests now include structured analysis of the GLx diagnostic commands emitted during screenshot sweeps. The analyzer reads the `glxmaterial`, `glxpostprocess`, and `glxstaticworld`/stream sections from the run log and fails the gate on release-blocking renderer states:

- material renderer enabled but not ready under the RC/stress profiles;
- material compile, link, precache, bind, not-ready, or program-limit failures;
- requested FBO output that is not ready, FBO init failures, bloom create failures, bloom pass failures, or minimized final output;
- dynamic stream readiness loss under the RC/stress profiles, sync/upload/reservation failures, same-frame wrap rejects, or streamed draw fallbacks;
- static-world renderer or packet batching disabled under the RC/stress profiles, static arena/indirect-buffer failures, or static-world GL errors.

Ordinary compatibility counters, unsupported capability fallbacks, packet-shape data, skipped material keys, and other tuning metrics remain in the manifest and Markdown summary for review, but they are not treated as blocking failures by themselves.

## Performance Samples

During GLx screenshot captures the sweep briefly enables `r_speeds 7`, waits a small number of frames, captures the screenshot, and disables `r_speeds` again. The compact `glx:` frame-counter lines are parsed into the manifest and Markdown summary as performance samples. They include tier, draw/index pressure, stream strategy/readiness, backend GPU timer text, material renderer failure counts, postprocess output state, stream draw pressure, and static-world draw/MDI counters.

Named RC gates require at least one GLx frame-counter sample in a non-dry-run screenshot sweep. `--perf-sample-wait` controls the number of frames sampled around each GLx capture, and `--no-perf-samples` is available only for focused local experiments that should not count as RC gate evidence.

Named gates also apply a built-in performance budget to the aggregate sample maxima. The default budget blocks stream rejects, material shader failures, material bind/precache failures, streamed/static draw fallbacks, and static MDI errors from silently entering RC evidence. For local experiments use `--no-performance-budget`; for runner-specific limits add a JSON file with `--performance-budget`:

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

Performance baselines are separate from hard budgets. Approve a reviewed aggregate sample with `--performance-baseline path/to/glx-performance.json --approve-performance-baseline`, then compare future candidates with `--performance-baseline path/to/glx-performance.json`. Counter growth is checked for draw/index pressure, stream pressure, fallback counters, and static-world counters; `--performance-max-growth-ratio` defaults to 20%.

## Automated Verification

`.github/workflows/glx-verification.yml` provides the first renderer-focused automation surface for these gates:

- `GLx logic tests` builds and runs the deterministic `fnq3_glx_logic_tests` target on hosted Ubuntu.
- `GLx RC gate plans` runs every named gate in `--dry-run` mode, writes the generated configs/manifests/Markdown summaries under `.tmp/glx-gate-plans`, runs the sweep image/diagnostic/performance unit tests, and uploads the gate-plan artifacts. This catches drift between the documented gates and the script-owned cvar/scene presets without requiring retail assets.
- `GLx runtime sweep` is a manual `workflow_dispatch` job for self-hosted GPU runners labeled for GLx validation. It requires a built client executable and a retail `baseq3` basepath, can optionally approve or compare screenshot and performance baselines, accepts an extra performance budget file, writes a Markdown summary, and uploads the full sweep output for review.

The pure logic target intentionally covers GLx decisions that do not need a driver: capability-tier and extension parsing, stream strategy fallback selection, material-key allowlists, static-world packet classification, and static draw-policy gating. Runtime sweeps remain responsible for the parts that require a real OpenGL context, retail assets, and screenshots.

Hosted dry-run gate artifacts are planning evidence only. Blocking RC evidence still requires non-dry-run runtime artifacts from the blocking Windows and Linux matrix.

## Promotion Boundary

Passing these gates is the start of promotion review, not the end of deprecation. `opengl` should only become a migration alias to GLx after RC evidence is reviewed, migration notes are written, and a rollback path remains available. `opengl2` should move behind a legacy build flag before either legacy OpenGL renderer is removed.
