#ifndef GLX_STREAM_LOGIC_H
#define GLX_STREAM_LOGIC_H

#include "../renderercommon/tr_glx_public.h"
#include "glx_types.h"

#include <cctype>

namespace glx {

struct StreamStrategySelection {
	StreamStrategy strategy;
	qboolean knownMode;
	unsigned int fallbackCount;
	const char *reason;
};

struct StreamRuntimeSupport {
	StreamStrategy strategy;
	qboolean syncObjects;
	qboolean syncFunctions;
	qboolean mapBufferRange;
	qboolean mapRangeFunction;
	qboolean bufferSubDataFunction;
};

struct StreamRuntimeFallback {
	StreamStrategy strategy;
	qboolean ready;
	qboolean syncReady;
	unsigned int fallbackCount;
	const char *reason;
};

struct StreamMaterialGateConfig {
	int keyMode;
	qboolean multitexture;
	qboolean depthFragment;
	qboolean texMods;
	qboolean environment;
	qboolean dynamicLights;
	qboolean screenMaps;
	qboolean videoMaps;
};

struct StreamMaterialGateResult {
	qboolean allowed;
	qboolean hasMultitexture;
	qboolean hasDepthFragment;
	qboolean hasTexMods;
	qboolean hasEnvironment;
	qboolean hasDynamicLight;
	qboolean hasScreenMap;
	qboolean hasVideoMap;
	qboolean hasSecondTexcoord;
	qboolean multitextureGateAllowed;
	qboolean depthFragmentGateAllowed;
	qboolean texModsGateAllowed;
	qboolean environmentGateAllowed;
	qboolean dynamicLightGateAllowed;
	qboolean screenMapGateAllowed;
	qboolean videoMapGateAllowed;
	qboolean secondTexcoordGateAllowed;
};

struct StreamSpecialDrawGateConfig {
	qboolean streamDraw;
	qboolean shadows;
	qboolean beams;
	qboolean postprocess;
};

static ID_INLINE int GLX_Stream_LogicStricmp( const char *lhs, const char *rhs )
{
	if ( !lhs ) {
		lhs = "";
	}
	if ( !rhs ) {
		rhs = "";
	}

	while ( *lhs || *rhs ) {
		const int l = std::tolower( static_cast<unsigned char>( *lhs ) );
		const int r = std::tolower( static_cast<unsigned char>( *rhs ) );
		if ( l != r ) {
			return l - r;
		}
		if ( *lhs ) {
			lhs++;
		}
		if ( *rhs ) {
			rhs++;
		}
	}

	return 0;
}

static ID_INLINE qboolean GLX_Stream_ModeNameIs( const char *value, const char *mode )
{
	return !GLX_Stream_LogicStricmp( value, mode ) ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_Stream_ModeNameIsKnown( const char *value )
{
	return GLX_Stream_ModeNameIs( value, "auto" ) ||
		GLX_Stream_ModeNameIs( value, "persistent" ) ||
		GLX_Stream_ModeNameIs( value, "maprange" ) ||
		GLX_Stream_ModeNameIs( value, "orphan" ) ? qtrue : qfalse;
}

static ID_INLINE StreamStrategySelection GLX_Stream_SelectStrategy( const char *requestedMode,
	const FeatureSet &features )
{
	const qboolean knownMode = GLX_Stream_ModeNameIsKnown( requestedMode );
	const qboolean autoMode = ( GLX_Stream_ModeNameIs( requestedMode, "auto" ) || !knownMode ) ? qtrue : qfalse;
	const qboolean forcePersistent = GLX_Stream_ModeNameIs( requestedMode, "persistent" );
	const qboolean forceMapRange = GLX_Stream_ModeNameIs( requestedMode, "maprange" );
	const qboolean forceOrphan = GLX_Stream_ModeNameIs( requestedMode, "orphan" );
	StreamStrategySelection selection {
		StreamStrategy::OrphanSubData,
		knownMode,
		0,
		"portable orphan/subdata fallback"
	};

	if ( forceOrphan ) {
		selection.reason = "forced by r_glxStreamMode";
		return selection;
	}

	if ( ( forcePersistent || autoMode ) && features.bufferStorage && features.syncObjects ) {
		selection.strategy = StreamStrategy::PersistentMapped;
		selection.reason = forcePersistent ? "forced by r_glxStreamMode" :
			"buffer storage and sync objects available";
		return selection;
	}

	if ( forcePersistent ) {
		selection.fallbackCount++;
	}

	if ( ( forceMapRange || autoMode || forcePersistent ) && features.mapBufferRange ) {
		selection.strategy = StreamStrategy::MapBufferRange;
		selection.reason = forcePersistent ? "persistent unavailable, map range available" :
			( forceMapRange ? "forced by r_glxStreamMode" : "map buffer range available" );
		return selection;
	}

	if ( forceMapRange ) {
		selection.fallbackCount++;
	}

	if ( forcePersistent || forceMapRange ) {
		selection.reason = "requested strategy unavailable, using orphan/subdata";
	}

	return selection;
}

static ID_INLINE StreamRuntimeFallback GLX_Stream_ApplyRuntimeFunctionFallbacks(
	const StreamRuntimeSupport &support )
{
	StreamRuntimeFallback result {
		support.strategy,
		qtrue,
		( support.syncObjects && support.syncFunctions ) ? qtrue : qfalse,
		0,
		nullptr
	};

	if ( result.strategy == StreamStrategy::PersistentMapped && !result.syncReady ) {
		result.fallbackCount++;
		if ( support.mapBufferRange && support.mapRangeFunction ) {
			result.strategy = StreamStrategy::MapBufferRange;
			result.reason = "persistent sync functions unavailable, using map range";
		} else {
			result.strategy = StreamStrategy::OrphanSubData;
			result.reason = "persistent sync functions unavailable, using orphan/subdata";
		}
	}

	if ( result.strategy == StreamStrategy::MapBufferRange && !support.mapRangeFunction ) {
		result.fallbackCount++;
		result.strategy = StreamStrategy::OrphanSubData;
		result.reason = "map range function unavailable, using orphan/subdata";
	}

	if ( result.strategy == StreamStrategy::OrphanSubData && !support.bufferSubDataFunction ) {
		result.ready = qfalse;
		result.reason = "buffer subdata function unavailable";
	}

	return result;
}

static ID_INLINE int GLX_Stream_ClampedKeyMode( int mode )
{
	if ( mode < 0 ) {
		return 0;
	}
	if ( mode > 2 ) {
		return 2;
	}
	return mode;
}

static ID_INLINE StreamMaterialGateResult GLX_Stream_EvaluateMaterialGate(
	int flags, int texMods0, int texMods1, const StreamMaterialGateConfig &config )
{
	StreamMaterialGateResult result {};
	const int mode = GLX_Stream_ClampedKeyMode( config.keyMode );
	const qboolean hasMultitexture = ( flags & GLX_STAGE_MULTITEXTURE ) ? qtrue : qfalse;
	const qboolean multitextureAllowed = config.multitexture;
	const qboolean hasDepthFragment = ( flags & GLX_STAGE_DEPTH_FRAGMENT ) ? qtrue : qfalse;
	const qboolean depthFragmentAllowed = config.depthFragment;
	const qboolean hasTexMods = ( ( flags & GLX_STAGE_TEXMOD ) || texMods0 > 0 || texMods1 > 0 ) ? qtrue : qfalse;
	const qboolean texModsAllowed = ( config.texMods || mode >= 1 ) ? qtrue : qfalse;
	const qboolean hasEnvironment = ( flags & GLX_STAGE_ENVIRONMENT ) ? qtrue : qfalse;
	const qboolean environmentAllowed = ( config.environment || mode >= 2 ) ? qtrue : qfalse;
	const qboolean hasDynamicLight = ( flags & GLX_STAGE_DLIGHT_MAP ) ? qtrue : qfalse;
	const qboolean dynamicLightAllowed = ( config.dynamicLights || mode >= 2 ) ? qtrue : qfalse;
	const qboolean hasScreenMap = ( flags & GLX_STAGE_SCREEN_MAP ) ? qtrue : qfalse;
	const qboolean screenMapAllowed = ( config.screenMaps || mode >= 2 ) ? qtrue : qfalse;
	const qboolean hasVideoMap = ( flags & GLX_STAGE_VIDEO_MAP ) ? qtrue : qfalse;
	const qboolean videoMapAllowed = ( config.videoMaps || mode >= 2 ) ? qtrue : qfalse;
	const qboolean hasSecondTexcoord = ( flags & GLX_STAGE_ST1 ) ? qtrue : qfalse;
	const qboolean secondTexcoordAllowed = multitextureAllowed && hasMultitexture ? qtrue : qfalse;

	result.allowed = qtrue;
	result.hasMultitexture = hasMultitexture;
	result.hasDepthFragment = hasDepthFragment;
	result.hasTexMods = hasTexMods;
	result.hasEnvironment = hasEnvironment;
	result.hasDynamicLight = hasDynamicLight;
	result.hasScreenMap = hasScreenMap;
	result.hasVideoMap = hasVideoMap;
	result.hasSecondTexcoord = hasSecondTexcoord;
	result.multitextureGateAllowed = multitextureAllowed;
	result.depthFragmentGateAllowed = depthFragmentAllowed;
	result.texModsGateAllowed = texModsAllowed;
	result.environmentGateAllowed = environmentAllowed;
	result.dynamicLightGateAllowed = dynamicLightAllowed;
	result.screenMapGateAllowed = screenMapAllowed;
	result.videoMapGateAllowed = videoMapAllowed;
	result.secondTexcoordGateAllowed = secondTexcoordAllowed;

	if ( hasMultitexture && !result.multitextureGateAllowed ) {
		result.allowed = qfalse;
	}
	if ( hasDepthFragment && !result.depthFragmentGateAllowed ) {
		result.allowed = qfalse;
	}
	if ( hasTexMods && !result.texModsGateAllowed ) {
		result.allowed = qfalse;
	}
	if ( hasEnvironment && !result.environmentGateAllowed ) {
		result.allowed = qfalse;
	}
	if ( hasDynamicLight && !result.dynamicLightGateAllowed ) {
		result.allowed = qfalse;
	}
	if ( hasScreenMap && !result.screenMapGateAllowed ) {
		result.allowed = qfalse;
	}
	if ( hasVideoMap && !result.videoMapGateAllowed ) {
		result.allowed = qfalse;
	}
	if ( hasSecondTexcoord && !result.secondTexcoordGateAllowed ) {
		result.allowed = qfalse;
	}

	return result;
}

static ID_INLINE qboolean GLX_Stream_EvaluateShadowDrawGate( const StreamSpecialDrawGateConfig &config )
{
	return config.streamDraw && config.shadows ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_Stream_EvaluateBeamDrawGate( const StreamSpecialDrawGateConfig &config )
{
	return config.streamDraw && config.beams ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_Stream_EvaluatePostProcessDrawGate( const StreamSpecialDrawGateConfig &config )
{
	return config.streamDraw && config.postprocess ? qtrue : qfalse;
}

} // namespace glx

#endif // GLX_STREAM_LOGIC_H
