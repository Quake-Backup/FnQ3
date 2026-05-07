# Technical Notes

## Purpose

This file is the maintainer-facing companion to [`README.md`](../../README.md). Keep user installation guidance in the README and use this document for repo structure, release flow, and implementation conventions.

## Project Constraints

FnQuake3 exists to modernize Quake III Arena without losing the properties that make it a long-lived engine target:

1. Retail Quake III Arena compatibility stays intact.
2. Demo playback compatibility stays intact.
3. Performance regressions need a clear reason and measurement.
4. Platform additions should not silently narrow the supported matrix.

Compatibility-sensitive areas include:

- demo parsing and recording
- network protocol behavior
- filesystem search order and pak loading
- VM ABI and bytecode execution
- renderer defaults that affect demo output or deterministic behavior

## Repository Layout

- [`code/`](../../code): engine and platform code.
- [`docs/`](../../docs): technical docs, upstream reference material, and README templates.
- [`version/`](../../version): shared project version metadata.
- [`scripts/`](../../scripts): repo-local automation for docs and release packaging.
- [`.install/`](../../.install): tracked distribution docs plus generated manifests and package archives.
- [`.tmp/`](../../.tmp): ignored scratch workspace for temporary outputs.

## Versioning

The canonical metadata lives in [`version/fnq3_version.h`](../../version/fnq3_version.h).

That header feeds:

- runtime version strings via [`code/qcommon/q_shared.h`](../../code/qcommon/q_shared.h)
- Windows resource metadata via [`code/win32/win_resource.rc`](../../code/win32/win_resource.rc)
- Make and CMake version reporting
- documentation rendering
- nightly and tagged release archive naming

Current policy:

- Tagged releases use semantic version tags in the form `vX.Y.Z`.
- Nightly builds produce a unique tag per build (e.g. `nightly-0.1.0.42-20240403-abc12345`), combining the build version, date, and commit for a persistent per-build release.
- The base version in `fnq3_version.h` should always represent the next intended stable release line.
- Release-facing change history lives in [`docs/fnquake3/CHANGELOG.md`](./CHANGELOG.md). Keep the `Unreleased` section current as work lands.
- Use [`scripts/changelog.py`](../../scripts/changelog.py) to extract a section or promote `Unreleased` into a dated release section during tagging.

Typical changelog helper usage:

```powershell
python scripts/changelog.py section --version Unreleased
python scripts/changelog.py prepare-release --version 0.1.0 --date 2026-04-25
```

## Docs Flow

The user-facing docs are generated from templates:

- [`docs/templates/README.md.in`](../templates/README.md.in)
- [`docs/templates/install-readme.html.in`](../templates/install-readme.html.in)

Refresh them with:

```powershell
python scripts/generate_docs.py
```

That command rewrites:

- [`README.md`](../../README.md)
- [`.install/README.html`](../../.install/README.html)

## Release Packaging

The packaging entry point is [`scripts/release.py`](../../scripts/release.py).
Nightly CI orchestration lives in [`scripts/nightly.py`](../../scripts/nightly.py).

Typical local usage:

```powershell
python scripts/nightly.py summary
python scripts/release.py --channel nightly --artifact-root <downloaded-artifacts-dir>
python scripts/release.py --channel release --artifact-root <downloaded-artifacts-dir> --ref-name v0.1.0
```

The script:

1. refreshes generated docs
2. stages each platform artifact under `.tmp/release/`
3. injects shared docs into the staged package
4. writes versioned `.zip` archives into `.install/packages/`
5. emits `.install/release-manifest.json` and `.install/SHA256SUMS.txt`

## CI Notes

[`.github/workflows/nightly.yml`](../../.github/workflows/nightly.yml) owns scheduled and manual nightly publishing.

Expected behavior:

- pull requests build only
- `main` pushes validate the main branch without publishing a nightly release
- scheduled nightly runs produce a new unique-tagged release per build when `main` has advanced since the last nightly
- published GitHub releases upload stable archives built from the tagged version

## Audio Backend Notes

- The default client audio path is the OpenAL backend selected by `s_backend openal`.
- `s_backend legacy` keeps the original Quake III mixer/device backend available as a fallback path.
- OpenAL headers are vendored under [`code/openal/include`](../../code/openal/include), and Windows x86/x64 package builds stage a matching `OpenAL32.dll` from [`code/openal/windows`](../../code/openal/windows).
- The runtime reporting cvar is `s_backendActive`. Device selection for the OpenAL backend uses `s_alDevice`.
- The OpenAL backend also exposes `s_alReverb`, `s_alOcclusion`, `s_alReverbGain`, and `s_alOcclusionStrength` for the environmental spatial layer. Reverb enablement is latched because the EFX reverb slot is created at backend init. Listener environment changes blend EFX preset parameters and per-source wet/tone values over a short transition, with the active-to-target environment visible in the spatial debug overlay and `s_alDebugDump`. Occlusion traces feed a smoothed per-voice target; direct-path attenuation is kept separate from tone-filter sweeps so wall transitions do not zipper. The per-voice EFX filters are intentionally limited to low-pass, high-pass, and band-pass presets chosen by source class and occlusion/environment state.
- Modern OpenAL startup requests are exposed as latched cvars: `s_alHrtf`, `s_alHrtfId`, `s_alOutputMode`, `s_alDistanceModel`, `s_alFrequency`, `s_alRefresh`, `s_alMonoSources`, `s_alStereoSources`, `s_alOutputLimiter`, and `s_alSpatializeStereo`. Context creation first tries requested modern attributes, then standard source/frequency hints, then default attributes before the outer backend fallback can select legacy. Keep `s_info` as the canonical place to compare requested values against active runtime/device values. When `ALC_SOFT_device_clock` is available, `s_info` should refresh the clock/latency query live so latency diagnostics are current instead of just an init-time snapshot.
- OpenAL enumeration is available through `s_alListDevices` and `s_alListHrtfs`. The HRTF command uses the live OpenAL device when possible and otherwise opens the requested/default device temporarily for diagnostics.
- Mono world sounds use true OpenAL positional sources driven by Quake listener/source coordinates. They use the active standard OpenAL distance model with reference distance `80`, max distance `1330`, and rolloff `1`. Keep local/UI/announcer, raw/music streams, and authored multi-channel samples non-spatial. Two-channel world samples also stay direct by default and may only enter positional routing through the opt-in `s_alSpatializeStereo` compatibility switch when `AL_SOFT_source_spatialize` is available. Stereo and surround samples/streams should request `AL_DIRECT_CHANNELS_SOFT` when `AL_SOFT_direct_channels` is available, and prefer `AL_REMIX_UNMATCHED_SOFT` when `AL_SOFT_direct_channels_remix` is available so unmatched authored channels are folded into narrower output layouts. `AL_EXT_MCFORMATS` gates native quad/5.1/6.1/7.1 PCM submission; runtimes without it must keep playing authored surround content through the stereo downmix fallback.
- World voice property updates are batched with `AL_SOFT_deferred_updates` when available. Keep streaming queue updates outside that batch so music/raw buffer progress remains straightforward to reason about.
- `FNQ3_AUDIO_LOOPBACK_TESTS` builds `fnq3_audio_loopback_tests`, a headless OpenAL Soft loopback harness under [`tests/audio`](../../tests/audio). It dynamically loads OpenAL, skips with exit code `77` when `ALC_SOFT_loopback` is unavailable, and otherwise verifies HRTF status visibility, distance attenuation, stereo channel isolation, optional 5.1 buffer acceptance, idle silence, and EFX low-/high-/band-pass filters. CTest registers it as `fnq3_audio_loopback`.
- `AL_SOFT_source_latency` is optional. When present, `s_alDebugDump` should use `AL_SEC_OFFSET_LATENCY_SOFT` for the selected OpenAL source so voice-level offset/latency diagnostics line up with the device-level clock/latency values printed by `s_info`.
- `s_alSourceClassDebug` is a developer cvar for dump-only source-class aggregation. It should not affect source allocation, routing, filters, or playback state.
- `fnq3-audiozonesc` builds the optional audio-zone sidecar compiler under [`code/tools/audiozones`](../../code/tools/audiozones). It compiles `maps/<mapname>.audiozones` text files into little-endian `maps/<mapname>.azb` files with AABB zones, preset index, reverb gain, occlusion multiplier, LF/HF tone multipliers, transition time, priority, and a short debug name. Runtime loading uses normal `FS_ReadFile` search semantics, so sidecars can live loose or in packages without creating a new asset path.
- Keep dedicated-server builds free of the OpenAL runtime dependency.

### Audio Zone Sidecars

Audio zones are an optional polishing path, not a map requirement. Missing files, invalid files, disabled zones, and listener positions outside every authored zone must fall back to the generic listener-probe environment heuristics.

Runtime behavior:

- Current map `maps/foo.bsp` maps to sidecar `maps/foo.azb`.
- `s_alAudioZones 1` enables sidecar loading; `s_alAudioZones 0` forces generic heuristics.
- The sidecar is rechecked when the active map path or the cvar state changes.
- Higher `priority` wins for overlapping zones. Equal priorities prefer the smaller AABB so nested rooms override broader area zones naturally.
- The selected zone overrides only the audio environment values. It does not affect collision, visibility, demos, protocol, VM behavior, entity state, or asset compatibility.
- If a selected zone uses the `outdoors` or `underwater` preset, the corresponding environment flag is set so the existing tone-class logic keeps behaving consistently.
- `s_info`, `s_alDebugOverlay 2`, and `s_alDebugDump` expose whether zones are active and which values they contributed.

The source format intentionally stays small:

```text
audiozones 1

zone "atrium" {
  bounds -512 -512 -64 512 512 384
  environment hall
  reverbGain 1.10
  occlusionMultiplier 0.85
  lpfBias 0.95
  hpfBias 1.00
  transitionMs 900
  priority 10
}
```

Accepted environment names are `small-room`, `room`, `stone-room`, `hallway`, `hall`, `outdoors`, and `underwater`. `bounds` may be replaced by separate `mins` and `maxs` properties. `directHF`/`wetHF` and `directLF`/`wetLF` are available when a zone needs separate low-pass or high-pass bias instead of the combined `lpfBias`/`hpfBias` shortcuts.

### Audio Migration Expectations

- Treat the modern audio work as client render-side only. It must not alter demo formats, network protocol behavior, filesystem search order, VM ABI behavior, or which sound assets/mods are accepted.
- Preserve existing player controls and config behavior when adding OpenAL features. `s_backend`, `s_backendActive`, `s_alDevice`, `s_alReverb`, `s_alOcclusion`, `s_alReverbGain`, `s_alOcclusionStrength`, `s_doppler`, `s_info`, and `s_alDebugDump` are compatibility surfaces now, not throwaway diagnostics.
- Keep new OpenAL startup cvars latched and request-oriented. The runtime may legitimately choose a different active HRTF state, output mode, source count, limiter state, frequency, or refresh rate; `s_info` should remain the canonical requested-vs-active report.
- Keep fallback deterministic and observable: requested device first, system default device if the requested device cannot be opened, safer OpenAL context attributes next, then legacy backend fallback. Console warnings should explain denied or unsupported requests without treating normal OpenAL capability differences as fatal errors.
- Keep mono world sounds positional and keep local/UI/announcer, raw/music streams, and stereo samples on the direct non-spatial path by default. `s_alSpatializeStereo` is an opt-in compatibility escape hatch for two-channel world samples only, and only on runtimes with `AL_SOFT_source_spatialize`; authored surround layouts must remain direct.
- Keep audio-zone sidecars optional and data-only. They may refine environmental rendering, but must not become required content or a gameplay contract.
- Update [`docs/AUDIO.md`](../AUDIO.md) for player-facing defaults and troubleshooting, and update the README templates rather than hand-editing generated README outputs. After template changes, run `python scripts/generate_docs.py`.
- Validate audio-facing migration changes with a normal client build. When OpenAL Soft loopback is available, also run the `fnq3_audio_loopback` CTest target so HRTF reporting, distance gain, direct stereo routing, idle silence, and EFX filters stay covered.

## Naming

Active build, packaging, and distribution surfaces should use `FnQuake3` naming consistently.
Historical upstream references should only remain where they are part of provenance, copyright notices, or archived material.
