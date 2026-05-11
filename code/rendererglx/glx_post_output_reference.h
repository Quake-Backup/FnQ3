#ifndef GLX_POST_OUTPUT_REFERENCE_H
#define GLX_POST_OUTPUT_REFERENCE_H

#include "glx_color_math.h"
#include "glx_render_ir.h"

namespace glx {

static inline bool GLX_PostOutputReference_UsesLiftGammaGain( ColorGradeMode grade )
{
	return grade == ColorGradeMode::LiftGammaGain ||
		grade == ColorGradeMode::LiftGammaGainLut3D;
}

static inline bool GLX_PostOutputReference_UsesLut( ColorGradeMode grade )
{
	return grade == ColorGradeMode::Lut3D ||
		grade == ColorGradeMode::LiftGammaGainLut3D;
}

static inline ColorMathVec3 GLX_PostOutputReference_Max0( const ColorMathVec3 &color )
{
	ColorMathVec3 out {};
	out.r = color.r > 0.0f ? color.r : 0.0f;
	out.g = color.g > 0.0f ? color.g : 0.0f;
	out.b = color.b > 0.0f ? color.b : 0.0f;
	return out;
}

static inline ColorMathVec3 GLX_PostOutputReference_ApplyLiftGammaGain(
	const ColorMathVec3 &color, const OutputTransform &transform )
{
	ColorMathVec3 out {};
	out.r = std::pow( color.r + transform.gradeLift[0] > 0.0f ?
		color.r + transform.gradeLift[0] : 0.0f,
		1.0f / ( transform.gradeGamma[0] > 0.0001f ? transform.gradeGamma[0] : 0.0001f ) ) *
		( transform.gradeGain[0] > 0.0f ? transform.gradeGain[0] : 0.0f );
	out.g = std::pow( color.g + transform.gradeLift[1] > 0.0f ?
		color.g + transform.gradeLift[1] : 0.0f,
		1.0f / ( transform.gradeGamma[1] > 0.0001f ? transform.gradeGamma[1] : 0.0001f ) ) *
		( transform.gradeGain[1] > 0.0f ? transform.gradeGain[1] : 0.0f );
	out.b = std::pow( color.b + transform.gradeLift[2] > 0.0f ?
		color.b + transform.gradeLift[2] : 0.0f,
		1.0f / ( transform.gradeGamma[2] > 0.0001f ? transform.gradeGamma[2] : 0.0001f ) ) *
		( transform.gradeGain[2] > 0.0f ? transform.gradeGain[2] : 0.0f );

	return GLX_PostOutputReference_Max0( GLX_ColorMath_AdaptWhitePointBradford(
		out, transform.whitePointSourceKelvin, transform.whitePointTargetKelvin ) );
}

static inline ColorMathVec3 GLX_PostOutputReference_ApplyColorGrade(
	const ColorMathVec3 &color, const OutputTransform &transform,
	const ColorMathVec3 *lutAtlas, int lutWidth, int lutHeight )
{
	ColorMathVec3 out = color;

	if ( GLX_PostOutputReference_UsesLiftGammaGain( transform.grade ) ) {
		out = GLX_PostOutputReference_ApplyLiftGammaGain( out, transform );
	}
	if ( GLX_PostOutputReference_UsesLut( transform.grade ) &&
		transform.lutSize >= 2.0f ) {
		out = GLX_ColorMath_SampleLutAtlas( lutAtlas, lutWidth, lutHeight,
			out, transform.lutScale );
	}
	return out;
}

static inline ColorMathVec3 GLX_PostOutputReference_ApplyToneMap(
	const ColorMathVec3 &color, ToneMapOperator toneMap )
{
	ColorMathVec3 out = color;

	if ( toneMap == ToneMapOperator::Reinhard ) {
		out.r = GLX_ColorMath_ToneMapReinhard( out.r );
		out.g = GLX_ColorMath_ToneMapReinhard( out.g );
		out.b = GLX_ColorMath_ToneMapReinhard( out.b );
	} else if ( toneMap == ToneMapOperator::Aces ) {
		out.r = GLX_ColorMath_ToneMapAcesFitted( out.r );
		out.g = GLX_ColorMath_ToneMapAcesFitted( out.g );
		out.b = GLX_ColorMath_ToneMapAcesFitted( out.b );
	}
	return out;
}

static inline ColorMathVec3 GLX_PostOutputReference_EncodeSrgb( const ColorMathVec3 &color )
{
	ColorMathVec3 out {};
	out.r = GLX_ColorMath_LinearToSrgb( color.r );
	out.g = GLX_ColorMath_LinearToSrgb( color.g );
	out.b = GLX_ColorMath_LinearToSrgb( color.b );
	return out;
}

static inline ColorMathVec3 GLX_PostOutputReference_EncodeHdr10Pq(
	const ColorMathVec3 &color, const OutputTransform &transform )
{
	const float paperWhite = transform.paperWhiteNits > 0.0f ?
		transform.paperWhiteNits : 203.0f;
	const float maxOutput = transform.maxOutputNits > paperWhite ?
		transform.maxOutputNits : paperWhite;
	const ColorMathVec3 bt2020 = GLX_ColorMath_LinearSrgbToBt2020(
		GLX_PostOutputReference_Max0( color ) );

	ColorMathVec3 out {};
	out.r = GLX_ColorMath_PqEncodeNits( bt2020.r * paperWhite, maxOutput );
	out.g = GLX_ColorMath_PqEncodeNits( bt2020.g * paperWhite, maxOutput );
	out.b = GLX_ColorMath_PqEncodeNits( bt2020.b * paperWhite, maxOutput );
	return out;
}

static inline ColorMathVec3 GLX_PostOutputReference_EncodeTransfer(
	const ColorMathVec3 &color, const OutputTransform &transform )
{
	switch ( transform.transfer ) {
	case OutputTransfer::SdrSrgb:
	case OutputTransfer::ScreenshotSrgb:
		return GLX_PostOutputReference_EncodeSrgb( color );
	case OutputTransfer::Hdr10Pq:
		return GLX_PostOutputReference_EncodeHdr10Pq( color, transform );
	case OutputTransfer::LinearSrgb:
	case OutputTransfer::ScRgb:
	case OutputTransfer::MacEdr:
	default:
		return GLX_PostOutputReference_Max0( color );
	}
}

static inline ColorMathVec3 GLX_PostOutputReference_Evaluate(
	const ColorMathVec3 &sceneLinear, const OutputTransform &transform,
	const ColorMathVec3 *lutAtlas, int lutWidth, int lutHeight )
{
	const float exposure = transform.exposure > 0.0f ? transform.exposure : 0.0f;
	ColorMathVec3 color {};
	color.r = sceneLinear.r * exposure;
	color.g = sceneLinear.g * exposure;
	color.b = sceneLinear.b * exposure;
	color = GLX_PostOutputReference_Max0( color );
	color = GLX_PostOutputReference_ApplyColorGrade( color, transform,
		lutAtlas, lutWidth, lutHeight );
	color = GLX_PostOutputReference_ApplyToneMap( color, transform.toneMap );
	return GLX_PostOutputReference_EncodeTransfer( color, transform );
}

} // namespace glx

#endif // GLX_POST_OUTPUT_REFERENCE_H
