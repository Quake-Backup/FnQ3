# GLx Color-Space Audit

Accepted current-state audit, 2026-05-09.

This document records the GLx/OpenGL-lineage color rules used by the scene-linear pipeline. The compatibility SDR path stays display-referred so retail Quake III visuals and demos do not shift under the default settings. When `r_hdr 1` enables scene-linear rendering, authored color textures are decoded from sRGB at sample time, lighting/post targets remain linear, and the final SDR output shader encodes to sRGB.

## Runtime Controls

| Control | Default | Role |
|---|---:|---|
| `r_hdr` | `0` | Selects display-referred SDR compatibility (`0`) or the scene-linear HDR pipeline (`1`). |
| `r_hdrPrecision` | `0` | Selects SDR/debug FBO storage precision; `r_hdr 1` always requires an explicit floating-point `RGBA16F` scene target. |
| `r_srgbTextures` | `1` | Allows hardware sRGB decode for authored color images when `r_hdr 1` is active and the backend supports it. |
| `r_framebufferSRGB` | `1` | Allows `GL_FRAMEBUFFER_SRGB` only for actual sRGB-encoded draw targets. The current SDR final pass shader-encodes output, so the OpenGL path keeps this state disabled to avoid double encoding. |
| `r_glxColorPipelineDebug` | `0` | Emits per-frame color-pipeline metadata: `1` prints CSV rows, `2` prints JSON rows. |
| `r_colorGrade` | `0` | Enables the scene-linear grading stage for `r_hdr 1`; the default is disabled and identity-safe. |
| `r_colorGradeLUT` | empty | Optional 3D LUT atlas. Atlases are sampled as linear data and use width `N*N`, height `N`, with blue slices laid out horizontally. |

## Texture Classes

| Texture class | Examples | Declared space | Scene-linear sampling |
|---|---|---|---|
| Authored color maps | map textures, model skins, sky images, UI images, cinematic scratch frames, replacement default image | sRGB | OpenGL uses `GL_SRGB8` / `GL_SRGB8_ALPHA8` when `r_hdr 1` and `r_srgbTextures 1`; Vulkan uses `VK_FORMAT_R8G8B8A8_SRGB`. |
| Lightmaps | BSP lightmaps, merged lightmap atlases, external `maps/<map>/lm_*` atlases | linear lighting data | Never sRGB-decoded. Existing overbright/lightscale baking remains compatibility-sensitive. |
| Procedural light data | `*dlight`, `*identityLight` | linear | Never sRGB-decoded. |
| Lookup/data textures | `*fog`, solid utility images | data | Never sRGB-decoded. |
| Upload/capture targets | FBO color, bloom chain, screen-map/capture buffers | linear or SDR output as declared by pass | Not sampled as authored sRGB unless explicitly created as an authored color image. |

## Framebuffer And Blending Rules

| Pass or target | Storage/encoding | Rule |
|---|---|---|
| Main scene FBO | SDR/debug storage uses `GL_RGBA8`, `GL_RGBA16`, or debug `GL_RGBA4`; `r_hdr 1` uses `GL_RGBA16F` with upload format `GL_RGBA` and type `GL_HALF_FLOAT` | Scene-linear rendering blends into a floating-point linear target. Init fails if `r_hdr 1` does not get a float scene target. The legacy SDR path remains display-referred for compatibility. |
| Bloom extraction and blur | Linear numeric storage | Threshold, blur, and blend operate on linear scene values when `r_hdr 1` is active. |
| Color grading stage | Scene-linear math | Exposure is applied first, then optional lift/gamma/gain, Bradford white-point adaptation, and 3D LUT atlas grading. The stage runs before tone mapping and does not change the default image while controls remain identity. |
| Tone map stage | Scene-linear to display-referred scale | ACES/Reinhard tone mapping is applied after grading when `r_hdr 1` is active. |
| Final SDR output shader | Encodes to SDR sRGB | The shader applies the sRGB transfer function for scene-linear output. Legacy SDR keeps the existing gamma/overbright path. This is the selected SDR contract: shader encode, not fixed-function framebuffer encode. |
| `GL_FRAMEBUFFER_SRGB` | Disabled in the current OpenGL final path | The final shader already writes sRGB-encoded values to the default framebuffer. Enabling fixed-function encode here would double-encode. |
| Screenshot/video capture | SDR sRGB bytes after final output transform | Runtime evidence and baselines should treat captures as SDR sRGB unless a later platform-output task records another capture space. |

## Backend Notes

OpenGL advertises sRGB texture and framebuffer-sRGB capability from extension/core-version probes. `r_speeds 7` and `glxpostprocess` report both the color pipeline and color audit state, including sRGB texture decode, framebuffer-sRGB state, capture color space, float scene-target state, final encode path, and output-contract validity. When hardware HDR/EDR output is inactive, SDR output clamps max-output nits to paper white instead of reserving HDR headroom. The texture audit manifest reports authored sRGB, linear, data, and unknown image counts plus the number of images decoded through sRGB. Missing authored sRGB decode rows and unexpected decode on linear/data rows are proof failures.

The canonical classification rows live in [GLX_TEXTURE_CLASSIFICATION_MANIFEST.json](GLX_TEXTURE_CLASSIFICATION_MANIFEST.json). Runtime sweeps preserve color evidence in three places: compact `r_speeds 7` counters, per-frame `glx: color-frame-csv` or `glx: color-frame-json` rows from `r_glxColorPipelineDebug`, and screenshot color/luma histograms attached to capture results. Captured PNGs also get `.histogram.json` and `.luma-falsecolor.png` sidecars for artifact review. Diagnostic gates force JSON color-frame output for the run unless explicitly overridden, and then reject the artifact if per-frame color metadata is missing. Release gates require the color pipeline, color audit, output backend, texture audit, target-format metadata, performance color metadata, color-frame metadata, screenshot histogram metadata, and color-sweep luma false-color sidecar metadata to be present before accepting GLx proof.

The P0 color sweep matrix is executed as separate GLx launches so latched controls such as `r_srgbTextures` and `r_outputBackend` are applied before renderer startup. It includes a legacy SDR bloom-off reference, scene-linear SDR rows for legacy, Reinhard, and ACES tone mapping, low/high exposure probes, an authored-texture sRGB-decode control row that must prove decode is disabled in both compact diagnostics and per-frame color dumps, an automatic output-backend row for native SDR/HDR platform evidence, and an explicit Windows scRGB request row that falls back safely when HDR output is unavailable.

Vulkan already selects an SDR nonlinear swapchain color space for normal presentation and HDR10 formats only behind native HDR checks. Task Q adds sRGB sampled-image formats for authored color images in the scene-linear path while keeping capture output as SDR sRGB bytes.
