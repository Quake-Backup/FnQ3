#ifndef GLX_POSTPROCESS_H
#define GLX_POSTPROCESS_H

#include "glx_local.h"
#include "glx_render_ir.h"

namespace glx {

struct PostProcessState {
	cvar_t *r_glxPostProcessDebug;
	cvar_t *r_hdr;
	cvar_t *r_hdrPrecision;
	cvar_t *r_srgbTextures;
	cvar_t *r_framebufferSRGB;
	cvar_t *r_tonemap;
	cvar_t *r_tonemapExposure;
	cvar_t *r_colorGrade;
	cvar_t *r_colorGradeLift;
	cvar_t *r_colorGradeGamma;
	cvar_t *r_colorGradeGain;
	cvar_t *r_colorGradeWhitePoint;
	cvar_t *r_colorGradeAdaptWhitePoint;
	cvar_t *r_colorGradeLUT;
	cvar_t *r_colorGradeLUTScale;
	cvar_t *r_hdrDisplayPaperWhite;
	cvar_t *r_hdrDisplayMaxLuminance;
	cvar_t *r_outputBackend;
	cvar_t *r_outputAllowExperimentalLinuxHDR;
	cvar_t *r_bloom_threshold;
	cvar_t *r_bloom_threshold_mode;
	cvar_t *r_bloom_soft_knee;
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
	int hdrPrecisionMode;
	int toneMapMode;
	int renderScaleMode;
	int bloomMode;
	int bloomThresholdMode;
	int lastFboReadIndex;
	int lastScreenshotMask;
	int lastResult;
	qboolean textureSrgbAvailable;
	qboolean textureSrgbDecode;
	qboolean framebufferSrgbAvailable;
	qboolean framebufferSrgbEnabled;
	rendererDisplayOutput_t displayOutput;
	OutputTransform lastOutput;
	qboolean lastBloomAvailable;
	qboolean lastBloomFinalStage;
	float lastGreyscale;
	float lastExposure;
	float lastBloomSoftKnee;
	float lastPaperWhiteNits;
	float lastMaxOutputNits;
	float lastGradeLift[3];
	float lastGradeGamma[3];
	float lastGradeGain[3];
	float lastWhitePointSourceKelvin;
	float lastWhitePointTargetKelvin;
	float lastColorGradeLutSize;
	float lastColorGradeLutScale;
	rendererOutputRequest_t lastRequestedBackend;
	rendererOutputBackend_t lastSelectedBackend;
	rendererOutputBackend_t lastNativeBackend;
	qboolean lastOutputHardwareActive;
	qboolean lastOutputExperimental;
	qboolean lastDisplayHdrEnabled;
	qboolean lastDisplayHdrHeadroomValid;
	qboolean lastDisplayIccProfileAvailable;
	int lastDisplayIccProfileBytes;
	float lastDisplayHdrHeadroom;
	float lastDisplaySdrWhiteNits;
	float lastDisplayMaxNits;
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
	unsigned int sceneLinearFrames;
	unsigned int toneMappedFrames;
	unsigned int gradedFrames;
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
	int renderScaleMode, int bloomMode, qboolean textureSrgbAvailable,
	qboolean framebufferSrgbAvailable, qboolean framebufferSrgbEnabled );
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
