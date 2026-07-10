/*
===========================================================================
Copyright (C) 2026

This file is part of FnQuake3.

FnQuake3 is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
===========================================================================
*/

#ifndef TR_FOG_MATH_H
#define TR_FOG_MATH_H

#include <math.h>

/*
The original fog image stores this curve in a 256 x 32 RGBA8 lookup.  Modern
renderers can evaluate it directly so fog remains continuous and does not
require a dependent texture read.  The legacy helper intentionally preserves
the table truncation for r_fogMode 0.  Keep these constants synchronized with
the GLSL helpers in rendererglx/glx_material.cpp and renderervk/shaders/.
*/
#define FOG_DISTANCE_BIAS ( 1.0f / 512.0f )
#define FOG_DEPTH_MIN     ( 1.0f / 32.0f )
#define FOG_DEPTH_MAX     ( 31.0f / 32.0f )
#define FOG_DEPTH_RANGE   ( 30.0f / 32.0f )
#define FOG_DISTANCE_SCALE 8.0f

static ID_INLINE float R_AnalyticFogFactor( float s, float t )
{
	s -= FOG_DISTANCE_BIAS;
	if ( s <= 0.0f || t < FOG_DEPTH_MIN ) {
		return 0.0f;
	}

	if ( t < FOG_DEPTH_MAX ) {
		s *= ( t - FOG_DEPTH_MIN ) / FOG_DEPTH_RANGE;
	}

	s *= FOG_DISTANCE_SCALE;
	if ( s >= 1.0f ) {
		return 1.0f;
	}

	return sqrtf( s );
}

static ID_INLINE float R_LegacyFogFactor( float s, float t,
	const float *fogTable, int fogTableSize )
{
	s -= FOG_DISTANCE_BIAS;
	if ( s < 0.0f || t < FOG_DEPTH_MIN || !fogTable || fogTableSize < 2 ) {
		return 0.0f;
	}

	if ( t < FOG_DEPTH_MAX ) {
		s *= ( t - FOG_DEPTH_MIN ) / FOG_DEPTH_RANGE;
	}

	s *= FOG_DISTANCE_SCALE;
	if ( s > 1.0f ) {
		s = 1.0f;
	}

	return fogTable[(int)( s * ( fogTableSize - 1 ) )];
}

#endif // TR_FOG_MATH_H
