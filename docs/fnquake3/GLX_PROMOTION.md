# GLx Promotion Gate

## Status

GLx is the canonical OpenGL-lineage renderer module, but it is not the default renderer yet. The default renderer remains `opengl`, `cl_renderer glx` remains an explicit selection path, and `opengl2` remains a separately selectable legacy renderer when built.

The promotion gate is intentionally stricter than the RC gate. RC proof shows that the current compatibility-first GLx surface is viable. Promotion proof is the point where maintainers may safely make `opengl` a migration alias for GLx and move `opengl2` behind a legacy build flag.

Run the local status check with:

```sh
python scripts/glx_promotion.py
```

Require a fully green promotion decision with reviewed runtime evidence:

```sh
python scripts/glx_promotion.py --proof-root .tmp/glx-proof --require-ready
```

The script reports `blocked` while the repository is still policy-compliant but not ready. It reports `failed` if the source tree has already promoted renderer defaults before the required proof is present.

## Required Inputs

The gate requires all of the following:

- every row in [GLX_FEATURE_MATRIX.md](GLX_FEATURE_MATRIX.md) is `covered`;
- the five product tiers `GL12`, `GL2X`, `GL3X`, `GL41`, and `GL46` remain represented in code and documentation;
- the GLx proof root contains passing non-dry-run `rc-smoke`, `rc-parity`, and `rc-proof` manifests for the blocking Windows and Linux platforms;
- the same proof root contains passing non-dry-run `glx-ownership` profile manifests for the blocking Windows and Linux platforms, with ownership diagnostics reporting zero legacy delegation;
- the release candidate has reviewed migration notes and a rollback package plan.

## Migration Alias Plan

After the promotion gate reports `ready`, `opengl` may become a migration alias for GLx. That change must preserve user intent and compatibility:

- `cl_renderer glx` continues to load the GLx module directly;
- `cl_renderer opengl` resolves to GLx only in promoted builds and must still fail closed if GLx is missing;
- saved configs using `opengl` remain valid;
- release notes identify the alias, the affected platforms, and how to select the legacy package if needed;
- demos, protocols, VM ABI, pak loading, and default gameplay cvars remain unchanged.

Before the gate is ready, `opengl` must continue to select the legacy OpenGL renderer, and build defaults must remain `RENDERER_DEFAULT=opengl`.

## OpenGL2 Legacy Flag Plan

`opengl2` must not disappear as part of the alias change. Once GLx is promoted, `opengl2` can move behind an explicit legacy build flag and stay available for rollback, driver comparison, and old configuration recovery. The build and packaging notes must name the flag and the packages that still include the legacy renderer module.

## Rollback Package Contract

Every promoted release needs a rollback package or documented package variant that keeps the legacy OpenGL renderer available. The rollback package must include:

- the same engine version metadata and protocol behavior as the promoted package;
- the legacy OpenGL renderer module and, when applicable, the `opengl2` legacy module;
- README or release-note instructions for selecting the legacy renderer;
- the GLx proof corpus document, promotion report, release proof summary, and checksums;
- a clear rollback trigger for unexplained demo, screenshot, driver, or performance regressions.

The rollback path is not optional. It is the safety valve that lets GLx become the default without turning one driver-specific regression into a release-blocking dead end.
