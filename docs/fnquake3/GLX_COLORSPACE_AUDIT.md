# GLx Color-Space Audit

Accepted current-state audit, 2026-05-09.

This document records the GLx/OpenGL-lineage color rules used by the scene-linear pipeline. The compatibility SDR path stays display-referred so retail Quake III visuals and demos do not shift under the default settings. When `r_hdr 1` enables scene-linear rendering, authored color textures are decoded from sRGB at sample time, lighting/post targets remain linear, and the final SDR output shader encodes to sRGB.

## Runtime Controls

| Control | Default | Role |
|---|---:|---|
| `r_hdr` | `0` | Selects display-referred SDR compatibility (`0`) or the scene-linear HDR pipeline (`1`). |
| `r_hdrPrecision` | `0` | Selects internal FBO storage precision; it does not define color space. |
| `r_srgbTextures` | `1` | Allows hardware sRGB decode for authored color images when `r_hdr 1` is active and the backend supports it. |
| `r_framebufferSRGB` | `1` | Allows `GL_FRAMEBUFFER_SRGB` only for actual sRGB-encoded draw targets. The current SDR final pass shader-encodes output, so the OpenGL path keeps this state disabled to avoid double encoding. |
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
| Main scene FBO | Linear numeric storage (`GL_RGBA8`, `GL_RGBA16`, or debug `GL_RGBA4`) | Scene-linear rendering blends into linear targets. The legacy SDR path remains display-referred for compatibility. |
| Bloom extraction and blur | Linear numeric storage | Threshold, blur, and blend operate on linear scene values when `r_hdr 1` is active. |
| Color grading stage | Scene-linear math | Exposure is applied first, then optional lift/gamma/gain, Bradford white-point adaptation, and 3D LUT atlas grading. The stage runs before tone mapping and does not change the default image while controls remain identity. |
| Tone map stage | Scene-linear to display-referred scale | ACES/Reinhard tone mapping is applied after grading when `r_hdr 1` is active. |
| Final SDR output shader | Encodes to SDR sRGB | The shader applies the sRGB transfer function for scene-linear output. Legacy SDR keeps the existing gamma/overbright path. |
| `GL_FRAMEBUFFER_SRGB` | Disabled in the current OpenGL final path | The final shader already writes sRGB-encoded values to the default framebuffer. Enabling fixed-function encode here would double-encode. |
| Screenshot/video capture | SDR sRGB bytes after final output transform | Runtime evidence and baselines should treat captures as SDR sRGB unless a later platform-output task records another capture space. |

## Backend Notes

OpenGL advertises sRGB texture and framebuffer-sRGB capability from extension/core-version probes. `r_speeds 7` and `glxpostprocess` report both the color pipeline and color audit state, including sRGB texture decode, framebuffer-sRGB state, and capture color space.

Vulkan already selects an SDR nonlinear swapchain color space for normal presentation and HDR10 formats only behind native HDR checks. Task Q adds sRGB sampled-image formats for authored color images in the scene-linear path while keeping capture output as SDR sRGB bytes.
