/*
===========================================================================
Copyright (C) 2026 FnQuake3 contributors

Shared, renderer-only liquid helpers. Keep this header independent of a
specific backend so OpenGL/GLx and Vulkan classify and age liquid effects in
exactly the same way.
===========================================================================
*/
#ifndef TR_LIQUID_H
#define TR_LIQUID_H

#include "../qcommon/q_shared.h"

#define LIQUID_CONTENTS_MASK ( CONTENTS_WATER | CONTENTS_SLIME | CONTENTS_LAVA )
#define LIQUID_MAX_ACTIVE_IMPULSES 8
#define LIQUID_MAX_STORED_IMPULSES 16
#define LIQUID_IMPULSE_LIFETIME_MSEC 2400
#define LIQUID_WARP_TO_PIXELS 160.0f
#define LIQUID_MAX_WARP_PIXELS 8.0f
#define LIQUID_RIPPLE_PIXEL_SCALE 3.0f

static ID_INLINE qboolean R_LiquidContentsEnabled( int contents, int reflectionMode )
{
	if ( reflectionMode <= 0 ) {
		return qfalse;
	}
	if ( contents & CONTENTS_WATER ) {
		return qtrue;
	}
	return ( reflectionMode >= 2 && ( contents & ( CONTENTS_SLIME | CONTENTS_LAVA ) ) ) ? qtrue : qfalse;
}

static ID_INLINE float R_LiquidContentsReflectionScale( int contents )
{
	if ( contents & CONTENTS_WATER ) {
		return 1.0f;
	}
	if ( contents & CONTENTS_SLIME ) {
		return 0.55f;
	}
	if ( contents & CONTENTS_LAVA ) {
		return 0.25f;
	}
	return 0.0f;
}

static ID_INLINE void R_LiquidContentsFresnelColor( int contents, vec3_t color )
{
	if ( contents & CONTENTS_WATER ) {
		color[0] = 0.42f;
		color[1] = 0.58f;
		color[2] = 0.70f;
	} else if ( contents & CONTENTS_SLIME ) {
		color[0] = 0.30f;
		color[1] = 0.55f;
		color[2] = 0.18f;
	} else {
		color[0] = 0.95f;
		color[1] = 0.38f;
		color[2] = 0.08f;
	}
}

static ID_INLINE qboolean R_LiquidInteractionActive( const liquidInteraction_t *interaction, int sceneTime )
{
	int age;

	if ( !interaction || interaction->radius <= 0.0f || interaction->strength <= 0.0f ) {
		return qfalse;
	}
	age = sceneTime - interaction->time;
	return ( age >= 0 && age < LIQUID_IMPULSE_LIFETIME_MSEC ) ? qtrue : qfalse;
}

static ID_INLINE void R_LiquidWorldToLocal( const vec3_t world, const vec3_t origin,
	const vec3_t axis[3], vec3_t local )
{
	vec3_t delta;

	VectorSubtract( world, origin, delta );
	local[0] = DotProduct( delta, axis[0] );
	local[1] = DotProduct( delta, axis[1] );
	local[2] = DotProduct( delta, axis[2] );
}

#endif /* TR_LIQUID_H */
