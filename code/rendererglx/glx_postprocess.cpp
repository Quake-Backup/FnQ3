#include "glx_postprocess.h"

#include <cstdio>
#include <cstring>

namespace glx {

static void GLX_PostProcess_SetReason( PostProcessState *state, const char *reason )
{
	if ( !state ) {
		return;
	}

	if ( !reason ) {
		reason = "";
	}

	std::snprintf( state->reason, sizeof( state->reason ), "%s", reason );
	state->reason[sizeof( state->reason ) - 1] = '\0';
}

static float GLX_PostProcess_ClampFloat( float value, float minValue, float maxValue )
{
	if ( value < minValue ) {
		return minValue;
	}
	if ( value > maxValue ) {
		return maxValue;
	}
	return value;
}

static void GLX_PostProcess_InitDisplayOutput( rendererDisplayOutput_t *output )
{
	if ( !output ) {
		return;
	}

	std::memset( output, 0, sizeof( *output ) );
	output->displayIndex = -1;
	output->nativeBackend = ROUTPUT_BACKEND_SDR_SRGB;
	output->sdrWhiteNits = 203.0f;
	output->hdrHeadroom = 1.0f;
	output->maxLuminanceNits = 203.0f;
	output->maxFullFrameLuminanceNits = 203.0f;
	std::snprintf( output->reason, sizeof( output->reason ), "%s", "display output query unavailable" );
	output->reason[sizeof( output->reason ) - 1] = '\0';
}

static void GLX_PostProcess_QueryDisplayOutput( PostProcessState *state )
{
	if ( !state ) {
		return;
	}

	GLX_PostProcess_InitDisplayOutput( &state->displayOutput );
	if ( RI().GLimp_QueryDisplayOutput ) {
		RI().GLimp_QueryDisplayOutput( &state->displayOutput );
	}
}

static rendererOutputRequest_t GLX_PostProcess_OutputRequestForMode( int mode )
{
	if ( mode < ROUTPUT_REQUEST_AUTO || mode >= ROUTPUT_REQUEST_COUNT ) {
		return ROUTPUT_REQUEST_AUTO;
	}
	return static_cast<rendererOutputRequest_t>( mode );
}

static rendererOutputBackend_t GLX_PostProcess_BackendForRequest( rendererOutputRequest_t request )
{
	switch ( request ) {
	case ROUTPUT_REQUEST_WINDOWS_SCRGB:
		return ROUTPUT_BACKEND_WINDOWS_SCRGB;
	case ROUTPUT_REQUEST_HDR10_PQ:
		return ROUTPUT_BACKEND_HDR10_PQ;
	case ROUTPUT_REQUEST_MACOS_EDR:
		return ROUTPUT_BACKEND_MACOS_EDR;
	case ROUTPUT_REQUEST_LINUX_EXPERIMENTAL_HDR:
		return ROUTPUT_BACKEND_LINUX_EXPERIMENTAL_HDR;
	case ROUTPUT_REQUEST_SDR_SRGB:
	case ROUTPUT_REQUEST_AUTO:
	default:
		return ROUTPUT_BACKEND_SDR_SRGB;
	}
}

static qboolean GLX_PostProcess_DisplaySupportsBackend( const rendererDisplayOutput_t &display,
	rendererOutputBackend_t backend, qboolean allowExperimentalLinux )
{
	switch ( backend ) {
	case ROUTPUT_BACKEND_SDR_SRGB:
		return qtrue;
	case ROUTPUT_BACKEND_WINDOWS_SCRGB:
		return ( display.valid && display.windowsScRgbSupported &&
			( display.hdrEnabled || display.hdrHeadroomValid ) ) ? qtrue : qfalse;
	case ROUTPUT_BACKEND_HDR10_PQ:
		return ( display.valid && display.windowsHdr10Supported &&
			( display.hdrEnabled || display.hdrHeadroomValid ) ) ? qtrue : qfalse;
	case ROUTPUT_BACKEND_MACOS_EDR:
		return ( display.valid && display.macosEdrSupported &&
			( display.hdrEnabled || display.hdrHeadroomValid ) ) ? qtrue : qfalse;
	case ROUTPUT_BACKEND_LINUX_EXPERIMENTAL_HDR:
		return ( allowExperimentalLinux && display.valid && display.linuxHdrExperimental &&
			display.explicitLinuxHdrProtocol && ( display.hdrEnabled || display.hdrHeadroomValid ) ) ?
			qtrue : qfalse;
	default:
		return qfalse;
	}
}

static rendererOutputBackend_t GLX_PostProcess_SelectBackend( const PostProcessState *state,
	qboolean sceneLinear, rendererOutputRequest_t request )
{
	const qboolean allowExperimentalLinux = ( state && state->r_outputAllowExperimentalLinuxHDR &&
		state->r_outputAllowExperimentalLinuxHDR->integer ) ? qtrue : qfalse;
	rendererOutputBackend_t backend;

	if ( !state || !sceneLinear || request == ROUTPUT_REQUEST_SDR_SRGB ) {
		return ROUTPUT_BACKEND_SDR_SRGB;
	}

	const rendererDisplayOutput_t &display = state->displayOutput;

	if ( request == ROUTPUT_REQUEST_AUTO ) {
		backend = display.nativeBackend;
	} else {
		backend = GLX_PostProcess_BackendForRequest( request );
	}

	if ( GLX_PostProcess_DisplaySupportsBackend( display, backend, allowExperimentalLinux ) ) {
		return backend;
	}

	return ROUTPUT_BACKEND_SDR_SRGB;
}

static OutputTransfer GLX_PostProcess_OutputTransferForBackend( rendererOutputBackend_t backend )
{
	switch ( backend ) {
	case ROUTPUT_BACKEND_WINDOWS_SCRGB:
		return OutputTransfer::ScRgb;
	case ROUTPUT_BACKEND_HDR10_PQ:
		return OutputTransfer::Hdr10Pq;
	case ROUTPUT_BACKEND_MACOS_EDR:
		return OutputTransfer::MacEdr;
	case ROUTPUT_BACKEND_LINUX_EXPERIMENTAL_HDR:
		return OutputTransfer::LinearSrgb;
	case ROUTPUT_BACKEND_SDR_SRGB:
	default:
		return OutputTransfer::SdrSrgb;
	}
}

static int GLX_PostProcess_HdrPrecisionMode( const PostProcessState *state, int hdrMode )
{
	const int precision = ( state && state->r_hdrPrecision ) ? state->r_hdrPrecision->integer : 0;

	if ( precision == -1 || precision == 8 || precision == 16 ) {
		return precision;
	}
	if ( state && state->r_hdr && state->r_hdr->integer < 0 ) {
		return -1;
	}
	return hdrMode > 0 ? 16 : 8;
}

static void GLX_PostProcess_ParseVec3Cvar( const cvar_t *cvar, float fallback0,
	float fallback1, float fallback2, float minValue, float maxValue, float out[3] )
{
	float values[3] = { fallback0, fallback1, fallback2 };

	if ( cvar && cvar->string && cvar->string[0] ) {
		(void)std::sscanf( cvar->string, "%f %f %f", &values[0], &values[1], &values[2] );
	}
	out[0] = GLX_PostProcess_ClampFloat( values[0], minValue, maxValue );
	out[1] = GLX_PostProcess_ClampFloat( values[1], minValue, maxValue );
	out[2] = GLX_PostProcess_ClampFloat( values[2], minValue, maxValue );
}

static ToneMapOperator GLX_PostProcess_ToneMapOperatorForMode( int mode )
{
	switch ( mode ) {
	case 1:
		return ToneMapOperator::Reinhard;
	case 2:
		return ToneMapOperator::Aces;
	default:
		return ToneMapOperator::Legacy;
	}
}

static ColorGradeMode GLX_PostProcess_ColorGradeForMode( int mode )
{
	switch ( mode ) {
	case 1:
		return ColorGradeMode::LiftGammaGain;
	case 2:
		return ColorGradeMode::Lut3D;
	case 3:
		return ColorGradeMode::LiftGammaGainLut3D;
	default:
		return ColorGradeMode::None;
	}
}

static OutputTransform GLX_PostProcess_MakeOutputTransform( PostProcessState *state,
	int hdrMode, int renderScaleMode, float greyscale )
{
	OutputTransform output = GLX_RenderIR_DefaultOutputTransform();
	const qboolean sceneLinear = hdrMode > 0 ? qtrue : qfalse;
	const int toneMapMode = ( sceneLinear && state && state->r_tonemap ) ?
		state->r_tonemap->integer : 0;
	int gradeMode = ( sceneLinear && state && state->r_colorGrade ) ?
		state->r_colorGrade->integer : 0;
	const float exposure = ( sceneLinear && state && state->r_tonemapExposure ) ?
		GLX_PostProcess_ClampFloat( state->r_tonemapExposure->value, 0.1f, 8.0f ) : 1.0f;
	const float bloomThreshold = ( state && state->r_bloom_threshold ) ?
		GLX_PostProcess_ClampFloat( state->r_bloom_threshold->value, 0.0f, 64.0f ) :
		( state && state->lastBloomThreshold > 0.0f ? state->lastBloomThreshold : 0.75f );
	const float bloomSoftKnee = ( state && state->r_bloom_soft_knee ) ?
		GLX_PostProcess_ClampFloat( state->r_bloom_soft_knee->value, 0.0f, 1.0f ) : 0.0f;
	const float paperWhite = ( state && state->r_hdrDisplayPaperWhite ) ?
		GLX_PostProcess_ClampFloat( state->r_hdrDisplayPaperWhite->value, 80.0f, 500.0f ) : 203.0f;
	float maxOutput = ( state && state->r_hdrDisplayMaxLuminance ) ?
		GLX_PostProcess_ClampFloat( state->r_hdrDisplayMaxLuminance->value, 200.0f, 10000.0f ) : 1000.0f;
	const rendererOutputRequest_t outputRequest = GLX_PostProcess_OutputRequestForMode(
		( state && state->r_outputBackend ) ? state->r_outputBackend->integer : ROUTPUT_REQUEST_AUTO );
	const rendererOutputBackend_t selectedBackend = GLX_PostProcess_SelectBackend( state,
		sceneLinear, outputRequest );
	const qboolean outputHardwareActive = ( sceneLinear &&
		selectedBackend != ROUTPUT_BACKEND_SDR_SRGB ) ? qtrue : qfalse;

	if ( maxOutput < paperWhite ) {
		maxOutput = paperWhite;
	}
	if ( outputHardwareActive && state && state->displayOutput.maxLuminanceNits > 0.0f ) {
		maxOutput = GLX_PostProcess_ClampFloat( state->displayOutput.maxLuminanceNits,
			paperWhite, maxOutput );
	}
	if ( gradeMode < 0 ) {
		gradeMode = 0;
	} else if ( gradeMode > 3 ) {
		gradeMode = 3;
	}

	output.transfer = outputHardwareActive ? GLX_PostProcess_OutputTransferForBackend( selectedBackend ) :
		OutputTransfer::SdrSrgb;
	output.sceneColorSpace = sceneLinear ? SceneColorSpace::SceneLinear : SceneColorSpace::DisplayReferredSdr;
	output.toneMap = GLX_PostProcess_ToneMapOperatorForMode( toneMapMode );
	output.grade = GLX_PostProcess_ColorGradeForMode( gradeMode );
	output.requestedBackend = outputRequest;
	output.selectedBackend = selectedBackend;
	output.nativeBackend = state ? state->displayOutput.nativeBackend : ROUTPUT_BACKEND_SDR_SRGB;
	output.outputHardwareActive = outputHardwareActive;
	output.outputExperimental = ( selectedBackend == ROUTPUT_BACKEND_LINUX_EXPERIMENTAL_HDR ) ? qtrue : qfalse;
	output.displayHdrEnabled = ( state && state->displayOutput.hdrEnabled ) ? qtrue : qfalse;
	output.displayHdrHeadroomValid = ( state && state->displayOutput.hdrHeadroomValid ) ? qtrue : qfalse;
	output.displayIccProfileAvailable = ( state && state->displayOutput.iccProfileAvailable ) ? qtrue : qfalse;
	output.displayIccProfileBytes = state ? state->displayOutput.iccProfileBytes : 0;
	output.hdrMode = sceneLinear ? 1 : 0;
	output.precisionMode = GLX_PostProcess_HdrPrecisionMode( state, hdrMode );
	output.renderScaleMode = renderScaleMode;
	output.exposure = exposure;
	output.bloomThreshold = bloomThreshold;
	output.bloomSoftKnee = bloomSoftKnee;
	output.paperWhiteNits = paperWhite;
	output.maxOutputNits = maxOutput;
	output.displayHdrHeadroom = state ? state->displayOutput.hdrHeadroom : 1.0f;
	output.displaySdrWhiteNits = state ? state->displayOutput.sdrWhiteNits : 203.0f;
	output.displayMaxNits = state ? state->displayOutput.maxLuminanceNits : 203.0f;
	output.greyscale = greyscale;
	GLX_PostProcess_ParseVec3Cvar( state ? state->r_colorGradeLift : nullptr,
		0.0f, 0.0f, 0.0f, -1.0f, 1.0f, output.gradeLift );
	GLX_PostProcess_ParseVec3Cvar( state ? state->r_colorGradeGamma : nullptr,
		1.0f, 1.0f, 1.0f, 0.1f, 8.0f, output.gradeGamma );
	GLX_PostProcess_ParseVec3Cvar( state ? state->r_colorGradeGain : nullptr,
		1.0f, 1.0f, 1.0f, 0.0f, 8.0f, output.gradeGain );
	output.whitePointSourceKelvin = ( sceneLinear && state && state->r_colorGradeWhitePoint ) ?
		GLX_PostProcess_ClampFloat( state->r_colorGradeWhitePoint->value, 1000.0f, 40000.0f ) : 6504.0f;
	output.whitePointTargetKelvin = ( sceneLinear && state && state->r_colorGradeAdaptWhitePoint ) ?
		GLX_PostProcess_ClampFloat( state->r_colorGradeAdaptWhitePoint->value, 1000.0f, 40000.0f ) : 6504.0f;
	output.lutScale = ( sceneLinear && state && state->r_colorGradeLUTScale ) ?
		GLX_PostProcess_ClampFloat( state->r_colorGradeLUTScale->value, 1.0f, 32.0f ) : 4.0f;
	output.lutSize = ( output.grade == ColorGradeMode::Lut3D ||
		output.grade == ColorGradeMode::LiftGammaGainLut3D ) ? 16.0f : 0.0f;
	if ( output.grade == ColorGradeMode::None || output.grade == ColorGradeMode::Lut3D ) {
		output.gradeLift[0] = output.gradeLift[1] = output.gradeLift[2] = 0.0f;
		output.gradeGamma[0] = output.gradeGamma[1] = output.gradeGamma[2] = 1.0f;
		output.gradeGain[0] = output.gradeGain[1] = output.gradeGain[2] = 1.0f;
		output.whitePointSourceKelvin = 6504.0f;
		output.whitePointTargetKelvin = 6504.0f;
	}
	return output;
}

static void GLX_PostProcess_CopyOutputDetails( PostProcessState *state )
{
	if ( !state ) {
		return;
	}

	state->lastExposure = state->lastOutput.exposure;
	state->lastBloomThreshold = state->lastOutput.bloomThreshold;
	state->lastBloomSoftKnee = state->lastOutput.bloomSoftKnee;
	state->lastPaperWhiteNits = state->lastOutput.paperWhiteNits;
	state->lastMaxOutputNits = state->lastOutput.maxOutputNits;
	for ( int i = 0; i < 3; i++ ) {
		state->lastGradeLift[i] = state->lastOutput.gradeLift[i];
		state->lastGradeGamma[i] = state->lastOutput.gradeGamma[i];
		state->lastGradeGain[i] = state->lastOutput.gradeGain[i];
	}
	state->lastWhitePointSourceKelvin = state->lastOutput.whitePointSourceKelvin;
	state->lastWhitePointTargetKelvin = state->lastOutput.whitePointTargetKelvin;
	state->lastColorGradeLutSize = state->lastOutput.lutSize;
	state->lastColorGradeLutScale = state->lastOutput.lutScale;
	state->lastRequestedBackend = state->lastOutput.requestedBackend;
	state->lastSelectedBackend = state->lastOutput.selectedBackend;
	state->lastNativeBackend = state->lastOutput.nativeBackend;
	state->lastOutputHardwareActive = state->lastOutput.outputHardwareActive;
	state->lastOutputExperimental = state->lastOutput.outputExperimental;
	state->lastDisplayHdrEnabled = state->lastOutput.displayHdrEnabled;
	state->lastDisplayHdrHeadroomValid = state->lastOutput.displayHdrHeadroomValid;
	state->lastDisplayIccProfileAvailable = state->lastOutput.displayIccProfileAvailable;
	state->lastDisplayIccProfileBytes = state->lastOutput.displayIccProfileBytes;
	state->lastDisplayHdrHeadroom = state->lastOutput.displayHdrHeadroom;
	state->lastDisplaySdrWhiteNits = state->lastOutput.displaySdrWhiteNits;
	state->lastDisplayMaxNits = state->lastOutput.displayMaxNits;
}

const char *GLX_PostProcess_ResultName( int result )
{
	switch ( result ) {
	case GLX_POSTPROCESS_RESULT_BLOOM_FINAL:
		return "bloom-final";
	case GLX_POSTPROCESS_RESULT_GAMMA_DIRECT:
		return "gamma-direct";
	case GLX_POSTPROCESS_RESULT_GAMMA_BLIT:
		return "gamma-blit";
	case GLX_POSTPROCESS_RESULT_MINIMIZED:
		return "minimized";
	default:
		return "none";
	}
}

const char *GLX_PostProcess_BloomCreateResultName( int result )
{
	switch ( result ) {
	case GLX_BLOOM_CREATE_SUCCESS:
		return "success";
	case GLX_BLOOM_CREATE_TEXTURE_UNITS:
		return "texture-units";
	case GLX_BLOOM_CREATE_FBO:
		return "fbo";
	default:
		return "none";
	}
}

const char *GLX_PostProcess_BloomResultName( int result )
{
	switch ( result ) {
	case GLX_BLOOM_RESULT_SKIPPED:
		return "skipped";
	case GLX_BLOOM_RESULT_INTERMEDIATE:
		return "intermediate";
	case GLX_BLOOM_RESULT_FINAL:
		return "final";
	case GLX_BLOOM_RESULT_CREATE_FAILED:
		return "create-failed";
	default:
		return "none";
	}
}

void GLX_PostProcess_RegisterCvars( PostProcessState *state )
{
	if ( !state ) {
		return;
	}

	state->r_glxPostProcessDebug = RI().Cvar_Get( "r_glxPostProcessDebug", "0",
		CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxPostProcessDebug,
		"Print GLx framebuffer, render-scale, gamma, and bloom parity diagnostics." );
	state->r_hdr = RI().Cvar_Get( "r_hdr", "0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_hdr,
		"Selects the scene-linear HDR render pipeline. Internal framebuffer storage precision is controlled by r_hdrPrecision." );
	state->r_hdrPrecision = RI().Cvar_Get( "r_hdrPrecision", "0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_hdrPrecision,
		"Internal FBO color precision: 0 automatic, -1 debug 4-bit, 8 force 8-bit, 16 force 16-bit." );
	state->r_srgbTextures = RI().Cvar_Get( "r_srgbTextures", "1", CVAR_ARCHIVE_ND | CVAR_LATCH );
	RI().Cvar_SetDescription( state->r_srgbTextures,
		"Use sRGB texture formats for authored color images in the scene-linear HDR pipeline." );
	state->r_framebufferSRGB = RI().Cvar_Get( "r_framebufferSRGB", "1", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_framebufferSRGB,
		"Allow GL_FRAMEBUFFER_SRGB when the draw target is an sRGB framebuffer." );
	state->r_tonemap = RI().Cvar_Get( "r_tonemap", "0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_tonemap,
		"Final-pass tone mapper for the scene-linear HDR pipeline: 0 legacy, 1 Reinhard, 2 ACES." );
	state->r_tonemapExposure = RI().Cvar_Get( "r_tonemapExposure", "1.0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_tonemapExposure,
		"Exposure multiplier used by scene-linear tone mapping and bloom extraction." );
	state->r_colorGrade = RI().Cvar_Get( "r_colorGrade", "0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_colorGrade,
		"Scene-linear color grading for r_hdr 1: 0 none, 1 lift/gamma/gain, 2 3D LUT, 3 both." );
	state->r_colorGradeLift = RI().Cvar_Get( "r_colorGradeLift", "0 0 0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_colorGradeLift,
		"Lift offset applied to scene-linear RGB before tone mapping." );
	state->r_colorGradeGamma = RI().Cvar_Get( "r_colorGradeGamma", "1 1 1", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_colorGradeGamma,
		"Per-channel color-grade gamma for scene-linear RGB." );
	state->r_colorGradeGain = RI().Cvar_Get( "r_colorGradeGain", "1 1 1", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_colorGradeGain,
		"Per-channel scene-linear gain applied before tone mapping." );
	state->r_colorGradeWhitePoint = RI().Cvar_Get( "r_colorGradeWhitePoint", "6504", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_colorGradeWhitePoint,
		"Source scene white point in Kelvin for Bradford chromatic adaptation." );
	state->r_colorGradeAdaptWhitePoint = RI().Cvar_Get( "r_colorGradeAdaptWhitePoint", "6504", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_colorGradeAdaptWhitePoint,
		"Target scene white point in Kelvin for Bradford chromatic adaptation." );
	state->r_colorGradeLUT = RI().Cvar_Get( "r_colorGradeLUT", "", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_colorGradeLUT,
		"Optional 3D LUT atlas image. Layout is width N*N, height N, with horizontal blue slices." );
	state->r_colorGradeLUTScale = RI().Cvar_Get( "r_colorGradeLUTScale", "4.0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_colorGradeLUTScale,
		"Scene-linear range represented by the 3D LUT atlas." );
	state->r_hdrDisplayPaperWhite = RI().Cvar_Get( "r_hdrDisplayPaperWhite", "203", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_hdrDisplayPaperWhite,
		"SDR reference white level in nits for color-managed output transforms." );
	state->r_hdrDisplayMaxLuminance = RI().Cvar_Get( "r_hdrDisplayMaxLuminance", "1000", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_hdrDisplayMaxLuminance,
		"Display/output maximum luminance in nits for tone scale and HDR metadata." );
	state->r_outputBackend = RI().Cvar_Get( "r_outputBackend", "0", CVAR_ARCHIVE_ND | CVAR_LATCH );
	RI().Cvar_SetDescription( state->r_outputBackend,
		"Final display output backend: 0 auto, 1 SDR sRGB, 2 Windows scRGB, 3 HDR10 PQ, 4 macOS EDR, 5 Linux experimental HDR." );
	state->r_outputAllowExperimentalLinuxHDR = RI().Cvar_Get( "r_outputAllowExperimentalLinuxHDR", "0", CVAR_ARCHIVE_ND | CVAR_LATCH );
	RI().Cvar_SetDescription( state->r_outputAllowExperimentalLinuxHDR,
		"Allow Linux HDR output only when SDL reports HDR headroom and an explicit compositor/protocol path." );
	state->r_bloom_threshold = RI().Cvar_Get( "r_bloom_threshold", "0.75", CVAR_ARCHIVE_ND );
	state->r_bloom_threshold_mode = RI().Cvar_Get( "r_bloom_threshold_mode", "0", CVAR_ARCHIVE_ND );
	state->r_bloom_soft_knee = RI().Cvar_Get( "r_bloom_soft_knee", "0.0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( state->r_bloom_soft_knee,
		"Softens scene-linear bloom extraction around r_bloom_threshold." );
	state->lastOutput = GLX_RenderIR_DefaultOutputTransform();
	GLX_PostProcess_QueryDisplayOutput( state );
	state->hdrPrecisionMode = state->lastOutput.precisionMode;
	GLX_PostProcess_CopyOutputDetails( state );
}

void GLX_PostProcess_OnOpenGLReady( PostProcessState *state, const Capabilities &caps )
{
	if ( !state ) {
		return;
	}

	state->glReady = qtrue;
	if ( caps.config ) {
		state->vidWidth = caps.config->vidWidth;
		state->vidHeight = caps.config->vidHeight;
	}
	GLX_PostProcess_QueryDisplayOutput( state );
	state->lastOutput = GLX_PostProcess_MakeOutputTransform( state,
		state->hdrMode, state->renderScaleMode, state->lastGreyscale );
	state->hdrPrecisionMode = state->lastOutput.precisionMode;
	state->toneMapMode = static_cast<int>( state->lastOutput.toneMap );
	GLX_PostProcess_CopyOutputDetails( state );
	GLX_PostProcess_SetReason( state, "waiting for FBO initialization" );
}

void GLX_PostProcess_Shutdown( PostProcessState *state )
{
	if ( !state ) {
		return;
	}

	state->glReady = qfalse;
	state->fboReady = qfalse;
	state->programReady = qfalse;
	state->framebufferFnsReady = qfalse;
	GLX_PostProcess_SetReason( state, "renderer shutdown" );
}

void GLX_PostProcess_RecordFboInit( PostProcessState *state, qboolean requested, qboolean ready,
	qboolean programReady, qboolean framebufferFnsReady, int vidWidth, int vidHeight,
	int captureWidth, int captureHeight, int windowWidth, int windowHeight,
	int internalFormat, int textureFormat, int textureType, qboolean multiSampled,
	qboolean superSampled, qboolean windowAdjusted, int blitFilter, int hdrMode,
	int renderScaleMode, int bloomMode, qboolean textureSrgbAvailable,
	qboolean framebufferSrgbAvailable, qboolean framebufferSrgbEnabled )
{
	if ( !state ) {
		return;
	}

	state->fboInitAttempts++;
	state->fboRequested = requested;
	state->fboReady = ready;
	state->programReady = programReady;
	state->framebufferFnsReady = framebufferFnsReady;
	state->vidWidth = vidWidth;
	state->vidHeight = vidHeight;
	state->captureWidth = captureWidth;
	state->captureHeight = captureHeight;
	state->windowWidth = windowWidth;
	state->windowHeight = windowHeight;
	state->internalFormat = internalFormat;
	state->textureFormat = textureFormat;
	state->textureType = textureType;
	state->multiSampled = multiSampled;
	state->superSampled = superSampled;
	state->windowAdjusted = windowAdjusted;
	state->blitFilter = blitFilter;
	state->hdrMode = hdrMode;
	state->renderScaleMode = renderScaleMode;
	state->bloomMode = bloomMode;
	state->textureSrgbAvailable = textureSrgbAvailable;
	state->textureSrgbDecode = ( state->r_srgbTextures && state->r_srgbTextures->integer &&
		textureSrgbAvailable && hdrMode > 0 ) ? qtrue : qfalse;
	state->framebufferSrgbAvailable = framebufferSrgbAvailable;
	state->framebufferSrgbEnabled = framebufferSrgbEnabled;
	GLX_PostProcess_QueryDisplayOutput( state );
	state->lastOutput = GLX_PostProcess_MakeOutputTransform( state,
		hdrMode, renderScaleMode, state->lastGreyscale );
	state->hdrPrecisionMode = state->lastOutput.precisionMode;
	state->toneMapMode = static_cast<int>( state->lastOutput.toneMap );
	state->bloomThresholdMode = state->r_bloom_threshold_mode ? state->r_bloom_threshold_mode->integer : 0;
	GLX_PostProcess_CopyOutputDetails( state );

	if ( !requested ) {
		state->fboDisabledInits++;
		GLX_PostProcess_SetReason( state, "r_fbo disabled" );
	} else if ( !programReady || !framebufferFnsReady ) {
		state->fboInitFailures++;
		GLX_PostProcess_SetReason( state, "FBO or ARB program functions unavailable" );
	} else if ( ready ) {
		state->fboInitSuccesses++;
		GLX_PostProcess_SetReason( state, "FBO ready" );
	} else {
		state->fboInitFailures++;
		GLX_PostProcess_SetReason( state, "FBO creation failed" );
	}

	if ( state->r_glxPostProcessDebug && state->r_glxPostProcessDebug->integer ) {
		RI().Printf( PRINT_ALL,
			"GLx postprocess FBO init: requested %s, ready %s, size %ix%i, capture %ix%i, scene-linear HDR %i, precision %i, bloom %i, %s\n",
			BoolName( requested ), BoolName( ready ), vidWidth, vidHeight, captureWidth, captureHeight,
			state->lastOutput.hdrMode, state->hdrPrecisionMode, bloomMode, state->reason );
	}
}

void GLX_PostProcess_RecordFboShutdown( PostProcessState *state )
{
	if ( !state ) {
		return;
	}

	if ( state->fboReady || state->fboRequested ) {
		state->fboShutdowns++;
	}

	state->fboReady = qfalse;
	state->multiSampled = qfalse;
	state->superSampled = qfalse;
	GLX_PostProcess_SetReason( state, "FBO shutdown" );
}

void GLX_PostProcess_RecordFrame( PostProcessState *state, qboolean minimized, qboolean bloomAvailable,
	qboolean programReady, int screenshotMask, qboolean windowAdjusted, int fboReadIndex,
	int hdrMode, int renderScaleMode, float greyscale )
{
	if ( !state ) {
		return;
	}

	state->frames++;
	state->lastBloomAvailable = bloomAvailable;
	state->programReady = programReady;
	state->lastScreenshotMask = screenshotMask;
	state->windowAdjusted = windowAdjusted;
	state->lastFboReadIndex = fboReadIndex;
	state->hdrMode = hdrMode;
	state->renderScaleMode = renderScaleMode;
	state->lastGreyscale = greyscale;
	state->textureSrgbDecode = ( state->r_srgbTextures && state->r_srgbTextures->integer &&
		state->textureSrgbAvailable && hdrMode > 0 ) ? qtrue : qfalse;
	if ( state->frames == 1 || ( state->frames % 120u ) == 0u ) {
		GLX_PostProcess_QueryDisplayOutput( state );
	}
	state->lastOutput = GLX_PostProcess_MakeOutputTransform( state,
		hdrMode, renderScaleMode, greyscale );
	state->hdrPrecisionMode = state->lastOutput.precisionMode;
	state->toneMapMode = static_cast<int>( state->lastOutput.toneMap );
	state->bloomThresholdMode = state->r_bloom_threshold_mode ? state->r_bloom_threshold_mode->integer : 0;
	GLX_PostProcess_CopyOutputDetails( state );

	if ( minimized ) {
		state->minimizedFrames++;
	}
	if ( bloomAvailable ) {
		state->bloomAvailableFrames++;
	}
	if ( screenshotMask ) {
		state->screenshotFrames++;
	}
	if ( windowAdjusted ) {
		state->windowAdjustedFrames++;
	}
	if ( state->lastOutput.hdrMode ) {
		state->hdrFrames++;
		state->sceneLinearFrames++;
	}
	if ( state->lastOutput.toneMap != ToneMapOperator::Legacy ) {
		state->toneMappedFrames++;
	}
	if ( state->lastOutput.grade != ColorGradeMode::None ) {
		state->gradedFrames++;
	}
	if ( renderScaleMode ) {
		state->renderScaleFrames++;
	}
	if ( greyscale != 0.0f ) {
		state->greyscaleFrames++;
	}
}

void GLX_PostProcess_RecordFrameResult( PostProcessState *state, int result )
{
	if ( !state ) {
		return;
	}

	state->lastResult = result;
	switch ( result ) {
	case GLX_POSTPROCESS_RESULT_BLOOM_FINAL:
		state->bloomFinalFrames++;
		break;
	case GLX_POSTPROCESS_RESULT_GAMMA_DIRECT:
		state->gammaDirectFrames++;
		break;
	case GLX_POSTPROCESS_RESULT_GAMMA_BLIT:
		state->gammaBlitFrames++;
		break;
	case GLX_POSTPROCESS_RESULT_MINIMIZED:
		state->minimizedOutputFrames++;
		break;
	default:
		break;
	}
}

void GLX_PostProcess_RecordBloomCreate( PostProcessState *state, int result,
	int requestedPasses, int effectivePasses, int textureUnits )
{
	if ( !state ) {
		return;
	}

	state->bloomCreateAttempts++;
	state->lastBloomCreateResult = result;
	state->lastBloomRequestedPasses = requestedPasses;
	state->lastBloomEffectivePasses = effectivePasses;
	state->lastBloomTextureUnits = textureUnits;

	switch ( result ) {
	case GLX_BLOOM_CREATE_SUCCESS:
		state->bloomCreateSuccesses++;
		GLX_PostProcess_SetReason( state, "bloom FBO chain ready" );
		break;
	case GLX_BLOOM_CREATE_TEXTURE_UNITS:
		state->bloomCreateTextureUnitFailures++;
		GLX_PostProcess_SetReason( state, "not enough texture units for requested bloom passes" );
		break;
	case GLX_BLOOM_CREATE_FBO:
		state->bloomCreateFboFailures++;
		GLX_PostProcess_SetReason( state, "bloom FBO creation failed" );
		break;
	default:
		break;
	}

	if ( state->r_glxPostProcessDebug && state->r_glxPostProcessDebug->integer ) {
		RI().Printf( PRINT_ALL, "GLx bloom create: %s, requested/effective passes %i/%i, texture units %i\n",
			GLX_PostProcess_BloomCreateResultName( result ), requestedPasses, effectivePasses, textureUnits );
	}
}

void GLX_PostProcess_RecordBloom( PostProcessState *state, int result, qboolean finalStage,
	int bloomMode, int requestedPasses, int effectivePasses, int blendBase, int filterSize,
	int textureUnits, int thresholdMode, int modulate, float threshold, float intensity,
	float reflection )
{
	if ( !state ) {
		return;
	}

	state->bloomCalls++;
	state->lastBloomResult = result;
	state->lastBloomFinalStage = finalStage;
	state->lastBloomMode = bloomMode;
	state->lastBloomRequestedPasses = requestedPasses;
	state->lastBloomEffectivePasses = effectivePasses;
	state->lastBloomBlendBase = blendBase;
	state->lastBloomFilterSize = filterSize;
	state->lastBloomTextureUnits = textureUnits;
	state->lastBloomThresholdMode = thresholdMode;
	state->lastBloomModulate = modulate;
	state->lastBloomThreshold = threshold;
	state->lastBloomIntensity = intensity;
	state->lastBloomReflection = reflection;
	state->bloomMode = bloomMode;
	state->bloomThresholdMode = thresholdMode;
	state->lastOutput.bloomThreshold = threshold;
	state->lastOutput.bloomSoftKnee = state->r_bloom_soft_knee ?
		GLX_PostProcess_ClampFloat( state->r_bloom_soft_knee->value, 0.0f, 1.0f ) :
		state->lastOutput.bloomSoftKnee;
	state->lastBloomSoftKnee = state->lastOutput.bloomSoftKnee;

	switch ( result ) {
	case GLX_BLOOM_RESULT_SKIPPED:
		state->bloomSkips++;
		break;
	case GLX_BLOOM_RESULT_INTERMEDIATE:
		state->bloomRendered++;
		state->bloomIntermediatePasses++;
		if ( bloomMode == 1 ) {
			state->bloomMode1Passes++;
		} else if ( bloomMode == 2 ) {
			state->bloomMode2Passes++;
		}
		break;
	case GLX_BLOOM_RESULT_FINAL:
		state->bloomRendered++;
		state->bloomFinalPasses++;
		if ( bloomMode == 1 ) {
			state->bloomMode1Passes++;
		} else if ( bloomMode == 2 ) {
			state->bloomMode2Passes++;
		}
		break;
	case GLX_BLOOM_RESULT_CREATE_FAILED:
		state->bloomFailures++;
		break;
	default:
		break;
	}

	if ( ( result == GLX_BLOOM_RESULT_INTERMEDIATE || result == GLX_BLOOM_RESULT_FINAL ) &&
		reflection != 0.0f ) {
		state->bloomReflectionPasses++;
	}

	if ( state->r_glxPostProcessDebug && state->r_glxPostProcessDebug->integer > 1 ) {
		RI().Printf( PRINT_ALL,
			"GLx bloom: %s, final %s, mode %i, passes %i/%i, blend base %i, filter %i, reflection %.2f\n",
			GLX_PostProcess_BloomResultName( result ), BoolName( finalStage ), bloomMode,
			requestedPasses, effectivePasses, blendBase, filterSize, reflection );
	}
}

void GLX_PostProcess_RecordCopyScreen( PostProcessState *state, int viewportWidth, int viewportHeight )
{
	if ( !state ) {
		return;
	}

	state->copyScreenCalls++;
	state->lastFboReadIndex = 2;

	if ( state->r_glxPostProcessDebug && state->r_glxPostProcessDebug->integer > 1 ) {
		RI().Printf( PRINT_ALL, "GLx postprocess screen-map copy: viewport %ix%i\n",
			viewportWidth, viewportHeight );
	}
}

void GLX_PostProcess_RecordBlit( PostProcessState *state, int kind, qboolean depthOnly,
	int srcWidth, int srcHeight, int dstWidth, int dstHeight )
{
	if ( !state ) {
		return;
	}

	if ( kind == GLX_FBO_BLIT_MS ) {
		state->msaaBlits++;
		if ( depthOnly ) {
			state->msaaDepthBlits++;
		}
	} else if ( kind == GLX_FBO_BLIT_SS ) {
		state->ssaaBlits++;
	}

	if ( state->r_glxPostProcessDebug && state->r_glxPostProcessDebug->integer > 1 ) {
		RI().Printf( PRINT_ALL, "GLx postprocess blit: %s %ix%i -> %ix%i%s\n",
			kind == GLX_FBO_BLIT_SS ? "ssaa" : "msaa",
			srcWidth, srcHeight, dstWidth, dstHeight, depthOnly ? " depth" : "" );
	}
}

void GLX_PostProcess_PrintInfo( const PostProcessState &state )
{
	RI().Printf( PRINT_ALL, "\nGLx postprocess parity\n" );
	RI().Printf( PRINT_ALL,
		"  FBO: requested %s, ready %s, programs %s, framebuffer funcs %s, reason: %s\n",
		BoolName( state.fboRequested ), BoolName( state.fboReady ),
		BoolName( state.programReady ), BoolName( state.framebufferFnsReady ),
		state.reason[0] ? state.reason : "none" );
	RI().Printf( PRINT_ALL,
		"  target: render %ix%i, capture %ix%i, window %ix%i, format 0x%04x (0x%04x:0x%04x)\n",
		state.vidWidth, state.vidHeight, state.captureWidth, state.captureHeight,
		state.windowWidth, state.windowHeight, state.internalFormat,
		state.textureFormat, state.textureType );
	RI().Printf( PRINT_ALL,
		"  controls: scene-linear HDR %s, precision %i, renderScale %i, bloom %i, MSAA %s, supersample %s, adjusted window %s, greyscale %.2f\n",
		BoolName( state.lastOutput.hdrMode ? qtrue : qfalse ), state.hdrPrecisionMode,
		state.renderScaleMode, state.bloomMode,
		BoolName( state.multiSampled ), BoolName( state.superSampled ),
		BoolName( state.windowAdjusted ), state.lastGreyscale );
	RI().Printf( PRINT_ALL,
		"  color pipeline: space %s, transfer %s, tone-map %s, exposure %.2f, grade %s, paper-white %.0f nits, max %.0f nits\n",
		GLX_RenderIR_SceneColorSpaceName( state.lastOutput.sceneColorSpace ),
		GLX_RenderIR_OutputTransferName( state.lastOutput.transfer ),
		GLX_RenderIR_ToneMapName( state.lastOutput.toneMap ),
		state.lastOutput.exposure,
		GLX_RenderIR_ColorGradeName( state.lastOutput.grade ),
		state.lastOutput.paperWhiteNits,
		state.lastOutput.maxOutputNits );
	RI().Printf( PRINT_ALL,
		"  output backend: request %s, selected %s, native %s, hardware %s, experimental %s, display-hdr %s, headroom %.2f, sdr-white %.0f nits, display-max %.0f nits, icc %s/%i, driver %s, display %s, reason: %s\n",
		RendererOutputRequestName( state.lastOutput.requestedBackend ),
		RendererOutputBackendName( state.lastOutput.selectedBackend ),
		RendererOutputBackendName( state.lastOutput.nativeBackend ),
		BoolName( state.lastOutput.outputHardwareActive ),
		BoolName( state.lastOutput.outputExperimental ),
		BoolName( state.lastOutput.displayHdrEnabled ),
		state.lastOutput.displayHdrHeadroom,
		state.lastOutput.displaySdrWhiteNits,
		state.lastOutput.displayMaxNits,
		BoolName( state.lastOutput.displayIccProfileAvailable ),
		state.lastOutput.displayIccProfileBytes,
		state.displayOutput.videoDriver[0] ? state.displayOutput.videoDriver : "unknown",
		state.displayOutput.displayName[0] ? state.displayOutput.displayName : "unknown",
		state.displayOutput.reason[0] ? state.displayOutput.reason : "none" );
	RI().Printf( PRINT_ALL,
		"  color grade stage: mode %s, lift %.2f/%.2f/%.2f, gamma %.2f/%.2f/%.2f, gain %.2f/%.2f/%.2f, white-point %.0f->%.0f K, lut-size %.0f, lut-scale %.2f\n",
		GLX_RenderIR_ColorGradeName( state.lastOutput.grade ),
		state.lastGradeLift[0], state.lastGradeLift[1], state.lastGradeLift[2],
		state.lastGradeGamma[0], state.lastGradeGamma[1], state.lastGradeGamma[2],
		state.lastGradeGain[0], state.lastGradeGain[1], state.lastGradeGain[2],
		state.lastWhitePointSourceKelvin, state.lastWhitePointTargetKelvin,
		state.lastColorGradeLutSize, state.lastColorGradeLutScale );
	RI().Printf( PRINT_ALL,
		"  color audit: srgb-decode %s requested %s available %s, framebuffer-srgb %s requested %s available %s, capture sdr-srgb\n",
		BoolName( state.textureSrgbDecode ),
		BoolName( state.r_srgbTextures && state.r_srgbTextures->integer ? qtrue : qfalse ),
		BoolName( state.textureSrgbAvailable ),
		BoolName( state.framebufferSrgbEnabled ),
		BoolName( state.r_framebufferSRGB && state.r_framebufferSRGB->integer ? qtrue : qfalse ),
		BoolName( state.framebufferSrgbAvailable ) );
	RI().Printf( PRINT_ALL,
		"  FBO lifecycle: %u init attempts, %u ready, %u failed, %u disabled, %u shutdowns\n",
		state.fboInitAttempts, state.fboInitSuccesses, state.fboInitFailures,
		state.fboDisabledInits, state.fboShutdowns );
	RI().Printf( PRINT_ALL,
		"  frames: %u post, %u bloom-final, %u gamma-direct, %u gamma-blit, %u minimized output, %u screenshots\n",
		state.frames, state.bloomFinalFrames, state.gammaDirectFrames,
		state.gammaBlitFrames, state.minimizedOutputFrames, state.screenshotFrames );
	RI().Printf( PRINT_ALL,
		"  frame features: %u bloom-available, %u scene-linear, %u tone-mapped, %u graded, %u render-scale, %u greyscale, %u window-adjusted, %u minimized\n",
		state.bloomAvailableFrames, state.sceneLinearFrames, state.toneMappedFrames,
		state.gradedFrames, state.renderScaleFrames,
		state.greyscaleFrames, state.windowAdjustedFrames, state.minimizedFrames );
	RI().Printf( PRINT_ALL,
		"  bloom create: last %s, %u/%u ready, texture-unit failures %u, FBO failures %u\n",
		GLX_PostProcess_BloomCreateResultName( state.lastBloomCreateResult ),
		state.bloomCreateSuccesses, state.bloomCreateAttempts,
		state.bloomCreateTextureUnitFailures, state.bloomCreateFboFailures );
	RI().Printf( PRINT_ALL,
		"  bloom passes: calls %u, rendered %u, final %u, pre-final %u, skipped %u, failures %u, mode1 %u, mode2 %u, reflections %u\n",
		state.bloomCalls, state.bloomRendered, state.bloomFinalPasses,
		state.bloomIntermediatePasses, state.bloomSkips, state.bloomFailures,
		state.bloomMode1Passes, state.bloomMode2Passes, state.bloomReflectionPasses );
	RI().Printf( PRINT_ALL,
		"  bloom config: last %s, requested/effective passes %i/%i, blend base %i, filter %i, units %i, threshold %.2f mode %i, soft-knee %.2f, modulate %i, intensity %.2f, reflection %.2f\n",
		GLX_PostProcess_BloomResultName( state.lastBloomResult ),
		state.lastBloomRequestedPasses, state.lastBloomEffectivePasses,
		state.lastBloomBlendBase, state.lastBloomFilterSize, state.lastBloomTextureUnits,
		state.lastBloomThreshold, state.lastBloomThresholdMode, state.lastBloomSoftKnee, state.lastBloomModulate,
		state.lastBloomIntensity, state.lastBloomReflection );
	RI().Printf( PRINT_ALL,
		"  copies/blits: screen-map copies %u, MSAA blits %u (%u depth), SSAA blits %u, last output %s\n",
		state.copyScreenCalls, state.msaaBlits, state.msaaDepthBlits,
		state.ssaaBlits, GLX_PostProcess_ResultName( state.lastResult ) );
}

} // namespace glx
