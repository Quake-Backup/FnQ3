/*
===========================================================================
Copyright (C) 2026 FnQuake3 contributors.

FnQuake3 world dynamic-light sidecar format.

World dlights are renderer-only visual data.  They are never exposed to the
game VM, never participate in snapshots, and therefore cannot affect Quake III
protocol or demo compatibility.
===========================================================================
*/

#ifndef TR_WORLD_DLIGHTS_H
#define TR_WORLD_DLIGHTS_H

#define WORLD_DLIGHT_FORMAT_NAME "fnquake3-world-dlights"
#define WORLD_DLIGHT_FORMAT_VERSION 1
#define WORLD_DLIGHT_FILE_EXTENSION ".dlight"
#define WORLD_DLIGHT_LEGACY_FILE_EXTENSION ".lights.json"
#define WORLD_DLIGHT_MAX_FILE_SIZE ( 512 * 1024 )
#define WORLD_DLIGHT_MAX_LIGHTS 256

/* Defaults used when an authored light omits optional properties. */
#define WORLD_DLIGHT_DEFAULT_RADIUS 300.0f
#define WORLD_DLIGHT_DEFAULT_INTENSITY 300.0f
#define WORLD_DLIGHT_DEFAULT_INNER_ANGLE 35.0f
#define WORLD_DLIGHT_DEFAULT_OUTER_ANGLE 50.0f
#define WORLD_DLIGHT_DEFAULT_SHADOW_RESOLUTION 256

#endif
