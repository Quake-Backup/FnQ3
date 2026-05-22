<div align="center">

# FnQ3
### Fappin' and Fraggin'

<p>
  <a href="https://github.com/themuffinator/FnQ3/releases/latest"><img alt="Latest Release" src="https://img.shields.io/badge/Latest-Release-2563eb?style=for-the-badge"></a>
  <a href="#3-getting-started"><img alt="Getting Started" src="https://img.shields.io/badge/Getting-Started-16a34a?style=for-the-badge"></a>
  <a href="#4-documentation"><img alt="Documentation" src="https://img.shields.io/badge/Documentation-7c3aed?style=for-the-badge"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-GPL--2.0-c2410c?style=for-the-badge"></a>
</p>

*Compatibility target: Retail Quake III Arena 1.32 · Base version: `0.1.0` · Current build: `0.1.0`*

</div>

## 1. Introduction

**FnQ3** is a modernized *Quake III Arena* source port for players who want the original game to feel at home on current hardware without losing what made it special in the first place.

What sets it apart is the balance: FnQ3 keeps retail compatibility, demos, and classic content behavior front and center, while adding cleaner presentation, better platform support, a stronger day-to-day user experience, and carefully chosen modern features that still respect the base game.

## 2. Features

### Play the original game with a cleaner modern fit

- Keeps retail *Quake III Arena* compatibility as the priority, including classic game data, demo playback, and mod expectations.
- Ships with modern platform support built around **SDL3** for video, audio, and input.
- Uses a modern **OpenAL**-based audio path by default, with spatial sound improvements and a safe fallback to the classic mixer when needed.

### Sharper presentation without changing the identity of Quake III

- Flexible display options with renderer choice, fullscreen and windowed play, render scaling, texture picmip filtering, HDR, anti-aliasing, bloom tuning, and cel-shaded world/model presentation. See the [Display Guide](docs/DISPLAY.md).
- High-quality dynamic lights and opt-in dynamic-light shadow maps for GLx/OpenGL-lineage and Vulkan renderers, with compatibility-safe defaults. See the [Display Guide](docs/DISPLAY.md#dynamic-lighting-and-shadowing).
- Optional visual polish such as soft particles, player rim lighting, stencil-style highlights, model cel lighting, and BSP world depth-edge outlines. See the [Display Guide](docs/DISPLAY.md#soft-particles) and [Visuals Guide](docs/VISUALS.md).
- Better widescreen handling for HUDs, menus, UI previews, and cinematics. See the [Aspect Correction Guide](docs/ASPECT_CORRECTION.md).

### Better everyday usability

- An upgraded console with smoother scrolling, scaling options, mouse support, text selection, drag and drop, and live completion help. See the [Console Guide](docs/CONSOLE.md).
- Expanded screenshot tools with cleaner naming, optional metadata sidecars, watermark support, and cube-map capture. See the [Screenshot Guide](docs/SCREENSHOTS.md).
- Quality-of-life touches like live rainbow text preview and more flexible player-facing configuration.

### Wider content compatibility

- Supports older **Quake 3 IHV / q3test** maps and legacy **`.dm3`** demos alongside standard retail content.
- Includes practical compatibility for selected **Quake Live** assets such as `IBSP v47` maps, encrypted beta `.pk3` archives, and related material behavior.
- Reads **Quake II** `.pak` archives and `.wal` textures for broader content experimentation.

## 3. Getting Started

1. Install *Quake III Arena* and make sure your original `baseq3` game data is present.
2. Download the latest FnQuake3 build from the [latest release page](https://github.com/themuffinator/FnQ3/releases/latest).
3. Extract the release archive into your Quake III Arena folder so the FnQuake3 executables sit next to your existing game files.
4. Start the FnQuake3 executable for your platform.
5. If you want to tune visuals, audio, screenshots, or the console, use the guides in the [Documentation](#4-documentation) section below.

If you want to compile FnQuake3 yourself instead, start with the [Build Guide](BUILD.md).

## 4. Documentation

### Player guides

- [Display Guide](docs/DISPLAY.md) for renderer choice, video modes, render scaling, texture picmip, HDR, anti-aliasing, bloom, soft particles, dynamic lighting, shadow maps, and cel shading.
- [Visuals Guide](docs/VISUALS.md) for player highlighting and other presentation controls.
- [Aspect Correction Guide](docs/ASPECT_CORRECTION.md) for HUD, menu, and cinematic layout options.
- [Audio Guide](docs/AUDIO.md) for backend selection, devices, HRTF, fallback behavior, and troubleshooting.
- [Console Guide](docs/CONSOLE.md) for console layout, scaling, completion, and interaction.
- [Screenshot Guide](docs/SCREENSHOTS.md) for capture commands, naming, metadata sidecars, watermarks, and cube-map export.
- [Changelog](docs/fnquake3/CHANGELOG.md) for release-facing change history.

### Technical and build docs

- [Build Guide](BUILD.md) for compiling FnQuake3 locally.
- [GLx Renderer Guide](docs/GLX.md) for the canonical OpenGL-lineage renderer, migration notes, and troubleshooting.
- [Modern Audio Engine Notes](docs/fnquake3/AUDIO_ENGINE.md) for engine architecture and compatibility boundaries.
- [Technical Notes](docs/fnquake3/TECHNICAL.md) for repository structure, release flow, and maintainer conventions.

## 5. Credits

FnQuake3 follows a clear upstream lineage from the [Quake III Arena SDK](https://github.com/id-Software/Quake-III-Arena), through [ioquake3](https://github.com/ioquake/ioq3), to [Quake3e](https://github.com/ec-/Quake3e), and then onward through the project-specific work in this repository.

Additional compatibility and feature work draws from projects and references such as [CNQ3](https://bitbucket.org/CPMADevs/cnq3), [Spearmint](https://github.com/zturtleman/spearmint), [WolfcamQL](https://github.com/brugal/wolfcamql), Luigi Auriemma's [qldec](https://aluigi.altervista.org/papers.htm#qldec), and [DarkMatter-Q2](https://github.com/Paril/DarkMatter-Q2).

See [CREDITS.md](CREDITS.md) for the fuller credits list and project acknowledgements.
