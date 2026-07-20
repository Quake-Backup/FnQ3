/*
===========================================================================

FnQuake3 global-fog sidecar format.

The renderer owns the file-system loading; this header keeps the strict,
renderer-independent text grammar shared by the OpenGL-lineage and Vulkan
backends.  A sidecar is deliberately visual-only: it never changes the BSP,
visibility, game state, demo stream, or VM behavior.

===========================================================================
*/

#ifndef TR_GLOBAL_FOG_H
#define TR_GLOBAL_FOG_H

#define GLOBAL_FOG_SIDECAR_MAX_BYTES 16384

typedef enum {
	GLOBAL_FOG_EXP = 0,
	GLOBAL_FOG_EXP2,
	GLOBAL_FOG_LINEAR
} globalFogMode_t;

typedef struct {
	qboolean		loaded;
	globalFogMode_t	mode;
	vec3_t			color;
	float			density;
	float			start;
	float			end;
	float			opacity;
	qboolean		sky;
} globalFog_t;

static ID_INLINE void R_GlobalFogClear( globalFog_t *fog )
{
	Com_Memset( fog, 0, sizeof( *fog ) );
	fog->mode = GLOBAL_FOG_EXP2;
	fog->opacity = 1.0f;
	fog->sky = qtrue;
}

static ID_INLINE qboolean R_GlobalFogParseFloat( const char *token, float *out )
{
	char *end;
	double value;

	if ( !token || !*token ) {
		return qfalse;
	}
	value = strtod( token, &end );
	if ( end == token || *end || value != value || value > 3.402823466e+38 || value < -3.402823466e+38 ) {
		return qfalse;
	}
	*out = (float)value;
	return qtrue;
}

static ID_INLINE qboolean R_GlobalFogParseBoolean( const char *token, qboolean *out )
{
	if ( !Q_stricmp( token, "1" ) || !Q_stricmp( token, "true" ) || !Q_stricmp( token, "yes" ) ) {
		*out = qtrue;
		return qtrue;
	}
	if ( !Q_stricmp( token, "0" ) || !Q_stricmp( token, "false" ) || !Q_stricmp( token, "no" ) ) {
		*out = qfalse;
		return qtrue;
	}
	return qfalse;
}

/*
====================
R_GlobalFogParse

Grammar (one keyword followed by its values; whitespace and // comments are
accepted):

  color <red> <green> <blue>    normalized RGB, each in [0, 1]
  mode <exp|exp2|linear>        defaults to exp2
  density <value>               required, in world-unit^-1
  start <world units>           optional, defaults to zero
  end <world units>             required for linear mode
  opacity <value>               optional maximum blend amount, defaults to 1
  sky <0|1>                     whether clear-depth sky pixels receive fog
====================
*/
static ID_INLINE qboolean R_GlobalFogParse( globalFog_t *fog, const char *text,
	char *error, int errorSize )
{
	const char *cursor = text;
	const char *token;
	qboolean colorSeen = qfalse;
	qboolean densitySeen = qfalse;
	qboolean modeSeen = qfalse;
	qboolean startSeen = qfalse;
	qboolean endSeen = qfalse;
	qboolean opacitySeen = qfalse;
	qboolean skySeen = qfalse;

	R_GlobalFogClear( fog );
	if ( !text ) {
		Com_sprintf( error, errorSize, "empty file" );
		return qfalse;
	}

	while ( 1 ) {
		token = COM_ParseExt( &cursor, qtrue );
		if ( !token[0] ) {
			break;
		}

		if ( !Q_stricmp( token, "color" ) ) {
			int i;
			if ( colorSeen ) {
				Com_sprintf( error, errorSize, "duplicate color directive" );
				return qfalse;
			}
			for ( i = 0; i < 3; i++ ) {
				token = COM_ParseExt( &cursor, qtrue );
				if ( !R_GlobalFogParseFloat( token, &fog->color[i] ) ||
					fog->color[i] < 0.0f || fog->color[i] > 1.0f ) {
					Com_sprintf( error, errorSize, "color must contain three normalized values" );
					return qfalse;
				}
			}
			colorSeen = qtrue;
		} else if ( !Q_stricmp( token, "mode" ) ) {
			if ( modeSeen ) {
				Com_sprintf( error, errorSize, "duplicate mode directive" );
				return qfalse;
			}
			token = COM_ParseExt( &cursor, qtrue );
			if ( !Q_stricmp( token, "exp" ) ) {
				fog->mode = GLOBAL_FOG_EXP;
			} else if ( !Q_stricmp( token, "exp2" ) ) {
				fog->mode = GLOBAL_FOG_EXP2;
			} else if ( !Q_stricmp( token, "linear" ) ) {
				fog->mode = GLOBAL_FOG_LINEAR;
			} else {
				Com_sprintf( error, errorSize, "mode must be exp, exp2, or linear" );
				return qfalse;
			}
			modeSeen = qtrue;
		} else if ( !Q_stricmp( token, "density" ) ) {
			if ( densitySeen ) {
				Com_sprintf( error, errorSize, "duplicate density directive" );
				return qfalse;
			}
			token = COM_ParseExt( &cursor, qtrue );
			if ( !R_GlobalFogParseFloat( token, &fog->density ) ||
				fog->density <= 0.0f || fog->density > 0.1f ) {
				Com_sprintf( error, errorSize, "density must be greater than zero and no greater than 0.1" );
				return qfalse;
			}
			densitySeen = qtrue;
		} else if ( !Q_stricmp( token, "start" ) ) {
			if ( startSeen ) {
				Com_sprintf( error, errorSize, "duplicate start directive" );
				return qfalse;
			}
			token = COM_ParseExt( &cursor, qtrue );
			if ( !R_GlobalFogParseFloat( token, &fog->start ) || fog->start < 0.0f ) {
				Com_sprintf( error, errorSize, "start must be a non-negative distance" );
				return qfalse;
			}
			startSeen = qtrue;
		} else if ( !Q_stricmp( token, "end" ) ) {
			if ( endSeen ) {
				Com_sprintf( error, errorSize, "duplicate end directive" );
				return qfalse;
			}
			token = COM_ParseExt( &cursor, qtrue );
			if ( !R_GlobalFogParseFloat( token, &fog->end ) || fog->end <= 0.0f ) {
				Com_sprintf( error, errorSize, "end must be a positive distance" );
				return qfalse;
			}
			endSeen = qtrue;
		} else if ( !Q_stricmp( token, "opacity" ) ) {
			if ( opacitySeen ) {
				Com_sprintf( error, errorSize, "duplicate opacity directive" );
				return qfalse;
			}
			token = COM_ParseExt( &cursor, qtrue );
			if ( !R_GlobalFogParseFloat( token, &fog->opacity ) ||
				fog->opacity < 0.0f || fog->opacity > 1.0f ) {
				Com_sprintf( error, errorSize, "opacity must be in [0, 1]" );
				return qfalse;
			}
			opacitySeen = qtrue;
		} else if ( !Q_stricmp( token, "sky" ) ) {
			if ( skySeen ) {
				Com_sprintf( error, errorSize, "duplicate sky directive" );
				return qfalse;
			}
			token = COM_ParseExt( &cursor, qtrue );
			if ( !R_GlobalFogParseBoolean( token, &fog->sky ) ) {
				Com_sprintf( error, errorSize, "sky must be 0/1, true/false, or yes/no" );
				return qfalse;
			}
			skySeen = qtrue;
		} else {
			Com_sprintf( error, errorSize, "unknown directive '%s'", token );
			return qfalse;
		}
	}

	if ( !colorSeen || !densitySeen ) {
		Com_sprintf( error, errorSize, "color and density are required" );
		return qfalse;
	}
	if ( fog->mode == GLOBAL_FOG_LINEAR && ( !endSeen || fog->end <= fog->start ) ) {
		Com_sprintf( error, errorSize, "linear fog requires end greater than start" );
		return qfalse;
	}

	fog->loaded = qtrue;
	return qtrue;
}

#endif // TR_GLOBAL_FOG_H
