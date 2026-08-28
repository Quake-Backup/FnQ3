/*
===========================================================================
Copyright (C) 2026 FnQuake3 contributors.

Wireframe geometry for the world dynamic-light debug overlay.

The emitters below build line lists in world space and are pure math, so the
raster backends share one definition of what a debug light looks like instead
of each growing its own.  Every emitter appends vertex pairs; a caller draws
the accumulated buffer as an unindexed line list.
===========================================================================
*/

#ifndef TR_DLIGHT_DEBUG_H
#define TR_DLIGHT_DEBUG_H

#include <math.h>

#define DLIGHT_DEBUG_OFF 0
#define DLIGHT_DEBUG_PROMOTED 1
#define DLIGHT_DEBUG_ALL 2

#define DLIGHT_DEBUG_CIRCLE_SEGMENTS 24
#define DLIGHT_DEBUG_CONE_EDGES 8

/* Vertices one light can contribute: an origin cross (3 axes), a radius
   sphere (3 great circles), and for a spot the cone edges plus its inner and
   outer rim circles. */
#define DLIGHT_DEBUG_VERTS_PER_LIGHT \
	( 3 * 2 + 3 * DLIGHT_DEBUG_CIRCLE_SEGMENTS * 2 + \
	  DLIGHT_DEBUG_CONE_EDGES * 2 + 2 * DLIGHT_DEBUG_CIRCLE_SEGMENTS * 2 )

/* Flush threshold, sized so a single light always fits in the tail. */
#define DLIGHT_DEBUG_MAX_VERTS ( DLIGHT_DEBUG_VERTS_PER_LIGHT * 8 )

typedef struct {
	float	*verts;			/* xyz triples, two per line segment */
	int		maxVerts;
	int		numVerts;
	int		dropped;		/* segments the buffer could not hold */
} dlightDebugLines_t;

static ID_INLINE void R_DlightDebugBegin( dlightDebugLines_t *lines, float *verts, int maxVerts )
{
	lines->verts = verts;
	lines->maxVerts = maxVerts;
	lines->numVerts = 0;
	lines->dropped = 0;
}

static ID_INLINE qboolean R_DlightDebugRoomFor( const dlightDebugLines_t *lines, int verts )
{
	return ( lines->numVerts + verts <= lines->maxVerts ) ? qtrue : qfalse;
}

static ID_INLINE void R_DlightDebugLine( dlightDebugLines_t *lines,
	const vec3_t a, const vec3_t b )
{
	float *out;

	if ( !R_DlightDebugRoomFor( lines, 2 ) ) {
		lines->dropped++;
		return;
	}

	out = lines->verts + lines->numVerts * 3;
	out[0] = a[0];
	out[1] = a[1];
	out[2] = a[2];
	out[3] = b[0];
	out[4] = b[1];
	out[5] = b[2];
	lines->numVerts += 2;
}

/*
Three axis-aligned bars through the light's origin.  Drawn independently of
the radius sphere so a light whose radius is huge, tiny, or zero still shows
where it actually sits.
*/
static ID_INLINE void R_DlightDebugCross( dlightDebugLines_t *lines,
	const vec3_t origin, float size )
{
	vec3_t a;
	vec3_t b;
	int axis;

	for ( axis = 0; axis < 3; axis++ ) {
		VectorCopy( origin, a );
		VectorCopy( origin, b );
		a[axis] -= size;
		b[axis] += size;
		R_DlightDebugLine( lines, a, b );
	}
}

static ID_INLINE void R_DlightDebugCircle( dlightDebugLines_t *lines,
	const vec3_t center, const vec3_t axisU, const vec3_t axisV, float radius,
	int segments )
{
	vec3_t previous;
	vec3_t current;
	int i;

	if ( segments < 3 || radius <= 0.0f ) {
		return;
	}

	for ( i = 0; i <= segments; i++ ) {
		float theta = ( 2.0f * (float)M_PI * (float)i ) / (float)segments;
		float c = cosf( theta ) * radius;
		float s = sinf( theta ) * radius;

		current[0] = center[0] + axisU[0] * c + axisV[0] * s;
		current[1] = center[1] + axisU[1] * c + axisV[1] * s;
		current[2] = center[2] + axisU[2] * c + axisV[2] * s;
		if ( i > 0 ) {
			R_DlightDebugLine( lines, previous, current );
		}
		VectorCopy( current, previous );
	}
}

/*
Three great circles standing in for the light's reach.  This is the radius the
renderer actually attenuates against, so a light whose sphere does not touch
any surface cannot contribute no matter how bright it is authored.
*/
static ID_INLINE void R_DlightDebugSphere( dlightDebugLines_t *lines,
	const vec3_t origin, float radius )
{
	static const vec3_t axisX = { 1.0f, 0.0f, 0.0f };
	static const vec3_t axisY = { 0.0f, 1.0f, 0.0f };
	static const vec3_t axisZ = { 0.0f, 0.0f, 1.0f };

	if ( radius <= 0.0f ) {
		return;
	}

	R_DlightDebugCircle( lines, origin, axisX, axisY, radius, DLIGHT_DEBUG_CIRCLE_SEGMENTS );
	R_DlightDebugCircle( lines, origin, axisY, axisZ, radius, DLIGHT_DEBUG_CIRCLE_SEGMENTS );
	R_DlightDebugCircle( lines, origin, axisZ, axisX, radius, DLIGHT_DEBUG_CIRCLE_SEGMENTS );
}

/*
Spot cone: edge rays from the apex out to the outer rim, the outer rim itself,
and the inner rim where the cone's falloff begins.  `halfAngle` is in degrees
from the centreline, matching the sidecar's innerAngle/outerAngle.
*/
static ID_INLINE void R_DlightDebugCone( dlightDebugLines_t *lines,
	const vec3_t origin, const vec3_t direction, float length,
	float innerHalfAngle, float outerHalfAngle )
{
	vec3_t forward;
	vec3_t axisU;
	vec3_t axisV;
	vec3_t center;
	vec3_t rim;
	float outerRadius;
	float innerRadius;
	int i;

	if ( length <= 0.0f ) {
		return;
	}
	VectorCopy( direction, forward );
	if ( VectorNormalize( forward ) <= 0.0f ) {
		return;
	}

	outerHalfAngle = Com_Clamp( 1.0f, 89.0f, outerHalfAngle );
	innerHalfAngle = Com_Clamp( 0.0f, outerHalfAngle, innerHalfAngle );

	MakeNormalVectors( forward, axisU, axisV );
	VectorMA( origin, length, forward, center );
	outerRadius = length * tanf( DEG2RAD( outerHalfAngle ) );
	innerRadius = length * tanf( DEG2RAD( innerHalfAngle ) );

	for ( i = 0; i < DLIGHT_DEBUG_CONE_EDGES; i++ ) {
		float theta = ( 2.0f * (float)M_PI * (float)i ) / (float)DLIGHT_DEBUG_CONE_EDGES;
		float c = cosf( theta ) * outerRadius;
		float s = sinf( theta ) * outerRadius;

		rim[0] = center[0] + axisU[0] * c + axisV[0] * s;
		rim[1] = center[1] + axisU[1] * c + axisV[1] * s;
		rim[2] = center[2] + axisU[2] * c + axisV[2] * s;
		R_DlightDebugLine( lines, origin, rim );
	}

	R_DlightDebugCircle( lines, center, axisU, axisV, outerRadius,
		DLIGHT_DEBUG_CIRCLE_SEGMENTS );
	if ( innerRadius > 0.0f ) {
		R_DlightDebugCircle( lines, center, axisU, axisV, innerRadius,
			DLIGHT_DEBUG_CIRCLE_SEGMENTS );
	}
}

#endif
