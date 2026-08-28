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

#include <math.h>

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

/* Authored shadow-resolution requests are clamped to this range before the
   raster spot atlas sees them. */
#define WORLD_DLIGHT_MIN_SHADOW_RESOLUTION 64
#define WORLD_DLIGHT_MAX_SHADOW_RESOLUTION 1024

/* Exponent used to derive a shadow-map request from a light's reach.  A light
   twice as large does not need twice the texels, so the curve is sublinear;
   the default 300-unit radius lands exactly on the 256-pixel default. */
#define WORLD_DLIGHT_SHADOW_RESOLUTION_RADIUS_POWER 0.9f

/* Optional distance fade.  Both ends zero disables fading, which is the
   version-1 default and reproduces the pre-fade behaviour exactly. */
#define WORLD_DLIGHT_DEFAULT_FADE_START 0.0f
#define WORLD_DLIGHT_DEFAULT_FADE_END 0.0f
#define WORLD_DLIGHT_MAX_FADE_DISTANCE 65536.0f

static ID_INLINE int R_WorldDlightClampShadowResolution( int resolution )
{
	if ( resolution < WORLD_DLIGHT_MIN_SHADOW_RESOLUTION ) {
		return WORLD_DLIGHT_MIN_SHADOW_RESOLUTION;
	}
	if ( resolution > WORLD_DLIGHT_MAX_SHADOW_RESOLUTION ) {
		return WORLD_DLIGHT_MAX_SHADOW_RESOLUTION;
	}
	return resolution;
}

static ID_INLINE int R_WorldDlightCeilShadowResolution( int resolution )
{
	int result = WORLD_DLIGHT_MIN_SHADOW_RESOLUTION;

	while ( result < resolution && result < WORLD_DLIGHT_MAX_SHADOW_RESOLUTION ) {
		result *= 2;
	}
	return R_WorldDlightClampShadowResolution( result );
}

/*
Pick the shadow-map request a light of this reach deserves.  The atlas
allocator floors whatever it receives to a power of two, so the generator
emits one directly instead of a flat constant that oversizes small emitters
and starves large ones.
*/
static ID_INLINE int R_WorldDlightShadowResolutionForRadius( float radius )
{
	/* the negated form also rejects NaN */
	if ( !( radius > 0.0f ) ) {
		return WORLD_DLIGHT_DEFAULT_SHADOW_RESOLUTION;
	}

	return R_WorldDlightCeilShadowResolution(
		(int)( powf( radius, WORLD_DLIGHT_SHADOW_RESOLUTION_RADIUS_POWER ) + 0.5f ) );
}

/*
Smooth 1..0 ramp across the authored fade band, so a light leaving the view
budget dims out instead of popping.  Returns 1 whenever fading is disabled or
the sample sits inside the fully-lit range.
*/
static ID_INLINE float R_WorldDlightDistanceFade( float fadeStart, float fadeEnd, float distance )
{
	float fade;

	if ( !( fadeEnd > 0.0f ) || !( fadeEnd > fadeStart ) ) {
		return 1.0f;
	}
	if ( distance <= fadeStart ) {
		return 1.0f;
	}
	if ( distance >= fadeEnd ) {
		return 0.0f;
	}

	fade = ( fadeEnd - distance ) / ( fadeEnd - fadeStart );
	return fade * fade * ( 3.0f - 2.0f * fade );
}

#endif
