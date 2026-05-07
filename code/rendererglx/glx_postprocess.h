#ifndef GLX_POSTPROCESS_H
#define GLX_POSTPROCESS_H

#include "glx_local.h"

namespace glx {

struct PostProcessState {
	cvar_t *r_glxPostProcessDebug;
	qboolean glReady;
	qboolean fboRequested;
	qboolean fboReady;
	qboolean programReady;
	qboolean framebufferFnsReady;
	qboolean multiSampled;
	qboolean superSampled;
	qboolean windowAdjusted;
	int vidWidth;
	int vidHeight;
	int captureWidth;
	int captureHeight;
	int windowWidth;
	int windowHeight;
	int internalFormat;
	int textureFormat;
	int textureType;
	int blitFilter;
	int hdrMode;
	int renderScaleMode;
	int bloomMode;
	int lastFboReadIndex;
	int lastScreenshotMask;
	int lastResult;
	qboolean lastBloomAvailable;
	qboolean lastBloomFinalStage;
	float lastGreyscale;
	int lastBloomMode;
	int lastBloomRequestedPasses;
	int lastBloomEffectivePasses;
	int lastBloomBlendBase;
	int lastBloomFilterSize;
	int lastBloomTextureUnits;
	int lastBloomThresholdMode;
	int lastBloomModulate;
	float lastBloomThreshold;
	float lastBloomIntensity;
	float lastBloomReflection;
	int lastBloomCreateResult;
	int lastBloomResult;
	char reason[128];
	unsigned int fboInitAttempts;
	unsigned int fboInitSuccesses;
	unsigned int fboInitFailures;
	unsigned int fboDisabledInits;
	unsigned int fboShutdowns;
	unsigned int frames;
	unsigned int minimizedFrames;
	unsigned int renderScaleFrames;
	unsigned int hdrFrames;
	unsigned int greyscaleFrames;
	unsigned int windowAdjustedFrames;
	unsigned int screenshotFrames;
	unsigned int bloomAvailableFrames;
	unsigned int bloomFinalFrames;
	unsigned int gammaDirectFrames;
	unsigned int gammaBlitFrames;
	unsigned int minimizedOutputFrames;
	unsigned int copyScreenCalls;
	unsigned int msaaBlits;
	unsigned int msaaDepthBlits;
	unsigned int ssaaBlits;
	unsigned int bloomCreateAttempts;
	unsigned int bloomCreateSuccesses;
	unsigned int bloomCreateTextureUnitFailures;
	unsigned int bloomCreateFboFailures;
	unsigned int bloomCalls;
	unsigned int bloomSkips;
	unsigned int bloomRendered;
	unsigned int bloomIntermediatePasses;
	unsigned int bloomFinalPasses;
	unsigned int bloomFailures;
	unsigned int bloomMode1Passes;
	unsigned int bloomMode2Passes;
	unsigned int bloomReflectionPasses;
};

void GLX_PostProcess_RegisterCvars( PostProcessState *state );
void GLX_PostProcess_OnOpenGLReady( PostProcessState *state, const Capabilities &caps );
void GLX_PostProcess_Shutdown( PostProcessState *state );
void GLX_PostProcess_RecordFboInit( PostProcessState *state, qboolean requested, qboolean ready,
	qboolean programReady, qboolean framebufferFnsReady, int vidWidth, int vidHeight,
	int captureWidth, int captureHeight, int windowWidth, int windowHeight,
	int internalFormat, int textureFormat, int textureType, qboolean multiSampled,
	qboolean superSampled, qboolean windowAdjusted, int blitFilter, int hdrMode,
	int renderScaleMode, int bloomMode );
void GLX_PostProcess_RecordFboShutdown( PostProcessState *state );
void GLX_PostProcess_RecordFrame( PostProcessState *state, qboolean minimized, qboolean bloomAvailable,
	qboolean programReady, int screenshotMask, qboolean windowAdjusted, int fboReadIndex,
	int hdrMode, int renderScaleMode, float greyscale );
void GLX_PostProcess_RecordFrameResult( PostProcessState *state, int result );
void GLX_PostProcess_RecordBloomCreate( PostProcessState *state, int result,
	int requestedPasses, int effectivePasses, int textureUnits );
void GLX_PostProcess_RecordBloom( PostProcessState *state, int result, qboolean finalStage,
	int bloomMode, int requestedPasses, int effectivePasses, int blendBase, int filterSize,
	int textureUnits, int thresholdMode, int modulate, float threshold, float intensity,
	float reflection );
void GLX_PostProcess_RecordCopyScreen( PostProcessState *state, int viewportWidth, int viewportHeight );
void GLX_PostProcess_RecordBlit( PostProcessState *state, int kind, qboolean depthOnly,
	int srcWidth, int srcHeight, int dstWidth, int dstHeight );
void GLX_PostProcess_PrintInfo( const PostProcessState &state );
const char *GLX_PostProcess_ResultName( int result );
const char *GLX_PostProcess_BloomCreateResultName( int result );
const char *GLX_PostProcess_BloomResultName( int result );

} // namespace glx

#endif // GLX_POSTPROCESS_H
