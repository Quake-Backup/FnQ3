#ifndef GLX_MATERIAL_KEY_H
#define GLX_MATERIAL_KEY_H

#include "../qcommon/q_shared.h"
#include "../renderercommon/tr_glx_public.h"

namespace glx {

static constexpr unsigned int GLX_MATERIAL_FEATURE_NONE = 0x0000;
static constexpr unsigned int GLX_MATERIAL_FEATURE_TEXMOD = 0x0001;
static constexpr unsigned int GLX_MATERIAL_FEATURE_ENVIRONMENT = 0x0002;

enum class MaterialProgramMode {
	SingleTexture,
	MultiModulate,
	MultiAdd,
	MultiReplace,
	MultiDecal,
	Fog
};

struct MaterialProgramKey {
	MaterialProgramMode mode;
	unsigned int features;
};

static ID_INLINE qboolean GLX_Material_ModeForInputs( int flags, int materialCombine,
	qboolean fogPass, MaterialProgramMode *mode )
{
	if ( !mode ) {
		return qfalse;
	}

	if ( fogPass ) {
		*mode = MaterialProgramMode::Fog;
		return qtrue;
	}

	if ( !( flags & GLX_STAGE_MULTITEXTURE ) ) {
		*mode = MaterialProgramMode::SingleTexture;
		return qtrue;
	}

	switch ( materialCombine ) {
	case GLX_MATERIAL_COMBINE_MODULATE:
		*mode = MaterialProgramMode::MultiModulate;
		return qtrue;
	case GLX_MATERIAL_COMBINE_ADD:
		*mode = MaterialProgramMode::MultiAdd;
		return qtrue;
	case GLX_MATERIAL_COMBINE_REPLACE:
		*mode = MaterialProgramMode::MultiReplace;
		return qtrue;
	case GLX_MATERIAL_COMBINE_DECAL:
		*mode = MaterialProgramMode::MultiDecal;
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE unsigned int GLX_Material_FeaturesForInputs( int flags,
	int texMods0, int texMods1, qboolean fogPass )
{
	unsigned int features = GLX_MATERIAL_FEATURE_NONE;

	if ( fogPass ) {
		return GLX_MATERIAL_FEATURE_NONE;
	}

	if ( ( flags & GLX_STAGE_TEXMOD ) || texMods0 > 0 || texMods1 > 0 ) {
		features |= GLX_MATERIAL_FEATURE_TEXMOD;
	}
	if ( flags & GLX_STAGE_ENVIRONMENT ) {
		features |= GLX_MATERIAL_FEATURE_ENVIRONMENT;
	}

	return features;
}

static ID_INLINE qboolean GLX_Material_KeyForInputs( int flags, int materialCombine,
	int texMods0, int texMods1, qboolean fogPass, MaterialProgramKey *key )
{
	MaterialProgramMode mode;

	if ( !key || !GLX_Material_ModeForInputs( flags, materialCombine, fogPass, &mode ) ) {
		return qfalse;
	}

	key->mode = mode;
	key->features = GLX_Material_FeaturesForInputs( flags, texMods0, texMods1, fogPass );
	return qtrue;
}

static ID_INLINE qboolean GLX_Material_KeyEquals( const MaterialProgramKey &lhs,
	const MaterialProgramKey &rhs )
{
	return lhs.mode == rhs.mode && lhs.features == rhs.features ? qtrue : qfalse;
}

} // namespace glx

#endif // GLX_MATERIAL_KEY_H
