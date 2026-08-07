# World dlights

FnQuake3 can add renderer-owned dynamic lights to a BSP without adding map
entities or changing game, VM, snapshot, protocol, or demo state. A map named
`maps/example.bsp` may provide `maps/example.dlight`. The renderer reads the
sidecar when the world is loaded and submits its visible lights only when both
`r_dlightMode 2` and `r_dlightLoadWorld 1` are active. Missing or invalid files
never prevent the BSP from loading.

The file is UTF-8 JSON with an explicit format name and version:

```json
{
  "format": "fnquake3-world-dlights",
  "version": 1,
  "lights": [
    {
      "name": "upper_hall",
      "type": "spot",
      "origin": [128, -64, 320],
      "direction": [0, 0, -1],
      "color": [1.0, 0.78, 0.55],
      "radius": 480,
      "intensity": 600,
      "innerAngle": 35,
      "outerAngle": 50,
      "castsShadows": true,
      "shadowResolution": 256,
      "priority": 1.0
    }
  ]
}
```

Version 1 supports `point` and `spot` lights. `origin` is the only required
per-light property. A spot's normalized `direction` points away from its
emitting surface. Colors should normally use normalized components from 0 to 1;
the reader also accepts conventional 0-to-255 colors. `radius` controls reach
in Quake world units. `innerAngle` and `outerAngle` are half-angles in degrees
from a spot's centerline. `intensity` is a source-strength weight for view and
shadow budgeting (RGB remains the authored radiance), while `priority` is the
designer multiplier for that ranking. `shadowResolution` requests a raster
spot-atlas tile size between 64 and 1024 pixels.

Omitted properties use conservative authoring defaults: point type, white
color, 300-unit radius and intensity, downward direction, 35/50-degree inner
and outer spot angles, shadow casting enabled, 256-pixel shadow resolution,
and priority 1. The loader accepts at most 256 lights from a file no larger
than 512 KiB. Unknown object properties are skipped so version-1 tools may
attach their own metadata.

## Runtime controls

- `r_dlightLoadWorld 1` enables the loaded sidecar; `0` keeps it out of the
  scene. The default is `1`.
- `r_dlightMode 2` is required. Modes 0 and 1 deliberately ignore world
  dlights so compatibility and model-lighting behavior remain explicit.
- `r_staticLightMaxLights` limits how many visible world lights are promoted
  per view; its default is 8.
- On the raster renderers, `r_staticLightShadows 1` and
  `r_staticLightShadowMaxLights 2` control point world-light shadow
  eligibility. The shared `r_dlightShadows` planner must also be enabled.
- On the raster renderers, `r_spotShadows 1` enables spotlight shadow-map
  planning; this is the default. RTX instead uses each light's
  `castsShadows` value for ray-traced visibility.
- `r_staticLightDebug 1` prints load, visibility, budget, and promotion
  counters.
- `r_dlightReloadWorld` reloads the active map's sidecar. The older
  `r_staticLightReload` command remains as an alias.

The renderer retains read compatibility with the earlier
`maps/<map>.lights.json` prototype when no `.dlight` file exists. New tools
always write the versioned `.dlight` format; a present but invalid `.dlight`
file is reported rather than silently replaced by legacy data.

## Automatic generation

After loading a map, run:

```text
r_dlightGenerateWorld
```

The command exports `maps/<current-map>.dlight` from the current BSP's
non-sky `q3map_surfaceLight` surfaces and reloads it. To protect hand-authored
tuning, it refuses to replace an existing file; use
`r_dlightGenerateWorld force` for an intentional overwrite.

The generator handles planar faces, patch grids, and triangle soups. It
area-weights triangle centroids, geometric normals, and vertex colors; honors
`q3map_lightRGB`/`q3map_lightColor` and the averaged `q3map_lightImage` color;
uses the baked/vertex average as a fallback; and follows
`q3map_lightSubdivide` for large emitters. Each generated light is placed 8 to
64 units above its surface, points a spotlight along the outward averaged
normal, inherits the resolved surfacelight color and intensity, and enables
shadows. The generated file is a first pass intended for review: authors can
adjust radius, cone, priority, or remove redundant lights before packaging it
with the map.

`r_surfaceLightProxies` is a separate live-lighting path fed by the same BSP
metadata. Leave it at `0` when using a generated sidecar unless the duplicate
contribution is intentional; in particular, RTX currently defaults that cvar
to `1` for maps that do not provide authored world dlights.
