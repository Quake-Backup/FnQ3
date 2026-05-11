#ifndef GLX_POST_SHADER_PLAN_H
#define GLX_POST_SHADER_PLAN_H

#include "glx_render_ir.h"

namespace glx {

static constexpr unsigned int GLX_POST_SHADER_FEATURE_NONE = 0x00000000u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_LEGACY_GAMMA = 0x00000001u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_SCENE_LINEAR = 0x00000002u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_LIFT_GAMMA_GAIN = 0x00000004u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_WHITE_POINT = 0x00000008u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_LUT_3D = 0x00000010u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_TONEMAP_REINHARD = 0x00000020u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_TONEMAP_ACES = 0x00000040u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_ENCODE_SRGB = 0x00000080u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_ENCODE_HDR10_PQ = 0x00000100u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_LINEAR_OUTPUT = 0x00000200u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_BT2020_OUTPUT = 0x00000400u;
static constexpr unsigned int GLX_POST_SHADER_FEATURE_GAMUT_COMPRESS = 0x00000800u;

struct PostShaderKey {
	qboolean sceneLinear;
	ColorGradeMode grade;
	ToneMapOperator toneMap;
	OutputTransfer transfer;
	OutputPrimaries outputPrimaries;
	GamutMapMode gamutMap;
	qboolean lutActive;
	qboolean whitePointAdaptation;
};

struct PostShaderPlan {
	PostShaderKey key;
	qboolean valid;
	unsigned int featureMask;
	unsigned int hash;
	int textureCount;
	int uniformVec4Count;
};

static ID_INLINE qboolean GLX_PostShader_GradeUsesLiftGammaGain( ColorGradeMode grade )
{
	return grade == ColorGradeMode::LiftGammaGain ||
		grade == ColorGradeMode::LiftGammaGainLut3D ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_PostShader_GradeUsesLut( ColorGradeMode grade )
{
	return grade == ColorGradeMode::Lut3D ||
		grade == ColorGradeMode::LiftGammaGainLut3D ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_PostShader_WhitePointAdaptationActive(
	const OutputTransform &transform )
{
	if ( !GLX_PostShader_GradeUsesLiftGammaGain( transform.grade ) ) {
		return qfalse;
	}
	const float delta = transform.whitePointSourceKelvin - transform.whitePointTargetKelvin;
	return ( delta > 1.0f || delta < -1.0f ) ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_PostShader_LutActive( const OutputTransform &transform )
{
	return ( GLX_PostShader_GradeUsesLut( transform.grade ) &&
		transform.lutSize >= 2.0f ) ? qtrue : qfalse;
}

static ID_INLINE unsigned int GLX_PostShader_FeaturesForKey( const PostShaderKey &key )
{
	unsigned int features = GLX_POST_SHADER_FEATURE_NONE;

	if ( key.sceneLinear ) {
		features |= GLX_POST_SHADER_FEATURE_SCENE_LINEAR;
	} else {
		features |= GLX_POST_SHADER_FEATURE_LEGACY_GAMMA;
	}
	if ( key.sceneLinear && GLX_PostShader_GradeUsesLiftGammaGain( key.grade ) ) {
		features |= GLX_POST_SHADER_FEATURE_LIFT_GAMMA_GAIN;
	}
	if ( key.sceneLinear && key.whitePointAdaptation ) {
		features |= GLX_POST_SHADER_FEATURE_WHITE_POINT;
	}
	if ( key.sceneLinear && key.lutActive ) {
		features |= GLX_POST_SHADER_FEATURE_LUT_3D;
	}
	if ( key.sceneLinear && key.toneMap == ToneMapOperator::Reinhard ) {
		features |= GLX_POST_SHADER_FEATURE_TONEMAP_REINHARD;
	}
	if ( key.sceneLinear && key.toneMap == ToneMapOperator::Aces ) {
		features |= GLX_POST_SHADER_FEATURE_TONEMAP_ACES;
	}

	switch ( key.transfer ) {
	case OutputTransfer::SdrSrgb:
	case OutputTransfer::ScreenshotSrgb:
		features |= key.sceneLinear ? GLX_POST_SHADER_FEATURE_ENCODE_SRGB :
			GLX_POST_SHADER_FEATURE_LEGACY_GAMMA;
		break;
	case OutputTransfer::Hdr10Pq:
		features |= GLX_POST_SHADER_FEATURE_ENCODE_HDR10_PQ;
		break;
	case OutputTransfer::LinearSrgb:
	case OutputTransfer::ScRgb:
	case OutputTransfer::MacEdr:
	default:
		features |= GLX_POST_SHADER_FEATURE_LINEAR_OUTPUT;
		break;
	}
	if ( key.outputPrimaries == OutputPrimaries::Bt2020 ) {
		features |= GLX_POST_SHADER_FEATURE_BT2020_OUTPUT;
	}
	if ( key.gamutMap == GamutMapMode::CompressToOutput ) {
		features |= GLX_POST_SHADER_FEATURE_GAMUT_COMPRESS;
	}
	return features;
}

static ID_INLINE unsigned int GLX_PostShader_HashKey( const PostShaderKey &key,
	unsigned int featureMask )
{
	unsigned int hash = 2166136261u;

	hash = GLX_RenderIR_HashValue( hash, key.sceneLinear ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( key.grade ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( key.toneMap ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( key.transfer ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( key.outputPrimaries ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( key.gamutMap ) );
	hash = GLX_RenderIR_HashValue( hash, key.lutActive ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, key.whitePointAdaptation ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, featureMask );
	return hash ? hash : 1u;
}

static ID_INLINE PostShaderPlan GLX_PostShader_BuildPlan(
	const OutputTransform &transform )
{
	PostShaderPlan plan {};

	plan.valid = GLX_RenderIR_ValidateOutputTransform( transform );
	plan.key.sceneLinear = ( transform.sceneColorSpace == SceneColorSpace::SceneLinear ) ?
		qtrue : qfalse;
	plan.key.grade = plan.key.sceneLinear ? transform.grade : ColorGradeMode::None;
	plan.key.toneMap = plan.key.sceneLinear ? transform.toneMap : ToneMapOperator::Legacy;
	plan.key.transfer = transform.transfer;
	plan.key.outputPrimaries = transform.outputPrimaries;
	plan.key.gamutMap = transform.gamutMap;
	plan.key.lutActive = plan.key.sceneLinear ? GLX_PostShader_LutActive( transform ) : qfalse;
	plan.key.whitePointAdaptation = plan.key.sceneLinear ?
		GLX_PostShader_WhitePointAdaptationActive( transform ) : qfalse;
	plan.featureMask = GLX_PostShader_FeaturesForKey( plan.key );
	plan.textureCount = plan.key.lutActive ? 2 : 1;
	plan.uniformVec4Count = 4;
	if ( GLX_PostShader_GradeUsesLiftGammaGain( plan.key.grade ) ) {
		plan.uniformVec4Count += 6;
	}
	if ( plan.key.lutActive ) {
		plan.uniformVec4Count += 2;
	}
	if ( plan.key.transfer == OutputTransfer::Hdr10Pq ) {
		plan.uniformVec4Count += 1;
	}
	plan.hash = GLX_PostShader_HashKey( plan.key, plan.featureMask );
	return plan;
}

} // namespace glx

#endif // GLX_POST_SHADER_PLAN_H
