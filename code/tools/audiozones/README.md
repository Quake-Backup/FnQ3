# Audio Zone Compiler

`fnq3-audiozonesc` compiles optional maintainer-authored `maps/<map>.audiozones`
files into compact `maps/<map>.azb` sidecars. The game ignores missing or invalid
sidecars and keeps the generic trace-based OpenAL environment heuristics.

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
.tmp/cmake-check/fnq3-audiozonesc.exe --dump baseq3/maps/q3dm17.azb
```

Supported environment names are `small-room`, `room`, `stone-room`, `hallway`,
`hall`, `outdoors`, and `underwater`. Bounds are axis-aligned boxes in Quake
world units. Higher `priority` wins when zones overlap; equal priorities prefer
the smaller box.
