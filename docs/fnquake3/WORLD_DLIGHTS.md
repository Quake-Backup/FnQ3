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
      "priority": 1.0,
      "fadeStart": 900,
      "fadeEnd": 1400
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

A light's `type` decides which shadow path it can reach: only `point` lights
are eligible for the raster point-shadow (cube) planner, and only `spot`
lights are eligible for the spot-atlas planner. A light authored as a spot is
submitted as a linear light, which the point planner rejects by design.

`fadeStart` and `fadeEnd` are optional viewer distances that fade a light out
instead of letting it pop when it loses the per-view budget or leaves the PVS.
Between the two distances the light's radiance ramps smoothly to zero while
its radius — and therefore the shape of the lit volume — stays fixed; past
`fadeEnd` the light is neither submitted nor allowed to hold a shadow-atlas
tile. Both default to `0`, which disables fading, so sidecars written before
these keys existed behave exactly as they did before. A band that does not end
past where it starts is treated as disabled.

Omitted properties use conservative authoring defaults: point type, white
color, 300-unit radius and intensity, downward direction, 35/50-degree inner
and outer spot angles, shadow casting enabled, 256-pixel shadow resolution,
priority 1, and no distance fade. The loader accepts at most 256 lights from a
file no larger than 512 KiB. Unknown object properties are skipped so
version-1 tools may attach their own metadata.

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

## Debugging

When a sidecar loads but nothing looks different, the answer is almost always
one gate rather than the light data. Two tools cover that:

`r_dlightWorldStatus` prints the whole chain in one shot — which file loaded,
how many point and spot lights it holds, the value of every cvar that can
suppress them, how many lights were promoted, dropped by the PVS, or dropped
by the budget last frame, and how many point shadows were planned versus
rejected. Read it top to bottom; the first line that disagrees with the
expected value is the cause.

`r_dlightDebugDraw` draws each world dlight as wireframe: a cross at the
origin, three great circles at the light's radius, and for a spot the cone
edges plus its inner and outer rim. Only lights in the current PVS are drawn,
so the overlay reads as the set of lights acting on the room you are standing
in rather than every light in the map showing through walls. Mode `1` draws
only the lights promoted this frame; mode `2` adds the ones that passed the
PVS test but did not reach the frame, in grey. Promoted lights draw in their own colour, at half
strength when they did not get a shadow slot. The overlay is drawn over the
scene so lights buried in geometry stay visible, which is usually the point.
Both are cheat-protected and available on the OpenGL and Vulkan renderers.

A light that draws a sphere touching no surface cannot contribute regardless
of how bright it is authored, and a grey light is one the budget or the PVS
dropped rather than one authored wrong. Note that `r_dlightScale` (default
`0.5`) shrinks the submitted radius, so the lit volume is smaller than the
authored sphere the overlay draws.

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
falls back to the average color of the emitter's own texture the way q3map2
does when a shader names neither; uses the baked/vertex average only after
that; and follows
`q3map_lightSubdivide` for large emitters. Each generated light is placed 4
units in front of its surface, points along the outward normal, and inherits
the resolved surfacelight color and intensity. The offset only has to break
the coplanar tie with the emitter; pushing further moves the apparent source
off the fixture and, on a recessed emitter, through the brush behind it. A
proxy whose origin still resolves inside solid geometry is discarded rather
than kept as a light that can never contribute.

"In front of" is decided by the surface's own authored normal — the face plane
for a planar surface, the baked vertex normals for patches and triangle soups
— not by the triangle winding. Quake III culls GL's front face for
`CT_FRONT_SIDED`, so a visible BSP face is wound clockwise when seen from
outside and its winding cross product is the *negation* of the outward normal.
Placing lights along that cross buries every one of them inside the brush it
came from, where it lights nothing and casts no shadow. As a second guard, an
origin that still resolves into a leaf the world cannot see out of is dropped.
`r_surfaceLightProxyDebug 1` reports both as `flipped:` and `solid:` counts.

Each entry carries the classification the proxy builder derived rather than a
fixed shape: a small emitter is exported as a `point` light and a large one as
a `spot`, spots carry the cone angle computed from the emitter's footprint,
and `shadowResolution` follows the light's reach instead of a flat default.
Exporting every entry as a spot — as earlier builds did — silently stripped
every generated point light of its cube shadow on reload. Entries also carry a
`shader` field naming the emitting surface's shader, which the loader ignores
but which lets an author trace a light back to its source.

### Brightness

`q3map_surfaceLight` is a radiosity emission budget, not a dynamic-light peak.
The map already ships that energy baked into its lightmap, so a proxy emitting
at full texture color adds a second copy of light the room has already
received — which washes areas out. The generator instead treats the authored
value as a *relative* strength: it normalizes the resolved color to unit peak,
then scales it by the square root of the emission relative to a reference of
300, so a bright fixture reads brighter without being proportionally hotter.

`r_surfaceLightProxyRadiance` sets the peak a reference-strength emitter
contributes; it defaults to `0.15`. Raise it for more pronounced accents,
lower it if lights still wash out. It is applied when the world is loaded, so
reload the map before running `r_dlightGenerateWorld` to rebake with a new
value. Proxy reach is capped at 1024 units — a proxy is an accent around its
fixture, not an area light for the room.

The generated file is a first pass intended for review: authors can adjust
radius, cone, priority, fade distances, or remove redundant lights before
packaging it with the map.

`r_surfaceLightProxies` is a separate live-lighting path fed by the same BSP
metadata. Leave it at `0` when using a generated sidecar unless the duplicate
contribution is intentional; in particular, RTX currently defaults that cvar
to `1` for maps that do not provide authored world dlights.
