#ifndef GLX_POST_SHADER_SOURCE_H
#define GLX_POST_SHADER_SOURCE_H

#include "glx_post_shader_plan.h"

namespace glx {

static constexpr int GLX_POST_SHADER_SOURCE_VERSION = 3;
static constexpr int GLX_POST_SHADER_VERTEX_SOURCE_BYTES = 1024;
static constexpr int GLX_POST_SHADER_FRAGMENT_SOURCE_BYTES = 8192;

struct PostShaderSourceSummary {
	qboolean valid;
	qboolean truncated;
	unsigned int sourceHash;
	unsigned int featureMask;
	int vertexBytes;
	int fragmentBytes;
};

static ID_INLINE int GLX_PostShaderSource_StringLength( const char *text )
{
	int length = 0;
	if ( !text ) {
		return 0;
	}
	while ( text[length] ) {
		length++;
	}
	return length;
}

static ID_INLINE qboolean GLX_PostShaderSource_Append( char *out, int outSize,
	int *used, const char *text )
{
	const int length = GLX_PostShaderSource_StringLength( text );
	int copied = 0;

	if ( !used || !text ) {
		return qfalse;
	}

	if ( out && outSize > 0 ) {
		if ( *used < outSize - 1 ) {
			const int room = outSize - 1 - *used;
			const int toCopy = length < room ? length : room;
			for ( copied = 0; copied < toCopy; copied++ ) {
				out[*used + copied] = text[copied];
			}
			out[*used + copied] = '\0';
		} else {
			out[outSize - 1] = '\0';
		}
	}

	*used += length;
	return ( !out || outSize <= 0 || *used < outSize ) ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_PostShaderSource_AppendFeatureDefine( char *out,
	int outSize, int *used, const char *name, qboolean enabled )
{
	qboolean ok = qtrue;
	ok = ( GLX_PostShaderSource_Append( out, outSize, used, "#define " ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_Append( out, outSize, used, name ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_Append( out, outSize, used, enabled ? " 1\n" : " 0\n" ) && ok ) ? qtrue : qfalse;
	return ok;
}

static ID_INLINE qboolean GLX_PostShaderSource_FeatureEnabled(
	const PostShaderPlan &plan, unsigned int feature )
{
	return ( plan.featureMask & feature ) != 0u ? qtrue : qfalse;
}

static ID_INLINE unsigned int GLX_PostShaderSource_HashText( unsigned int hash,
	const char *text )
{
	if ( !text ) {
		return hash;
	}
	while ( *text ) {
		hash ^= static_cast<unsigned int>( static_cast<unsigned char>( *text ) );
		hash *= 16777619u;
		text++;
	}
	return hash;
}

static ID_INLINE qboolean GLX_PostShaderSource_WriteVertex( char *out, int outSize,
	int *bytes )
{
	int used = 0;
	qboolean ok = qtrue;

	if ( out && outSize > 0 ) {
		out[0] = '\0';
	}

	ok = ( GLX_PostShaderSource_Append( out, outSize, &used,
		"#version 120\n"
		"varying vec2 v_TexCoord;\n"
		"void main() {\n"
		"	v_TexCoord = gl_MultiTexCoord0.st;\n"
		"	gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;\n"
		"}\n" ) && ok ) ? qtrue : qfalse;

	if ( bytes ) {
		*bytes = used;
	}
	return ok;
}

static ID_INLINE qboolean GLX_PostShaderSource_WriteFeatureDefines(
	const PostShaderPlan &plan, char *out, int outSize, int *used )
{
	qboolean ok = qtrue;

	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_LEGACY_GAMMA",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_LEGACY_GAMMA ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_SCENE_LINEAR",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_SCENE_LINEAR ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_LIFT_GAMMA_GAIN",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_LIFT_GAMMA_GAIN ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_WHITE_POINT",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_WHITE_POINT ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_LUT_3D",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_LUT_3D ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_TONEMAP_REINHARD",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_TONEMAP_REINHARD ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_TONEMAP_ACES",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_TONEMAP_ACES ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_ENCODE_SRGB",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_ENCODE_SRGB ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_ENCODE_HDR10_PQ",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_ENCODE_HDR10_PQ ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_LINEAR_OUTPUT",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_LINEAR_OUTPUT ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_BT2020_OUTPUT",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_BT2020_OUTPUT ) ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_AppendFeatureDefine( out, outSize, used,
		"GLX_POST_GAMUT_COMPRESS",
		GLX_PostShaderSource_FeatureEnabled( plan, GLX_POST_SHADER_FEATURE_GAMUT_COMPRESS ) ) && ok ) ? qtrue : qfalse;

	return ok;
}

static ID_INLINE qboolean GLX_PostShaderSource_WriteFragment(
	const PostShaderPlan &plan, char *out, int outSize, int *bytes )
{
	int used = 0;
	qboolean ok = plan.valid;

	if ( out && outSize > 0 ) {
		out[0] = '\0';
	}
	if ( !plan.valid ) {
		if ( bytes ) {
			*bytes = 0;
		}
		return qfalse;
	}

	ok = ( GLX_PostShaderSource_Append( out, outSize, &used,
		"#version 120\n"
		"// GLx generated post/output shader source v1.\n" ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_WriteFeatureDefines( plan, out, outSize, &used ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_Append( out, outSize, &used,
		"varying vec2 v_TexCoord;\n"
		"uniform sampler2D u_Scene;\n"
		"uniform sampler2D u_ColorGradeLut;\n" ) && ok ) ? qtrue : qfalse;
	ok = ( GLX_PostShaderSource_Append( out, outSize, &used,
		"uniform vec4 u_PostParams0; // exposure, paper white, max output, unused\n"
		"uniform vec4 u_Lift;\n"
		"uniform vec4 u_InvGamma;\n"
		"uniform vec4 u_Gain;\n"
		"uniform vec4 u_WhitePoint0;\n"
		"uniform vec4 u_WhitePoint1;\n"
		"uniform vec4 u_WhitePoint2;\n"
		"uniform vec4 u_LutParams; // scale, sizeMinusOne, texelCenter, invScale\n"
		"vec3 glxSaturate(vec3 color) { return clamp(color, 0.0, 1.0); }\n"
		"vec3 glxLinearToSrgb(vec3 color) {\n"
		"	vec3 lo = color * 12.92;\n"
		"	vec3 hi = 1.055 * pow(max(color, vec3(0.0)), vec3(1.0 / 2.4)) - vec3(0.055);\n"
		"	return mix(hi, lo, step(color, vec3(0.0031308)));\n"
		"}\n"
		"vec3 glxApplyLiftGammaGain(vec3 color) {\n"
		"	return max(pow(max(color + u_Lift.xyz, vec3(0.0)), u_InvGamma.xyz) * u_Gain.xyz, vec3(0.0));\n"
		"}\n"
		"vec3 glxApplyWhitePoint(vec3 color) {\n"
		"	return max(vec3(dot(u_WhitePoint0.xyz, color), dot(u_WhitePoint1.xyz, color), dot(u_WhitePoint2.xyz, color)), vec3(0.0));\n"
		"}\n"
		"vec3 glxSampleLutAtlas(vec3 color) {\n"
		"	float sizeMinusOne = max(u_LutParams.y, 1.0);\n"
		"	float size = sizeMinusOne + 1.0;\n"
		"	vec3 p = clamp(color * u_LutParams.w, 0.0, 1.0) * sizeMinusOne;\n"
		"	float slice = floor(p.b);\n"
		"	float nextSlice = min(slice + 1.0, sizeMinusOne);\n"
		"	vec2 uv0 = (vec2(p.r + slice * size, p.g) + vec2(0.5)) / vec2(size * size, size);\n"
		"	vec2 uv1 = (vec2(p.r + nextSlice * size, p.g) + vec2(0.5)) / vec2(size * size, size);\n"
		"	return mix(texture2D(u_ColorGradeLut, uv0).rgb, texture2D(u_ColorGradeLut, uv1).rgb, fract(p.b)) * u_LutParams.x;\n"
		"}\n"
		"vec3 glxToneMapReinhard(vec3 color) { return color / (color + vec3(1.0)); }\n"
		"vec3 glxToneMapAces(vec3 color) {\n"
		"	const float a = 2.51;\n"
		"	const float b = 0.03;\n"
		"	const float c = 2.43;\n"
		"	const float d = 0.59;\n"
		"	const float e = 0.14;\n"
		"	return glxSaturate((color * (a * color + vec3(b))) / (color * (c * color + vec3(d)) + vec3(e)));\n"
		"}\n"
		"vec3 glxLinearSrgbToBt2020(vec3 color) {\n"
		"	return mat3(0.6274, 0.0691, 0.0164, 0.3293, 0.9195, 0.0880, 0.0433, 0.0114, 0.8956) * color;\n"
		"}\n"
		"vec3 glxPqEncode(vec3 nits) {\n"
		"	const float m1 = 0.1593017578125;\n"
		"	const float m2 = 78.84375;\n"
		"	const float c1 = 0.8359375;\n"
		"	const float c2 = 18.8515625;\n"
		"	const float c3 = 18.6875;\n"
		"	vec3 p = pow(clamp(nits / 10000.0, 0.0, 1.0), vec3(m1));\n"
		"	return pow((vec3(c1) + c2 * p) / (vec3(1.0) + c3 * p), vec3(m2));\n"
		"}\n"
		"vec3 glxEncodeTransfer(vec3 color) {\n"
		"#if GLX_POST_BT2020_OUTPUT\n"
		"	color = glxLinearSrgbToBt2020(max(color, vec3(0.0)));\n"
		"#endif\n"
		"#if GLX_POST_GAMUT_COMPRESS\n"
		"	color = clamp(color, 0.0, max(u_PostParams0.z / max(u_PostParams0.y, 0.001), 1.0));\n"
		"#endif\n"
		"#if GLX_POST_ENCODE_HDR10_PQ\n"
		"	return glxPqEncode(max(color, vec3(0.0)) * max(u_PostParams0.y, 1.0));\n"
		"#elif GLX_POST_ENCODE_SRGB\n"
		"	return glxLinearToSrgb(max(color, vec3(0.0)));\n"
		"#else\n"
		"	return max(color, vec3(0.0));\n"
		"#endif\n"
		"}\n"
		"void main() {\n"
		"	vec3 color = texture2D(u_Scene, v_TexCoord).rgb;\n"
		"#if GLX_POST_SCENE_LINEAR\n"
		"	color = max(color * u_PostParams0.x, vec3(0.0));\n"
		"#if GLX_POST_LIFT_GAMMA_GAIN\n"
		"	color = glxApplyLiftGammaGain(color);\n"
		"#endif\n"
		"#if GLX_POST_WHITE_POINT\n"
		"	color = glxApplyWhitePoint(color);\n"
		"#endif\n"
		"#if GLX_POST_LUT_3D\n"
		"	color = glxSampleLutAtlas(color);\n"
		"#endif\n"
		"#if GLX_POST_TONEMAP_REINHARD\n"
		"	color = glxToneMapReinhard(color);\n"
		"#elif GLX_POST_TONEMAP_ACES\n"
		"	color = glxToneMapAces(color);\n"
		"#endif\n"
		"	color = glxEncodeTransfer(color);\n"
		"#elif GLX_POST_ENCODE_SRGB\n"
		"	color = glxLinearToSrgb(max(color, vec3(0.0)));\n"
		"#endif\n"
		"	gl_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);\n"
		"}\n" ) && ok ) ? qtrue : qfalse;

	if ( bytes ) {
		*bytes = used;
	}
	return ok;
}

static ID_INLINE PostShaderSourceSummary GLX_PostShaderSource_BuildSummary(
	const PostShaderPlan &plan )
{
	PostShaderSourceSummary summary {};
	char vertex[GLX_POST_SHADER_VERTEX_SOURCE_BYTES];
	char fragment[GLX_POST_SHADER_FRAGMENT_SOURCE_BYTES];
	qboolean vertexOk;
	qboolean fragmentOk;

	vertexOk = GLX_PostShaderSource_WriteVertex( vertex, sizeof( vertex ),
		&summary.vertexBytes );
	fragmentOk = GLX_PostShaderSource_WriteFragment( plan, fragment, sizeof( fragment ),
		&summary.fragmentBytes );
	summary.valid = ( plan.valid && vertexOk && fragmentOk ) ? qtrue : qfalse;
	summary.truncated = ( plan.valid && ( !vertexOk || !fragmentOk ) ) ? qtrue : qfalse;
	summary.featureMask = plan.featureMask;

	unsigned int hash = 2166136261u;
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( GLX_POST_SHADER_SOURCE_VERSION ) );
	hash = GLX_RenderIR_HashValue( hash, plan.hash );
	hash = GLX_RenderIR_HashValue( hash, plan.featureMask );
	hash = GLX_PostShaderSource_HashText( hash, vertex );
	hash = GLX_PostShaderSource_HashText( hash, fragment );
	summary.sourceHash = hash ? hash : 1u;
	return summary;
}

} // namespace glx

#endif // GLX_POST_SHADER_SOURCE_H
