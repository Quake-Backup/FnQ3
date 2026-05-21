#include "tr_local.h"
#include "tr_common.h"
#include "tr_glx_compat.h"

#ifndef GL_RG
#define GL_RG 0x8227
#endif

#ifndef GL_RG16F
#define GL_RG16F 0x822F
#endif

#define COMMON_DEPTH_STENCIL
//#define DEPTH_RENDER_BUFFER
//#define USE_FBO_BLIT

// screenMap texture dimensions
#define SCR_WIDTH 128
#define SCR_HEIGHT 64

#define BLOOM_BASE 5
#define FBO_COUNT (BLOOM_BASE+(MAX_BLUR_PASSES*2))

#if BLOOM_BASE < 2
#error no space for main/postprocess buffers
#endif

static GLuint programs[ PROGRAM_COUNT ];
static GLuint current_vp;
static GLuint current_fp;

static int programCompiled = 0;
static int programEnabled	= 0;

qboolean fboEnabled = qfalse;
qboolean fboBloomInited = qfalse;
int      fboReadIndex = 0;
GLint    fboInternalFormat;
GLint    fboTextureFormat;
GLint    fboTextureType;
static GLint fboBloomInternalFormat;
static GLint fboBloomTextureFormat;
static GLint fboBloomTextureType;
static int   fboBloomFormatMode;
static qboolean framebufferSrgbEnabled = qfalse;
int      fboBloomPasses;
int      fboBloomBlendBase;
int      fboBloomFilterSize;
static float fboEffectiveTonemapExposure = 1.0f;
static int   fboExposureFrame = -1;
#ifdef RENDERER_GLX
static GLfloat fboExposureSamplePixels[ 128 * 128 * 4 ];
#endif

qboolean windowAdjusted;
int		blitX0, blitX1;
int		blitY0, blitY1;
int		blitClear;
GLenum	blitFilter;

qboolean superSampled;

typedef struct frameBuffer_s {
	GLuint fbo;
	GLuint color;			// renderbuffer if multisampled
	GLuint depthStencil;	// renderbuffer if multisampled
	GLint  width;
	GLint  height;
	qboolean multiSampled;
	GLint  internalFormat;
} frameBuffer_t;

#ifdef USE_FBO
static GLuint commonDepthStencil;
static GLuint depthFadeTexture;
static qboolean depthFadeCopied;

static frameBuffer_t frameBufferMS;
static frameBuffer_t frameBuffers[ FBO_COUNT ];
static frameBuffer_t menuDofBuffers[ 2 ];

static qboolean frameBufferMultiSampling = qfalse;

qboolean blitMSfbo = qfalse;
#endif

#ifdef USE_FBO
static int FBO_HdrSceneLinearMode( void )
{
	return ( r_hdr && r_hdr->integer > 0 ) ? 1 : 0;
}

static int FBO_HdrPrecisionMode( void )
{
	const int precision = r_hdrPrecision ? r_hdrPrecision->integer : 0;

	if ( FBO_HdrSceneLinearMode() ) {
		return 16;
	}
	if ( precision == -1 || precision == 8 || precision == 16 ) {
		return precision;
	}
	if ( r_hdr && r_hdr->integer < 0 ) {
		return -1;
	}
	return 8;
}

static qboolean FBO_InternalFormatIsFloat( GLint internalFormat )
{
	return ( internalFormat == GL_RGBA16F || internalFormat == GL_RGB16F ||
		internalFormat == GL_R11F_G11F_B10F || internalFormat == GL_RG16F ) ? qtrue : qfalse;
}

static int FBO_HdrBloomFormatMode( void )
{
	const int mode = r_hdrBloomFormat ? r_hdrBloomFormat->integer : GLX_HDR_BLOOM_FORMAT_AUTO;

	if ( mode >= GLX_HDR_BLOOM_FORMAT_AUTO && mode <= GLX_HDR_BLOOM_FORMAT_RG16F ) {
		return mode;
	}
	return GLX_HDR_BLOOM_FORMAT_AUTO;
}

static const char *FBO_HdrBloomFormatModeName( int mode )
{
	switch ( mode )
	{
		case GLX_HDR_BLOOM_FORMAT_RGBA16F:
			return "rgba16f";
		case GLX_HDR_BLOOM_FORMAT_R11G11B10F:
			return "r11g11b10f";
		case GLX_HDR_BLOOM_FORMAT_RG16F:
			return "rg16f";
		case GLX_HDR_BLOOM_FORMAT_AUTO:
		default:
			return "auto";
	}
}

static qboolean FBO_FrameBufferIsBloom( const frameBuffer_t *fb )
{
	const int index = (int)( fb - frameBuffers );

	return ( index >= BLOOM_BASE && index < FBO_COUNT ) ? qtrue : qfalse;
}

static void FBO_AddFormatCandidate( GLint *formats, int *count, GLint format )
{
	int i;

	for ( i = 0; i < *count; i++ )
	{
		if ( formats[i] == format ) {
			return;
		}
	}

	formats[*count] = format;
	(*count)++;
}

static void FBO_PositiveIntermediateCandidates( qboolean rgb, GLint *formats, int *count )
{
	const int mode = FBO_HdrBloomFormatMode();

	*count = 0;

	if ( !FBO_HdrSceneLinearMode() ) {
		FBO_AddFormatCandidate( formats, count, GL_RGB10_A2 );
		return;
	}

	if ( mode == GLX_HDR_BLOOM_FORMAT_RGBA16F ) {
		FBO_AddFormatCandidate( formats, count, GL_RGBA16F );
		return;
	}

	if ( rgb ) {
		if ( mode != GLX_HDR_BLOOM_FORMAT_RG16F ) {
			FBO_AddFormatCandidate( formats, count, GL_R11F_G11F_B10F );
		}
	} else {
		if ( mode != GLX_HDR_BLOOM_FORMAT_R11G11B10F ) {
			FBO_AddFormatCandidate( formats, count, GL_RG16F );
		}
	}

	FBO_AddFormatCandidate( formats, count, GL_RGBA16F );
}

static void FBO_FormatCandidatesForBuffer( const frameBuffer_t *fb, GLint *formats, int *count )
{
	if ( FBO_FrameBufferIsBloom( fb ) ) {
		FBO_PositiveIntermediateCandidates( qtrue, formats, count );
		return;
	}

	*count = 0;
	FBO_AddFormatCandidate( formats, count, fboInternalFormat );
}

static GLint FBO_MainInternalFormat( void )
{
	if ( FBO_HdrSceneLinearMode() ) {
		return GL_RGBA16F;
	}

	switch ( FBO_HdrPrecisionMode() )
	{
		case -1:
			return GL_RGBA4;
		case 16:
			return GL_RGBA16;
		default:
			return GL_RGBA8;
	}
}

static int FBO_ToneMapMode( void )
{
	int mode;

	if ( !FBO_HdrSceneLinearMode() || !r_tonemap ) {
		return 0;
	}
	mode = r_tonemap->integer;
	if ( mode < 0 ) {
		return 0;
	}
	if ( mode > 2 ) {
		return 2;
	}
	return mode;
}

static float FBO_TonemapExposureCvar( void )
{
	if ( !FBO_HdrSceneLinearMode() || !r_tonemapExposure ) {
		return 1.0f;
	}
	return Com_Clamp( 0.1f, 8.0f, r_tonemapExposure->value );
}

static float FBO_TonemapExposure( void )
{
	if ( !FBO_HdrSceneLinearMode() ) {
		return 1.0f;
	}
	if ( fboExposureFrame != tr.frameCount ) {
		fboEffectiveTonemapExposure = FBO_TonemapExposureCvar();
	}
	return fboEffectiveTonemapExposure;
}

static int FBO_ColorGradeMode( void )
{
	int mode;

	if ( !FBO_HdrSceneLinearMode() || !r_colorGrade ) {
		return 0;
	}
	mode = r_colorGrade->integer;
	if ( mode < 0 ) {
		return 0;
	}
	if ( mode > 3 ) {
		return 3;
	}
	return mode;
}

static qboolean FBO_ColorGradeUsesLiftGammaGain( int mode )
{
	return ( mode == 1 || mode == 3 ) ? qtrue : qfalse;
}

static qboolean FBO_ColorGradeUsesLut( int mode )
{
	return ( mode == 2 || mode == 3 ) ? qtrue : qfalse;
}

static void FBO_ParseVec3Cvar( const cvar_t *cvar, float fallback0, float fallback1,
	float fallback2, float minValue, float maxValue, vec3_t out )
{
	float values[3];

	values[0] = fallback0;
	values[1] = fallback1;
	values[2] = fallback2;
	if ( cvar && cvar->string && cvar->string[0] ) {
		(void)sscanf( cvar->string, "%f %f %f", &values[0], &values[1], &values[2] );
	}
	out[0] = Com_Clamp( minValue, maxValue, values[0] );
	out[1] = Com_Clamp( minValue, maxValue, values[1] );
	out[2] = Com_Clamp( minValue, maxValue, values[2] );
}

static void FBO_SetIdentity3x3( float matrix[9] )
{
	matrix[0] = 1.0f; matrix[1] = 0.0f; matrix[2] = 0.0f;
	matrix[3] = 0.0f; matrix[4] = 1.0f; matrix[5] = 0.0f;
	matrix[6] = 0.0f; matrix[7] = 0.0f; matrix[8] = 1.0f;
}

static void FBO_CctToXyz( float kelvin, float xyz[3] )
{
	float x, y;
	const float t = Com_Clamp( 1667.0f, 25000.0f, kelvin );
	const float t2 = t * t;
	const float t3 = t2 * t;

	if ( t <= 4000.0f ) {
		x = -0.2661239e9f / t3 - 0.2343580e6f / t2 + 0.8776956e3f / t + 0.179910f;
	} else {
		x = -3.0258469e9f / t3 + 2.1070379e6f / t2 + 0.2226347e3f / t + 0.240390f;
	}

	if ( t < 2222.0f ) {
		y = -1.1063814f * x * x * x - 1.34811020f * x * x + 2.18555832f * x - 0.20219683f;
	} else if ( t < 4000.0f ) {
		y = -0.9549476f * x * x * x - 1.37418593f * x * x + 2.09137015f * x - 0.16748867f;
	} else {
		y = 3.0817580f * x * x * x - 5.87338670f * x * x + 3.75112997f * x - 0.37001483f;
	}

	if ( y <= 0.0001f ) {
		xyz[0] = 0.95047f;
		xyz[1] = 1.0f;
		xyz[2] = 1.08883f;
		return;
	}
	xyz[0] = x / y;
	xyz[1] = 1.0f;
	xyz[2] = ( 1.0f - x - y ) / y;
}

static void FBO_BuildBradfordAdaptation( float sourceKelvin, float targetKelvin, float matrix[9] )
{
	static const float bradford[9] = {
		 0.8951f,  0.2664f, -0.1614f,
		-0.7502f,  1.7135f,  0.0367f,
		 0.0389f, -0.0685f,  1.0296f
	};
	static const float bradfordInv[9] = {
		 0.9869929f, -0.1470543f,  0.1599627f,
		 0.4323053f,  0.5183603f,  0.0492912f,
		-0.0085287f,  0.0400428f,  0.9684867f
	};
	float src[3], dst[3], srcCone[3], dstCone[3], scale[3];
	float scaledBradford[9];
	int row, col;

	FBO_CctToXyz( sourceKelvin, src );
	FBO_CctToXyz( targetKelvin, dst );

	for ( row = 0; row < 3; row++ ) {
		srcCone[row] = bradford[row * 3 + 0] * src[0] +
			bradford[row * 3 + 1] * src[1] +
			bradford[row * 3 + 2] * src[2];
		dstCone[row] = bradford[row * 3 + 0] * dst[0] +
			bradford[row * 3 + 1] * dst[1] +
			bradford[row * 3 + 2] * dst[2];
		scale[row] = fabs( srcCone[row] ) > 0.0001f ? dstCone[row] / srcCone[row] : 1.0f;
	}

	for ( row = 0; row < 3; row++ ) {
		for ( col = 0; col < 3; col++ ) {
			scaledBradford[row * 3 + col] = scale[row] * bradford[row * 3 + col];
		}
	}

	for ( row = 0; row < 3; row++ ) {
		for ( col = 0; col < 3; col++ ) {
			matrix[row * 3 + col] =
				bradfordInv[row * 3 + 0] * scaledBradford[0 * 3 + col] +
				bradfordInv[row * 3 + 1] * scaledBradford[1 * 3 + col] +
				bradfordInv[row * 3 + 2] * scaledBradford[2 * 3 + col];
		}
	}
}

static qboolean FBO_ValidateColorGradeLutAtlas( const image_t *image, int *size )
{
	int lutSize;

	if ( !image || image->width <= 0 || image->height <= 0 ) {
		return qfalse;
	}
	if ( image->width != image->height * image->height ) {
		return qfalse;
	}
	lutSize = image->height;
	if ( lutSize < 2 || lutSize > 64 ) {
		return qfalse;
	}
	if ( size ) {
		*size = lutSize;
	}
	return qtrue;
}

static image_t *FBO_CreateIdentityColorGradeLut( int *size )
{
	static image_t *identityLut;
	enum { IDENTITY_LUT_SIZE = 16 };
	byte data[ IDENTITY_LUT_SIZE * IDENTITY_LUT_SIZE * IDENTITY_LUT_SIZE * 4 ];
	int r, g, b;
	const int width = IDENTITY_LUT_SIZE * IDENTITY_LUT_SIZE;

	if ( identityLut ) {
		if ( size ) {
			*size = IDENTITY_LUT_SIZE;
		}
		return identityLut;
	}

	for ( b = 0; b < IDENTITY_LUT_SIZE; b++ ) {
		for ( g = 0; g < IDENTITY_LUT_SIZE; g++ ) {
			for ( r = 0; r < IDENTITY_LUT_SIZE; r++ ) {
				const int index = ( g * width + b * IDENTITY_LUT_SIZE + r ) * 4;
				data[index + 0] = (byte)( r * 255 / ( IDENTITY_LUT_SIZE - 1 ) );
				data[index + 1] = (byte)( g * 255 / ( IDENTITY_LUT_SIZE - 1 ) );
				data[index + 2] = (byte)( b * 255 / ( IDENTITY_LUT_SIZE - 1 ) );
				data[index + 3] = 255;
			}
		}
	}

	identityLut = R_CreateImage( "*colorGradeIdentityLUT", NULL, data,
		width, IDENTITY_LUT_SIZE,
		IMGFLAG_CLAMPTOEDGE | IMGFLAG_NO_COMPRESSION |
		IMGFLAG_NOSCALE | IMGFLAG_COLORSPACE_LINEAR );
	if ( size ) {
		*size = IDENTITY_LUT_SIZE;
	}
	return identityLut;
}

static image_t *FBO_ColorGradeLutImage( int *size )
{
	static image_t *lutImage;
	static int lutSize;
	static int lutModificationCount = -1;
	const int flags = IMGFLAG_CLAMPTOEDGE | IMGFLAG_NO_COMPRESSION |
		IMGFLAG_NOSCALE | IMGFLAG_COLORSPACE_LINEAR;

	if ( !r_colorGradeLUT || r_colorGradeLUT->modificationCount == lutModificationCount ) {
		if ( size ) {
			*size = lutSize;
		}
		return lutImage;
	}

	lutModificationCount = r_colorGradeLUT->modificationCount;
	lutImage = NULL;
	lutSize = 0;

	if ( r_colorGradeLUT->string && r_colorGradeLUT->string[0] ) {
		image_t *loaded = R_FindImageFile( r_colorGradeLUT->string, flags );
		if ( FBO_ValidateColorGradeLutAtlas( loaded, &lutSize ) ) {
			lutImage = loaded;
		} else {
			ri.Printf( PRINT_WARNING,
				"WARNING: color-grade LUT '%s' must use width N*N and height N; using identity LUT\n",
				r_colorGradeLUT->string );
		}
	}

	if ( !lutImage ) {
		lutImage = FBO_CreateIdentityColorGradeLut( &lutSize );
	}

	if ( size ) {
		*size = lutSize;
	}
	return lutImage;
}

static qboolean FBO_ColorGradeLutActive( void )
{
	int size;
	const int mode = FBO_ColorGradeMode();

	if ( !FBO_ColorGradeUsesLut( mode ) || !qglActiveTextureARB || glConfig.numTextureUnits <= 2 ) {
		return qfalse;
	}
	return FBO_ColorGradeLutImage( &size ) && size > 1 ? qtrue : qfalse;
}

static float FBO_ColorGradeLutScale( void )
{
	if ( !r_colorGradeLUTScale ) {
		return 4.0f;
	}
	return Com_Clamp( 1.0f, 32.0f, r_colorGradeLUTScale->value );
}

static void FBO_BindColorGradeLut( void )
{
	int size;
	image_t *lutImage;

	if ( !FBO_ColorGradeLutActive() ) {
		return;
	}

	lutImage = FBO_ColorGradeLutImage( &size );
	if ( lutImage ) {
		GL_BindTexture( 2, lutImage->texnum );
	}
}

#ifdef RENDERER_GLX
static void FBO_PrepareGlxPostShaderColorGradeLut( void )
{
	int lutSize = 16;
	float lutScale = FBO_ColorGradeLutScale();
	const qboolean lutActive = FBO_ColorGradeLutActive();

	if ( lutActive ) {
		(void)FBO_ColorGradeLutImage( &lutSize );
		FBO_BindColorGradeLut();
	} else {
		lutScale = 4.0f;
	}
	GLX_CompatRecordColorGradeLut( lutActive, lutSize, lutScale );
}
#endif

static float FBO_OutputOverbrightScale( float obScale )
{
	return FBO_HdrSceneLinearMode() ? 1.0f : obScale;
}

static void FBO_SetOutputTransformParams( float gamma, float obScale )
{
	const float outputScale = FBO_OutputOverbrightScale( obScale );
	const float exposure = FBO_TonemapExposure();
	const float srgbOutput = FBO_HdrSceneLinearMode() ? 1.0f : 0.0f;
	const int gradeMode = FBO_ColorGradeMode();
	const qboolean lgg = FBO_ColorGradeUsesLiftGammaGain( gradeMode );
	vec3_t lift, gradeGamma, invGradeGamma, gain;
	float whitePointMatrix[9];
	float sourceWhitePoint = r_colorGradeWhitePoint ?
		Com_Clamp( 1000.0f, 40000.0f, r_colorGradeWhitePoint->value ) : 6504.0f;
	float targetWhitePoint = r_colorGradeAdaptWhitePoint ?
		Com_Clamp( 1000.0f, 40000.0f, r_colorGradeAdaptWhitePoint->value ) : 6504.0f;
	int lutSize = 16;
	float lutScale = FBO_ColorGradeLutScale();
	qboolean lutActive;

	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 0, gamma, gamma, gamma, outputScale );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 2, exposure, exposure, exposure, 1.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 3, srgbOutput, srgbOutput, srgbOutput, 1.0f );

	FBO_ParseVec3Cvar( r_colorGradeLift, 0.0f, 0.0f, 0.0f, -1.0f, 1.0f, lift );
	FBO_ParseVec3Cvar( r_colorGradeGamma, 1.0f, 1.0f, 1.0f, 0.1f, 8.0f, gradeGamma );
	FBO_ParseVec3Cvar( r_colorGradeGain, 1.0f, 1.0f, 1.0f, 0.0f, 8.0f, gain );

	if ( !lgg ) {
		VectorClear( lift );
		VectorSet( gradeGamma, 1.0f, 1.0f, 1.0f );
		VectorSet( gain, 1.0f, 1.0f, 1.0f );
		sourceWhitePoint = 6504.0f;
		targetWhitePoint = 6504.0f;
	}
	invGradeGamma[0] = 1.0f / gradeGamma[0];
	invGradeGamma[1] = 1.0f / gradeGamma[1];
	invGradeGamma[2] = 1.0f / gradeGamma[2];

	if ( lgg ) {
		FBO_BuildBradfordAdaptation( sourceWhitePoint, targetWhitePoint, whitePointMatrix );
	} else {
		FBO_SetIdentity3x3( whitePointMatrix );
	}
	lutActive = FBO_ColorGradeLutActive();
	if ( !lutActive ) {
		lutScale = 4.0f;
	} else {
		(void)FBO_ColorGradeLutImage( &lutSize );
	}
#ifdef RENDERER_GLX
	GLX_CompatRecordColorGradeLut( lutActive, lutSize, lutScale );
#endif

	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 4, lift[0], lift[1], lift[2], 0.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 5, invGradeGamma[0], invGradeGamma[1], invGradeGamma[2], 1.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 6, gain[0], gain[1], gain[2], 1.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 7, whitePointMatrix[0], whitePointMatrix[1], whitePointMatrix[2], 0.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 8, whitePointMatrix[3], whitePointMatrix[4], whitePointMatrix[5], 0.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 9, whitePointMatrix[6], whitePointMatrix[7], whitePointMatrix[8], 0.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 10, lutScale, (float)( lutSize - 1 ),
		1.0f / (float)lutSize, 1.0f / (float)( lutSize * lutSize ) );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 11, 0.5f, (float)lutSize, 1.0f / lutScale, 0.0f );
}

static void FBO_SetFramebufferSrgb( qboolean enable )
{
	static qboolean initialized = qfalse;

	if ( !framebufferSrgbAvailable ) {
		framebufferSrgbEnabled = qfalse;
		initialized = qtrue;
		return;
	}

	enable = ( enable &&
		r_framebufferSRGB && r_framebufferSRGB->integer &&
		framebufferSrgbAvailable ) ? qtrue : qfalse;

	if ( initialized && framebufferSrgbEnabled == enable ) {
		return;
	}

	if ( enable ) {
		qglEnable( GL_FRAMEBUFFER_SRGB );
	} else {
		qglDisable( GL_FRAMEBUFFER_SRGB );
	}
	framebufferSrgbEnabled = enable;
	initialized = qtrue;
}
#endif

#ifndef GL_TEXTURE_IMAGE_FORMAT
#define GL_TEXTURE_IMAGE_FORMAT 0x828F
#endif

#ifndef GL_TEXTURE_IMAGE_TYPE
#define GL_TEXTURE_IMAGE_TYPE 0x8290
#endif

extern void RB_SetGL2D( void );

#if defined(RENDERER_GLX) && defined(USE_FBO)
static void GLX_RecordFboInitState( qboolean requested, qboolean ready,
	qboolean programReady, qboolean framebufferFnsReady )
{
	GLX_CompatRecordFboInit( requested, ready, programReady, framebufferFnsReady,
		glConfig.vidWidth, glConfig.vidHeight, gls.captureWidth, gls.captureHeight,
		gls.windowWidth, gls.windowHeight, fboInternalFormat, fboTextureFormat,
		fboTextureType, frameBufferMultiSampling, superSampled, windowAdjusted,
		blitFilter, FBO_HdrSceneLinearMode(), r_renderScale ? r_renderScale->integer : 0,
		r_bloom ? r_bloom->integer : 0,
		textureSrgbAvailable, framebufferSrgbAvailable, framebufferSrgbEnabled );
}

static void GLX_RecordBloomCreateState( int result )
{
	GLX_CompatRecordBloomCreate( result,
		r_bloom_passes ? r_bloom_passes->integer : 0, fboBloomPasses,
		glConfig.numTextureUnits, fboBloomFormatMode,
		fboBloomInternalFormat, fboBloomTextureFormat, fboBloomTextureType );
}

static void GLX_RecordBloomState( int result, qboolean finalStage )
{
	GLX_CompatRecordBloom( result, finalStage,
		r_bloom ? r_bloom->integer : 0,
		r_bloom_passes ? r_bloom_passes->integer : 0,
		fboBloomPasses,
		fboBloomBlendBase,
		fboBloomFilterSize,
		glConfig.numTextureUnits,
		r_bloom_threshold_mode ? r_bloom_threshold_mode->integer : 0,
		r_bloom_modulate ? r_bloom_modulate->integer : 0,
		r_bloom_threshold ? r_bloom_threshold->value : 0.0f,
		r_bloom_intensity ? r_bloom_intensity->value : 0.0f,
		r_bloom_reflection ? r_bloom_reflection->value : 0.0f );
}
#endif

qboolean GL_ProgramAvailable( void )
{
	return (programCompiled != 0);
}


static void ARB_ProgramDisable( void )
{
	if ( current_vp )
		qglDisable( GL_VERTEX_PROGRAM_ARB );
	if ( current_fp )
		qglDisable( GL_FRAGMENT_PROGRAM_ARB );
	current_vp = 0;
	current_fp = 0;
	programEnabled = 0;
}


void GL_ProgramDisable( void )
{
	if ( programEnabled )
	{
		ARB_ProgramDisable();
	}
}


void ARB_ProgramEnableExt( GLuint vertexProgram, GLuint fragmentProgram )
{
	if ( programCompiled )
	{
		if ( current_vp != vertexProgram ) {
			current_vp = vertexProgram;
			if ( current_vp ) {
				qglEnable( GL_VERTEX_PROGRAM_ARB );
				qglBindProgramARB( GL_VERTEX_PROGRAM_ARB, current_vp );
			} else {
				qglDisable( GL_VERTEX_PROGRAM_ARB );
			}
		}

		if ( current_fp != fragmentProgram ) {
			current_fp = fragmentProgram;
			if ( current_fp ) {
				qglEnable( GL_FRAGMENT_PROGRAM_ARB );
				qglBindProgramARB( GL_FRAGMENT_PROGRAM_ARB, current_fp );
			} else {
				qglDisable( GL_FRAGMENT_PROGRAM_ARB );
			}
		}
		programEnabled = 1;
	}
}


static void ARB_ProgramEnable( programNum vp, programNum fp )
{
	ARB_ProgramEnableExt( programs[ vp ], programs[ fp ] );
}


void GL_ProgramEnable( void )
{
	ARB_ProgramEnable( DUMMY_VERTEX, SPRITE_FRAGMENT );
}


#ifdef USE_PMLIGHT
#ifdef RENDERER_GLX
static qboolean GLX_TryStreamDrawPMLightPass( int numIndexes, const glIndex_t *indexes )
{
	const shaderCommands_t *input;
	const vec2_t *texCoords;
	glxStreamReservation_t reservation;
	qboolean ok = qtrue;
	int xyzBytes;
	int normalBytes;
	int texBytes;
	int indexBytes;
	int normalOffset;
	int texOffset;
	int indexOffset;
	int totalBytes;
	int materialFlags;
	unsigned int categoryMask;
	unsigned int oldArrayBuffer = 0;
	unsigned int oldElementArrayBuffer = 0;

	if ( !GLX_CompatStreamDrawEnabled() ) {
		return qfalse;
	}
	if ( !qglBindBufferARB ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_NO_BIND_BUFFER );
		return qfalse;
	}

	input = &tess;
	texCoords = (const vec2_t *)input->svars.texcoordPtr[0];
	if ( !indexes || !texCoords ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_BAD_INPUT );
		return qfalse;
	}
	if ( input->numVertexes <= 0 || numIndexes <= 0 ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_EMPTY_BATCH );
		return qfalse;
	}

	materialFlags = GLX_STAGE_DLIGHT_MAP | GLX_STAGE_ST0;
	categoryMask = GLX_CompatDynamicCategoryMaskForTess( input, materialFlags );
	if ( !GLX_CompatStreamDrawAllowsMaterial( materialFlags, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, 0, 0,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		0, 0, GLX_MATERIAL_FOG_ADJUST_NONE, 0, qfalse ) ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_MATERIAL_KEY );
		return qfalse;
	}

	xyzBytes = input->numVertexes * (int)sizeof( input->xyz[0] );
	normalBytes = input->numVertexes * (int)sizeof( input->normal[0] );
	texBytes = input->numVertexes * (int)sizeof( texCoords[0] );
	indexBytes = numIndexes * (int)sizeof( indexes[0] );
	normalOffset = GLX_CompatAlignInt( xyzBytes, 16 );
	texOffset = GLX_CompatAlignInt( normalOffset + normalBytes, 16 );
	indexOffset = GLX_CompatAlignInt( texOffset + texBytes, 16 );
	totalBytes = GLX_CompatAlignInt( indexOffset + indexBytes, 64 );

	if ( !GLX_CompatStreamReserve( totalBytes, 64, &reservation ) ) {
		GLX_CompatRecordStreamDrawResult( input->numVertexes, numIndexes,
			totalBytes, indexBytes, 0, qfalse, qfalse, qfalse, materialFlags, categoryMask, qfalse );
		return qfalse;
	}

	if ( !GLX_CompatStreamUploadAt( &reservation, 0, input->xyz, xyzBytes ) ) {
		ok = qfalse;
	}
	if ( ok && !GLX_CompatStreamUploadAt( &reservation, normalOffset, input->normal, normalBytes ) ) {
		ok = qfalse;
	}
	if ( ok && !GLX_CompatStreamUploadAt( &reservation, texOffset, texCoords, texBytes ) ) {
		ok = qfalse;
	}
	if ( ok && !GLX_CompatStreamUploadAt( &reservation, indexOffset, indexes, indexBytes ) ) {
		ok = qfalse;
	}
	GLX_CompatStreamCommit( &reservation );

	if ( !ok ) {
		GLX_CompatRecordStreamDrawResult( input->numVertexes, numIndexes,
			totalBytes, indexBytes, 0, qfalse, qfalse, qfalse, materialFlags, categoryMask, qfalse );
		return qfalse;
	}

	oldArrayBuffer = GLX_CompatBindStreamArrayBuffer( reservation.buffer );
	oldElementArrayBuffer = GLX_CompatBindStreamElementArrayBuffer( reservation.buffer );

	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_TEXCOORD_ARRAY | CLS_NORMAL_ARRAY );
	qglVertexPointer( 3, GL_FLOAT, sizeof( input->xyz[0] ), (const GLvoid *)(intptr_t)( reservation.offset ) );
	qglNormalPointer( GL_FLOAT, sizeof( input->normal[0] ), (const GLvoid *)(intptr_t)( reservation.offset + normalOffset ) );
	qglTexCoordPointer( 2, GL_FLOAT, 0, (const GLvoid *)(intptr_t)( reservation.offset + texOffset ) );

	if ( !GLX_CompatDrawElements( GL_TRIANGLES, numIndexes, GL_INDEX_TYPE,
		(const GLvoid *)(intptr_t)( reservation.offset + indexOffset ),
		GLX_LEGACY_DELEGATION_NONE, GLX_DRAW_STREAM_GENERIC ) ) {
		ok = qfalse;
	}

	GLX_CompatRestoreStreamElementArrayBuffer( oldElementArrayBuffer );
	GLX_CompatRestoreStreamArrayBuffer( 0 );
	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_TEXCOORD_ARRAY | CLS_NORMAL_ARRAY );
	qglVertexPointer( 3, GL_FLOAT, sizeof( input->xyz[0] ), input->xyz );
	qglNormalPointer( GL_FLOAT, sizeof( input->normal[0] ), input->normal );
	qglTexCoordPointer( 2, GL_FLOAT, 0, texCoords );
	GLX_CompatRestoreStreamArrayBuffer( oldArrayBuffer );

	GLX_CompatRecordStreamDrawResult( input->numVertexes, numIndexes,
		totalBytes, indexBytes, 0, qfalse, qfalse, qfalse, materialFlags, categoryMask, ok );
	return ok;
}
#endif

static void ARB_DrawLightingElements( int numIndexes, const glIndex_t *indexes )
{
	qboolean glxStreamedDraw = qfalse;

	if ( numIndexes <= 0 ) {
		return;
	}

#ifdef RENDERER_GLX
	glxStreamedDraw = GLX_TryStreamDrawPMLightPass( numIndexes, indexes );
#endif
	if ( glxStreamedDraw ) {
		return;
	}

	if ( qglLockArraysEXT )
		qglLockArraysEXT( 0, tess.numVertexes );

	R_DrawElements( numIndexes, indexes );

	if ( qglUnlockArraysEXT )
		qglUnlockArraysEXT();
}

#ifndef RENDERER_GLX
static void ARB_Lighting( const shaderStage_t* pStage )
{
	const dlight_t* dl;
	byte clipBits[ SHADER_MAX_VERTEXES ];
	glIndex_t hitIndexes[ SHADER_MAX_INDEXES ];
	int numIndexes;
	int clip;
	int i;
	
	backEnd.pc.c_lit_vertices_lateculltest += tess.numVertexes;

	dl = tess.light;

	for ( i = 0; i < tess.numVertexes; ++i ) {
		vec3_t dist;
		VectorSubtract( dl->transformed, tess.xyz[i], dist );

		if ( tess.surfType != SF_GRID && DotProduct( dist, tess.normal[i] ) <= 0.0f ) {
			clipBits[ i ] = 63;
			continue;
		}

		clip = 0;
		if ( dist[0] > dl->radius ) {
			clip |= 1;
		} else if ( dist[0] < -dl->radius ) {
			clip |= 2;
		}
		if ( dist[1] > dl->radius ) {
			clip |= 4;
		} else if ( dist[1] < -dl->radius ) {
			clip |= 8;
		}
		if ( dist[2] > dl->radius ) {
			clip |= 16;
		} else if ( dist[2] < -dl->radius ) {
			clip |= 32;
		}

		clipBits[i] = clip;
	}

	// build a list of triangles that need light
	numIndexes = 0;

	for ( i = 0 ; i < tess.numIndexes ; i += 3 ) {
		int		a, b, c;

		a = tess.indexes[i];
		b = tess.indexes[i+1];
		c = tess.indexes[i+2];
		if ( clipBits[a] & clipBits[b] & clipBits[c] ) {
			continue;	// not lighted
		}
		hitIndexes[numIndexes] = a;
		hitIndexes[numIndexes+1] = b;
		hitIndexes[numIndexes+2] = c;
		numIndexes += 3;
	}

	backEnd.pc.c_lit_indices_latecull_in += numIndexes;
	backEnd.pc.c_lit_indices_latecull_out += tess.numIndexes - numIndexes;

	if ( !numIndexes )
		return;

	if ( tess.shader->sort < SS_OPAQUE ) {
		GL_State( GLS_SRCBLEND_DST_COLOR | GLS_DSTBLEND_ONE | GLS_DEPTHFUNC_EQUAL );
	} else {
		GL_State( GLS_SRCBLEND_ONE | GLS_DSTBLEND_ONE | GLS_DEPTHFUNC_EQUAL );
	}

	GL_SelectTexture( 0 );

	R_BindAnimatedImage( &pStage->bundle[ tess.shader->lightingBundle ] );
	
	ARB_DrawLightingElements( numIndexes, hitIndexes );
}
#endif


static void ARB_Lighting_Fast( const shaderStage_t* pStage )
{
	if ( !tess.numIndexes )
		return;

	if ( tess.shader->sort < SS_OPAQUE ) {
		GL_State( GLS_SRCBLEND_DST_COLOR | GLS_DSTBLEND_ONE | GLS_DEPTHFUNC_EQUAL );
	} else {
		GL_State( GLS_SRCBLEND_ONE | GLS_DSTBLEND_ONE | GLS_DEPTHFUNC_EQUAL );
	}

	GL_SelectTexture( 0 );

	R_BindAnimatedImage( &pStage->bundle[ tess.shader->lightingBundle ] );
	
	ARB_DrawLightingElements( tess.numIndexes, tess.indexes );
}


static float ARB_ComputeTextureIntensityScale( const image_t *image )
{
	if ( image == NULL || r_intensity->value <= 1.0f ) {
		return 1.0f;
	}

	if ( image->flags & IMGFLAG_NOLIGHTSCALE ) {
		return 1.0f;
	}

	if ( ( image->flags & IMGFLAG_MIPMAP ) || image->uploadWidth != image->width ||
		image->uploadHeight != image->height ) {
		return r_intensity->value;
	}

	return 1.0f;
}

void ARB_SetupLightParams( const shaderStage_t *pStage )
{
	programNum vertexProgram;
	programNum fragmentProgram;
	const fogProgramParms_t *fp;
	qboolean fogPass;
	const dlight_t *dl;
	vec3_t lightRGB;
	float radius;
	float textureScale;

	tess.dlightUpdateParams = qfalse;
	tess.cullType = tess.shader->cullType;

	if ( !programCompiled || !pStage )
		return;

	dl = tess.light;

	if ( !glConfig.deviceSupportsGamma && !fboEnabled )
		VectorScale( dl->color, 2 * powf( r_intensity->value, r_gamma->value ), lightRGB );
	else
		VectorCopy( dl->color, lightRGB );

	radius = dl->radius;

	fogPass = ( tess.fogNum && tess.shader->fogPass );
	fp = NULL;

	vertexProgram = DLIGHT_VERTEX;

	if ( dl->linear ) {
		fragmentProgram = (tess.shader->cullType == CT_TWO_SIDED) ? DLIGHT_LINEAR_ABS_FRAGMENT : DLIGHT_LINEAR_FRAGMENT;
	} else {
		fragmentProgram = (tess.shader->cullType == CT_TWO_SIDED) ? DLIGHT_ABS_FRAGMENT : DLIGHT_FRAGMENT;
	}

	if ( fogPass ) {
		fp = RB_CalcFogProgramParms();
		// switch to fog programs
		if ( fp->eyeOutside ) {
			vertexProgram += 2;
		} else {
			vertexProgram += 1;
		}
		++fragmentProgram;
	}

	ARB_ProgramEnable( vertexProgram, fragmentProgram );

	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 0, lightRGB[0], lightRGB[1], lightRGB[2], 1.0f / Square( radius ) );
	textureScale = ARB_ComputeTextureIntensityScale( pStage->bundle[ tess.shader->lightingBundle ].image[0] );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 5, textureScale, 1.0f, 1.0f, 1.0f );

	if ( dl->linear )
	{
		vec3_t ab;
		VectorSubtract( dl->transformed2, dl->transformed, ab );
		//qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 2, dl->transformed[0], dl->transformed[1], dl->transformed[2], 0 );
		//qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 3, dl->transformed2[0], dl->transformed2[1], dl->transformed2[2], 0 );
		qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 4, ab[0], ab[1], ab[2], 1.0f / DotProduct( ab, ab ) );
	}

	qglProgramLocalParameter4fARB( GL_VERTEX_PROGRAM_ARB, 0, backEnd.or.viewOrigin[0], backEnd.or.viewOrigin[1], backEnd.or.viewOrigin[2], 0 );
	qglProgramLocalParameter4fARB( GL_VERTEX_PROGRAM_ARB, 1, dl->transformed[0], dl->transformed[1], dl->transformed[2], 0 );

	if ( fogPass )
	{
		GL_BindTexture( 1, tr.fogImage->texnum );
		//qglProgramLocalParameter4fvARB( GL_FRAGMENT_PROGRAM_ARB, 5, fp->fogColor );
		qglProgramLocalParameter4fvARB( GL_VERTEX_PROGRAM_ARB, 2, fp->fogDistanceVector );
		qglProgramLocalParameter4fvARB( GL_VERTEX_PROGRAM_ARB, 3, fp->fogDepthVector );
		qglProgramLocalParameter4fARB( GL_VERTEX_PROGRAM_ARB, 4, fp->eyeT, 0.0f, 0.0f, 0.0f );
		GL_SelectTexture( 0 );
	}
}


void ARB_LightingPass( void )
{
	const shaderStage_t* pStage;

	if ( tess.shader->lightingStage < 0 )
		return;

	pStage = tess.xstages[ tess.shader->lightingStage ];
	// Keep parity with VK_LightingPass: fog, light, and texture scale are
	// resolved per lit batch because fogNum and the selected surface texture
	// can change without an entity/light transform change.
	ARB_SetupLightParams( pStage );

	RB_DeformTessGeometry();

	GL_Cull( tess.shader->cullType );

	// set polygon offset if necessary
	if ( tess.shader->polygonOffset )
	{
		qglEnable( GL_POLYGON_OFFSET_FILL );
		qglPolygonOffset( r_offsetFactor->value, r_offsetUnits->value );
	}

	R_ComputeTexCoords( 0, &pStage->bundle[ tess.shader->lightingBundle ] );

	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_TEXCOORD_ARRAY | CLS_NORMAL_ARRAY );

	// Since this is a single pass, prepare the array state once; the draw helper
	// locks client arrays only when it falls back from the GLx stream path.

	qglTexCoordPointer( 2, GL_FLOAT, 0, tess.svars.texcoordPtr[0] );
	qglNormalPointer( GL_FLOAT, sizeof( tess.normal[0] ), tess.normal );
	qglVertexPointer( 3, GL_FLOAT, sizeof( tess.xyz[0] ), tess.xyz );

#ifdef RENDERER_GLX
	ARB_Lighting_Fast( pStage );
#else
	// CPU may limit performance in following cases
	if ( tess.light->linear || gl_version >= 40 )
		ARB_Lighting_Fast( pStage );
	else
		ARB_Lighting( pStage );
#endif

	// reset polygon offset
	if ( tess.shader->polygonOffset ) 
	{
		qglDisable( GL_POLYGON_OFFSET_FILL );
	}
}
#endif // USE_PMLIGHT


const char *fogOutVPCode = {
	"PARAM fogDistanceVector = program.local[2]; \n"
	"PARAM fogDepthVector = program.local[3]; \n"
	"PARAM eyeT = program.local[4]; \n"
	"PARAM _01_32 = 0.03125; \n"
	"PARAM _30_32 = 0.93750; \n"
	"TEMP st; \n"
	
	// s = DotProduct( v, fogDistanceVector ) + fogDistanceVector[3];
	"DP3 st.x, fogDistanceVector, vertex.position; \n"	
	"ADD st.x, st.x, fogDistanceVector.w; \n"

	// t = DotProduct( v, fogDepthVector ) + fogDepthVector[3];
	"DP3 st.y, fogDepthVector, vertex.position; \n"	
	"ADD st.y, st.y, fogDepthVector.w; \n"

	// if ( t < 1.0 ) { t = 1.0/32; } else { t = 1.0/32 + 30.0/32 * t / ( t - eyeT ); }
	"SGE st.w, st.y, 1.0; \n"
	"SUB st.z, st.y, eyeT.x; \n"
	"RCP st.z, st.z; \n"
	"MUL st.z, st.z, st.y; \n"
	"MUL st.z, st.z, _30_32; \n"
	"MAD st.y, st.z, st.w, _01_32; \n"
	
	//"MOV st.z, {1.0}; \n"
	"MOV st.w, {1.0}; \n"

	"MOV result.texcoord[4], st; \n"
};


const char *fogInVPCode = {

	"PARAM fogDistanceVector = program.local[2]; \n"
	"PARAM fogDepthVector = program.local[3]; \n"
	"PARAM eyeT = program.local[4]; \n"
	"PARAM _01_32 = 0.03125; \n"
	"PARAM _30_32 = 0.93750; \n"
	"TEMP st; \n"
	
	// s = DotProduct( v, fogDistanceVector ) + fogDistanceVector[3];
	"DP3 st.x, fogDistanceVector, vertex.position; \n"	
	"ADD st.x, st.x, fogDistanceVector.w; \n"

	// t = DotProduct( v, fogDepthVector ) + fogDepthVector[3];
	"DP3 st.y, fogDepthVector, vertex.position; \n"
	"ADD st.y, st.y, fogDepthVector.w; \n"

	//if ( t < 0 ) { t = 1.0/32; } else { t = 31.0/32; }
	"SGE st.w, st.y, 0.0; \n"
	"MAD st.y, st.w, _30_32, _01_32; \n"

	//"MOV st.z, {1.0}; \n"
	"MOV st.w, {1.0}; \n"

	"MOV result.texcoord[4], st; \n"
};


#ifdef USE_PMLIGHT
static const char *dlightVP = {
	"!!ARBvp1.0 \n"
	"OPTION ARB_position_invariant; \n"
	"PARAM posEye = program.local[0]; \n"
	"PARAM posLight = program.local[1]; \n"
	"OUTPUT lv = result.texcoord[1]; \n" // 1
	"OUTPUT ev = result.texcoord[2]; \n" // 2
	"OUTPUT n = result.texcoord[3]; \n"  // 3
	"MOV result.texcoord[0], vertex.texcoord; \n" // 0
	"SUB lv, posLight, vertex.position; \n"
	"SUB ev, posEye, vertex.position; \n"
	"MOV n, vertex.normal; \n"
	"%s" // fog shader if needed
	"END \n"
};


static const char *ARB_BuildDlightFP( char *program, int programIndex )
{
	qboolean fog = qfalse;
	qboolean linear = qfalse;
	qboolean abslight = qfalse;

	program[0] = '\0';

	switch ( programIndex ) {
		case DLIGHT_FRAGMENT_FOG:
		case DLIGHT_ABS_FRAGMENT_FOG:
		case DLIGHT_LINEAR_FRAGMENT_FOG:
		case DLIGHT_LINEAR_ABS_FRAGMENT_FOG:
			fog = qtrue;
			break;
	}

	switch ( programIndex ) {
		case DLIGHT_LINEAR_FRAGMENT:
		case DLIGHT_LINEAR_FRAGMENT_FOG:
		case DLIGHT_LINEAR_ABS_FRAGMENT:
		case DLIGHT_LINEAR_ABS_FRAGMENT_FOG:
			linear = qtrue;
			break;
	}

	switch ( programIndex ) {
		case DLIGHT_ABS_FRAGMENT:
		case DLIGHT_ABS_FRAGMENT_FOG:
		case DLIGHT_LINEAR_ABS_FRAGMENT:
		case DLIGHT_LINEAR_ABS_FRAGMENT_FOG:
			abslight = qtrue;
			break;
	}

	strcat( program,
	"!!ARBfp1.0 \n"
	"OPTION ARB_precision_hint_fastest; \n"
	"PARAM lightRGB = program.local[0]; \n"
	"PARAM texFactors = program.local[5]; \n"
	//"PARAM lightRange2recip = program.local[1]; \n"
	"TEMP base, tmp; \n"
	"TEX base, fragment.texcoord[0], texture[0], 2D; \n"
	"MUL base.xyz, base, texFactors.x; \n" );

	if ( linear ) {
		strcat( program,
		"PARAM lightVector = program.local[4]; \n"
		"ATTRIB LV = fragment.texcoord[1]; \n"
		"TEMP dnLV; \n"
		// project fragment on light vector
		"DP3 tmp.w, -LV, lightVector; \n"
		"MUL_SAT tmp.x, tmp.w, lightVector.w; \n"
		// calculate light vector from projection point
		"MAD dnLV, lightVector, tmp.x, LV; \n"
		);
	} else {
		strcat( program, "ATTRIB dnLV = fragment.texcoord[1]; \n" );
	}

	strcat( program,
	"ATTRIB dnEV = fragment.texcoord[2]; \n" // 2
	"ATTRIB n = fragment.texcoord[3]; \n"    // 3
	
	// normalize light vector
	"TEMP lv; \n"
	"DP3 tmp.w, dnLV, dnLV; \n"
	"RSQ lv.w, tmp.w; \n"
	"MUL lv.xyz, dnLV, lv.w; \n"

	// calculate light intensity
	"TEMP light; \n"
	"MUL tmp.x, tmp.w, lightRGB.w; \n"
	"SUB tmp.x, {1.0}, tmp.x; \n"
	// discard blank fragments
	"KIL tmp.x; \n"

	"MUL light, lightRGB, tmp.x; \n" ); // light.rgb

	if ( r_dlightSpecColor->value > 0 )
		strcat( program, va( "PARAM specRGB = %1.2f; \n", r_dlightSpecColor->value ) );

	strcat( program, va( "PARAM specEXP = %1.2f; \n", r_dlightSpecPower->value ) );

	strcat( program,
	// normalize eye vector
	"TEMP ev; \n"
	"DP3 ev.w, dnEV, dnEV; \n"
	"RSQ ev.w, ev.w; \n"
	"MUL ev.xyz, dnEV, ev.w; \n"

	// normalize (eye + light) vector
	"ADD tmp, lv, ev; \n"
	"DP3 tmp.w, tmp, tmp; \n"
	"RSQ tmp.w, tmp.w; \n"
	"MUL tmp.xyz, tmp, tmp.w; \n" );

	// modulate specular strength
	if ( abslight ) {
		strcat( program,
		"DP3 tmp.w, n, tmp; \n"
		"ABS tmp.w, tmp.w; \n" );
	} else {
		strcat( program,
		"DP3_SAT tmp.w, n, tmp; \n" );
	}

	strcat( program,
	"POW tmp.w, tmp.w, specEXP.w; \n"
	"TEMP spec; \n" );

	if ( r_dlightSpecColor->value > 0 ) {
		// by constant
		strcat( program, "MUL spec, specRGB, tmp.w; \n" );
	} else {
		// by texture
		strcat( program, va( "MUL tmp.w, tmp.w, %1.2f; \n", -r_dlightSpecColor->value ) );
		strcat( program, "MUL spec, base, tmp.w; \n" );
	}

	// diffuse
	if ( abslight ) {
		strcat( program,
		"TEMP bump; \n"
		"DP3 bump.w, n, lv; \n"
		// make sure that light and eye vectors are on the same plane side
		"DP3 tmp.w, n, ev; \n"
		"MUL tmp.w, tmp.w, bump.w; \n"
		"KIL tmp.w; \n"
		"ABS bump.w, bump.w; \n" );
	} else {
		strcat( program,
		"TEMP bump; \n"
		"DP3_SAT bump.w, n, lv; \n" );
	}

	strcat( program, "MAD base, base, bump.w, spec; \n" );

	if ( fog ) {
		strcat( program,
		"TEMP fog; \n"
		"TEX fog, fragment.texcoord[4], texture[1], 2D; \n" // fog texture
		//"MUL fog, fog, fogColor; \n"
		// blend with fog
		//"LRP_SAT base, fog.a, fog, base; \n"
		// modulate by inverted fog alpha
		"SUB fog.a, {1.0}, fog.a; \n"
		"MUL base, base, fog.a; \n" );
	}

	strcat( program,
	"MUL result.color, base, light; \n"
	"END \n" );
	
	r_dlightSpecColor->modified = qfalse;
	r_dlightSpecPower->modified = qfalse;

	return program;
}

#endif // USE_PMLIGHT


static const char *dummyVP = {
	"!!ARBvp1.0 \n"
	"OPTION ARB_position_invariant; \n"
	"MOV result.texcoord[0], vertex.texcoord; \n"
	"END \n" 
};


static const char *spriteFP = {
	"!!ARBfp1.0 \n"
	"OPTION ARB_precision_hint_fastest; \n"
	"TEMP base; \n"
	"TEX base, fragment.texcoord[0], texture[0], 2D; \n"
	"TEMP test; \n"
	"SUB test.a, base.a, 0.85; \n"
	"KIL test.a; \n"
	"MOV base, 0.0; \n"
	"MOV result.color, base; \n"
	"MOV result.depth, fragment.position.z; \n"
	"END \n"
};

static const char *depthFadeFP = {
	"!!ARBfp1.0 \n"
	"OPTION ARB_precision_hint_fastest; \n"
	"PARAM invTexRes = program.local[0]; \n"
	"PARAM fadeInfo = program.local[1]; \n"
	"PARAM fadeScale = program.local[2]; \n"
	"PARAM fadeBias = program.local[3]; \n"
	"PARAM one = { 1.0, 1.0, 1.0, 1.0 }; \n"
	"PARAM smooth = { -2.0, 3.0, 0.0, 0.0 }; \n"
	"TEMP base, faded, depthTC, sceneDepth, denom, sceneLinear, fragLinear, fade; \n"
	"TEX base, fragment.texcoord[0], texture[0], 2D; \n"
	"MUL base, base, fragment.color; \n"
	"MUL depthTC.xy, fragment.position, invTexRes; \n"
	"TEX sceneDepth, depthTC, texture[1], 2D; \n"
	"LRP denom.x, sceneDepth.x, one.x, fadeInfo.x; \n"
	"RCP sceneLinear.x, denom.x; \n"
	"MUL sceneLinear.x, sceneLinear.x, fadeInfo.y; \n"
	"LRP denom.x, fragment.position.z, one.x, fadeInfo.x; \n"
	"RCP fragLinear.x, denom.x; \n"
	"MUL fragLinear.x, fragLinear.x, fadeInfo.y; \n"
	"SUB fade.x, sceneLinear.x, fragLinear.x; \n"
	"ADD fade.x, fade.x, fadeInfo.w; \n"
	"MUL_SAT fade.x, fade.x, fadeInfo.z; \n"
	"MUL fade.y, fade.x, fade.x; \n"
	"MAD fade.z, smooth.x, fade.x, smooth.y; \n"
	"MUL fade.x, fade.y, fade.z; \n"
	"MUL faded, base, fadeScale; \n"
	"ADD faded, faded, fadeBias; \n"
	"LRP result.color, fade.x, base, faded; \n"
	"END \n"
};

qboolean GL_DepthFadeProgramAvailable( void )
{
#ifdef USE_FBO
	return programCompiled && FBO_DepthFadeReady();
#else
	return qfalse;
#endif
}

void GL_DepthFadeProgramEnable( const shader_t *shader )
{
#ifdef USE_FBO
	const byte scaleAndBias = r_depthFadeScaleAndBias[shader->dfType];
	vec4_t scale;
	vec4_t bias;
	int i;

	if ( !GL_DepthFadeProgramAvailable() ) {
		return;
	}

	for ( i = 0; i < 4; i++ ) {
		scale[i] = ( scaleAndBias & ( 1 << i ) ) ? 1.0f : 0.0f;
		bias[i] = ( scaleAndBias & ( 1 << ( i + 4 ) ) ) ? 1.0f : 0.0f;
	}

	ARB_ProgramEnable( DUMMY_VERTEX, DEPTH_FADE_FRAGMENT );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 0,
		1.0f / (float)glConfig.vidWidth, 1.0f / (float)glConfig.vidHeight, 0.0f, 0.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 1,
		backEnd.viewParms.zFar / r_znear->value, backEnd.viewParms.zFar, shader->dfInvDist, shader->dfBias );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 2, scale[0], scale[1], scale[2], scale[3] );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 3, bias[0], bias[1], bias[2], bias[3] );
#endif
}


#ifdef USE_FBO
static char *ARB_BuildGreyscaleProgram( char *buf ) {
	char *s;

	if ( r_greyscale->value == 0 ) {
		*buf = '\0';
		return buf;
	}

	s = Q_stradd( buf, "PARAM sRGB = { 0.2126, 0.7152, 0.0722, 1.0 }; \n" );

	if ( r_greyscale->value == 1.0 ) {
		Q_stradd( s, "DP3 base.xyz, base, sRGB; \n"  );
	} else {
		s = Q_stradd( s, "TEMP luma; \n" );
		s = Q_stradd( s, "DP3 luma, base, sRGB; \n" );
		/*s +=*/ sprintf( s, "LRP base.xyz, %1.2f, luma, base; \n", r_greyscale->value );
	}

	return buf;
}

static char *ARB_BuildToneMapProgram( char *buf ) {
	char *s = buf;

	*buf = '\0';

	switch ( FBO_ToneMapMode() ) {
	case 1:
		s = Q_stradd( s,
			"PARAM toneOne = { 1.0, 1.0, 1.0, 1.0 }; \n"
			"TEMP denom; \n"
			"ADD denom.xyz, base, toneOne; \n"
			"RCP denom.x, denom.x; \n"
			"RCP denom.y, denom.y; \n"
			"RCP denom.z, denom.z; \n"
			"MUL base.xyz, base, denom; \n" );
		break;
	case 2:
		s = Q_stradd( s,
			"PARAM acesA = { 2.51, 2.51, 2.51, 1.0 }; \n"
			"PARAM acesB = { 0.03, 0.03, 0.03, 1.0 }; \n"
			"PARAM acesC = { 2.43, 2.43, 2.43, 1.0 }; \n"
			"PARAM acesD = { 0.59, 0.59, 0.59, 1.0 }; \n"
			"PARAM acesE = { 0.14, 0.14, 0.14, 1.0 }; \n"
			"TEMP numerator; \n"
			"TEMP denominator; \n"
			"MAD numerator.xyz, base, acesA, acesB; \n"
			"MUL numerator.xyz, numerator, base; \n"
			"MAD denominator.xyz, base, acesC, acesD; \n"
			"MAD denominator.xyz, denominator, base, acesE; \n"
			"RCP denominator.x, denominator.x; \n"
			"RCP denominator.y, denominator.y; \n"
			"RCP denominator.z, denominator.z; \n"
			"MUL base.xyz, numerator, denominator; \n" );
		break;
	default:
		break;
	}

	return buf;
}

static char *ARB_BuildColorGradeProgram( char *buf ) {
	char *s = buf;
	const int mode = FBO_ColorGradeMode();
	const qboolean lgg = FBO_ColorGradeUsesLiftGammaGain( mode );
	const qboolean lut = FBO_ColorGradeLutActive();

	*buf = '\0';

	if ( !lgg && !lut ) {
		return buf;
	}

	s = Q_stradd( s, "PARAM zeroGrade = { 0.0, 0.0, 0.0, 0.0 }; \n" );

	if ( lgg ) {
		s = Q_stradd( s,
			"PARAM gradeLift = program.local[4]; \n"
			"PARAM gradeGamma = program.local[5]; \n"
			"PARAM gradeGain = program.local[6]; \n"
			"PARAM whitePoint0 = program.local[7]; \n"
			"PARAM whitePoint1 = program.local[8]; \n"
			"PARAM whitePoint2 = program.local[9]; \n"
			"TEMP gradeColor; \n"
			"ADD base.xyz, base, gradeLift; \n"
			"MAX base.xyz, base, zeroGrade; \n"
			"POW base.x, base.x, gradeGamma.x; \n"
			"POW base.y, base.y, gradeGamma.y; \n"
			"POW base.z, base.z, gradeGamma.z; \n"
			"MUL base.xyz, base, gradeGain; \n"
			"DP3 gradeColor.x, base, whitePoint0; \n"
			"DP3 gradeColor.y, base, whitePoint1; \n"
			"DP3 gradeColor.z, base, whitePoint2; \n"
			"MAX base.xyz, gradeColor, zeroGrade; \n" );
	}

	if ( lut ) {
		s = Q_stradd( s,
			"PARAM lutControl = program.local[10]; \n"
			"PARAM lutExtra = program.local[11]; \n"
			"PARAM oneGrade = { 1.0, 1.0, 1.0, 1.0 }; \n"
			"TEMP lutCoord; \n"
			"TEMP lutSlice; \n"
			"TEMP lutUv0; \n"
			"TEMP lutUv1; \n"
			"TEMP lutLow; \n"
			"TEMP lutHigh; \n"
			"MUL lutCoord.xyz, base, lutExtra.z; \n"
			"MAX lutCoord.xyz, lutCoord, zeroGrade; \n"
			"MIN lutCoord.xyz, lutCoord, oneGrade; \n"
			"MUL lutCoord.xyz, lutCoord, lutControl.y; \n"
			"FLR lutSlice.x, lutCoord.z; \n"
			"FRC lutSlice.y, lutCoord.z; \n"
			"ADD lutSlice.z, lutSlice.x, oneGrade.x; \n"
			"MIN lutSlice.z, lutSlice.z, lutControl.y; \n"
			"MAD lutUv0.x, lutSlice.x, lutExtra.y, lutCoord.x; \n"
			"ADD lutUv0.x, lutUv0.x, lutExtra.x; \n"
			"MUL lutUv0.x, lutUv0.x, lutControl.w; \n"
			"ADD lutUv0.y, lutCoord.y, lutExtra.x; \n"
			"MUL lutUv0.y, lutUv0.y, lutControl.z; \n"
			"MAD lutUv1.x, lutSlice.z, lutExtra.y, lutCoord.x; \n"
			"ADD lutUv1.x, lutUv1.x, lutExtra.x; \n"
			"MUL lutUv1.x, lutUv1.x, lutControl.w; \n"
			"MOV lutUv1.y, lutUv0.y; \n"
			"TEX lutLow, lutUv0, texture[2], 2D; \n"
			"TEX lutHigh, lutUv1, texture[2], 2D; \n"
			"LRP base.xyz, lutSlice.y, lutHigh, lutLow; \n"
			"MUL base.xyz, base, lutControl.x; \n" );
	}

	return buf;
}

static char *ARB_BuildOutputEncodeProgram( char *buf ) {
	char *s = buf;

	s = Q_stradd( s,
		"PARAM outputTransfer = program.local[3]; \n"
		"PARAM srgbCutoff = { 0.0031308, 0.0031308, 0.0031308, 1.0 }; \n"
		"PARAM srgbGamma = { 0.4166667, 0.4166667, 0.4166667, 1.0 }; \n"
		"PARAM srgbScaleLow = { 12.92, 12.92, 12.92, 1.0 }; \n"
		"PARAM srgbScaleHigh = { 1.055, 1.055, 1.055, 1.0 }; \n"
		"PARAM srgbOffset = { 0.055, 0.055, 0.055, 0.0 }; \n"
		"PARAM zero = { 0.0, 0.0, 0.0, 0.0 }; \n"
		"TEMP legacyOut; \n"
		"TEMP srgbHi; \n"
		"TEMP srgbLo; \n"
		"TEMP srgbMask; \n"
		"MAX base.xyz, base, zero; \n"
		"MOV legacyOut, base; \n"
		"POW legacyOut.x, legacyOut.x, gamma.x; \n"
		"POW legacyOut.y, legacyOut.y, gamma.y; \n"
		"POW legacyOut.z, legacyOut.z, gamma.z; \n"
		"MUL legacyOut.xyz, legacyOut, gamma.w; \n"
		"POW srgbHi.x, base.x, srgbGamma.x; \n"
		"POW srgbHi.y, base.y, srgbGamma.y; \n"
		"POW srgbHi.z, base.z, srgbGamma.z; \n"
		"MAD srgbHi.xyz, srgbHi, srgbScaleHigh, -srgbOffset; \n"
		"MUL srgbLo.xyz, base, srgbScaleLow; \n"
		"SLT srgbMask.xyz, base, srgbCutoff; \n"
		"LRP srgbHi.xyz, srgbMask, srgbLo, srgbHi; \n"
		"LRP base.xyz, outputTransfer.x, srgbHi, legacyOut; \n" );

	return buf;
}


static const char *gammaFP = {
	"!!ARBfp1.0 \n"
	"OPTION ARB_precision_hint_fastest; \n"
	"PARAM gamma = program.local[0]; \n"
	"PARAM exposure = program.local[2]; \n"
	"TEMP base; \n"
	"TEX base, fragment.texcoord[0], texture[0], 2D; \n"
	"MUL base.xyz, base, exposure.x; \n"
	"%s" // scene-linear color grading, if requested
	"%s" // tone scale, if scene-linear mode requested it
	"%s" // legacy gamma or SDR sRGB output transfer
	"%s" // for greyscale shader if needed
	"MOV base.w, 1.0; \n"
	"MOV_SAT result.color, base; \n"
	"END \n"
};

static char *ARB_BuildBloomProgram( char *buf ) {
	char *s = buf;

	s = Q_stradd( s,
		"!!ARBfp1.0 \n"
		"OPTION ARB_precision_hint_fastest; \n"
		"PARAM thres = program.local[0]; \n"
		"PARAM exposure = program.local[1]; \n"
		"PARAM knee = program.local[2]; \n"
		"TEMP base; \n"
		"TEMP intensity; \n"
		"TEX base, fragment.texcoord[0], texture[0], 2D; \n"
		"MUL base.xyz, base, exposure.x; \n" );

	if ( r_bloom_threshold_mode->integer == 0 ) {
		// max(r, g, b)
		s = Q_stradd( s,
			"MAX intensity.x, base.x, base.y; \n"
			"MAX intensity.x, intensity.x, base.z; \n" );
	} else if ( r_bloom_threshold_mode->integer == 1 ) {
		// (r+g+b)/3
		s = Q_stradd( s,
			"PARAM scale = { 0.3333, 0.3334, 0.3333, 1.0 }; \n"
			"DP3 intensity.x, base, scale; \n" );
	} else {
		// luma(r,g,b)
		s = Q_stradd( s,
			"PARAM luma = { 0.2126, 0.7152, 0.0722, 1.0 }; \n"
			"DP3 intensity.x, base, luma; \n" );
	}

	if ( r_bloom_soft_knee && r_bloom_soft_knee->value > 0.0f ) {
		s = Q_stradd( s,
			"PARAM smooth = { -2.0, 3.0, 0.0, 1.0 }; \n"
			"TEMP weight; \n"
			"TEMP weight2; \n"
			"TEMP smoothTerm; \n"
			"ADD weight.x, intensity.x, -knee.x; \n"
			"MUL_SAT weight.x, weight.x, knee.y; \n"
			"MUL weight2.x, weight.x, weight.x; \n"
			"MAD smoothTerm.x, smooth.x, weight.x, smooth.y; \n"
			"MUL weight.x, weight2.x, smoothTerm.x; \n"
			"MUL base.rgb, base, weight.x; \n" );
	} else {
		s = Q_stradd( s,
			"SGE intensity.w, intensity.x, thres.x; \n"
			"MUL base.rgb, base, intensity.w; \n" );
	}

	// modulation
	if ( r_bloom_modulate->integer ) {
		if ( r_bloom_modulate->integer == 1 ) {
			// by itself
			s = Q_stradd( s, "MUL base, base, base; \n" );
		} else {
			// by intensity
			if ( r_bloom_threshold_mode->integer != 2 ) {
				s = Q_stradd( s,
					"PARAM modLuma = { 0.2126, 0.7152, 0.0722, 1.0 }; \n"
					"DP3 intensity.x, base, modLuma; \n" );
			}
			s = Q_stradd( s, "MUL base, base, intensity.x; \n" );
		}
	}

	/*s = */ Q_stradd( s,
		"MOV base.w, 1.0; \n"
		"MOV result.color, base; \n"
		"END \n" );

	return buf;
}


// Gaussian blur shader
static char *ARB_BuildBlurProgram( char *buf, int taps ) {
	int i;
	char *s = buf;

	*s = '\0';

	s = Q_stradd( s,
		"!!ARBfp1.0 \n"
		"OPTION ARB_precision_hint_fastest; \n"
		"ATTRIB tc = fragment.texcoord[0]; \n" );

	for ( i = 0; i < taps; i++ ) {
		s = Q_stradd( s, va( "PARAM p%i = program.local[%i]; \n", i, i ) ); // tex_offset_x, tex_offset_y, 0.0, weight
	}

	s = Q_stradd( s, "TEMP cc; \n"
		"MOV cc, {0.0, 0.0, 0.0, 1.0};\n" ); // initialize final color

	for ( i = 0; i < taps; i++ ) {
		s = Q_stradd( s, va( "TEMP c%i, tc%i; \n", i, i ) );
	}

	for ( i = 0; i < taps; i++ ) {
		s = Q_stradd( s, va( "ADD tc%i.xy, tc, p%i; \n", i, i ) );
	}

	for ( i = 0; i < taps; i++ ) {
		s = Q_stradd( s, va( "TEX c%i, tc%i, texture[0], 2D; \n", i, i ) );
		s = Q_stradd( s, va( "MAD cc, c%i, p%i.w, cc; \n", i, i ) ); // cc = cc + cN + pN.w
	}

	/*s = */ Q_stradd( s,
		"MOV cc.a, 1.0; \n"
		"MOV_SAT result.color, cc; \n"
		"END \n" );

	return buf;
}


static char *ARB_BuildBlendProgram( char *buf, int count ) {
	int i;
	char *s = buf;

	*s = '\0';
	s = Q_stradd( s, 
		"!!ARBfp1.0 \n"
		"OPTION ARB_precision_hint_fastest; \n"
		"ATTRIB tc = fragment.texcoord[0]; \n"
		"TEMP cx, cc;\n"
		"MOV cc, {0.0, 0.0, 0.0, 1.0}; \n" );

	for ( i = 0; i < count; i++ ) {
		s = Q_stradd( s, va( "TEX cx, fragment.texcoord[0], texture[%i], 2D; \n"
			"ADD cc, cx, cc; \n", i ) );
	}

	/*s = */ Q_stradd( s,
		"MOV cc.a, 1.0; \n"
		"MOV_SAT result.color, cc; \n"
		"END \n" );

	return buf;
}


// blend 2 texture together
static const char *blend2FP = {
	"!!ARBfp1.0 \n"
	"OPTION ARB_precision_hint_fastest; \n"
	"PARAM factor = program.local[1]; \n"
	"TEMP base; \n"
	"TEMP post; \n"
	"TEX base, fragment.texcoord[0], texture[0], 2D; \n"
	"TEX post, fragment.texcoord[0], texture[1], 2D; \n"
	"MAD base, post, factor.x, base; \n"
	//"ADD base, base, post; \n"
	"MOV base.w, 1.0; \n"
	"MOV_SAT result.color, base; \n"
	"END \n"
};

// combined blend + gamma correction pass
static const char *blend2gammaFP = {
	"!!ARBfp1.0 \n"
	"OPTION ARB_precision_hint_fastest; \n"
	"PARAM gamma = program.local[0]; \n"
	"PARAM factor = program.local[1]; \n"
	"PARAM exposure = program.local[2]; \n"
	"TEMP base; \n"
	"TEMP post; \n"
	"TEX base, fragment.texcoord[0], texture[0], 2D; \n"
	"TEX post, fragment.texcoord[0], texture[1], 2D; \n"
	//"ADD base, base, post; \n"
	"MAD base, post, factor.x, base; \n"
	"MUL base.xyz, base, exposure.x; \n"
	"%s" // scene-linear color grading, if requested
	"%s" // tone scale, if scene-linear mode requested it
	"%s" // legacy gamma or SDR sRGB output transfer
	"%s" // for greyscale shader if needed
	"MOV base.w, 1.0; \n"
	"MOV_SAT result.color, base; \n"
	"END \n" 
};


static void RenderQuad( int w, int h )
{
	static const vec2_t t[4] = { {0.0, 1.0}, {1.0, 1.0}, {0.0, 0.0}, {1.0, 0.0} };
	static vec3_t v[4] = { { 0 } };
	qboolean glxStreamedDraw = qfalse;
	
	v[1][0] = w;
	v[2][1] = h;
	v[3][0] = w;
	v[3][1] = h;

	GL_ClientState( 0, CLS_TEXCOORD_ARRAY );
#ifdef RENDERER_GLX
	GLX_CompatRecordFullscreenPass();
#endif

	qglVertexPointer( 3, GL_FLOAT, 0, v );
	qglTexCoordPointer( 2, GL_FLOAT, 0, t );

	if ( GLX_CompatStreamDrawPostProcessEnabled() ) {
		glxStreamedDraw = GLX_CompatTryStreamDrawArrayTexcoordPass( 4, v,
			(int)sizeof( v[0] ), t, 0, GL_TRIANGLE_STRIP, GLX_STAGE_POSTPROCESS_PASS,
			GLX_DYNAMIC_CATEGORY_MASK_SPECIAL );
	}
	if ( !glxStreamedDraw ) {
#ifdef RENDERER_GLX
		GLX_CompatDrawArrays( GL_TRIANGLE_STRIP, 0, 4,
			GLX_LEGACY_DELEGATION_DRAW_ARRAY, GLX_DRAW_NONE );
#else
		qglDrawArrays( GL_TRIANGLE_STRIP, 0, 4 );
#endif
	}
}


static void ARB_BlurParams( int width, int height, int ksize, qboolean horizontal )
{
	static float weight[ MAX_FILTER_SIZE ];
	static int old_ksize = -1;

	static const float x_k[ MAX_FILTER_SIZE+1 ][ MAX_FILTER_SIZE + 1 ] = {
		// [1/weight], coeff.1, coeff.2, [...]
		{ 0 },
		{ 1.0/1, 1 },
		{ 1.0/2, 1, 1 },
	//	{ 1/4,   1, 2, 1 },
		{ 1.0/16,  5, 6, 5 },
		{ 1.0/8,   1, 3, 3, 1 },
		{ 1.0/16,  1, 4, 6, 4, 1 },
		{ 1.0/32,  1, 5, 10, 10, 5, 1 },
		{ 1.0/64,  1, 6, 15, 20, 15, 6, 1 },
		{ 1.0/128, 1, 7, 21, 35, 35, 21, 7, 1 },
		{ 1.0/256, 1, 8, 28, 56, 70, 56, 28, 8, 1 },
		{ 1.0/512, 1, 9, 36, 84, 126, 126, 84, 36, 9, 1 },
		{ 1.0/1024, 1, 10, 45, 120, 210, 252, 210, 120, 45, 10, 1 },
		{ 1.0/2048, 1, 11, 55, 165, 330, 462, 462, 330, 165, 55, 11, 1 },
		{ 1.0/4096, 1, 12, 66, 220, 495, 792, 924, 792, 495, 220, 66, 12, 1 },
		{ 1.0/8192, 1, 13, 78, 286, 715, 1287, 1716, 1716, 1287, 715, 286, 78, 13, 1 },
		{ 1.0/16384, 1, 14, 91, 364, 1001, 2002, 3003, 3432, 3003, 2002, 1001, 364, 91, 14, 1 },
		{ 1.0/32768, 1, 15, 105, 455, 1365, 3003, 5005, 6435, 6435, 5005, 3003, 1365, 455, 105, 15, 1 },
		{ 1.0/65536, 1, 16, 120, 560, 1820, 4368, 8008, 11440, 12870, 11440, 8008, 4368, 1820, 560, 120, 16, 1 },
		{ 1.0/131072, 1, 17, 136, 680, 2380, 6188, 12376, 19448, 24310, 24310, 19448, 12376, 6188, 2380, 680, 136, 17, 1 },
		{ 1.0/262144, 1, 18, 153, 816, 3060, 8568, 18564, 31824, 43758, 48620, 43758, 31824, 18564, 8568, 3060, 816, 153, 18, 1 },
		{ 1.0/524288, 1, 19, 171, 969, 3876, 11628, 27132, 50388, 75582, 92378, 92378, 75582, 50388, 27132, 11628, 3876, 969, 171, 19, 1 },

	};

	static const float x_o[ MAX_FILTER_SIZE+1 ][ MAX_FILTER_SIZE ] = {
		{ 0 },
		{ 0.0 },
		{ -0.5, 0.5 },
	//	{ -1.0, 0.0, 1.0 },
		{ -1.2f, 0.0, 1.2f },
		{ -1.5, -0.5, 0.5, 1.5 },
		{ -2.0, -1.0, 0.0, 1.0, 2.0 },
		{ -2.5, -1.5, -0.5, 0.5, 1.5, 2.5 },
		{ -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0 },
		{ -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5 },
		{ -4.0, -3.0, -2.0, -1.0, 0.0, 1.0,	2.0, 3.0, 4.0 },
		{ -4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5 },
		{ -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0 },
		{ -5.5, -4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5 },
		{ -6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0 },
		{ -6.5, -5.5, -4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5 },
		{ -7.0, -6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0 },
		{ -7.5, -6.5, -5.5, -4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5 },
		{ -8.0, -7.0, -6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0 },
		{ -8.5, -7.5, -6.5, -5.5, -4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5 },
		{ -9.0, -8.0, -7.0, -6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0 },
		{ -9.5, -8.5, -7.5, -6.5, -5.5, -4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5 },
	};

	const float *coeffs = x_k[ ksize ] + 1;
	const float *off = x_o[ ksize ];

	int i;
	float rsum;
	float texel_size_x;
	float texel_size_y;
	float offset[ MAX_FILTER_SIZE ][ 2 ]; // xy

	// texel size
	texel_size_x = 1.0 / (float) width;
	texel_size_y = 1.0 / (float) height;
	rsum = x_k[ ksize ][ 0 ];

	if ( old_ksize != ksize ) {
		old_ksize = ksize;
		for ( i = 0; i < ksize; i++ ) {
			weight[i] = coeffs[i] * rsum;
		}
	}

	// calculate texture offsets for lookup
	for ( i = 0; i < ksize; i++ ) {
		offset[i][0] = texel_size_x * off[i];
		offset[i][1] = texel_size_y * off[i];
	}

	if ( horizontal ) {
		// horizontal pass
		for (  i = 0; i < ksize; i++ )
			qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, i, offset[i][0], 0.0, 0.0, weight[i] );
	} else {
		// vertical pass
		for (  i = 0; i < ksize; i++ )
			qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, i, 0.0, offset[i][1], 0.0, weight[i] );
	}
}
#endif // USE_FBO


static void ARB_DeletePrograms( void )
{
	qglDeleteProgramsARB( ARRAY_LEN( programs ) - PROGRAM_BASE, programs + PROGRAM_BASE );
	Com_Memset( programs, 0, sizeof( programs ) );
	programCompiled = 0;
}


qboolean ARB_CompileProgram( programType ptype, const char *text, GLuint program )
{
	GLint errorPos;
	unsigned int errCode;
	int kind;

	if ( ptype == Fragment )
		kind = GL_FRAGMENT_PROGRAM_ARB;
	else
		kind = GL_VERTEX_PROGRAM_ARB;

	qglBindProgramARB( kind, program );
	qglProgramStringARB( kind, GL_PROGRAM_FORMAT_ASCII_ARB, strlen( text ), text );
	qglGetIntegerv( GL_PROGRAM_ERROR_POSITION_ARB, &errorPos );
	if ( (errCode = qglGetError()) != GL_NO_ERROR || errorPos != -1 )
	{
		// we may receive error with active FBO but compiled programs will continue to work properly
		if ( (errCode == GL_INVALID_OPERATION && !fboEnabled) || errorPos != -1 )
		{
			ri.Printf( PRINT_ALL, S_COLOR_YELLOW "%s Compile Error(%i,%i): %s\n" S_COLOR_CYAN "%s\n", (ptype == Fragment) ? "FP" : "VP",
				errCode, errorPos, qglGetString( GL_PROGRAM_ERROR_STRING_ARB ), text );
			qglBindProgramARB( kind, 0 );
			ARB_DeletePrograms();
			return qfalse;
		}
	}

	return qtrue;
}


qboolean ARB_UpdatePrograms( void )
{
#ifdef USE_PMLIGHT
	const char *program;
	int i;
#endif
#if defined (USE_FBO) || defined (USE_PMLIGHT)
	char buf[8192];
#endif
#ifdef USE_FBO
	char buf2[8192];
	char buf3[8192];
	char buf4[8192];
#endif

	if ( !qglGenProgramsARB )
		return qfalse;

	if ( programCompiled ) // delete old programs
	{
		ARB_ProgramDisable();
		ARB_DeletePrograms();
	}

	qglGenProgramsARB( ARRAY_LEN( programs ) - PROGRAM_BASE, programs + PROGRAM_BASE );

#ifdef USE_PMLIGHT
	if ( !ARB_CompileProgram( Vertex, va( dlightVP, "" ), programs[ DLIGHT_VERTEX ] ) )
		return qfalse;
	if ( !ARB_CompileProgram( Vertex, va( dlightVP, fogInVPCode ), programs[ DLIGHT_VERTEX_FOG_IN ] ) )
		return qfalse;
	if ( !ARB_CompileProgram( Vertex, va( dlightVP, fogOutVPCode ), programs[ DLIGHT_VERTEX_FOG_OUT ] ) )
		return qfalse;

	for ( i = DLIGHT_FRAGMENT; i <= DLIGHT_LINEAR_ABS_FRAGMENT_FOG; i++ ) {
		program = ARB_BuildDlightFP( buf, i );
		if ( !ARB_CompileProgram( Fragment, program, programs[ i ] ) ) {
			return qfalse;
		}
	}
#endif // USE_PMLIGHT

	if ( !ARB_CompileProgram( Vertex, dummyVP, programs[ DUMMY_VERTEX ] ) )
		return qfalse;

	if ( !ARB_CompileProgram( Fragment, spriteFP, programs[ SPRITE_FRAGMENT ] ) )
		return qfalse;

	if ( !ARB_CompileProgram( Fragment, depthFadeFP, programs[ DEPTH_FADE_FRAGMENT ] ) )
		return qfalse;

#ifdef USE_FBO
	if ( !ARB_CompileProgram( Fragment, va( gammaFP,
			ARB_BuildColorGradeProgram( buf ), ARB_BuildToneMapProgram( buf2 ),
			ARB_BuildOutputEncodeProgram( buf3 ), ARB_BuildGreyscaleProgram( buf4 ) ),
			programs[ GAMMA_FRAGMENT ] ) )
		return qfalse;

	if ( !ARB_CompileProgram( Fragment, ARB_BuildBloomProgram( buf ), programs[ BLOOM_EXTRACT_FRAGMENT ] ) )
		return qfalse;
	
	// only 1, 2, 3, 6, 8, 10, 12, 14, 16, 18 and 20 produces real visual difference
	fboBloomFilterSize = r_bloom_filter_size->integer;
	if ( !ARB_CompileProgram( Fragment, ARB_BuildBlurProgram( buf, fboBloomFilterSize ), programs[ BLUR_FRAGMENT ] ) )
		return qfalse;

	if ( !ARB_CompileProgram( Fragment, ARB_BuildBlurProgram( buf, 6 ), programs[ BLUR2_FRAGMENT ] ) )
		return qfalse;

	fboBloomBlendBase = r_bloom_blend_base->integer;
	if ( fboBloomBlendBase < 0 )
		fboBloomBlendBase = 0;
	if ( fboBloomBlendBase >= r_bloom_passes->integer )
		fboBloomBlendBase = r_bloom_passes->integer - 1;
	if ( !ARB_CompileProgram( Fragment, ARB_BuildBlendProgram( buf, r_bloom_passes->integer - fboBloomBlendBase ), programs[ BLENDX_FRAGMENT ] ) )
		return qfalse;

	if ( !ARB_CompileProgram( Fragment, blend2FP, programs[ BLEND2_FRAGMENT ] ) )
		return qfalse;

	if ( !ARB_CompileProgram( Fragment, va( blend2gammaFP,
			ARB_BuildColorGradeProgram( buf ), ARB_BuildToneMapProgram( buf2 ),
			ARB_BuildOutputEncodeProgram( buf3 ), ARB_BuildGreyscaleProgram( buf4 ) ),
			programs[ BLEND2_GAMMA_FRAGMENT ] ) )
		return qfalse;
#endif // USE_FBO

	programCompiled = 1;

	return qtrue;
}

#ifdef USE_FBO

static void FBO_Bind( GLuint target, GLuint buffer );
static qboolean FBO_Create( frameBuffer_t *fb, GLsizei width, GLsizei height,
	qboolean depthStencil, GLint *outFormat, GLint *outType );

void FBO_Clean( frameBuffer_t *fb )
{
	if ( fb->fbo )
	{
		FBO_Bind( GL_FRAMEBUFFER, fb->fbo );
		if ( fb->multiSampled )
		{
			qglBindRenderbuffer( GL_RENDERBUFFER, 0 );
			if ( fb->color )
			{
				qglDeleteRenderbuffers( 1, &fb->color );
				fb->color = 0;
			}
			if ( fb->depthStencil )
			{
				qglDeleteRenderbuffers( 1, &fb->depthStencil );
				fb->depthStencil = 0;
			}
		}
		else
		{
			GL_BindTexture( 0, 0 );
			if ( fb->color )
			{
				qglFramebufferTexture2D( GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, 0, 0 );
				qglDeleteTextures( 1, &fb->color );
				fb->color = 0;
			}
			if ( fb->depthStencil )
			{
#ifdef DEPTH_RENDER_BUFFER
				if ( fb->depthStencil && fb->depthStencil != commonDepthStencil )
				{
					qglDeleteRenderbuffers( 1, &fb->depthStencil );
					fb->depthStencil = 0;
				}
#else
				if ( glConfig.stencilBits == 0 )
					qglFramebufferTexture2D( GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, 0, 0 );
				else
					qglFramebufferTexture2D( GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_TEXTURE_2D, 0, 0 );

				if ( fb->depthStencil && fb->depthStencil != commonDepthStencil )
				{
					qglDeleteTextures( 1, &fb->depthStencil );
					fb->depthStencil = 0;
				}
#endif
			}
		}
		FBO_Bind( GL_FRAMEBUFFER, 0 );
		qglDeleteFramebuffers( 1, &fb->fbo );
		fb->fbo = 0;
	}
	Com_Memset( fb, 0, sizeof( *fb ) );
}


static void FBO_CleanBloom( void )
{
	int i;
	for ( i = 0; i < MAX_BLUR_PASSES; i++ )
	{
		FBO_Clean( &frameBuffers[ i * 2 + BLOOM_BASE + 0 ] );
		FBO_Clean( &frameBuffers[ i * 2 + BLOOM_BASE + 1 ] );
	}
}


static void FBO_CleanDepth( void )
{
	if ( depthFadeTexture )
	{
		GL_BindTexture( 1, 0 );
		qglDeleteTextures( 1, &depthFadeTexture );
		depthFadeTexture = 0;
		depthFadeCopied = qfalse;
	}

#ifdef COMMON_DEPTH_STENCIL
	if ( commonDepthStencil )
	{
#ifdef DEPTH_RENDER_BUFFER
		qglDeleteRenderbuffers( 1, &commonDepthStencil );
#else
		GL_BindTexture( 0, 0 );
		qglDeleteTextures( 1, &commonDepthStencil );
#endif
		commonDepthStencil = 0;
	}
#endif
}


static GLuint FBO_CreateDepthFadeTexture( GLsizei width, GLsizei height )
{
	GLuint tex;

	qglGenTextures( 1, &tex );
	GL_BindTexture( 1, tex );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE );
	qglTexImage2D( GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT32, width, height, 0, GL_DEPTH_COMPONENT, GL_FLOAT, NULL );

	return tex;
}


static GLuint FBO_CreateDepthTextureOrBuffer( GLsizei width, GLsizei height )
{
#ifdef DEPTH_RENDER_BUFFER
	GLuint buffer;
	qglGenRenderbuffers( 1, &buffer );
	qglBindRenderbuffer( GL_RENDERBUFFER, buffer );
	if ( glConfig.stencilBits == 0 )
		qglRenderbufferStorage( GL_RENDERBUFFER, GL_DEPTH_COMPONENT32, width, height );
	else
		qglRenderbufferStorage( GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, width, height );
	return buffer;
#else
	GLuint tex;
	qglGenTextures( 1, &tex );
	GL_BindTexture( 0, tex );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST );
	if ( glConfig.stencilBits == 0 )
		qglTexImage2D( GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT32, width, height, 0, GL_DEPTH_COMPONENT, GL_FLOAT, NULL );
	else
		qglTexImage2D( GL_TEXTURE_2D, 0, GL_DEPTH24_STENCIL8, width, height, 0, GL_DEPTH_STENCIL, GL_UNSIGNED_INT_24_8, NULL );
	return tex;
#endif
}


static const char *glDefToStr( GLint define )
{
	#define CASE_STR(x) case (x): return #x
	static int index;
	static char buf[8][32];
	char *s;

	switch ( define )
	{
		// texture formats
		CASE_STR(GL_BGR);
		CASE_STR(GL_BGRA);
		CASE_STR(GL_RG);
		CASE_STR(GL_RGB);
		CASE_STR(GL_RGBA);
		CASE_STR(GL_RGBA4);
		CASE_STR(GL_RGBA8);
		CASE_STR(GL_RGBA12);
		CASE_STR(GL_RGBA16);
		CASE_STR(GL_RG16F);
		CASE_STR(GL_RGBA16F);
		CASE_STR(GL_RGB16F);
		CASE_STR(GL_RGB10_A2);
		CASE_STR(GL_R11F_G11F_B10F);
		CASE_STR(GL_SRGB);
		CASE_STR(GL_SRGB8);
		CASE_STR(GL_SRGB_ALPHA);
		CASE_STR(GL_SRGB8_ALPHA8);
		// data types
		CASE_STR(GL_BYTE);
		CASE_STR(GL_UNSIGNED_BYTE);
		CASE_STR(GL_SHORT);
		CASE_STR(GL_UNSIGNED_SHORT);
		CASE_STR(GL_INT);
		CASE_STR(GL_UNSIGNED_INT);
		CASE_STR(GL_FLOAT);
		CASE_STR(GL_HALF_FLOAT);
		CASE_STR(GL_DOUBLE);
		CASE_STR(GL_UNSIGNED_SHORT_4_4_4_4);
		CASE_STR(GL_UNSIGNED_INT_8_8_8_8);
		CASE_STR(GL_UNSIGNED_INT_10_10_10_2);
		CASE_STR(GL_UNSIGNED_SHORT_4_4_4_4_REV);
		CASE_STR(GL_UNSIGNED_INT_8_8_8_8_REV);
		CASE_STR(GL_UNSIGNED_INT_2_10_10_10_REV);
		CASE_STR(GL_UNSIGNED_NORMALIZED);
		// error codes
		CASE_STR(GL_NO_ERROR);
		CASE_STR(GL_INVALID_ENUM);
		CASE_STR(GL_INVALID_VALUE);
		CASE_STR(GL_INVALID_OPERATION);
		CASE_STR(GL_STACK_OVERFLOW);
		CASE_STR(GL_STACK_UNDERFLOW);
		CASE_STR(GL_OUT_OF_MEMORY);
		// fbo error codes
		CASE_STR(GL_FRAMEBUFFER_COMPLETE);
		CASE_STR(GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT);
		CASE_STR(GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT);
		CASE_STR(GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER);
		CASE_STR(GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER);
		CASE_STR(GL_FRAMEBUFFER_UNSUPPORTED);
	}
	s = buf[ index ]; // to handle multiple invocations as function parameters
	sprintf( s, "0x%04x", define );
	index = ( index + 1 ) & 7;
	return s;
}


static void getPreferredFormatAndType( GLint format, GLint *pFormat, GLint *pType )
{
	GLint preferredFormat;
	GLint preferredType;

	if ( format == GL_RGBA16F ) {
		*pFormat = GL_RGBA;
		*pType = GL_HALF_FLOAT;
		return;
	}
	if ( format == GL_RG16F ) {
		*pFormat = GL_RG;
		*pType = GL_HALF_FLOAT;
		return;
	}
	if ( format == GL_RGB16F || format == GL_R11F_G11F_B10F ) {
		*pFormat = GL_RGB;
		*pType = GL_HALF_FLOAT;
		return;
	}

	if ( qglGetInternalformativ && gl_version >= 43 ) {
		qglGetInternalformativ( GL_TEXTURE_2D, /*GL_RGBA8*/ format, GL_TEXTURE_IMAGE_FORMAT, 1, &preferredFormat );
		if ( qglGetError() != GL_NO_ERROR ) {
			goto __fallback;
		}
		qglGetInternalformativ( GL_TEXTURE_2D, /*GL_RGBA8*/ format, GL_TEXTURE_IMAGE_TYPE, 1, &preferredType );
		if ( qglGetError() != GL_NO_ERROR ) {
			goto __fallback;
		}
		if ( preferredFormat == 0 ) // nVidia ION drivers can do that
			preferredFormat = GL_RGBA;
		if ( preferredType == GL_UNSIGNED_NORMALIZED ) { // Intel HD 530 drivers can do that as well
			if ( format == GL_RGBA16F || format == GL_RGB16F ||
				format == GL_R11F_G11F_B10F || format == GL_RG16F )
				preferredType = GL_HALF_FLOAT;
			else if ( format == GL_RGBA12 || format == GL_RGBA16 )
				preferredType = GL_UNSIGNED_SHORT;
			else
				preferredType = GL_UNSIGNED_BYTE;
		}
	} else {
__fallback:
		if ( format == GL_RGBA16F ) {
			preferredFormat = GL_RGBA;
			preferredType = GL_HALF_FLOAT;
		} else if ( format == GL_RG16F ) {
			preferredFormat = GL_RG;
			preferredType = GL_HALF_FLOAT;
		} else if ( format == GL_RGB16F || format == GL_R11F_G11F_B10F ) {
			preferredFormat = GL_RGB;
			preferredType = GL_HALF_FLOAT;
		} else if ( format == GL_RGBA12 || format == GL_RGBA16 ) {
			preferredFormat = GL_RGBA;
			preferredType = GL_UNSIGNED_SHORT;
		} else {
			preferredFormat = GL_RGBA;
			preferredType = GL_UNSIGNED_BYTE;
		}
	}

	*pFormat = preferredFormat;
	*pType = preferredType;
}


static qboolean FBO_CreateWithFormat( frameBuffer_t *fb, GLsizei width, GLsizei height,
	qboolean depthStencil, GLint internalFormat, GLint *outFormat, GLint *outType )
{
	int fboStatus;
	GLint textureFormat;
	GLint textureType;

	fb->multiSampled = qfalse;
	fb->depthStencil = 0;
	fb->internalFormat = internalFormat;

	// color texture
	qglGenTextures( 1, &fb->color );
	GL_BindTexture( 0, fb->color );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR );

	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, gl_clamp_mode );
	qglTexParameteri( GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, gl_clamp_mode );

	getPreferredFormatAndType( internalFormat, &textureFormat, &textureType );

	qglTexImage2D( GL_TEXTURE_2D, 0, internalFormat, width, height, 0, textureFormat, textureType, NULL );
	// TODO: handle GL_INVALID_OPERATION in case of unsupported internalFormat/textureFormat
	
	if ( outFormat )
		*outFormat = textureFormat;
	if ( outType )
		*outType = textureType;

	qglGenFramebuffers( 1, &fb->fbo );
	FBO_Bind( GL_FRAMEBUFFER, fb->fbo );
	
	qglFramebufferTexture2D( GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fb->color, 0 );

	if ( depthStencil )
	{
#ifdef COMMON_DEPTH_STENCIL
		if ( !commonDepthStencil )
			commonDepthStencil = FBO_CreateDepthTextureOrBuffer( width, height );

		fb->depthStencil = commonDepthStencil;
#else
		fb->depthStencil = FBO_CreateDepthTextureOrBuffer( width, height );
#endif
#ifdef DEPTH_RENDER_BUFFER
		if ( glConfig.stencilBits == 0 )
			qglFramebufferRenderbuffer( GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, fb->depthStencil );
		else
			qglFramebufferRenderbuffer( GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, fb->depthStencil );
#else
		if ( glConfig.stencilBits == 0 )
			qglFramebufferTexture2D( GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, fb->depthStencil, 0 );
		else
			qglFramebufferTexture2D( GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_TEXTURE_2D, fb->depthStencil, 0 );
#endif
	}

	GL_BindTexture( 0, 0 );

	fboStatus = qglCheckFramebufferStatus( GL_FRAMEBUFFER );
	if ( fboStatus != GL_FRAMEBUFFER_COMPLETE )
	{
		ri.Printf( PRINT_ALL, "Failed to create %s (%s:%s) FBO (status %s, error %s)\n",
			glDefToStr( internalFormat ), glDefToStr( textureFormat ), glDefToStr( textureType ),
			glDefToStr( fboStatus ), glDefToStr( (int)qglGetError() ) );
		FBO_Clean( fb );
		return qfalse;
	}

	fb->width = width;
	fb->height = height;
	fb->internalFormat = internalFormat;

	qglClearColor( 0.0, 0.0, 0.0, 1.0 );
	if ( depthStencil )
		qglClear( GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT );
	else
		qglClear( GL_COLOR_BUFFER_BIT );
#ifdef RENDERER_GLX
	GLX_CompatRecordPostClear();
#endif

	FBO_Bind( GL_FRAMEBUFFER, 0 );

	return qtrue;
}


static qboolean FBO_CreateMS( frameBuffer_t *fb, int width, int height )
{
	GLsizei nSamples = r_ext_multisample->integer;
	int fboStatus;
	
	fb->multiSampled = qtrue;

	if ( nSamples <= 0 || !qglRenderbufferStorageMultisample )
	{
		return qfalse;
	}
	nSamples = PAD( nSamples, 2 );

	qglGenFramebuffers( 1, &fb->fbo );
	FBO_Bind( GL_FRAMEBUFFER, fb->fbo );

	qglGenRenderbuffers( 1, &fb->color );
	qglBindRenderbuffer( GL_RENDERBUFFER, fb->color );
	while ( nSamples > 0 ) {
		qglRenderbufferStorageMultisample( GL_RENDERBUFFER, nSamples, fboInternalFormat, width, height );
		if ( (int)qglGetError() == GL_INVALID_VALUE/* != GL_NO_ERROR */ ) {
			ri.Printf( PRINT_ALL, "...%ix MSAA is not available\n", nSamples );
			nSamples -= 2;
		} else {
			ri.Printf( PRINT_ALL, "...using %ix MSAA\n", nSamples );
			break;
		}
	}

	if ( nSamples <= 0 )
	{
		FBO_Clean( fb );
		return qfalse;
	}
	qglFramebufferRenderbuffer( GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, fb->color );

	qglGenRenderbuffers( 1, &fb->depthStencil );
	qglBindRenderbuffer( GL_RENDERBUFFER, fb->depthStencil );
	if ( glConfig.stencilBits == 0 )
		qglRenderbufferStorageMultisample( GL_RENDERBUFFER, nSamples, GL_DEPTH_COMPONENT32, width, height );
	else
		qglRenderbufferStorageMultisample( GL_RENDERBUFFER, nSamples, GL_DEPTH24_STENCIL8, width, height );

	if ( (int)qglGetError() != GL_NO_ERROR )
	{
		FBO_Clean( fb );
		return qfalse;
	}

	if ( glConfig.stencilBits == 0 )
		qglFramebufferRenderbuffer( GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, fb->depthStencil );
	else
		qglFramebufferRenderbuffer( GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, fb->depthStencil );

	fboStatus = qglCheckFramebufferStatus( GL_FRAMEBUFFER );
	if ( fboStatus != GL_FRAMEBUFFER_COMPLETE )
	{
		ri.Printf( PRINT_WARNING, "Failed to create MS FBO (status %s, error %s)\n", glDefToStr( fboStatus ), glDefToStr( (int)qglGetError() ) );
		FBO_Clean( fb );
		return qfalse;
	}

	fb->width = width;
	fb->height = height;

	qglClearColor( 0.0, 0.0, 0.0, 1.0 );
	qglClear( GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT );
#ifdef RENDERER_GLX
	GLX_CompatRecordPostClear();
#endif

	FBO_Bind( GL_FRAMEBUFFER, 0 );

	return qtrue;
}


static qboolean FBO_CreateBloom( void )
{
	int width = glConfig.vidWidth;
	int height = glConfig.vidHeight;
	int i;

	fboBloomPasses = 0;
	fboBloomInternalFormat = 0;
	fboBloomTextureFormat = 0;
	fboBloomTextureType = 0;
	fboBloomFormatMode = FBO_HdrBloomFormatMode();

	if ( FBO_HdrSceneLinearMode() && fboBloomFormatMode == GLX_HDR_BLOOM_FORMAT_RG16F )
	{
		ri.Printf( PRINT_WARNING,
			"...r_hdrBloomFormat %s is reserved for positive RG intermediates; RGB bloom will use the conservative fallback\n",
			FBO_HdrBloomFormatModeName( fboBloomFormatMode ) );
	}

	if ( glConfig.numTextureUnits < r_bloom_passes->integer )
	{
		ri.Printf( PRINT_WARNING, "...not enough texture units (%i) for %i-pass bloom\n",
			glConfig.numTextureUnits, r_bloom_passes->integer );
#ifdef RENDERER_GLX
		GLX_RecordBloomCreateState( GLX_BLOOM_CREATE_TEXTURE_UNITS );
#endif
		return qfalse;
	}

	for ( i = 0; i < r_bloom_passes->integer; i++ )
	{
		// we may need depth/stencil buffers for first bloom buffer in \r_bloom 2 mode
		if ( !FBO_Create( &frameBuffers[ i*2 + BLOOM_BASE + 0 ], width, height, i == 0 ? qtrue : qfalse, NULL, NULL ) ||
			!FBO_Create( &frameBuffers[ i*2 + BLOOM_BASE + 1 ], width, height, qfalse, NULL, NULL ) ) {
			FBO_CleanBloom();
#ifdef RENDERER_GLX
			GLX_RecordBloomCreateState( GLX_BLOOM_CREATE_FBO );
#endif
			return qfalse;
		}
		width = width / 2;
		height = height / 2;
		fboBloomPasses++;
		if ( width < 2 || height < 2 )
			break;
	}

	ri.Printf( PRINT_ALL, "...%i bloom passes\n", fboBloomPasses );
	if ( fboBloomInternalFormat )
	{
		ri.Printf( PRINT_ALL, "...bloom intermediate policy %s, format %s (%s:%s)\n",
			FBO_HdrBloomFormatModeName( fboBloomFormatMode ),
			glDefToStr( fboBloomInternalFormat ),
			glDefToStr( fboBloomTextureFormat ),
			glDefToStr( fboBloomTextureType ) );
	}
#ifdef RENDERER_GLX
	GLX_RecordBloomCreateState( GLX_BLOOM_CREATE_SUCCESS );
#endif

	return qtrue;
}


static qboolean FBO_Create( frameBuffer_t *fb, GLsizei width, GLsizei height,
	qboolean depthStencil, GLint *outFormat, GLint *outType )
{
	GLint formats[4];
	int formatCount;
	int i;

	FBO_FormatCandidatesForBuffer( fb, formats, &formatCount );

	for ( i = 0; i < formatCount; i++ )
	{
		if ( FBO_CreateWithFormat( fb, width, height, depthStencil, formats[i], outFormat, outType ) )
		{
			if ( FBO_FrameBufferIsBloom( fb ) ) {
				fboBloomInternalFormat = fb->internalFormat;
				getPreferredFormatAndType( fboBloomInternalFormat,
					&fboBloomTextureFormat, &fboBloomTextureType );
				fboBloomFormatMode = FBO_HdrBloomFormatMode();
			}
			return qtrue;
		}
	}

	return qfalse;
}


GLuint FBO_ScreenTexture( void )
{
	return frameBuffers[ 2 ].color;
}

qboolean FBO_DepthFadeAvailable( void )
{
	return ( fboEnabled && depthFadeTexture && r_depthFade && r_depthFade->integer ) ? qtrue : qfalse;
}

qboolean FBO_DepthFadeReady( void )
{
	return ( FBO_DepthFadeAvailable() && depthFadeCopied ) ? qtrue : qfalse;
}

void FBO_ResetDepthFade( void )
{
	depthFadeCopied = qfalse;
}

void FBO_CopyDepthFade( void )
{
	if ( !FBO_DepthFadeAvailable() ) {
		return;
	}

	if ( frameBufferMultiSampling ) {
		FBO_BlitMS( qtrue );
	}

	FBO_Bind( GL_READ_FRAMEBUFFER, frameBuffers[ 0 ].fbo );
	GL_BindTexture( 1, depthFadeTexture );
	qglCopyTexSubImage2D( GL_TEXTURE_2D, 0, 0, 0, 0, 0, frameBuffers[ 0 ].width, frameBuffers[ 0 ].height );
	GL_SelectTexture( 0 );
	depthFadeCopied = qtrue;

	FBO_BindMain();
}

void FBO_BindDepthFadeTexture( int texUnit )
{
	GL_BindTexture( texUnit, FBO_DepthFadeReady() ? depthFadeTexture : 0 );
}


static void FBO_Bind( GLuint target, GLuint buffer )
{
#if 1
	static GLuint draw_buffer = (GLuint)-1;
	static GLuint read_buffer = (GLuint)-1;
	if ( target == GL_FRAMEBUFFER ) {
		if ( draw_buffer != buffer || read_buffer != buffer ) {
			qglBindFramebuffer( GL_FRAMEBUFFER, buffer );
#ifdef RENDERER_GLX
			GLX_CompatRecordFboBind();
#endif
		}
		draw_buffer = buffer;
		read_buffer = buffer;
	} else {
		if ( target == GL_READ_FRAMEBUFFER ) {
			if ( read_buffer != buffer ) {
				qglBindFramebuffer( GL_READ_FRAMEBUFFER, buffer );
#ifdef RENDERER_GLX
				GLX_CompatRecordFboBind();
#endif
			}
			read_buffer = buffer;
		} else {
			if ( draw_buffer != buffer ) {
				qglBindFramebuffer( GL_DRAW_FRAMEBUFFER, buffer );
#ifdef RENDERER_GLX
				GLX_CompatRecordFboBind();
#endif
			}
			draw_buffer = buffer;
		}
	}
#else
	qglBindFramebuffer( target, buffer );
#ifdef RENDERER_GLX
	GLX_CompatRecordFboBind();
#endif
#endif
	FBO_SetFramebufferSrgb( qfalse );
}


void FBO_BindMain( void )
{
	if ( fboEnabled )
	{
		const frameBuffer_t *fb;
		if ( frameBufferMultiSampling )
		{
			blitMSfbo = qtrue;
			fb = &frameBufferMS;
		}
		else
		{
			blitMSfbo = qfalse;
			fb = &frameBuffers[ 0 ];
		}
		FBO_Bind( GL_FRAMEBUFFER, fb->fbo );
		fboReadIndex = 0;
	}
}

static void FBO_UpdateTonemapExposure( void )
{
	float manualExposure;

	if ( fboExposureFrame == tr.frameCount ) {
		return;
	}

	manualExposure = FBO_TonemapExposureCvar();
	fboExposureFrame = tr.frameCount;
	fboEffectiveTonemapExposure = manualExposure;

#ifdef RENDERER_GLX
	if ( FBO_HdrSceneLinearMode() )
	{
		int width = 0;
		int height = 0;
		qboolean sampled = qfalse;

		if ( GLX_CompatAutoExposureNeedsSamples( &width, &height ) )
		{
			if ( width > 128 ) {
				width = 128;
			}
			if ( height > 128 ) {
				height = 128;
			}
			if ( width > 0 && height > 0 && frameBuffers[ 0 ].color &&
				frameBuffers[ 3 ].fbo && width <= frameBuffers[ 3 ].width &&
				height <= frameBuffers[ 3 ].height )
			{
				GLenum error;

				ARB_ProgramDisable();
				FBO_Bind( GL_FRAMEBUFFER, frameBuffers[ 3 ].fbo );
				GL_BindTexture( 0, frameBuffers[ 0 ].color );
				GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
				qglViewport( 0, 0, width, height );
				qglScissor( 0, 0, width, height );
				RenderQuad( glConfig.vidWidth, glConfig.vidHeight );
				qglReadPixels( 0, 0, width, height, GL_RGBA, GL_FLOAT,
					fboExposureSamplePixels );
				error = qglGetError();
				sampled = ( error == GL_NO_ERROR ) ? qtrue : qfalse;
				qglViewport( 0, 0, glConfig.vidWidth, glConfig.vidHeight );
				qglScissor( 0, 0, glConfig.vidWidth, glConfig.vidHeight );
			}
		}

		fboEffectiveTonemapExposure = GLX_CompatUpdateAutoExposure(
			manualExposure, sampled ? fboExposureSamplePixels : NULL,
			sampled ? width : 0, sampled ? height : 0 );
	}
#endif
}


static void FBO_BlitToBackBuffer( int index )
{
	const frameBuffer_t *src = &frameBuffers[ index ];
#ifdef RENDERER_GLX
	GLX_CompatRecordFboBlit( GLX_FBO_BLIT_BACKBUFFER, qfalse,
		src->width, src->height, blitX1 - blitX0, blitY1 - blitY0 );
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_FBO_BLIT );
#endif

	FBO_Bind( GL_READ_FRAMEBUFFER, src->fbo );
	FBO_Bind( GL_DRAW_FRAMEBUFFER, 0 );
	//qglReadBuffer( GL_COLOR_ATTACHMENT0 );
	qglDrawBuffer( GL_BACK );

	if ( windowAdjusted )
	{
		if ( blitClear > 0 )
		{
			blitClear--;
			qglClearColor( 0.0, 0.0, 0.0, 1.0 );
			qglClear( GL_COLOR_BUFFER_BIT );
#ifdef RENDERER_GLX
			GLX_CompatRecordPostClear();
#endif
		}
		qglViewport( blitX0, blitY0, blitX1 - blitX0, blitY1 - blitY0 );
		qglScissor( blitX0, blitY0, blitX1 - blitX0, blitY1 - blitY0 );
	}

	qglBlitFramebuffer( 0, 0, src->width, src->height, blitX0, blitY0, blitX1, blitY1, GL_COLOR_BUFFER_BIT, blitFilter );
	fboReadIndex = index;
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_FBO_BLIT );
#endif
}


void FBO_BlitSS( void )
{
	const frameBuffer_t *src = &frameBuffers[ fboReadIndex ];
	const frameBuffer_t *dst = &frameBuffers[ 4 ];
#ifdef RENDERER_GLX
	GLX_CompatRecordFboBlit( GLX_FBO_BLIT_SS, qfalse,
		src->width, src->height, dst->width, dst->height );
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_FBO_BLIT );
#endif

	FBO_Bind( GL_DRAW_FRAMEBUFFER, dst->fbo );
	
	qglBlitFramebuffer( 0, 0, src->width, src->height, 0, 0, dst->width, dst->height, GL_COLOR_BUFFER_BIT, GL_LINEAR );

	FBO_Bind( GL_READ_FRAMEBUFFER, dst->fbo );
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_FBO_BLIT );
#endif
}


void FBO_BlitMS( qboolean depthOnly )
{
	//if ( blitMSfbo )
	//{
	const int w = glConfig.vidWidth;
	const int h = glConfig.vidHeight;

	const frameBuffer_t *r = &frameBufferMS;
	const frameBuffer_t *d = &frameBuffers[ 0 ];
#ifdef RENDERER_GLX
	GLX_CompatRecordFboBlit( GLX_FBO_BLIT_MS, depthOnly,
		r->width, r->height, d->width, d->height );
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_FBO_BLIT );
#endif

	fboReadIndex = 0;

	FBO_Bind( GL_READ_FRAMEBUFFER, r->fbo );
	FBO_Bind( GL_DRAW_FRAMEBUFFER, d->fbo );

	if ( depthOnly )
	{
		qglBlitFramebuffer( 0, 0, w, h, 0, 0, w, h, GL_DEPTH_BUFFER_BIT, GL_NEAREST );
		FBO_Bind( GL_READ_FRAMEBUFFER, d->fbo );
#ifdef RENDERER_GLX
		GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_FBO_BLIT );
#endif
		return;
	}

	qglBlitFramebuffer( 0, 0, w, h, 0, 0, w, h, GL_COLOR_BUFFER_BIT, GL_NEAREST );
	// bind all further reads to main buffer
	FBO_Bind( GL_READ_FRAMEBUFFER, d->fbo );
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_FBO_BLIT );
#endif
}


static void FBO_Blur( const frameBuffer_t *fb1, const frameBuffer_t *fb2,  const frameBuffer_t *fb3 )
{
	const int w = glConfig.vidWidth;
	const int h = glConfig.vidHeight;
#ifdef RENDERER_GLX
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_BLOOM_BLUR );
#endif

	qglViewport( 0, 0, fb1->width, fb1->height );

	// apply horizontal blur - render from FBO1 to FBO2
	FBO_Bind( GL_DRAW_FRAMEBUFFER, fb2->fbo );
	GL_BindTexture( 0, fb1->color );
	ARB_ProgramEnable( DUMMY_VERTEX, BLUR_FRAGMENT );
	ARB_BlurParams( fb1->width, fb1->height, fboBloomFilterSize, qtrue );
	RenderQuad( w, h );

	// apply vectical blur - render from FBO2 to FBO3
	FBO_Bind( GL_DRAW_FRAMEBUFFER, fb3->fbo );
	GL_BindTexture( 0, fb2->color );
	ARB_BlurParams( fb1->width, fb1->height, fboBloomFilterSize, qfalse );
	RenderQuad( w, h );
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM_BLUR );
#endif
}


static void FBO_Blur2( const frameBuffer_t *fb1, const frameBuffer_t *fb2,  const frameBuffer_t *fb3 )
{
	const int w = glConfig.vidWidth;
	const int h = glConfig.vidHeight;
#ifdef RENDERER_GLX
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_BLOOM_BLUR );
#endif

	qglViewport( 0, 0, fb1->width, fb1->height );

	// apply horizontal blur - render from FBO1 to FBO2
	FBO_Bind( GL_DRAW_FRAMEBUFFER, fb2->fbo );
	GL_BindTexture( 0, fb1->color );
	ARB_ProgramEnable( DUMMY_VERTEX, BLUR2_FRAGMENT );
	ARB_BlurParams( fb1->width, fb1->height, 6, qtrue );
	RenderQuad( w, h );

	// apply vectical blur - render from FBO2 to FBO3
	FBO_Bind( GL_DRAW_FRAMEBUFFER, fb3->fbo );
	GL_BindTexture( 0, fb2->color );
	ARB_BlurParams( fb1->width, fb1->height, 6, qfalse );
	RenderQuad( w, h );
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM_BLUR );
#endif
}


static qboolean FBO_EnsureMenuDepthOfFieldBuffers( void )
{
	const int width = MAX( 1, glConfig.vidWidth / 2 );
	const int height = MAX( 1, glConfig.vidHeight / 2 );

	if ( menuDofBuffers[0].fbo && menuDofBuffers[1].fbo &&
		menuDofBuffers[0].width == width && menuDofBuffers[0].height == height &&
		menuDofBuffers[1].width == width && menuDofBuffers[1].height == height ) {
		return qtrue;
	}

	FBO_Clean( &menuDofBuffers[0] );
	FBO_Clean( &menuDofBuffers[1] );

	if ( !FBO_Create( &menuDofBuffers[0], width, height, qfalse, NULL, NULL ) ||
		!FBO_Create( &menuDofBuffers[1], width, height, qfalse, NULL, NULL ) ) {
		FBO_Clean( &menuDofBuffers[0] );
		FBO_Clean( &menuDofBuffers[1] );
		return qfalse;
	}

	return qtrue;
}


void FBO_MenuDepthOfField( float amount )
{
	frameBuffer_t *source;
	int sourceIndex;
	int pass;

	amount = Com_Clamp( 0.0f, 1.0f, amount );
	if ( amount <= 0.0f || !fboEnabled || !programCompiled || !backEnd.doneSurfaces ||
		backEnd.framePostProcessed || ri.CL_IsMinimized() ) {
		return;
	}

	if ( blitMSfbo ) {
		FBO_BlitMS( qfalse );
		blitMSfbo = qfalse;
	}

	sourceIndex = fboReadIndex;
	if ( sourceIndex < 0 || sourceIndex >= FBO_COUNT ) {
		return;
	}

	source = &frameBuffers[ sourceIndex ];
	if ( !source->fbo || source->multiSampled || !source->color ) {
		return;
	}
	if ( !FBO_EnsureMenuDepthOfFieldBuffers() ) {
		return;
	}

	if ( !backEnd.projection2D ) {
		RB_SetGL2D();
	}

	FBO_Bind( GL_READ_FRAMEBUFFER, source->fbo );
	FBO_Bind( GL_DRAW_FRAMEBUFFER, menuDofBuffers[0].fbo );
	qglBlitFramebuffer( 0, 0, source->width, source->height,
		0, 0, menuDofBuffers[0].width, menuDofBuffers[0].height,
		GL_COLOR_BUFFER_BIT, GL_LINEAR );

	qglColor4f( 1.0f, 1.0f, 1.0f, 1.0f );
	GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
	for ( pass = 0; pass < 2; ++pass ) {
		FBO_Blur2( &menuDofBuffers[0], &menuDofBuffers[1], &menuDofBuffers[0] );
	}

	ARB_ProgramDisable();
	FBO_Bind( GL_FRAMEBUFFER, source->fbo );
	GL_BindTexture( 0, menuDofBuffers[0].color );
	GL_TexEnv( GL_MODULATE );
	GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_SRC_ALPHA |
		GLS_DSTBLEND_ONE_MINUS_SRC_ALPHA );
	qglViewport( 0, 0, source->width, source->height );
	qglScissor( 0, 0, source->width, source->height );
	qglColor4f( 1.0f, 1.0f, 1.0f, amount );
	RenderQuad( source->width, source->height );
	qglColor4f( 1.0f, 1.0f, 1.0f, 1.0f );

	fboReadIndex = sourceIndex;
	RB_SetGL2D();
}


void FBO_CopyScreen( void )
{
	const frameBuffer_t *dst;
	const frameBuffer_t *src;
	int yCrop;
#ifdef RENDERER_GLX
	GLX_CompatRecordFboCopyScreen( backEnd.viewParms.viewportWidth,
		backEnd.viewParms.viewportHeight );
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_COPY_SCREEN );
#endif

	qglViewport( 0, 0, glConfig.vidWidth, glConfig.vidHeight );
	qglScissor( 0, 0, glConfig.vidWidth, glConfig.vidHeight );

	// resolve multisample buffer first
	if ( blitMSfbo )
	{
		src = &frameBufferMS;
		dst = &frameBuffers[ 0 ];
#ifdef RENDERER_GLX
		GLX_CompatRecordFboBlit( GLX_FBO_BLIT_COPY_SCREEN, qfalse,
			src->width, src->height, dst->width, dst->height );
#endif
		FBO_Bind( GL_READ_FRAMEBUFFER, src->fbo );
		FBO_Bind( GL_DRAW_FRAMEBUFFER, dst->fbo );
		qglBlitFramebuffer( 0, 0, src->width, src->height, 0, 0, dst->width, dst->height, GL_COLOR_BUFFER_BIT, GL_NEAREST );
	}

	src = &frameBuffers[ 0 ];
	dst = &frameBuffers[ 2 ];
#ifdef RENDERER_GLX
	GLX_CompatRecordFboBlit( GLX_FBO_BLIT_COPY_SCREEN, qfalse,
		src->width, src->height, dst->width, dst->height );
#endif
	FBO_Bind( GL_READ_FRAMEBUFFER, src->fbo );
	FBO_Bind( GL_DRAW_FRAMEBUFFER, dst->fbo );

	yCrop = backEnd.viewParms.viewportHeight / 4;

	qglBlitFramebuffer( backEnd.viewParms.viewportX, backEnd.viewParms.viewportY + yCrop,
		backEnd.viewParms.viewportWidth + backEnd.viewParms.viewportX,
		backEnd.viewParms.viewportHeight + backEnd.viewParms.viewportY,
		0, 0, dst->width, dst->height, GL_COLOR_BUFFER_BIT, GL_LINEAR );

	//if ( !backEnd.projection2D )
	{
		qglMatrixMode( GL_PROJECTION );
		qglLoadMatrixf( GL_Ortho( 0, glConfig.vidWidth, glConfig.vidHeight, 0, 0, 1 ) );
		qglMatrixMode( GL_MODELVIEW );
		qglLoadIdentity();
		GL_Cull( CT_TWO_SIDED );
		qglDisable( GL_CLIP_PLANE0 );
	}

	qglColor4f( 1, 1, 1, 1 );
	GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
	FBO_Blur2( dst, dst+1, dst );
	ARB_ProgramDisable();

	//restore viewport and scissor
	qglViewport( backEnd.viewParms.viewportX, backEnd.viewParms.viewportY,
		backEnd.viewParms.viewportWidth, backEnd.viewParms.viewportHeight ); 
	qglScissor( backEnd.viewParms.scissorX, backEnd.viewParms.scissorY,
		backEnd.viewParms.scissorWidth, backEnd.viewParms.scissorHeight ); 

	FBO_BindMain();
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_COPY_SCREEN );
#endif
}


static void R_Setup_Quad_Lens( float offset, vec4_t color, vec3_t *verts, vec2_t *coords, vec4_t *colors )
{
	static const vec2_t t[6] = { {1.0, 0.0}, {0.0, 0.0}, {0.0, 1.0}, {0.0, 1.0}, {1.0, 1.0}, {1.0, 0.0} };

	const float width = (float)glConfig.vidWidth;
	const float height = (float)glConfig.vidHeight;
	int i;
	
	for ( i = 0; i < 6; i++ ) {
		coords[i][0] = t[i][0];
		coords[i][1] = t[i][1];
		Vector4Copy( color, colors[i] );
		verts[i][2] = 0.0;
	}

	verts[0][0] = -offset;
	verts[0][1] = -offset;

	verts[1][0] = width + offset;
	verts[1][1] = -offset;

	verts[2][0] = width + offset;
	verts[2][1] = height + offset;

	verts[3][0] = width + offset;
	verts[3][1] = height + offset;

	verts[4][0] = -offset;
	verts[4][1] = height + offset;

	verts[5][0] = -offset;
	verts[5][1] = -offset;
}


static void R_Bloom_LensEffect( float alpha )
{
	// lens rainbow colors
	static const GLfloat lc[][3] = {
		{ 0.78f, 0.23f, 0.34f },
		{ 0.78f, 0.39f, 0.21f },
		{ 0.78f, 0.59f, 0.21f },
		{ 0.71f, 0.75f, 0.21f },
		{ 0.52f, 0.78f, 0.21f },
		{ 0.32f, 0.78f, 0.21f },
		{ 0.21f, 0.78f, 0.28f },
		{ 0.21f, 0.78f, 0.47f },
		{ 0.21f, 0.77f, 0.66f },
		{ 0.21f, 0.67f, 0.78f },
		{ 0.21f, 0.47f, 0.78f },
		{ 0.21f, 0.28f, 0.78f },
		{ 0.35f, 0.21f, 0.78f },
		{ 0.53f, 0.21f, 0.78f },
		{ 0.72f, 0.21f, 0.75f },
		{ 0.78f, 0.21f, 0.59f },
	};
	int i;

	vec3_t verts[ ARRAY_LEN(lc) * 6 ];
	vec2_t coords[ ARRAY_LEN(lc) * 6 ];
	vec4_t colors[ ARRAY_LEN(lc) * 6 ];
	vec4_t color;
	qboolean glxStreamedDraw = qfalse;

	alpha /= (float)ARRAY_LEN( lc );
	for ( i = 0; i < ARRAY_LEN( lc ); i++ ) {
		VectorCopy( lc[i], color ); color[3] = alpha;
		R_Setup_Quad_Lens( (i+1)*144, color, &verts[i*6], &coords[i*6], &colors[i*6] );
	}

	GL_ClientState( 0, CLS_TEXCOORD_ARRAY | CLS_COLOR_ARRAY );

	qglVertexPointer( 3, GL_FLOAT, 0, verts );
	qglTexCoordPointer( 2, GL_FLOAT, 0, coords );
	qglColorPointer( 4, GL_FLOAT, 0, colors );

	if ( GLX_CompatStreamDrawPostProcessEnabled() ) {
		glxStreamedDraw = GLX_CompatTryStreamDrawArrayTexcoordColorPass(
			(int)ARRAY_LEN( verts ), verts, (int)sizeof( verts[0] ), coords, 0,
			colors, 4, GL_FLOAT, 0, GL_TRIANGLES, GLX_STAGE_POSTPROCESS_PASS,
			GLX_DYNAMIC_CATEGORY_MASK_SPECIAL );
	}
	if ( !glxStreamedDraw ) {
#ifdef RENDERER_GLX
		GLX_CompatDrawArrays( GL_TRIANGLES, 0, (int)ARRAY_LEN( verts ),
			GLX_LEGACY_DELEGATION_DRAW_ARRAY, GLX_DRAW_NONE );
#else
		qglDrawArrays( GL_TRIANGLES, 0, ARRAY_LEN( verts ) );
#endif
	}
}


qboolean FBO_Bloom( const float gamma, const float obScale, qboolean finalStage )
{
	const int w = glConfig.vidWidth;
	const int h = glConfig.vidHeight;

	frameBuffer_t *src, *dst;
	int finalBloomFBO;
	int i;
	float bloomThreshold;
	float bloomSoftKnee;
	float bloomKneeWidth;
#ifdef RENDERER_GLX
	qboolean glxPostShaderBound = qfalse;
#endif

	if ( backEnd.doneBloom || !backEnd.doneSurfaces )
	{
#ifdef RENDERER_GLX
		GLX_RecordBloomState( GLX_BLOOM_RESULT_SKIPPED, finalStage );
#endif
		return qfalse;
	}

	backEnd.doneBloom = qtrue;
#ifdef RENDERER_GLX
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_BLOOM );
#endif

	if ( !fboBloomInited )
	{
		if ( (fboBloomInited = FBO_CreateBloom() ) == qfalse )
		{
			ri.Printf( PRINT_WARNING, "...error creating framebuffers for bloom\n" );
			ri.Cvar_Set( "r_bloom", "0" );
			FBO_CleanBloom();
#ifdef RENDERER_GLX
			GLX_RecordBloomState( GLX_BLOOM_RESULT_CREATE_FAILED, finalStage );
			GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM );
#endif
			return qfalse;
		}
		else
		{
			ri.Printf( PRINT_ALL, "...bloom framebuffers created\n" );
		}
	}

	if ( blitMSfbo )
	{
		FBO_BlitMS( qfalse );
		blitMSfbo = qfalse;
	}
	FBO_UpdateTonemapExposure();
	
	// extract intensity from main FBO to BLOOM_BASE
	src = &frameBuffers[ 0 ];
	dst = &frameBuffers[ BLOOM_BASE ];
#ifdef RENDERER_GLX
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_BLOOM_EXTRACT );
#endif
	FBO_Bind( GL_FRAMEBUFFER, dst->fbo );
	GL_BindTexture( 0, src->color );
	qglViewport( 0, 0, dst->width, dst->height );
	ARB_ProgramEnable( DUMMY_VERTEX, BLOOM_EXTRACT_FRAGMENT );
	bloomThreshold = r_bloom_threshold ? Com_Clamp( 0.0f, 64.0f, r_bloom_threshold->value ) : 0.75f;
	bloomSoftKnee = r_bloom_soft_knee ? Com_Clamp( 0.0f, 1.0f, r_bloom_soft_knee->value ) : 0.0f;
	bloomKneeWidth = bloomThreshold * bloomSoftKnee;
	if ( bloomKneeWidth < 0.0001f ) {
		bloomKneeWidth = 0.0001f;
	}
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 0, bloomThreshold, bloomThreshold,
		bloomThreshold, 1.0 );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 1, FBO_TonemapExposure(), FBO_TonemapExposure(),
		FBO_TonemapExposure(), 1.0f );
	qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 2, bloomThreshold - bloomKneeWidth,
		1.0f / ( bloomKneeWidth * 2.0f ), 0.0f, 1.0f );
	RenderQuad( w, h );
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM_EXTRACT );
#endif

	// downscale and blur
	src = frameBuffers + BLOOM_BASE;
	for ( i = 1; i < fboBloomPasses; i++, src+=2 ) {
		dst = src + 2;
		// copy image to next level
#ifdef RENDERER_GLX
		GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_BLOOM_DOWNSCALE );
#endif
#ifdef USE_FBO_BLIT
		FBO_Bind( GL_READ_FRAMEBUFFER, src->fbo );
		FBO_Bind( GL_DRAW_FRAMEBUFFER, dst->fbo );
		qglBlitFramebuffer( 0, 0, src->width, src->height, 0, 0, dst->width, dst->height, GL_COLOR_BUFFER_BIT, GL_LINEAR );
#else
		ARB_ProgramDisable();
		FBO_Bind( GL_FRAMEBUFFER, dst->fbo );
		GL_BindTexture( 0, src->color );
		GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
		qglViewport( 0, 0, dst->width, dst->height );
		RenderQuad( w, h );
#endif
#ifdef RENDERER_GLX
		GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM_DOWNSCALE );
#endif
		FBO_Blur( dst, dst+1, dst );
	}

	// restore viewport
	qglViewport( 0, 0, w, h );

	// blend all bloom buffers to BLOOM_BASE+1 texture
	finalBloomFBO = BLOOM_BASE+1;
	GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
#ifdef RENDERER_GLX
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_BLOOM_BLEND );
#endif
	FBO_Bind( GL_FRAMEBUFFER, frameBuffers[ finalBloomFBO ].fbo );
	ARB_ProgramEnable( DUMMY_VERTEX, BLENDX_FRAGMENT );
	// setup all texture units
	for ( i = 0; i < fboBloomPasses - fboBloomBlendBase; i++ ) {
		GL_BindTexture( i, frameBuffers[ (i+fboBloomBlendBase)*2 + BLOOM_BASE ].color );
	}
	RenderQuad( w, h );
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM_BLEND );
#endif

	if ( r_bloom_reflection->value )
	{
#ifdef RENDERER_GLX
		GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_BLOOM_LENS_REFLECTION );
#endif
		ARB_ProgramDisable();

		// copy final bloom image to some downscaled buffer
		src = &frameBuffers[ finalBloomFBO ];
		dst = &frameBuffers[ BLOOM_BASE + 2 + 2 ]; // 4x downscale
		FBO_Bind( GL_DRAW_FRAMEBUFFER, dst->fbo );
		FBO_Bind( GL_READ_FRAMEBUFFER, src->fbo );
		qglBlitFramebuffer( 0, 0, src->width, src->height, 0, 0, dst->width, dst->height, GL_COLOR_BUFFER_BIT, GL_LINEAR );
		
		// set render target to paired destination buffer and draw reflections
		FBO_Bind( GL_DRAW_FRAMEBUFFER, (dst+1)->fbo );
		GL_BindTexture( 0, dst->color );
		GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_SRC_ALPHA | GLS_DSTBLEND_ONE );
		qglViewport( 0, 0, dst->width, dst->height );
		R_Bloom_LensEffect( fabs( r_bloom_reflection->value ) );
		
		// restore color and blend mode
		qglColor4f( 1.0f, 1.0f, 1.0f, 1.0f );
		GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
		
		// blur lens effect in paired buffer
		FBO_Blur( dst+1, dst, dst+1 );
		ARB_ProgramDisable();

		// add lens effect to final bloom buffer
		FBO_Bind( GL_FRAMEBUFFER, src->fbo );
		if ( r_bloom_reflection->value > 0 ) {
			GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ONE );
		} else {
			// negative reflection values will replace bloom texture with just lens effect
		}
		qglViewport( 0, 0, w, h );
		GL_BindTexture( 0, (dst+1)->color );
		RenderQuad( w, h );

		// restore blend mode
		GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
#ifdef RENDERER_GLX
		GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM_LENS_REFLECTION );
#endif
	}

	if ( windowAdjusted || backEnd.screenshotMask ) {
		finalStage = qfalse; // can't blit directly into back buffer in this case
	}

	// if we don't need to read pixels later - blend directly to back buffer
	if ( finalStage ) {
		if ( backEnd.screenshotMask ) {
			FBO_Bind( GL_FRAMEBUFFER, frameBuffers[ BLOOM_BASE ].fbo );
		} else {
			FBO_Bind( GL_FRAMEBUFFER, 0 );
		}
	} else {
		FBO_Bind( GL_FRAMEBUFFER, frameBuffers[ BLOOM_BASE ].fbo );
	}

	GL_BindTexture( 1, frameBuffers[ finalBloomFBO ].color ); // final bloom texture
	GL_BindTexture( 0, frameBuffers[ 0 ].color ); // original image
#ifdef RENDERER_GLX
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_BLOOM_FINAL );
#endif
	if ( finalStage ) {
#ifdef RENDERER_GLX
		FBO_PrepareGlxPostShaderColorGradeLut();
		glxPostShaderBound = GLX_CompatTryBindPostShaderFinal( qtrue, qtrue,
			r_bloom_intensity->value );
		if ( !glxPostShaderBound ) {
#endif
		// blend & apply gamma in one pass
		ARB_ProgramEnable( DUMMY_VERTEX, BLEND2_GAMMA_FRAGMENT );
		FBO_SetOutputTransformParams( gamma, obScale );
		FBO_BindColorGradeLut();
		qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 1, r_bloom_intensity->value, 0, 0, 0 );
#ifdef RENDERER_GLX
		}
#endif
	} else {
#ifdef RENDERER_GLX
		glxPostShaderBound = GLX_CompatTryBindPostShaderFinal( qtrue, qfalse,
			r_bloom_intensity->value );
		if ( !glxPostShaderBound ) {
#endif
		// just blend
		ARB_ProgramEnable( DUMMY_VERTEX, BLEND2_FRAGMENT );
		qglProgramLocalParameter4fARB( GL_FRAGMENT_PROGRAM_ARB, 1, r_bloom_intensity->value, 0, 0, 0 );
#ifdef RENDERER_GLX
		}
#endif
	}
	RenderQuad( w, h );
#ifdef RENDERER_GLX
	if ( glxPostShaderBound ) {
		GLX_CompatUnbindPostShader();
	} else {
		ARB_ProgramDisable();
	}
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM_FINAL );
#else
	ARB_ProgramDisable();
#endif

	if ( finalStage ) {
		if ( backEnd.screenshotMask ) {
			FBO_BlitToBackBuffer( BLOOM_BASE ); // so any further qglReadPixels() will read from BLOOM_BASE
			 // fboReadIndex = 0;
		} else {
			//	already in back buffer
			fboReadIndex = 0;
		}
	} else {
		// we need depth/stencil buffers there
		fboReadIndex = BLOOM_BASE;
	}

#ifdef RENDERER_GLX
	GLX_RecordBloomState( finalStage ? GLX_BLOOM_RESULT_FINAL : GLX_BLOOM_RESULT_INTERMEDIATE,
		finalStage );
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_BLOOM );
#endif

	return finalStage;
}


void R_BloomScreen( void )
{
	if ( r_bloom->integer == 1 && fboEnabled && qglActiveTextureARB )
	{
		if ( !backEnd.framePostProcessed && !backEnd.doneBloom && backEnd.doneSurfaces )
		{
			if ( !backEnd.projection2D )
				RB_SetGL2D();
			qglColor4f( 1, 1, 1, 1 );
			FBO_Bloom( 0, 0, qfalse );
		}
	}
}


void FBO_PostProcess( void )
{
	const float obScale = 1 << tr.overbrightBits;
	const float gamma = 1.0f / r_gamma->value;
	const float w = glConfig.vidWidth;
	const float h = glConfig.vidHeight;
	qboolean minimized;

	ARB_ProgramDisable();

	if ( !backEnd.projection2D )
	{
		qglViewport( 0, 0, glConfig.vidWidth, glConfig.vidHeight );
		qglScissor( 0, 0, glConfig.vidWidth, glConfig.vidHeight );
		qglMatrixMode( GL_PROJECTION );
		qglLoadMatrixf( GL_Ortho( 0, glConfig.vidWidth, glConfig.vidHeight, 0, 0, 1 ) );
		qglMatrixMode( GL_MODELVIEW );
		qglLoadIdentity();
		backEnd.projection2D = qtrue;
	}

	if ( blitMSfbo )
	{
		FBO_BlitMS( qfalse );
		blitMSfbo = qfalse;
	}
	FBO_UpdateTonemapExposure();

	qglColor4f( 1.0f, 1.0f, 1.0f, 1.0f );
	GL_State( GLS_DEPTHTEST_DISABLE | GLS_SRCBLEND_ONE | GLS_DSTBLEND_ZERO );
	GL_Cull( CT_TWO_SIDED );
	if ( r_anaglyphMode->integer )
		qglColorMask( GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE );

	minimized = ri.CL_IsMinimized();
#ifdef RENDERER_GLX
	GLX_CompatRecordPostProcessFrame( minimized,
		( r_bloom->integer && programCompiled && qglActiveTextureARB ) ? qtrue : qfalse,
		programCompiled ? qtrue : qfalse, backEnd.screenshotMask, windowAdjusted,
		fboReadIndex, FBO_HdrSceneLinearMode(), r_renderScale->integer, r_greyscale->value,
		gamma, FBO_OutputOverbrightScale( obScale ) );
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_POSTPROCESS );
#endif

	if ( r_bloom->integer && programCompiled && qglActiveTextureARB ) {
		if ( FBO_Bloom( gamma, obScale, !minimized ) ) {
#ifdef RENDERER_GLX
			GLX_CompatRecordPostProcessResult( GLX_POSTPROCESS_RESULT_BLOOM_FINAL );
			GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_POSTPROCESS );
#endif
			return;
		}
	}

	// check if we can perform final draw directly into back buffer
	if ( backEnd.screenshotMask == 0 && !windowAdjusted && !minimized ) {
#ifdef RENDERER_GLX
		qboolean glxPostShaderBound = qfalse;
#endif

		FBO_Bind( GL_FRAMEBUFFER, 0 );
		GL_BindTexture( 0, frameBuffers[ fboReadIndex ].color );
#ifdef RENDERER_GLX
		GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_GAMMA_DIRECT );
		FBO_PrepareGlxPostShaderColorGradeLut();
		glxPostShaderBound = GLX_CompatTryBindPostShaderFinal( qfalse, qtrue, 0.0f );
		if ( !glxPostShaderBound ) {
#endif
		ARB_ProgramEnable( DUMMY_VERTEX, GAMMA_FRAGMENT );
		FBO_SetOutputTransformParams( gamma, obScale );
		FBO_BindColorGradeLut();
#ifdef RENDERER_GLX
		}
#endif
		RenderQuad( w, h );
#ifdef RENDERER_GLX
		if ( glxPostShaderBound ) {
			GLX_CompatUnbindPostShader();
		} else {
			ARB_ProgramDisable();
		}
#else
		ARB_ProgramDisable();
#endif
#ifdef RENDERER_GLX
		GLX_CompatRecordPostProcessResult( GLX_POSTPROCESS_RESULT_GAMMA_DIRECT );
		GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_GAMMA_DIRECT );
		GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_POSTPROCESS );
#endif
		return;
	}

	// apply gamma shader
#ifdef RENDERER_GLX
	{
	qboolean glxPostShaderBound = qfalse;
#endif
	FBO_Bind( GL_FRAMEBUFFER, frameBuffers[ 1 ].fbo ); // destination - secondary buffer
	GL_BindTexture( 0, frameBuffers[ fboReadIndex ].color );  // source - main color buffer
#ifdef RENDERER_GLX
	GLX_CompatBeginGpuPassTimer( GLX_GPU_PASS_GAMMA_BLIT );
	FBO_PrepareGlxPostShaderColorGradeLut();
	glxPostShaderBound = GLX_CompatTryBindPostShaderFinal( qfalse, qtrue, 0.0f );
	if ( !glxPostShaderBound ) {
#endif
	ARB_ProgramEnable( DUMMY_VERTEX, GAMMA_FRAGMENT );
	FBO_SetOutputTransformParams( gamma, obScale );
	FBO_BindColorGradeLut();
#ifdef RENDERER_GLX
	}
#endif
	RenderQuad( w, h );
#ifdef RENDERER_GLX
	if ( glxPostShaderBound ) {
		GLX_CompatUnbindPostShader();
	} else {
		ARB_ProgramDisable();
	}
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_GAMMA_BLIT );
	}
#else
	ARB_ProgramDisable();
#endif

	if ( !minimized ) {
		FBO_BlitToBackBuffer( 1 );
#ifdef RENDERER_GLX
		GLX_CompatRecordPostProcessResult( GLX_POSTPROCESS_RESULT_GAMMA_BLIT );
#endif
#ifdef RENDERER_GLX
	} else {
		GLX_CompatRecordPostProcessResult( GLX_POSTPROCESS_RESULT_MINIMIZED );
#endif
	}
#ifdef RENDERER_GLX
	GLX_CompatEndGpuPassTimer( GLX_GPU_PASS_POSTPROCESS );
#endif
}


static void QGL_ResolveRenderSizeFromCvars( void )
{
	glConfig.vidWidth = gls.windowWidth;
	glConfig.vidHeight = gls.windowHeight;
	gls.captureWidth = glConfig.vidWidth;
	gls.captureHeight = glConfig.vidHeight;
	ri.CL_SetScaling( 1.0, gls.captureWidth, gls.captureHeight );

	if ( !qglGenProgramsARB || !qglGenFramebuffers || !r_fbo || !r_fbo->integer ) {
		return;
	}

	if ( r_renderScale && r_renderScale->integer ) {
		glConfig.vidWidth = r_renderWidth ? r_renderWidth->integer : glConfig.vidWidth;
		glConfig.vidHeight = r_renderHeight ? r_renderHeight->integer : glConfig.vidHeight;
		gls.captureWidth = glConfig.vidWidth;
		gls.captureHeight = glConfig.vidHeight;
		ri.CL_SetScaling( 1.0, gls.captureWidth, gls.captureHeight );
	}

	if ( r_ext_supersample && r_ext_supersample->integer ) {
		glConfig.vidWidth *= 2;
		glConfig.vidHeight *= 2;
		ri.CL_SetScaling( 2.0, gls.captureWidth, gls.captureHeight );
	}
}

void QGL_SetRenderScale( qboolean verbose )
{
	windowAdjusted = qfalse;

	blitX0 = blitY0 = 0;
	blitX1 = gls.windowWidth;
	blitY1 = gls.windowHeight;

	blitFilter = GL_NEAREST;

	superSampled = qfalse;

	if ( !qglGenProgramsARB || !qglGenFramebuffers )
		return;

	if ( !r_fbo->integer )
	{
		if ( verbose && r_renderScale->integer )
		{
			ri.Printf( PRINT_ALL, "...ignoring \\r_renderScale due to disabled FBO\n" );
		}
		return;
	}

	if ( r_ext_supersample->integer )
	{
		superSampled = qtrue;
		blitFilter = GL_LINEAR; // default value for (r_renderScale==0) case
	}

	if ( gls.windowWidth != glConfig.vidWidth || gls.windowHeight != glConfig.vidHeight )
	{
		if ( r_renderScale->integer > 0 )
		{
			int scaleMode = r_renderScale->integer - 1;
			if ( scaleMode & 1 )
			{
				// preserve aspect ratio (black bars on sides)
				float windowAspect = (float) gls.windowWidth / (float) gls.windowHeight;
				float renderAspect = (float) glConfig.vidWidth / (float) glConfig.vidHeight;
				if ( windowAspect >= renderAspect ) 
				{
					float scale = (float) gls.windowHeight / ( float ) glConfig.vidHeight;
					int bias = ( gls.windowWidth - scale * (float) glConfig.vidWidth ) / 2;
					blitX0 += bias;
					blitX1 -= bias;
				}
				else
				{
					float scale = (float) gls.windowWidth / ( float ) glConfig.vidWidth;
					int bias = ( gls.windowHeight - scale * (float) glConfig.vidHeight ) / 2;
					blitY0 += bias;
					blitY1 -= bias;
				}
			}
			// linear filtering
			if ( scaleMode & 2 )
				blitFilter = GL_LINEAR;
			else
				blitFilter = GL_NEAREST;
		}

		windowAdjusted = qtrue;
	}
}


void QGL_DoneFBO( void )
{
	if ( qglGenFramebuffers )
	{
		FBO_Bind(GL_FRAMEBUFFER, 0);
		FBO_Clean(&frameBufferMS);
		FBO_Clean(&frameBuffers[0]);
		FBO_Clean(&frameBuffers[1]);
		FBO_Clean(&frameBuffers[2]);
		FBO_Clean(&frameBuffers[3]);
		FBO_Clean(&frameBuffers[4]);
		FBO_Clean(&menuDofBuffers[0]);
		FBO_Clean(&menuDofBuffers[1]);
		FBO_CleanBloom();
		FBO_CleanDepth();
		fboEnabled = qfalse;
		fboBloomInited = qfalse;
#ifdef RENDERER_GLX
		GLX_CompatRecordFboShutdown();
#endif
	}
}


void QGL_InitFBO( void )
{
	int w, h;
	qboolean programReady;
	qboolean depthStencil;
	qboolean result = qfalse;

	QGL_DoneFBO();
	QGL_ResolveRenderSizeFromCvars();
	QGL_SetRenderScale( qtrue );

	w = glConfig.vidWidth;
	h = glConfig.vidHeight;
	
	fboEnabled = qfalse;
	frameBufferMultiSampling = qfalse;
	fboInternalFormat = FBO_MainInternalFormat();
	fboTextureFormat = 0;
	fboTextureType = 0;
	programReady = ( qglGenProgramsARB && GL_ProgramAvailable() ) ? qtrue : qfalse;

	if ( r_fbo->integer && ( !programReady || !qglGenFramebuffers ) )
		ri.Printf( PRINT_WARNING, "...FBO is not available\n" );

	if ( !r_fbo->integer || !programReady || !qglGenFramebuffers )
	{
#ifdef RENDERER_GLX
		GLX_RecordFboInitState( r_fbo->integer ? qtrue : qfalse, qfalse,
			programReady, qglGenFramebuffers ? qtrue : qfalse );
#endif
		return;
	}

	qglGetError(); // reset error code

	if ( windowAdjusted )
		blitClear = 2; // front & back buffers
	else
		blitClear = 0;

	if ( FBO_HdrSceneLinearMode() && !FBO_InternalFormatIsFloat( fboInternalFormat ) ) {
		ri.Printf( PRINT_WARNING, "...r_hdr 1 requires a floating-point scene FBO, got %s\n",
			glDefToStr( fboInternalFormat ) );
#ifdef RENDERER_GLX
		GLX_RecordFboInitState( qtrue, qfalse, qtrue, qtrue );
#endif
		return;
	}

	if ( FBO_CreateMS( &frameBufferMS, w, h ) )
	{
		frameBufferMultiSampling = qtrue;
		if ( r_flares->integer )
			depthStencil = qtrue;
		else
			depthStencil = qfalse;
		result = FBO_Create( &frameBuffers[ 0 ], w, h, depthStencil, &fboTextureFormat, &fboTextureType )
			&& FBO_Create( &frameBuffers[ 1 ], w, h, depthStencil, NULL, NULL )
			&& FBO_Create( &frameBuffers[ 2 ], SCR_WIDTH, SCR_HEIGHT, qfalse, NULL, NULL )
			&& FBO_Create( &frameBuffers[ 3 ], SCR_WIDTH, SCR_HEIGHT, qfalse, NULL, NULL );
		frameBufferMultiSampling = result;
	}
	else
	{
		result = FBO_Create( &frameBuffers[ 0 ], w, h, qtrue, &fboTextureFormat, &fboTextureType )
			&& FBO_Create( &frameBuffers[ 1 ], w, h, qtrue, NULL, NULL )
			&& FBO_Create( &frameBuffers[ 2 ], SCR_WIDTH, SCR_HEIGHT, qfalse, NULL, NULL )
			&& FBO_Create( &frameBuffers[ 3 ], SCR_WIDTH, SCR_HEIGHT, qfalse, NULL, NULL );
	}

	if ( result && superSampled )
	{
		result &= FBO_Create( &frameBuffers[ 4 ], gls.captureWidth, gls.captureHeight, qfalse, NULL, NULL );
	}

	if ( result )
	{
		fboEnabled = qtrue;
		depthFadeTexture = FBO_CreateDepthFadeTexture( w, h );
		FBO_BindMain();
		ri.Printf( PRINT_ALL, "...using %s (%s:%s) FBO\n", glDefToStr( fboInternalFormat ),
			glDefToStr( fboTextureFormat ), glDefToStr( fboTextureType ) );
	}
	else
	{
		QGL_DoneFBO();
	}
#ifdef RENDERER_GLX
	GLX_RecordFboInitState( qtrue, fboEnabled, qtrue, qtrue );
#endif
}
#endif // USE_FBO


void QGL_InitARB( void )
{
	ARB_UpdatePrograms();
#ifdef USE_FBO
	QGL_InitFBO();
#endif
	ri.Cvar_ResetGroup( CVG_RENDERER, qtrue );
}


void QGL_DoneARB( void )
{
#ifdef USE_FBO
	QGL_DoneFBO();
#endif
	if ( programCompiled )
	{
		ARB_ProgramDisable();
		ARB_DeletePrograms();
	}
}
