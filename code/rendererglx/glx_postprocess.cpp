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
	int renderScaleMode, int bloomMode )
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
			"GLx postprocess FBO init: requested %s, ready %s, size %ix%i, capture %ix%i, HDR %i, bloom %i, %s\n",
			BoolName( requested ), BoolName( ready ), vidWidth, vidHeight, captureWidth, captureHeight,
			hdrMode, bloomMode, state->reason );
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
	if ( hdrMode ) {
		state->hdrFrames++;
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
		"  controls: HDR %i, renderScale %i, bloom %i, MSAA %s, supersample %s, adjusted window %s, greyscale %.2f\n",
		state.hdrMode, state.renderScaleMode, state.bloomMode,
		BoolName( state.multiSampled ), BoolName( state.superSampled ),
		BoolName( state.windowAdjusted ), state.lastGreyscale );
	RI().Printf( PRINT_ALL,
		"  FBO lifecycle: %u init attempts, %u ready, %u failed, %u disabled, %u shutdowns\n",
		state.fboInitAttempts, state.fboInitSuccesses, state.fboInitFailures,
		state.fboDisabledInits, state.fboShutdowns );
	RI().Printf( PRINT_ALL,
		"  frames: %u post, %u bloom-final, %u gamma-direct, %u gamma-blit, %u minimized output, %u screenshots\n",
		state.frames, state.bloomFinalFrames, state.gammaDirectFrames,
		state.gammaBlitFrames, state.minimizedOutputFrames, state.screenshotFrames );
	RI().Printf( PRINT_ALL,
		"  frame features: %u bloom-available, %u HDR, %u render-scale, %u greyscale, %u window-adjusted, %u minimized\n",
		state.bloomAvailableFrames, state.hdrFrames, state.renderScaleFrames,
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
		"  bloom config: last %s, requested/effective passes %i/%i, blend base %i, filter %i, units %i, threshold %.2f mode %i, modulate %i, intensity %.2f, reflection %.2f\n",
		GLX_PostProcess_BloomResultName( state.lastBloomResult ),
		state.lastBloomRequestedPasses, state.lastBloomEffectivePasses,
		state.lastBloomBlendBase, state.lastBloomFilterSize, state.lastBloomTextureUnits,
		state.lastBloomThreshold, state.lastBloomThresholdMode, state.lastBloomModulate,
		state.lastBloomIntensity, state.lastBloomReflection );
	RI().Printf( PRINT_ALL,
		"  copies/blits: screen-map copies %u, MSAA blits %u (%u depth), SSAA blits %u, last output %s\n",
		state.copyScreenCalls, state.msaaBlits, state.msaaDepthBlits,
		state.ssaaBlits, GLX_PostProcess_ResultName( state.lastResult ) );
}

} // namespace glx
