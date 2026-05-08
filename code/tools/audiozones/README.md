# Audio Zone Compiler

`fnq3-audiozonesc` compiles optional `maps/<map>.azb` sidecars for the OpenAL
environment system. The game ignores missing or invalid sidecars and keeps the
generic trace-based OpenAL environment heuristics.

Sidecars can be written by hand as `maps/<map>.audiozones`, or generated from an
existing Quake III `maps/<map>.bsp`. Generated zones are intended as a solid
first pass: they are derived from BSP leaves, clusters, areas, surfaces, brushes,
shader contents, and surface flags, then can be merged with small manual
overrides for places that need art-directed tuning.

Example:

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

Build and run:

```powershell
cmake --build .tmp/cmake-check --target fnq3-audiozonesc --config Release
.tmp/cmake-check/fnq3-audiozonesc.exe -o baseq3/maps/q3dm17.azb baseq3/maps/q3dm17.audiozones
.tmp/cmake-check/fnq3-audiozonesc.exe --from-bsp -o baseq3/maps/q3dm17.azb baseq3/maps/q3dm17.bsp
.tmp/cmake-check/fnq3-audiozonesc.exe --from-bsp --merge baseq3/maps/q3dm17.audiozones -o baseq3/maps/q3dm17.azb baseq3/maps/q3dm17.bsp
.tmp/cmake-check/fnq3-audiozonesc.exe --dump baseq3/maps/q3dm17.azb
.tmp/cmake-check/fnq3-audiozonesc.exe --audit --samples 32768 baseq3/maps/q3dm17.azb
```

Supported environment names are `small-room`, `room`, `stone-room`, `hallway`,
`hall`, `outdoors`, and `underwater`. Bounds are axis-aligned boxes in Quake
world units. Higher `priority` wins when zones overlap; equal priorities prefer
the smaller box.

Generated BSP zones use negative priorities, so normal hand-authored zones with
the default priority `0` override them naturally. The compiler writes version 2
sidecars with material classes and portal hints between adjacent generated
volumes. The runtime still accepts version 1 sidecars; with version 2 files it
uses the generated outdoor/underwater flags and applies a bounded crossfade
toward adjacent zone environments when the listener is near a portal hint.

Use `--audit` on generated sidecars before listening passes. It runs the same
runtime parser used by the client, prints preset/material/flag/portal coverage,
reports suspicious overlap or portal patterns, and performs a deterministic
zone lookup/portal-blend profile across the sidecar bounds. `--samples N`
controls the profile grid size; `--strict` returns a non-zero exit code when
warnings are emitted, which is useful for CI experiments or large-map sweeps.
