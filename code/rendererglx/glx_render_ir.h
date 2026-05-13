#ifndef GLX_RENDER_IR_H
#define GLX_RENDER_IR_H

#include "glx_types.h"
#include "../renderercommon/tr_types.h"
#include "../renderercommon/tr_glx_public.h"

#include <cmath>

namespace glx {

enum class RenderProductKind {
	FramePass,
	WorldPacket,
	DynamicDraw,
	MaterialIR,
	UploadPlan,
	PostNode,
	OutputTransform
};

enum class FramePassKind {
	FrameSetup,
	SkyAndOpaqueWorld,
	OpaqueEntities,
	DynamicScene,
	TransparentLayers,
	FirstPersonWeapon,
	HudAnd2D,
	PostProcess,
	OutputExport
};

static constexpr int GLX_RENDER_IR_PASS_COUNT = 9;
static constexpr int GLX_RENDER_IR_PRODUCT_COUNT = 7;
static constexpr int GLX_RENDER_IR_PASS_SCHEDULE_TEXT_BYTES = 192;
static constexpr int GLX_RENDER_IR_MAX_POST_OUTPUT_NODES = 6;

struct FramePass {
	FramePassKind kind;
	int sequence;
	int sortStart;
	int sortEnd;
	unsigned int flags;
};

enum class UploadPlanKind {
	NoUpload,
	ClientMemory,
	TransientStream,
	StaticWorld,
	PostProcess,
	Readback
};

enum class UploadSyncPolicy {
	NoSync,
	Orphan,
	FrameFence,
	PersistentFence
};

struct UploadPlan {
	UploadPlanKind kind;
	int strategy;
	unsigned int buffer;
	unsigned int offset;
	unsigned int bytes;
	unsigned int vertexBytes;
	unsigned int indexBytes;
	unsigned int texcoordBytes;
	int alignment;
	UploadSyncPolicy sync;
};

struct MaterialIR {
	int sort;
	int flags;
	unsigned int stateBits;
	int rgbGen;
	int alphaGen;
	int rgbWaveFunc;
	int alphaWaveFunc;
	int tcGen0;
	int tcGen1;
	int texMods0;
	int texMods1;
	unsigned int texModTypes0;
	unsigned int texModTypes1;
	unsigned int texModSequence0;
	unsigned int texModSequence1;
	unsigned int texModWaveFuncs0;
	unsigned int texModWaveFuncs1;
	int fogAdjust;
	int materialCombine;
	qboolean fogPass;
	int shaderStagePasses;
};

struct MaterialFrameParameters {
	int sort;
	int shaderStagePasses;
	unsigned int featureMask;
};

struct MaterialObjectParameters {
	int rgbGen;
	int alphaGen;
	int rgbWaveFunc;
	int alphaWaveFunc;
	int tcGen0;
	int tcGen1;
};

struct MaterialStageParameters {
	int flags;
	unsigned int stateBits;
	int texMods0;
	int texMods1;
	unsigned int texModTypes0;
	unsigned int texModTypes1;
	unsigned int texModSequence0;
	unsigned int texModSequence1;
	unsigned int texModWaveFuncs0;
	unsigned int texModWaveFuncs1;
	int fogAdjust;
	int materialCombine;
	qboolean fogPass;
};

struct MaterialParameterBlock {
	MaterialFrameParameters frame;
	MaterialObjectParameters object;
	MaterialStageParameters material;
};

struct WorldPacket {
	int packetIndex;
	FramePassKind pass;
	int surfaces;
	int vertexes;
	int indexes;
	int firstItem;
	int itemCount;
	int vertexOffset;
	int indexOffset;
	MaterialIR material;
	UploadPlan upload;
};

enum class DynamicDrawKind {
	Arrays,
	Indexed
};

struct DynamicDraw {
	DynamicDrawKind kind;
	FramePassKind pass;
	unsigned int primitive;
	int first;
	int count;
	unsigned int indexType;
	const void *indices;
	int legacyReason;
	int profilerPath;
	MaterialIR material;
	UploadPlan upload;
};

enum class OutputTransfer {
	SdrSrgb,
	LinearSrgb,
	ScRgb,
	Hdr10Pq,
	MacEdr,
	ScreenshotSrgb
};

enum class CaptureExportPolicy {
	SdrSrgb = 0,
	HdrSceneLinear = 1,
	HdrOutput = 2
};

enum class SceneColorSpace {
	DisplayReferredSdr,
	SceneLinear
};

enum class ToneMapOperator {
	Legacy = 0,
	ReinhardSimple = 1,
	AcesFitted = 2,
	// Compatibility aliases kept so older cvar values and tests retain the same
	// visual result while diagnostics use the more precise canonical names.
	Reinhard = ReinhardSimple,
	Aces = AcesFitted
};

enum class ExposureReductionAlgorithm {
	Manual = 0,
	SimpleAverage = 1,
	HistogramPercentile = 2
};

enum class ColorGradeMode {
	NoColorGrade,
	LiftGammaGain,
	Lut3D,
	LiftGammaGainLut3D,
	// Compatibility alias for older tests and call sites without colliding with X11's None macro.
	Disabled = NoColorGrade
};

enum class OutputPrimaries {
	SrgbBt709,
	DisplayP3,
	Bt2020,
	// No matrix transform: the selected native/compositor backend owns colorimetry.
	Native,
	Unknown
};

enum class GamutMapMode {
	NoGamutMap,
	Clip,
	CompressToOutput,
	// Compatibility alias for older tests and call sites without colliding with X11's None macro.
	Disabled = NoGamutMap
};

struct OutputTransform {
	OutputTransfer transfer;
	SceneColorSpace sceneColorSpace;
	ToneMapOperator toneMap;
	ColorGradeMode grade;
	OutputPrimaries outputPrimaries;
	GamutMapMode gamutMap;
	ExposureReductionAlgorithm exposureAlgorithm;
	rendererOutputRequest_t requestedBackend;
	rendererOutputBackend_t selectedBackend;
	rendererOutputBackend_t nativeBackend;
	qboolean autoExposure;
	qboolean outputHardwareActive;
	qboolean outputExperimental;
	qboolean displayHdrEnabled;
	qboolean displayHdrHeadroomValid;
	qboolean displayIccProfileAvailable;
	int displayIccProfileBytes;
	int hdrMode;
	int requestedPrecisionMode;
	int precisionMode;
	int renderScaleMode;
	float exposure;
	float bloomThreshold;
	float bloomSoftKnee;
	float paperWhiteNits;
	float maxOutputNits;
	float displayHdrHeadroom;
	float displaySdrWhiteNits;
	float displayMaxNits;
	float greyscale;
	float legacyGamma;
	float legacyOverbright;
	float crtAmount;
	float crtScanlineStrength;
	float crtMaskStrength;
	float crtCurvature;
	float crtChromatic;
	float crtInvWidth;
	float crtInvHeight;
	float gradeLift[3];
	float gradeGamma[3];
	float gradeGain[3];
	float whitePointSourceKelvin;
	float whitePointTargetKelvin;
	float lutSize;
	float lutScale;
};

enum DisplayOutputChangeFlags : unsigned int {
	GLX_DISPLAY_OUTPUT_CHANGE_NONE = 0x00000000u,
	GLX_DISPLAY_OUTPUT_CHANGE_VALID = 0x00000001u,
	GLX_DISPLAY_OUTPUT_CHANGE_DISPLAY = 0x00000002u,
	GLX_DISPLAY_OUTPUT_CHANGE_BACKEND = 0x00000004u,
	GLX_DISPLAY_OUTPUT_CHANGE_HDR = 0x00000008u,
	GLX_DISPLAY_OUTPUT_CHANGE_HEADROOM = 0x00000010u,
	GLX_DISPLAY_OUTPUT_CHANGE_LUMINANCE = 0x00000020u,
	GLX_DISPLAY_OUTPUT_CHANGE_ICC = 0x00000040u,
	GLX_DISPLAY_OUTPUT_CHANGE_PLATFORM_CAPS = 0x00000080u
};

enum class PostNodeKind {
	NoPostNode,
	CopyScene,
	BloomPrefinal,
	BloomFinal,
	GammaDirect,
	GammaBlit,
	Resolve,
	ToneMap,
	Grade,
	Screenshot
};

struct PostNode {
	PostNodeKind kind;
	FramePassKind pass;
	int sequence;
	int inputTarget;
	int outputTarget;
	unsigned int flags;
	OutputTransform output;
};

enum PostOutputFallbackReason : unsigned int {
	GLX_POST_OUTPUT_FALLBACK_NONE = 0x00000000u,
	GLX_POST_OUTPUT_FALLBACK_TIER = 0x00000001u,
	GLX_POST_OUTPUT_FALLBACK_FBO_NOT_READY = 0x00000002u,
	GLX_POST_OUTPUT_FALLBACK_PROGRAM_NOT_READY = 0x00000004u,
	GLX_POST_OUTPUT_FALLBACK_FRAMEBUFFER_FNS = 0x00000008u,
	GLX_POST_OUTPUT_FALLBACK_MINIMIZED = 0x00000010u,
	GLX_POST_OUTPUT_FALLBACK_INVALID_OUTPUT = 0x00000020u,
	GLX_POST_OUTPUT_FALLBACK_OUTPUT_CONTRACT = 0x00000040u,
	GLX_POST_OUTPUT_FALLBACK_NO_NODES = 0x00000080u,
	GLX_POST_OUTPUT_FALLBACK_EXECUTOR_REJECT = 0x00000100u,
	GLX_POST_OUTPUT_FALLBACK_RESULT_MISMATCH = 0x00000200u,
	GLX_POST_OUTPUT_FALLBACK_EXECUTOR_NOT_IMPLEMENTED = 0x00000400u,
	GLX_POST_OUTPUT_FALLBACK_EXECUTOR_DISABLED = 0x00000800u,
	GLX_POST_OUTPUT_FALLBACK_EXECUTOR_NOT_BOUND = 0x00001000u
};

struct PostOutputPlanInputs {
	RenderProductTier tier;
	OutputTransform output;
	CaptureExportPolicy captureRequest;
	qboolean fboReady;
	qboolean programReady;
	qboolean framebufferFnsReady;
	qboolean outputContractValid;
	qboolean bloomAvailable;
	qboolean postShaderExecutorEnabled;
	qboolean minimized;
	qboolean windowAdjusted;
	int screenshotMask;
	int fboReadIndex;
	int sequenceBase;
	unsigned int flags;
};

struct PostOutputPlan {
	PostNode nodes[GLX_RENDER_IR_MAX_POST_OUTPUT_NODES];
	int nodeCount;
	OutputTransform output;
	CaptureExportPolicy captureRequest;
	CaptureExportPolicy captureSelected;
	qboolean captureHdrAware;
	qboolean captureSupported;
	qboolean outputValid;
	qboolean outputTransformPresent;
	qboolean outputTransformExecutable;
	qboolean executorImplemented;
	qboolean glxOwned;
	int executableNodeCount;
	unsigned int fallbackReasons;
	unsigned int hash;
	int predictedResult;
};

struct FrameProducts {
	const FramePass *passes;
	int passCount;
	const WorldPacket *worldPackets;
	int worldPacketCount;
	const DynamicDraw *dynamicDraws;
	int dynamicDrawCount;
	const PostNode *postNodes;
	int postNodeCount;
	OutputTransform output;
};

struct TierExecutionPolicy {
	const char *executorName;
	qboolean fixedFunction;
	qboolean clientMemoryDraws;
	qboolean streamUploads;
	qboolean materialCompiler;
	qboolean commonMaterials;
	qboolean dynamicEntities;
	qboolean postProcessLite;
	qboolean modernPostChain;
	qboolean sceneLinearOutput;
	qboolean fboPostProcess;
	qboolean uboFrameObjectConstants;
	qboolean timerQueries;
	qboolean syncAwareUploads;
	qboolean staticBufferOwnership;
	qboolean dynamicBufferOwnership;
	qboolean persistentUploads;
	qboolean indirectSubmission;
	qboolean directStateAccess;
	qboolean macOS41Ceiling;
	qboolean highQualitySdrOutput;
	qboolean optionalHardwareHdrOutput;
	qboolean debugOutputRequired;
	qboolean bufferStorageRequired;
	qboolean directStateAccessRequired;
	qboolean multiDrawIndirectRequired;
	qboolean bufferStorageUploads;
	qboolean syncHeavyStreaming;
	qboolean multiDrawIndirectSubmission;
	qboolean aggressiveStaticWorldSubmission;
	qboolean detailedGpuCounters;
	qboolean lightmaps;
	qboolean multitexture;
	qboolean fog;
	qboolean sprites;
	qboolean beams;
	qboolean dynamicLights;
	qboolean stencilShadowsIfAvailable;
	qboolean screenshots;
	qboolean demos;
	const char *unavailable;
};

static ID_INLINE const char *GLX_RenderIR_TierName( RenderProductTier tier )
{
	return GLX_RenderProductTierName( tier );
}

static ID_INLINE TierExecutionPolicy GLX_RenderIR_TierExecutionPolicy( RenderProductTier tier )
{
	TierExecutionPolicy policy {};

	switch ( tier ) {
	case RenderProductTier::GL12:
		policy.executorName = "fixed-function";
		policy.fixedFunction = qtrue;
		policy.clientMemoryDraws = qtrue;
		policy.lightmaps = qtrue;
		policy.multitexture = qtrue;
		policy.fog = qtrue;
		policy.sprites = qtrue;
		policy.beams = qtrue;
		policy.dynamicLights = qtrue;
		policy.stencilShadowsIfAvailable = qtrue;
		policy.screenshots = qtrue;
		policy.demos = qtrue;
		policy.unavailable =
			"GLSL material compiler, dynamic stream VBO uploads, FBO postprocess, "
			"UBO frame/object constants, timer queries, sync-aware uploads, scene-linear HDR, "
			"tone mapping, color grading, bloom post chain, indirect and multidraw static-world submission";
		return policy;
	case RenderProductTier::GL2X:
		policy.executorName = "programmable";
		policy.clientMemoryDraws = qtrue;
		policy.streamUploads = qtrue;
		policy.materialCompiler = qtrue;
		policy.commonMaterials = qtrue;
		policy.dynamicEntities = qtrue;
		policy.postProcessLite = qtrue;
		policy.lightmaps = qtrue;
		policy.multitexture = qtrue;
		policy.fog = qtrue;
		policy.sprites = qtrue;
		policy.beams = qtrue;
		policy.dynamicLights = qtrue;
		policy.stencilShadowsIfAvailable = qtrue;
		policy.screenshots = qtrue;
		policy.demos = qtrue;
		policy.unavailable =
			"required FBO postprocess, UBO-backed frame/object constants, sync-required persistent uploads, "
			"scene-linear HDR, tone mapping, color grading, indirect and multidraw static-world submission";
		return policy;
	case RenderProductTier::GL3X:
		policy.executorName = "performance";
		policy.clientMemoryDraws = qtrue;
		policy.streamUploads = qtrue;
		policy.materialCompiler = qtrue;
		policy.commonMaterials = qtrue;
		policy.dynamicEntities = qtrue;
		policy.postProcessLite = qtrue;
		policy.modernPostChain = qtrue;
		policy.sceneLinearOutput = qtrue;
		policy.fboPostProcess = qtrue;
		policy.uboFrameObjectConstants = qtrue;
		policy.timerQueries = qtrue;
		policy.syncAwareUploads = qtrue;
		policy.staticBufferOwnership = qtrue;
		policy.dynamicBufferOwnership = qtrue;
		policy.highQualitySdrOutput = qtrue;
		policy.optionalHardwareHdrOutput = qtrue;
		policy.lightmaps = qtrue;
		policy.multitexture = qtrue;
		policy.fog = qtrue;
		policy.sprites = qtrue;
		policy.beams = qtrue;
		policy.dynamicLights = qtrue;
		policy.stencilShadowsIfAvailable = qtrue;
		policy.screenshots = qtrue;
		policy.demos = qtrue;
		policy.unavailable =
			"persistent mapped buffer-storage uploads, direct-state access, and indirect/multidraw submission";
		return policy;
	case RenderProductTier::GL41:
		policy.executorName = "mac-modern";
		policy.clientMemoryDraws = qtrue;
		policy.streamUploads = qtrue;
		policy.materialCompiler = qtrue;
		policy.commonMaterials = qtrue;
		policy.dynamicEntities = qtrue;
		policy.postProcessLite = qtrue;
		policy.modernPostChain = qtrue;
		policy.sceneLinearOutput = qtrue;
		policy.fboPostProcess = qtrue;
		policy.uboFrameObjectConstants = qtrue;
		policy.timerQueries = qtrue;
		policy.syncAwareUploads = qtrue;
		policy.staticBufferOwnership = qtrue;
		policy.dynamicBufferOwnership = qtrue;
		policy.macOS41Ceiling = qtrue;
		policy.highQualitySdrOutput = qtrue;
		policy.optionalHardwareHdrOutput = qtrue;
		policy.lightmaps = qtrue;
		policy.multitexture = qtrue;
		policy.fog = qtrue;
		policy.sprites = qtrue;
		policy.beams = qtrue;
		policy.dynamicLights = qtrue;
		policy.stencilShadowsIfAvailable = qtrue;
		policy.screenshots = qtrue;
		policy.demos = qtrue;
		policy.unavailable =
			"required GL4.3 debug output, required GL4.4 buffer storage, "
			"required GL4.5 direct-state access, and required multi-draw-indirect submission";
		return policy;
	case RenderProductTier::GL46:
	default:
		policy.executorName = "high-end";
		policy.clientMemoryDraws = qtrue;
		policy.streamUploads = qtrue;
		policy.materialCompiler = qtrue;
		policy.commonMaterials = qtrue;
		policy.dynamicEntities = qtrue;
		policy.postProcessLite = qtrue;
		policy.modernPostChain = qtrue;
		policy.sceneLinearOutput = qtrue;
		policy.fboPostProcess = qtrue;
		policy.uboFrameObjectConstants = qtrue;
		policy.timerQueries = qtrue;
		policy.syncAwareUploads = qtrue;
		policy.staticBufferOwnership = qtrue;
		policy.dynamicBufferOwnership = qtrue;
		policy.persistentUploads = qtrue;
		policy.indirectSubmission = qtrue;
		policy.directStateAccess = qtrue;
		policy.highQualitySdrOutput = qtrue;
		policy.optionalHardwareHdrOutput = qtrue;
		policy.debugOutputRequired = qtrue;
		policy.bufferStorageRequired = qtrue;
		policy.directStateAccessRequired = qtrue;
		policy.multiDrawIndirectRequired = qtrue;
		policy.bufferStorageUploads = qtrue;
		policy.syncHeavyStreaming = qtrue;
		policy.multiDrawIndirectSubmission = qtrue;
		policy.aggressiveStaticWorldSubmission = qtrue;
		policy.detailedGpuCounters = qtrue;
		policy.lightmaps = qtrue;
		policy.multitexture = qtrue;
		policy.fog = qtrue;
		policy.sprites = qtrue;
		policy.beams = qtrue;
		policy.dynamicLights = qtrue;
		policy.stencilShadowsIfAvailable = qtrue;
		policy.screenshots = qtrue;
		policy.demos = qtrue;
		policy.unavailable = "none";
		return policy;
	}
}

static ID_INLINE const char *GLX_RenderIR_PassName( FramePassKind pass )
{
	switch ( pass ) {
	case FramePassKind::FrameSetup:
		return "frame-setup";
	case FramePassKind::SkyAndOpaqueWorld:
		return "sky-opaque-world";
	case FramePassKind::OpaqueEntities:
		return "opaque-entities";
	case FramePassKind::DynamicScene:
		return "dynamic-scene";
	case FramePassKind::TransparentLayers:
		return "transparent-layers";
	case FramePassKind::FirstPersonWeapon:
		return "first-person-weapon";
	case FramePassKind::HudAnd2D:
		return "hud-2d";
	case FramePassKind::PostProcess:
		return "postprocess";
	case FramePassKind::OutputExport:
		return "output-export";
	default:
		return "unknown";
	}
}

static ID_INLINE const char *GLX_RenderIR_OutputTransferName( OutputTransfer transfer )
{
	switch ( transfer ) {
	case OutputTransfer::SdrSrgb:
		return "sdr-srgb";
	case OutputTransfer::LinearSrgb:
		return "linear-srgb";
	case OutputTransfer::ScRgb:
		return "scrgb";
	case OutputTransfer::Hdr10Pq:
		return "hdr10-pq";
	case OutputTransfer::MacEdr:
		return "mac-edr";
	case OutputTransfer::ScreenshotSrgb:
		return "screenshot-srgb";
	default:
		return "unknown";
	}
}

static ID_INLINE const char *GLX_RenderIR_SceneColorSpaceName( SceneColorSpace space )
{
	switch ( space ) {
	case SceneColorSpace::DisplayReferredSdr:
		return "display-referred-sdr";
	case SceneColorSpace::SceneLinear:
		return "scene-linear";
	default:
		return "unknown";
	}
}

static ID_INLINE CaptureExportPolicy GLX_RenderIR_CaptureExportPolicyForCvar( int value )
{
	switch ( value ) {
	case 1:
		return CaptureExportPolicy::HdrSceneLinear;
	case 2:
		return CaptureExportPolicy::HdrOutput;
	case 0:
	default:
		return CaptureExportPolicy::SdrSrgb;
	}
}

static ID_INLINE const char *GLX_RenderIR_CaptureExportPolicyName(
	CaptureExportPolicy policy )
{
	switch ( policy ) {
	case CaptureExportPolicy::HdrSceneLinear:
		return "hdr-scene-linear";
	case CaptureExportPolicy::HdrOutput:
		return "hdr-output";
	case CaptureExportPolicy::SdrSrgb:
	default:
		return "sdr-srgb";
	}
}

static ID_INLINE qboolean GLX_RenderIR_CaptureExportPolicyHdrAware(
	CaptureExportPolicy policy )
{
	return policy == CaptureExportPolicy::HdrSceneLinear ||
		policy == CaptureExportPolicy::HdrOutput ? qtrue : qfalse;
}

static ID_INLINE CaptureExportPolicy GLX_RenderIR_ResolveCaptureExportPolicy(
	CaptureExportPolicy requested )
{
	(void)requested;
	return CaptureExportPolicy::SdrSrgb;
}

static ID_INLINE qboolean GLX_RenderIR_CaptureExportPolicySupported(
	CaptureExportPolicy requested )
{
	return GLX_RenderIR_ResolveCaptureExportPolicy( requested ) == requested ?
		qtrue : qfalse;
}

static ID_INLINE qboolean GLX_RenderIR_OutputTransferImplemented( OutputTransfer transfer )
{
	switch ( transfer ) {
	case OutputTransfer::SdrSrgb:
	case OutputTransfer::LinearSrgb:
	case OutputTransfer::ScRgb:
	case OutputTransfer::Hdr10Pq:
	case OutputTransfer::MacEdr:
	case OutputTransfer::ScreenshotSrgb:
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE qboolean GLX_RenderIR_SceneColorSpaceImplemented( SceneColorSpace space )
{
	switch ( space ) {
	case SceneColorSpace::DisplayReferredSdr:
	case SceneColorSpace::SceneLinear:
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE const char *GLX_RenderIR_ToneMapName( ToneMapOperator toneMap )
{
	switch ( toneMap ) {
	case ToneMapOperator::Legacy:
		return "legacy";
	case ToneMapOperator::ReinhardSimple:
		return "reinhard-simple";
	case ToneMapOperator::AcesFitted:
		return "aces-fitted";
	default:
		return "unknown";
	}
}

static ID_INLINE const char *GLX_RenderIR_ToneMapLegacyAliasName(
	ToneMapOperator toneMap )
{
	switch ( toneMap ) {
	case ToneMapOperator::ReinhardSimple:
		return "reinhard";
	case ToneMapOperator::AcesFitted:
		return "aces";
	default:
		return "";
	}
}

static ID_INLINE qboolean GLX_RenderIR_ToneMapOperatorImplemented(
	ToneMapOperator toneMap )
{
	switch ( toneMap ) {
	case ToneMapOperator::Legacy:
	case ToneMapOperator::ReinhardSimple:
	case ToneMapOperator::AcesFitted:
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE const char *GLX_RenderIR_ExposureReductionName(
	ExposureReductionAlgorithm algorithm )
{
	switch ( algorithm ) {
	case ExposureReductionAlgorithm::Manual:
		return "manual";
	case ExposureReductionAlgorithm::SimpleAverage:
		return "simple-average";
	case ExposureReductionAlgorithm::HistogramPercentile:
		return "histogram-percentile";
	default:
		return "unknown";
	}
}

static ID_INLINE qboolean GLX_RenderIR_ExposureReductionImplemented(
	ExposureReductionAlgorithm algorithm )
{
	switch ( algorithm ) {
	case ExposureReductionAlgorithm::Manual:
	case ExposureReductionAlgorithm::SimpleAverage:
	case ExposureReductionAlgorithm::HistogramPercentile:
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE const char *GLX_RenderIR_ColorGradeName( ColorGradeMode grade )
{
	switch ( grade ) {
	case ColorGradeMode::NoColorGrade:
		return "none";
	case ColorGradeMode::LiftGammaGain:
		return "lift-gamma-gain";
	case ColorGradeMode::Lut3D:
		return "lut3d";
	case ColorGradeMode::LiftGammaGainLut3D:
		return "lgg-lut3d";
	default:
		return "unknown";
	}
}

static ID_INLINE qboolean GLX_RenderIR_ColorGradeModeImplemented( ColorGradeMode grade )
{
	switch ( grade ) {
	case ColorGradeMode::NoColorGrade:
	case ColorGradeMode::LiftGammaGain:
	case ColorGradeMode::Lut3D:
	case ColorGradeMode::LiftGammaGainLut3D:
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE const char *GLX_RenderIR_OutputPrimariesName( OutputPrimaries primaries )
{
	switch ( primaries ) {
	case OutputPrimaries::SrgbBt709:
		return "srgb-bt709";
	case OutputPrimaries::DisplayP3:
		return "display-p3";
	case OutputPrimaries::Bt2020:
		return "bt2020";
	case OutputPrimaries::Native:
		return "native";
	case OutputPrimaries::Unknown:
	default:
		return "unknown";
	}
}

static ID_INLINE const char *GLX_RenderIR_OutputPrimariesContractName(
	OutputPrimaries primaries )
{
	switch ( primaries ) {
	case OutputPrimaries::SrgbBt709:
		return "srgb-bt709-matrix";
	case OutputPrimaries::DisplayP3:
		return "display-p3-matrix";
	case OutputPrimaries::Bt2020:
		return "bt2020-matrix";
	case OutputPrimaries::Native:
		return "native-pass-through";
	case OutputPrimaries::Unknown:
	default:
		return "unsupported";
	}
}

static ID_INLINE qboolean GLX_RenderIR_OutputPrimariesImplemented(
	OutputPrimaries primaries )
{
	switch ( primaries ) {
	case OutputPrimaries::SrgbBt709:
	case OutputPrimaries::DisplayP3:
	case OutputPrimaries::Bt2020:
	case OutputPrimaries::Native:
		return qtrue;
	case OutputPrimaries::Unknown:
	default:
		return qfalse;
	}
}

static ID_INLINE qboolean GLX_RenderIR_OutputPrimariesNativePassthroughAllowed(
	const OutputTransform &transform )
{
	return ( transform.outputPrimaries == OutputPrimaries::Native &&
		transform.sceneColorSpace == SceneColorSpace::SceneLinear &&
		transform.transfer == OutputTransfer::LinearSrgb &&
		transform.selectedBackend == ROUTPUT_BACKEND_LINUX_EXPERIMENTAL_HDR &&
		transform.outputHardwareActive &&
		transform.outputExperimental ) ? qtrue : qfalse;
}

static ID_INLINE const char *GLX_RenderIR_GamutMapName( GamutMapMode mode )
{
	switch ( mode ) {
	case GamutMapMode::NoGamutMap:
		return "none";
	case GamutMapMode::Clip:
		return "clip";
	case GamutMapMode::CompressToOutput:
		return "compress";
	default:
		return "unknown";
	}
}

static ID_INLINE qboolean GLX_RenderIR_GamutMapModeImplemented( GamutMapMode mode )
{
	switch ( mode ) {
	case GamutMapMode::NoGamutMap:
	case GamutMapMode::Clip:
	case GamutMapMode::CompressToOutput:
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE RenderProductTier GLX_RenderIR_TierForVersionAndFeatures( int major, int minor,
	const FeatureSet &features )
{
	return GLX_RenderProductTierForVersionAndFeatures( major, minor, features );
}

static ID_INLINE qboolean GLX_RenderIR_TierConsumesProduct( RenderProductTier tier,
	RenderProductKind product )
{
	switch ( tier ) {
	case RenderProductTier::GL12:
	case RenderProductTier::GL2X:
	case RenderProductTier::GL3X:
	case RenderProductTier::GL41:
	case RenderProductTier::GL46:
		break;
	default:
		return qfalse;
	}

	switch ( product ) {
	case RenderProductKind::FramePass:
	case RenderProductKind::WorldPacket:
	case RenderProductKind::DynamicDraw:
	case RenderProductKind::MaterialIR:
	case RenderProductKind::UploadPlan:
	case RenderProductKind::PostNode:
	case RenderProductKind::OutputTransform:
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE qboolean GLX_RenderIR_DefaultPassSchedule( FramePass *passes,
	int capacity, int *count )
{
	static const FramePassKind order[GLX_RENDER_IR_PASS_COUNT] = {
		FramePassKind::FrameSetup,
		FramePassKind::SkyAndOpaqueWorld,
		FramePassKind::OpaqueEntities,
		FramePassKind::DynamicScene,
		FramePassKind::TransparentLayers,
		FramePassKind::FirstPersonWeapon,
		FramePassKind::HudAnd2D,
		FramePassKind::PostProcess,
		FramePassKind::OutputExport
	};

	if ( count ) {
		*count = GLX_RENDER_IR_PASS_COUNT;
	}
	if ( !passes || capacity < GLX_RENDER_IR_PASS_COUNT ) {
		return qfalse;
	}

	for ( int i = 0; i < GLX_RENDER_IR_PASS_COUNT; i++ ) {
		passes[i].kind = order[i];
		passes[i].sequence = i;
		passes[i].sortStart = -1;
		passes[i].sortEnd = -1;
		passes[i].flags = 0;
	}
	return qtrue;
}

static ID_INLINE qboolean GLX_RenderIR_ValidatePassSchedule( const FramePass *passes,
	int count )
{
	FramePass expected[GLX_RENDER_IR_PASS_COUNT];
	int expectedCount = 0;

	if ( !passes || count != GLX_RENDER_IR_PASS_COUNT ) {
		return qfalse;
	}
	if ( !GLX_RenderIR_DefaultPassSchedule( expected, GLX_RENDER_IR_PASS_COUNT, &expectedCount ) ||
		expectedCount != count ) {
		return qfalse;
	}
	for ( int i = 0; i < count; i++ ) {
		if ( passes[i].kind != expected[i].kind || passes[i].sequence != i ) {
			return qfalse;
		}
	}
	return qtrue;
}

static ID_INLINE int GLX_RenderIR_AppendScheduleText( char *buffer, int capacity,
	int length, const char *text )
{
	if ( !text ) {
		return length;
	}

	for ( int i = 0; text[i]; i++ ) {
		if ( buffer && capacity > 0 && length < capacity - 1 ) {
			buffer[length] = text[i];
		}
		length++;
	}

	if ( buffer && capacity > 0 ) {
		const int terminator = length < capacity ? length : capacity - 1;
		buffer[terminator] = '\0';
	}
	return length;
}

static ID_INLINE int GLX_RenderIR_FormatPassSchedule( const FramePass *passes,
	int count, char *buffer, int capacity )
{
	int length = 0;

	if ( buffer && capacity > 0 ) {
		buffer[0] = '\0';
	}
	if ( !passes || count <= 0 ) {
		return 0;
	}

	for ( int i = 0; i < count; i++ ) {
		if ( i > 0 ) {
			length = GLX_RenderIR_AppendScheduleText( buffer, capacity, length, ">" );
		}
		length = GLX_RenderIR_AppendScheduleText( buffer, capacity, length,
			GLX_RenderIR_PassName( passes[i].kind ) );
	}
	return length;
}

static ID_INLINE unsigned int GLX_RenderIR_HashScheduleText( const char *text )
{
	unsigned int hash = 2166136261u;

	if ( !text ) {
		return 0;
	}
	for ( int i = 0; text[i]; i++ ) {
		hash ^= static_cast<unsigned int>( static_cast<unsigned char>( text[i] ) );
		hash *= 16777619u;
	}
	return hash;
}

static ID_INLINE unsigned int GLX_RenderIR_HashValue(
	unsigned int hash, unsigned int value )
{
	hash ^= value;
	hash *= 16777619u;
	return hash;
}

static ID_INLINE unsigned int GLX_RenderIR_HashFloatValue(
	unsigned int hash, float value )
{
	union {
		float f;
		unsigned int u;
	} bits;

	bits.f = value;
	return GLX_RenderIR_HashValue( hash, bits.u );
}

static ID_INLINE unsigned int GLX_RenderIR_HashStringValue(
	unsigned int hash, const char *text )
{
	if ( !text ) {
		return GLX_RenderIR_HashValue( hash, 0u );
	}
	for ( int i = 0; text[i]; i++ ) {
		hash ^= static_cast<unsigned int>( static_cast<unsigned char>( text[i] ) );
		hash *= 16777619u;
	}
	return GLX_RenderIR_HashValue( hash, 0u );
}

static ID_INLINE float GLX_RenderIR_SanitizeDisplayFloat( float value,
	float fallback, float minValue, float maxValue )
{
	if ( !std::isfinite( fallback ) ) {
		fallback = minValue;
	}
	if ( !std::isfinite( value ) ) {
		value = fallback;
	}
	if ( !std::isfinite( minValue ) ) {
		minValue = fallback;
	}
	if ( !std::isfinite( maxValue ) ) {
		maxValue = minValue;
	}
	if ( maxValue < minValue ) {
		const float tmp = minValue;
		minValue = maxValue;
		maxValue = tmp;
	}
	if ( value < minValue ) {
		return minValue;
	}
	if ( value > maxValue ) {
		return maxValue;
	}
	return value;
}

static ID_INLINE unsigned int GLX_RenderIR_QuantizedDisplayFloat( float value,
	float scale )
{
	if ( !std::isfinite( value ) ) {
		value = 0.0f;
	}
	if ( !std::isfinite( scale ) || scale <= 0.0f ) {
		scale = 1.0f;
	}
	const float scaled = value * scale;
	const float rounded = scaled >= 0.0f ? std::floor( scaled + 0.5f ) :
		-std::floor( -scaled + 0.5f );
	return static_cast<unsigned int>( static_cast<int>( rounded ) );
}

static ID_INLINE qboolean GLX_RenderIR_DisplayFloatChanged( float oldValue,
	float newValue, float scale )
{
	return GLX_RenderIR_QuantizedDisplayFloat( oldValue, scale ) !=
		GLX_RenderIR_QuantizedDisplayFloat( newValue, scale ) ? qtrue : qfalse;
}

static ID_INLINE void GLX_RenderIR_SanitizeDisplayOutput(
	rendererDisplayOutput_t *output )
{
	if ( !output ) {
		return;
	}

	if ( output->nativeBackend < ROUTPUT_BACKEND_SDR_SRGB ||
		output->nativeBackend >= ROUTPUT_BACKEND_COUNT ) {
		output->nativeBackend = ROUTPUT_BACKEND_SDR_SRGB;
	}
	output->sdrWhiteNits = GLX_RenderIR_SanitizeDisplayFloat(
		output->sdrWhiteNits, 203.0f, 80.0f, 10000.0f );
	output->hdrHeadroom = GLX_RenderIR_SanitizeDisplayFloat(
		output->hdrHeadroom, 1.0f, 1.0f, 64.0f );
	if ( output->hdrHeadroom <= 1.0f ) {
		output->hdrHeadroom = 1.0f;
		output->hdrHeadroomValid = qfalse;
	}
	output->maxLuminanceNits = GLX_RenderIR_SanitizeDisplayFloat(
		output->maxLuminanceNits, output->sdrWhiteNits, output->sdrWhiteNits, 10000.0f );
	output->maxFullFrameLuminanceNits = GLX_RenderIR_SanitizeDisplayFloat(
		output->maxFullFrameLuminanceNits, output->maxLuminanceNits,
		output->sdrWhiteNits, output->maxLuminanceNits );
	if ( output->iccProfileBytes < 0 ) {
		output->iccProfileBytes = 0;
		output->iccProfileAvailable = qfalse;
	}
	if ( !output->iccProfileAvailable ) {
		output->iccProfileBytes = 0;
	}
	if ( output->nativeBackend == ROUTPUT_BACKEND_WINDOWS_SCRGB &&
		!output->windowsScRgbSupported && !output->windowsHdr10Supported ) {
		output->nativeBackend = ROUTPUT_BACKEND_SDR_SRGB;
	}
	if ( output->nativeBackend == ROUTPUT_BACKEND_HDR10_PQ &&
		!output->windowsHdr10Supported ) {
		output->nativeBackend = ROUTPUT_BACKEND_SDR_SRGB;
	}
	if ( output->nativeBackend == ROUTPUT_BACKEND_MACOS_EDR &&
		!output->macosEdrSupported ) {
		output->nativeBackend = ROUTPUT_BACKEND_SDR_SRGB;
	}
	if ( output->nativeBackend == ROUTPUT_BACKEND_LINUX_EXPERIMENTAL_HDR &&
		( !output->linuxHdrExperimental || !output->explicitLinuxHdrProtocol ) ) {
		output->nativeBackend = ROUTPUT_BACKEND_SDR_SRGB;
	}
}

static ID_INLINE unsigned int GLX_RenderIR_HashDisplayOutput(
	const rendererDisplayOutput_t &output )
{
	unsigned int hash = 2166136261u;

	hash = GLX_RenderIR_HashValue( hash, output.valid ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( output.displayIndex ) );
	hash = GLX_RenderIR_HashStringValue( hash, output.videoDriver );
	hash = GLX_RenderIR_HashStringValue( hash, output.displayName );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( output.nativeBackend ) );
	hash = GLX_RenderIR_HashValue( hash, output.hdrEnabled ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, output.hdrHeadroomValid ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, GLX_RenderIR_QuantizedDisplayFloat(
		output.sdrWhiteNits, 10.0f ) );
	hash = GLX_RenderIR_HashValue( hash, GLX_RenderIR_QuantizedDisplayFloat(
		output.hdrHeadroom, 100.0f ) );
	hash = GLX_RenderIR_HashValue( hash, GLX_RenderIR_QuantizedDisplayFloat(
		output.maxLuminanceNits, 10.0f ) );
	hash = GLX_RenderIR_HashValue( hash, GLX_RenderIR_QuantizedDisplayFloat(
		output.maxFullFrameLuminanceNits, 10.0f ) );
	hash = GLX_RenderIR_HashValue( hash, output.iccProfileAvailable ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( output.iccProfileBytes ) );
	hash = GLX_RenderIR_HashValue( hash, output.windowsAdvancedColor ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, output.windowsScRgbSupported ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, output.windowsHdr10Supported ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, output.macosEdrSupported ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, output.linuxHdrExperimental ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, output.waylandColorProtocol ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, output.explicitLinuxHdrProtocol ? 1u : 0u );
	return hash ? hash : 1u;
}

static ID_INLINE unsigned int GLX_RenderIR_DisplayOutputChangeMask(
	const rendererDisplayOutput_t &oldOutput,
	const rendererDisplayOutput_t &newOutput )
{
	unsigned int mask = GLX_DISPLAY_OUTPUT_CHANGE_NONE;

	if ( oldOutput.valid != newOutput.valid ) {
		mask |= GLX_DISPLAY_OUTPUT_CHANGE_VALID;
	}
	if ( oldOutput.displayIndex != newOutput.displayIndex ||
		GLX_RenderIR_HashStringValue( 2166136261u, oldOutput.videoDriver ) !=
		GLX_RenderIR_HashStringValue( 2166136261u, newOutput.videoDriver ) ||
		GLX_RenderIR_HashStringValue( 2166136261u, oldOutput.displayName ) !=
		GLX_RenderIR_HashStringValue( 2166136261u, newOutput.displayName ) ) {
		mask |= GLX_DISPLAY_OUTPUT_CHANGE_DISPLAY;
	}
	if ( oldOutput.nativeBackend != newOutput.nativeBackend ) {
		mask |= GLX_DISPLAY_OUTPUT_CHANGE_BACKEND;
	}
	if ( oldOutput.hdrEnabled != newOutput.hdrEnabled ) {
		mask |= GLX_DISPLAY_OUTPUT_CHANGE_HDR;
	}
	if ( oldOutput.hdrHeadroomValid != newOutput.hdrHeadroomValid ||
		GLX_RenderIR_DisplayFloatChanged( oldOutput.hdrHeadroom,
			newOutput.hdrHeadroom, 100.0f ) ) {
		mask |= GLX_DISPLAY_OUTPUT_CHANGE_HEADROOM;
	}
	if ( GLX_RenderIR_DisplayFloatChanged( oldOutput.sdrWhiteNits,
			newOutput.sdrWhiteNits, 10.0f ) ||
		GLX_RenderIR_DisplayFloatChanged( oldOutput.maxLuminanceNits,
			newOutput.maxLuminanceNits, 10.0f ) ||
		GLX_RenderIR_DisplayFloatChanged( oldOutput.maxFullFrameLuminanceNits,
			newOutput.maxFullFrameLuminanceNits, 10.0f ) ) {
		mask |= GLX_DISPLAY_OUTPUT_CHANGE_LUMINANCE;
	}
	if ( oldOutput.iccProfileAvailable != newOutput.iccProfileAvailable ||
		oldOutput.iccProfileBytes != newOutput.iccProfileBytes ) {
		mask |= GLX_DISPLAY_OUTPUT_CHANGE_ICC;
	}
	if ( oldOutput.windowsAdvancedColor != newOutput.windowsAdvancedColor ||
		oldOutput.windowsScRgbSupported != newOutput.windowsScRgbSupported ||
		oldOutput.windowsHdr10Supported != newOutput.windowsHdr10Supported ||
		oldOutput.macosEdrSupported != newOutput.macosEdrSupported ||
		oldOutput.linuxHdrExperimental != newOutput.linuxHdrExperimental ||
		oldOutput.waylandColorProtocol != newOutput.waylandColorProtocol ||
		oldOutput.explicitLinuxHdrProtocol != newOutput.explicitLinuxHdrProtocol ) {
		mask |= GLX_DISPLAY_OUTPUT_CHANGE_PLATFORM_CAPS;
	}
	return mask;
}

static ID_INLINE unsigned int GLX_RenderIR_PassScheduleHash( const FramePass *passes,
	int count )
{
	char schedule[GLX_RENDER_IR_PASS_SCHEDULE_TEXT_BYTES];

	if ( !GLX_RenderIR_ValidatePassSchedule( passes, count ) ) {
		return 0;
	}
	GLX_RenderIR_FormatPassSchedule( passes, count, schedule,
		GLX_RENDER_IR_PASS_SCHEDULE_TEXT_BYTES );
	return GLX_RenderIR_HashScheduleText( schedule );
}

static ID_INLINE qboolean GLX_RenderIR_ValidateUploadPlan( const UploadPlan &plan )
{
	if ( plan.alignment < 0 ) {
		return qfalse;
	}
	if ( plan.kind == UploadPlanKind::NoUpload || plan.kind == UploadPlanKind::ClientMemory ) {
		return qtrue;
	}
	if ( plan.bytes == 0 ) {
		return qfalse;
	}
	if ( plan.vertexBytes + plan.indexBytes + plan.texcoordBytes > plan.bytes ) {
		return qfalse;
	}
	return qtrue;
}

static ID_INLINE qboolean GLX_RenderIR_ValidateMaterial( const MaterialIR &material )
{
	return material.shaderStagePasses >= 0 ? qtrue : qfalse;
}

static ID_INLINE unsigned int GLX_RenderIR_MaterialFeatureMask( const MaterialIR &material )
{
	unsigned int mask = 0;

	mask |= ( material.flags & ( GLX_STAGE_MULTITEXTURE | GLX_STAGE_DEPTH_FRAGMENT |
		GLX_STAGE_LIGHTMAP | GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT |
		GLX_STAGE_DLIGHT_MAP | GLX_STAGE_SCREEN_MAP | GLX_STAGE_VIDEO_MAP |
		GLX_STAGE_SHADOW_PASS | GLX_STAGE_BEAM_PASS | GLX_STAGE_POSTPROCESS_PASS ) );
	if ( material.texMods0 > 0 || material.texMods1 > 0 ) {
		mask |= GLX_STAGE_TEXMOD;
	}
	return mask;
}

static ID_INLINE MaterialParameterBlock GLX_RenderIR_MakeMaterialParameterBlock(
	const MaterialIR &material )
{
	MaterialParameterBlock block {};

	block.frame.sort = material.sort;
	block.frame.shaderStagePasses = material.shaderStagePasses;
	block.frame.featureMask = GLX_RenderIR_MaterialFeatureMask( material );
	block.object.rgbGen = material.rgbGen;
	block.object.alphaGen = material.alphaGen;
	block.object.rgbWaveFunc = material.rgbWaveFunc;
	block.object.alphaWaveFunc = material.alphaWaveFunc;
	block.object.tcGen0 = material.tcGen0;
	block.object.tcGen1 = material.tcGen1;
	block.material.flags = material.flags;
	block.material.stateBits = material.stateBits;
	block.material.texMods0 = material.texMods0;
	block.material.texMods1 = material.texMods1;
	block.material.texModTypes0 = material.texModTypes0;
	block.material.texModTypes1 = material.texModTypes1;
	block.material.texModSequence0 = material.texModSequence0;
	block.material.texModSequence1 = material.texModSequence1;
	block.material.texModWaveFuncs0 = material.texModWaveFuncs0;
	block.material.texModWaveFuncs1 = material.texModWaveFuncs1;
	block.material.fogAdjust = material.fogAdjust;
	block.material.materialCombine = material.materialCombine;
	block.material.fogPass = material.fogPass;
	return block;
}

static ID_INLINE qboolean GLX_RenderIR_ValidateMaterialParameterBlock(
	const MaterialParameterBlock &block )
{
	return block.frame.shaderStagePasses >= 0 &&
		block.material.texMods0 >= 0 &&
		block.material.texMods1 >= 0 ? qtrue : qfalse;
}

static ID_INLINE unsigned int GLX_RenderIR_HashMaterialParameterValue(
	unsigned int hash, unsigned int value )
{
	return GLX_RenderIR_HashValue( hash, value );
}

static ID_INLINE unsigned int GLX_RenderIR_HashMaterialParameterBlock(
	const MaterialParameterBlock &block )
{
	unsigned int hash = 2166136261u;

	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.frame.sort ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.frame.shaderStagePasses ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.frame.featureMask );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.object.rgbGen ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.object.alphaGen ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.object.rgbWaveFunc ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.object.alphaWaveFunc ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.object.tcGen0 ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.object.tcGen1 ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.material.flags ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.material.stateBits );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.material.texMods0 ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.material.texMods1 ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.material.texModTypes0 );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.material.texModTypes1 );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.material.texModSequence0 );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.material.texModSequence1 );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.material.texModWaveFuncs0 );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.material.texModWaveFuncs1 );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.material.fogAdjust ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, static_cast<unsigned int>( block.material.materialCombine ) );
	hash = GLX_RenderIR_HashMaterialParameterValue( hash, block.material.fogPass ? 1u : 0u );
	return hash ? hash : 1u;
}

static ID_INLINE unsigned int GLX_RenderIR_HashOutputTransform(
	const OutputTransform &transform )
{
	unsigned int hash = 2166136261u;

	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.transfer ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.sceneColorSpace ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.toneMap ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.grade ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.outputPrimaries ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.gamutMap ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.exposureAlgorithm ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.requestedBackend ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.selectedBackend ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.nativeBackend ) );
	hash = GLX_RenderIR_HashValue( hash, transform.autoExposure ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, transform.outputHardwareActive ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, transform.outputExperimental ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, transform.displayHdrEnabled ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, transform.displayHdrHeadroomValid ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, transform.displayIccProfileAvailable ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.displayIccProfileBytes ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.hdrMode ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.requestedPrecisionMode ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.precisionMode ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( transform.renderScaleMode ) );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.exposure );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.bloomThreshold );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.bloomSoftKnee );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.paperWhiteNits );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.maxOutputNits );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.displayHdrHeadroom );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.displaySdrWhiteNits );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.displayMaxNits );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.greyscale );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.legacyGamma );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.legacyOverbright );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.crtAmount );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.crtScanlineStrength );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.crtMaskStrength );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.crtCurvature );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.crtChromatic );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.crtInvWidth );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.crtInvHeight );
	for ( int i = 0; i < 3; i++ ) {
		hash = GLX_RenderIR_HashFloatValue( hash, transform.gradeLift[i] );
		hash = GLX_RenderIR_HashFloatValue( hash, transform.gradeGamma[i] );
		hash = GLX_RenderIR_HashFloatValue( hash, transform.gradeGain[i] );
	}
	hash = GLX_RenderIR_HashFloatValue( hash, transform.whitePointSourceKelvin );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.whitePointTargetKelvin );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.lutSize );
	hash = GLX_RenderIR_HashFloatValue( hash, transform.lutScale );
	return hash ? hash : 1u;
}

static ID_INLINE unsigned int GLX_RenderIR_HashPostNode( const PostNode &node )
{
	unsigned int hash = 2166136261u;

	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( node.kind ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( node.pass ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( node.sequence ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( node.inputTarget ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( node.outputTarget ) );
	hash = GLX_RenderIR_HashValue( hash, node.flags );
	hash = GLX_RenderIR_HashValue( hash, GLX_RenderIR_HashOutputTransform( node.output ) );
	return hash ? hash : 1u;
}

static ID_INLINE unsigned int GLX_RenderIR_HashPostOutputPlan( const PostOutputPlan &plan )
{
	unsigned int hash = 2166136261u;

	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( plan.nodeCount ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( plan.captureRequest ) );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( plan.captureSelected ) );
	hash = GLX_RenderIR_HashValue( hash, plan.captureHdrAware ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, plan.captureSupported ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, plan.outputValid ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, plan.outputTransformPresent ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, plan.outputTransformExecutable ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, plan.executorImplemented ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, plan.glxOwned ? 1u : 0u );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( plan.executableNodeCount ) );
	hash = GLX_RenderIR_HashValue( hash, plan.fallbackReasons );
	hash = GLX_RenderIR_HashValue( hash, static_cast<unsigned int>( plan.predictedResult ) );
	hash = GLX_RenderIR_HashValue( hash, GLX_RenderIR_HashOutputTransform( plan.output ) );
	for ( int i = 0; i < plan.nodeCount && i < GLX_RENDER_IR_MAX_POST_OUTPUT_NODES; i++ ) {
		hash = GLX_RenderIR_HashValue( hash, GLX_RenderIR_HashPostNode( plan.nodes[i] ) );
	}
	return hash ? hash : 1u;
}

static ID_INLINE qboolean GLX_RenderIR_ValidateWorldPacket( const WorldPacket &packet )
{
	return packet.surfaces >= 0 && packet.vertexes >= 0 && packet.indexes >= 0 &&
		packet.itemCount >= 0 &&
		GLX_RenderIR_ValidateMaterial( packet.material ) &&
		GLX_RenderIR_ValidateUploadPlan( packet.upload ) ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_RenderIR_ValidateDynamicDraw( const DynamicDraw &draw )
{
	if ( draw.primitive == 0 || draw.count <= 0 ) {
		return qfalse;
	}
	if ( draw.kind == DynamicDrawKind::Indexed && draw.indexType == 0 ) {
		return qfalse;
	}
	return GLX_RenderIR_ValidateMaterial( draw.material ) &&
		GLX_RenderIR_ValidateUploadPlan( draw.upload ) ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_RenderIR_ValidateOutputTransform( const OutputTransform &transform )
{
	const float scalarValues[] = {
		transform.exposure, transform.bloomThreshold, transform.bloomSoftKnee,
		transform.paperWhiteNits, transform.maxOutputNits, transform.displayHdrHeadroom,
		transform.displaySdrWhiteNits, transform.displayMaxNits, transform.greyscale,
		transform.legacyGamma, transform.legacyOverbright, transform.crtAmount,
		transform.crtScanlineStrength, transform.crtMaskStrength,
		transform.crtCurvature, transform.crtChromatic,
		transform.crtInvWidth, transform.crtInvHeight,
		transform.whitePointSourceKelvin, transform.whitePointTargetKelvin,
		transform.lutSize, transform.lutScale
	};

	for ( float value : scalarValues ) {
		if ( !std::isfinite( value ) ) {
			return qfalse;
		}
	}
	for ( int i = 0; i < 3; i++ ) {
		if ( !std::isfinite( transform.gradeLift[i] ) ||
			!std::isfinite( transform.gradeGamma[i] ) ||
			!std::isfinite( transform.gradeGain[i] ) ) {
			return qfalse;
		}
	}
	if ( transform.exposure < 0.0f || transform.bloomThreshold < 0.0f ||
		transform.bloomSoftKnee < 0.0f || transform.bloomSoftKnee > 1.0f ||
		transform.paperWhiteNits < 0.0f || transform.maxOutputNits < 0.0f ||
		transform.displayHdrHeadroom < 0.0f || transform.displaySdrWhiteNits < 0.0f ||
		transform.displayMaxNits < 0.0f || transform.displayIccProfileBytes < 0 ||
		transform.legacyGamma <= 0.0f || transform.legacyOverbright < 0.0f ||
		transform.crtAmount < 0.0f || transform.crtAmount > 1.0f ||
		transform.crtScanlineStrength < 0.0f || transform.crtScanlineStrength > 1.0f ||
		transform.crtMaskStrength < 0.0f || transform.crtMaskStrength > 1.0f ||
		transform.crtCurvature < 0.0f || transform.crtCurvature > 0.25f ||
		transform.crtChromatic < 0.0f || transform.crtChromatic > 8.0f ||
		transform.crtInvWidth <= 0.0f || transform.crtInvHeight <= 0.0f ||
		transform.whitePointSourceKelvin < 1000.0f || transform.whitePointTargetKelvin < 1000.0f ||
		transform.whitePointSourceKelvin > 40000.0f || transform.whitePointTargetKelvin > 40000.0f ||
		transform.lutSize < 0.0f || transform.lutScale < 0.0f ) {
		return qfalse;
	}
	if ( transform.requestedBackend < ROUTPUT_REQUEST_AUTO ||
		transform.requestedBackend >= ROUTPUT_REQUEST_COUNT ||
		transform.selectedBackend < ROUTPUT_BACKEND_SDR_SRGB ||
		transform.selectedBackend >= ROUTPUT_BACKEND_COUNT ||
		transform.nativeBackend < ROUTPUT_BACKEND_SDR_SRGB ||
		transform.nativeBackend >= ROUTPUT_BACKEND_COUNT ) {
		return qfalse;
	}
	if ( !GLX_RenderIR_OutputTransferImplemented( transform.transfer ) ||
		!GLX_RenderIR_SceneColorSpaceImplemented( transform.sceneColorSpace ) ||
		!GLX_RenderIR_ToneMapOperatorImplemented( transform.toneMap ) ||
		!GLX_RenderIR_ColorGradeModeImplemented( transform.grade ) ||
		!GLX_RenderIR_OutputPrimariesImplemented( transform.outputPrimaries ) ||
		!GLX_RenderIR_GamutMapModeImplemented( transform.gamutMap ) ||
		!GLX_RenderIR_ExposureReductionImplemented( transform.exposureAlgorithm ) ) {
		return qfalse;
	}
	if ( transform.exposureAlgorithm == ExposureReductionAlgorithm::Manual &&
		transform.autoExposure ) {
		return qfalse;
	}
	if ( transform.outputPrimaries == OutputPrimaries::Native &&
		!GLX_RenderIR_OutputPrimariesNativePassthroughAllowed( transform ) ) {
		return qfalse;
	}
	for ( int i = 0; i < 3; i++ ) {
		if ( transform.gradeGamma[i] <= 0.0f || transform.gradeGain[i] < 0.0f ) {
			return qfalse;
		}
	}
	if ( transform.precisionMode != -1 && transform.precisionMode != 8 &&
		transform.precisionMode != 16 ) {
		return qfalse;
	}
	if ( transform.requestedPrecisionMode != -1 && transform.requestedPrecisionMode != 0 &&
		transform.requestedPrecisionMode != 8 && transform.requestedPrecisionMode != 16 ) {
		return qfalse;
	}
	if ( transform.sceneColorSpace == SceneColorSpace::SceneLinear &&
		transform.hdrMode <= 0 ) {
		return qfalse;
	}
	if ( transform.sceneColorSpace == SceneColorSpace::SceneLinear &&
		transform.precisionMode != 16 ) {
		return qfalse;
	}
	if ( transform.outputHardwareActive &&
		( transform.selectedBackend == ROUTPUT_BACKEND_SDR_SRGB ||
		transform.sceneColorSpace != SceneColorSpace::SceneLinear ) ) {
		return qfalse;
	}
	if ( transform.outputHardwareActive ) {
		switch ( transform.selectedBackend ) {
		case ROUTPUT_BACKEND_WINDOWS_SCRGB:
			if ( transform.transfer != OutputTransfer::ScRgb ||
				transform.outputPrimaries != OutputPrimaries::SrgbBt709 ) {
				return qfalse;
			}
			break;
		case ROUTPUT_BACKEND_HDR10_PQ:
			if ( transform.transfer != OutputTransfer::Hdr10Pq ||
				transform.outputPrimaries != OutputPrimaries::Bt2020 ) {
				return qfalse;
			}
			break;
		case ROUTPUT_BACKEND_MACOS_EDR:
			if ( transform.transfer != OutputTransfer::MacEdr ||
				transform.outputPrimaries != OutputPrimaries::DisplayP3 ) {
				return qfalse;
			}
			break;
		case ROUTPUT_BACKEND_LINUX_EXPERIMENTAL_HDR:
			if ( !GLX_RenderIR_OutputPrimariesNativePassthroughAllowed( transform ) ) {
				return qfalse;
			}
			break;
		default:
			return qfalse;
		}
	}
	return qtrue;
}

static ID_INLINE qboolean GLX_RenderIR_ValidatePostNode( const PostNode &node )
{
	return node.sequence >= 0 && GLX_RenderIR_ValidateOutputTransform( node.output ) ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_RenderIR_TierSupportsUploadPlan( RenderProductTier tier,
	const UploadPlan &plan )
{
	if ( !GLX_RenderIR_ValidateUploadPlan( plan ) ) {
		return qfalse;
	}

	if ( tier == RenderProductTier::GL2X || tier == RenderProductTier::GL3X ||
		tier == RenderProductTier::GL41 ) {
		if ( plan.sync == UploadSyncPolicy::PersistentFence ||
			plan.strategy == static_cast<int>( StreamStrategy::PersistentMapped ) ) {
			return qfalse;
		}
		return qtrue;
	}

	if ( tier != RenderProductTier::GL12 ) {
		return qtrue;
	}

	switch ( plan.kind ) {
	case UploadPlanKind::NoUpload:
	case UploadPlanKind::ClientMemory:
	case UploadPlanKind::StaticWorld:
	case UploadPlanKind::Readback:
		return qtrue;
	case UploadPlanKind::TransientStream:
	case UploadPlanKind::PostProcess:
	default:
		return qfalse;
	}
}

static ID_INLINE qboolean GLX_RenderIR_TierSupportsMaterial( RenderProductTier tier,
	const MaterialIR &material )
{
	(void)tier;
	return GLX_RenderIR_ValidateMaterial( material );
}

static ID_INLINE qboolean GLX_RenderIR_TierSupportsWorldPacket( RenderProductTier tier,
	const WorldPacket &packet )
{
	return packet.surfaces >= 0 && packet.vertexes >= 0 && packet.indexes >= 0 &&
		packet.itemCount >= 0 &&
		GLX_RenderIR_TierSupportsMaterial( tier, packet.material ) &&
		GLX_RenderIR_TierSupportsUploadPlan( tier, packet.upload ) ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_RenderIR_TierSupportsDynamicDraw( RenderProductTier tier,
	const DynamicDraw &draw )
{
	if ( !GLX_RenderIR_ValidateDynamicDraw( draw ) ) {
		return qfalse;
	}
	return GLX_RenderIR_TierSupportsMaterial( tier, draw.material ) &&
		GLX_RenderIR_TierSupportsUploadPlan( tier, draw.upload ) ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_RenderIR_TierSupportsOutputTransform( RenderProductTier tier,
	const OutputTransform &transform )
{
	if ( !GLX_RenderIR_ValidateOutputTransform( transform ) ) {
		return qfalse;
	}
	if ( tier == RenderProductTier::GL2X ) {
		if ( transform.sceneColorSpace != SceneColorSpace::DisplayReferredSdr ) {
			return qfalse;
		}
		switch ( transform.transfer ) {
		case OutputTransfer::SdrSrgb:
		case OutputTransfer::ScreenshotSrgb:
			return qtrue;
		case OutputTransfer::LinearSrgb:
		case OutputTransfer::ScRgb:
		case OutputTransfer::Hdr10Pq:
		case OutputTransfer::MacEdr:
		default:
			return qfalse;
		}
	}
	if ( tier != RenderProductTier::GL12 ) {
		return qtrue;
	}
	if ( transform.sceneColorSpace != SceneColorSpace::DisplayReferredSdr ) {
		return qfalse;
	}

	switch ( transform.transfer ) {
	case OutputTransfer::SdrSrgb:
	case OutputTransfer::ScreenshotSrgb:
		return qtrue;
	case OutputTransfer::LinearSrgb:
	case OutputTransfer::ScRgb:
	case OutputTransfer::Hdr10Pq:
	case OutputTransfer::MacEdr:
	default:
		return qfalse;
	}
}

static ID_INLINE qboolean GLX_RenderIR_TierSupportsPostNode( RenderProductTier tier,
	const PostNode &node )
{
	if ( !GLX_RenderIR_ValidatePostNode( node ) ) {
		return qfalse;
	}
	if ( tier == RenderProductTier::GL2X ) {
		if ( !GLX_RenderIR_TierSupportsOutputTransform( tier, node.output ) ) {
			return qfalse;
		}
		switch ( node.kind ) {
		case PostNodeKind::NoPostNode:
		case PostNodeKind::CopyScene:
		case PostNodeKind::BloomPrefinal:
		case PostNodeKind::BloomFinal:
		case PostNodeKind::GammaDirect:
		case PostNodeKind::GammaBlit:
		case PostNodeKind::Resolve:
		case PostNodeKind::Screenshot:
			return qtrue;
		case PostNodeKind::ToneMap:
		case PostNodeKind::Grade:
		default:
			return qfalse;
		}
	}
	if ( tier != RenderProductTier::GL12 ) {
		return qtrue;
	}
	if ( !GLX_RenderIR_TierSupportsOutputTransform( tier, node.output ) ) {
		return qfalse;
	}

	switch ( node.kind ) {
	case PostNodeKind::NoPostNode:
	case PostNodeKind::CopyScene:
	case PostNodeKind::GammaDirect:
	case PostNodeKind::GammaBlit:
	case PostNodeKind::Resolve:
	case PostNodeKind::Screenshot:
		return qtrue;
	case PostNodeKind::BloomPrefinal:
	case PostNodeKind::BloomFinal:
	case PostNodeKind::ToneMap:
	case PostNodeKind::Grade:
	default:
		return qfalse;
	}
}

static ID_INLINE qboolean GLX_RenderIR_ModernPostOutputTier( RenderProductTier tier )
{
	return tier == RenderProductTier::GL3X ||
		tier == RenderProductTier::GL41 ||
		tier == RenderProductTier::GL46 ? qtrue : qfalse;
}

static ID_INLINE qboolean GLX_RenderIR_PostNodeExecutorImplemented( RenderProductTier tier,
	const PostNode &node )
{
	if ( !GLX_RenderIR_ModernPostOutputTier( tier ) ||
		!GLX_RenderIR_ValidatePostNode( node ) ) {
		return qfalse;
	}

	switch ( node.kind ) {
	case PostNodeKind::CopyScene:
	case PostNodeKind::BloomPrefinal:
	case PostNodeKind::BloomFinal:
	case PostNodeKind::GammaDirect:
	case PostNodeKind::GammaBlit:
	case PostNodeKind::Resolve:
	case PostNodeKind::ToneMap:
	case PostNodeKind::Grade:
	case PostNodeKind::Screenshot:
		return qtrue;
	case PostNodeKind::NoPostNode:
	default:
		return qfalse;
	}
}

static ID_INLINE qboolean GLX_RenderIR_OutputTransformExecutorImplemented( RenderProductTier tier,
	const OutputTransform &output )
{
	if ( !GLX_RenderIR_ModernPostOutputTier( tier ) ||
		!GLX_RenderIR_ValidateOutputTransform( output ) ||
		output.sceneColorSpace != SceneColorSpace::SceneLinear ||
		output.hdrMode <= 0 ||
		output.precisionMode != 16 ) {
		return qfalse;
	}

	switch ( output.transfer ) {
	case OutputTransfer::SdrSrgb:
	case OutputTransfer::ScreenshotSrgb:
	case OutputTransfer::LinearSrgb:
	case OutputTransfer::ScRgb:
	case OutputTransfer::Hdr10Pq:
	case OutputTransfer::MacEdr:
		return qtrue;
	default:
		return qfalse;
	}
}

static ID_INLINE OutputTransform GLX_RenderIR_CaptureOutputTransform(
	const OutputTransform &displayOutput, CaptureExportPolicy selected )
{
	OutputTransform capture = displayOutput;

	if ( selected == CaptureExportPolicy::SdrSrgb ) {
		capture.transfer = OutputTransfer::ScreenshotSrgb;
		capture.sceneColorSpace = SceneColorSpace::DisplayReferredSdr;
		capture.toneMap = ToneMapOperator::Legacy;
		capture.grade = ColorGradeMode::NoColorGrade;
		capture.outputPrimaries = OutputPrimaries::SrgbBt709;
		capture.gamutMap = GamutMapMode::NoGamutMap;
		capture.selectedBackend = ROUTPUT_BACKEND_SDR_SRGB;
		capture.outputHardwareActive = qfalse;
		capture.outputExperimental = qfalse;
		capture.hdrMode = 0;
		capture.precisionMode = 8;
		capture.maxOutputNits = capture.paperWhiteNits;
		for ( int i = 0; i < 3; i++ ) {
			capture.gradeLift[i] = 0.0f;
			capture.gradeGamma[i] = 1.0f;
			capture.gradeGain[i] = 1.0f;
		}
		capture.whitePointSourceKelvin = 6504.0f;
		capture.whitePointTargetKelvin = 6504.0f;
		capture.lutSize = 0.0f;
		capture.lutScale = 4.0f;
	}

	return capture;
}

static ID_INLINE void GLX_RenderIR_UpdatePostOutputImplementationStatus(
	PostOutputPlan *plan, RenderProductTier tier )
{
	if ( !plan ) {
		return;
	}

	plan->executableNodeCount = 0;
	for ( int i = 0; i < plan->nodeCount && i < GLX_RENDER_IR_MAX_POST_OUTPUT_NODES; i++ ) {
		if ( GLX_RenderIR_PostNodeExecutorImplemented( tier, plan->nodes[i] ) ) {
			plan->executableNodeCount++;
		}
	}
	plan->outputTransformExecutable = ( plan->outputTransformPresent &&
		GLX_RenderIR_OutputTransformExecutorImplemented( tier, plan->output ) ) ? qtrue : qfalse;
	plan->executorImplemented = ( plan->nodeCount > 0 &&
		plan->executableNodeCount == plan->nodeCount &&
		plan->outputTransformPresent &&
		plan->outputTransformExecutable ) ? qtrue : qfalse;

	if ( plan->outputTransformPresent && plan->nodeCount > 0 &&
		!plan->executorImplemented ) {
		plan->fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_EXECUTOR_NOT_IMPLEMENTED;
	}
}

static ID_INLINE void GLX_RenderIR_AddPostOutputNode( PostOutputPlan *plan,
	PostNodeKind kind, int sequence, int inputTarget, int outputTarget,
	unsigned int flags, const OutputTransform &output )
{
	if ( !plan || plan->nodeCount >= GLX_RENDER_IR_MAX_POST_OUTPUT_NODES ) {
		if ( plan ) {
			plan->fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_NO_NODES;
		}
		return;
	}

	PostNode &node = plan->nodes[plan->nodeCount++];
	node.kind = kind;
	node.pass = FramePassKind::PostProcess;
	node.sequence = sequence;
	node.inputTarget = inputTarget;
	node.outputTarget = outputTarget;
	node.flags = flags;
	node.output = output;
}

static ID_INLINE PostOutputPlan GLX_RenderIR_BuildPostOutputPlan(
	const PostOutputPlanInputs &inputs )
{
	PostOutputPlan plan {};
	const qboolean directBackBuffer = ( inputs.screenshotMask == 0 &&
		!inputs.windowAdjusted && !inputs.minimized ) ? qtrue : qfalse;
	int sequence = inputs.sequenceBase < 0 ? 0 : inputs.sequenceBase;

	plan.output = inputs.output;
	plan.captureRequest = inputs.captureRequest;
	plan.captureSelected = GLX_RenderIR_ResolveCaptureExportPolicy( inputs.captureRequest );
	plan.captureHdrAware = GLX_RenderIR_CaptureExportPolicyHdrAware( inputs.captureRequest );
	plan.captureSupported = GLX_RenderIR_CaptureExportPolicySupported( inputs.captureRequest );
	plan.outputValid = GLX_RenderIR_ValidateOutputTransform( inputs.output );
	plan.outputTransformPresent = plan.outputValid;
	plan.predictedResult = GLX_POSTPROCESS_RESULT_NONE;

	if ( !GLX_RenderIR_ModernPostOutputTier( inputs.tier ) ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_TIER;
	}
	if ( !inputs.fboReady ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_FBO_NOT_READY;
	}
	if ( !inputs.programReady ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_PROGRAM_NOT_READY;
	}
	if ( !inputs.framebufferFnsReady ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_FRAMEBUFFER_FNS;
	}
	if ( inputs.minimized ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_MINIMIZED;
	}
	if ( !plan.outputValid ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_INVALID_OUTPUT;
	}
	if ( !inputs.outputContractValid ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_OUTPUT_CONTRACT;
	}
	if ( GLX_RenderIR_ModernPostOutputTier( inputs.tier ) &&
		!inputs.postShaderExecutorEnabled ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_EXECUTOR_DISABLED;
	}

	if ( inputs.bloomAvailable ) {
		const PostNodeKind bloomKind = directBackBuffer ? PostNodeKind::BloomFinal :
			PostNodeKind::BloomPrefinal;
		GLX_RenderIR_AddPostOutputNode( &plan, bloomKind, sequence++,
			inputs.fboReadIndex, directBackBuffer ? 0 : 1, inputs.flags, inputs.output );
	}

	if ( plan.outputValid && inputs.output.grade != ColorGradeMode::NoColorGrade ) {
		GLX_RenderIR_AddPostOutputNode( &plan, PostNodeKind::Grade, sequence++,
			inputs.bloomAvailable ? 1 : inputs.fboReadIndex, 1, inputs.flags, inputs.output );
	}
	if ( plan.outputValid && inputs.output.toneMap != ToneMapOperator::Legacy ) {
		GLX_RenderIR_AddPostOutputNode( &plan, PostNodeKind::ToneMap, sequence++,
			inputs.bloomAvailable ? 1 : inputs.fboReadIndex, 1, inputs.flags, inputs.output );
	}

	if ( inputs.minimized ) {
		plan.predictedResult = GLX_POSTPROCESS_RESULT_MINIMIZED;
		GLX_RenderIR_AddPostOutputNode( &plan, PostNodeKind::Resolve, sequence++,
			inputs.fboReadIndex, 1, inputs.flags, inputs.output );
	} else if ( inputs.bloomAvailable && directBackBuffer ) {
		plan.predictedResult = GLX_POSTPROCESS_RESULT_BLOOM_FINAL;
	} else if ( directBackBuffer ) {
		plan.predictedResult = GLX_POSTPROCESS_RESULT_GAMMA_DIRECT;
		GLX_RenderIR_AddPostOutputNode( &plan, PostNodeKind::GammaDirect, sequence++,
			inputs.fboReadIndex, 0, inputs.flags, inputs.output );
	} else {
		plan.predictedResult = GLX_POSTPROCESS_RESULT_GAMMA_BLIT;
		GLX_RenderIR_AddPostOutputNode( &plan, PostNodeKind::GammaBlit, sequence++,
			inputs.bloomAvailable ? 1 : inputs.fboReadIndex, 0, inputs.flags, inputs.output );
	}
	if ( inputs.screenshotMask != 0 && !inputs.minimized ) {
		OutputTransform captureOutput =
			GLX_RenderIR_CaptureOutputTransform( inputs.output, plan.captureSelected );
		GLX_RenderIR_AddPostOutputNode( &plan, PostNodeKind::Screenshot, sequence++,
			0, 0, inputs.flags, captureOutput );
	}

	if ( plan.nodeCount <= 0 ) {
		plan.fallbackReasons |= GLX_POST_OUTPUT_FALLBACK_NO_NODES;
	}
	GLX_RenderIR_UpdatePostOutputImplementationStatus( &plan, inputs.tier );
	plan.glxOwned = ( plan.fallbackReasons == GLX_POST_OUTPUT_FALLBACK_NONE &&
		plan.executorImplemented ) ? qtrue : qfalse;
	plan.hash = GLX_RenderIR_HashPostOutputPlan( plan );
	return plan;
}

static ID_INLINE UploadPlan GLX_RenderIR_MakeUploadPlan( UploadPlanKind kind,
	int strategy, unsigned int bytes, unsigned int vertexBytes, unsigned int indexBytes )
{
	UploadPlan plan {};
	plan.kind = kind;
	plan.strategy = strategy;
	plan.bytes = bytes;
	plan.vertexBytes = vertexBytes;
	plan.indexBytes = indexBytes;
	plan.alignment = 0;
	plan.sync = UploadSyncPolicy::NoSync;
	return plan;
}

static ID_INLINE MaterialIR GLX_RenderIR_MakeMaterial( int sort, int flags,
	unsigned int stateBits, int shaderStagePasses )
{
	MaterialIR material {};
	material.sort = sort;
	material.flags = flags;
	material.stateBits = stateBits;
	material.alphaGen = GLX_MATERIAL_ALPHAGEN_SKIP;
	material.rgbWaveFunc = GLX_MATERIAL_WAVEFUNC_NONE;
	material.alphaWaveFunc = GLX_MATERIAL_WAVEFUNC_NONE;
	material.tcGen1 = GLX_MATERIAL_TCGEN_BAD;
	material.fogAdjust = GLX_MATERIAL_FOG_ADJUST_NONE;
	material.shaderStagePasses = shaderStagePasses;
	return material;
}

static ID_INLINE OutputTransform GLX_RenderIR_DefaultOutputTransform()
{
	OutputTransform transform {};
	transform.transfer = OutputTransfer::SdrSrgb;
	transform.sceneColorSpace = SceneColorSpace::DisplayReferredSdr;
	transform.toneMap = ToneMapOperator::Legacy;
	transform.grade = ColorGradeMode::NoColorGrade;
	transform.outputPrimaries = OutputPrimaries::SrgbBt709;
	transform.gamutMap = GamutMapMode::NoGamutMap;
	transform.exposureAlgorithm = ExposureReductionAlgorithm::Manual;
	transform.requestedBackend = ROUTPUT_REQUEST_AUTO;
	transform.selectedBackend = ROUTPUT_BACKEND_SDR_SRGB;
	transform.nativeBackend = ROUTPUT_BACKEND_SDR_SRGB;
	transform.autoExposure = qfalse;
	transform.hdrMode = 0;
	transform.requestedPrecisionMode = 0;
	transform.precisionMode = 8;
	transform.exposure = 1.0f;
	transform.bloomThreshold = 0.75f;
	transform.bloomSoftKnee = 0.0f;
	transform.paperWhiteNits = 203.0f;
	transform.maxOutputNits = 203.0f;
	transform.displayHdrHeadroom = 1.0f;
	transform.displaySdrWhiteNits = 203.0f;
	transform.displayMaxNits = 203.0f;
	transform.legacyGamma = 1.0f;
	transform.legacyOverbright = 1.0f;
	transform.crtAmount = 0.0f;
	transform.crtScanlineStrength = 0.55f;
	transform.crtMaskStrength = 0.35f;
	transform.crtCurvature = 0.01f;
	transform.crtChromatic = 1.35f;
	transform.crtInvWidth = 1.0f;
	transform.crtInvHeight = 1.0f;
	transform.gradeLift[0] = 0.0f;
	transform.gradeLift[1] = 0.0f;
	transform.gradeLift[2] = 0.0f;
	transform.gradeGamma[0] = 1.0f;
	transform.gradeGamma[1] = 1.0f;
	transform.gradeGamma[2] = 1.0f;
	transform.gradeGain[0] = 1.0f;
	transform.gradeGain[1] = 1.0f;
	transform.gradeGain[2] = 1.0f;
	transform.whitePointSourceKelvin = 6504.0f;
	transform.whitePointTargetKelvin = 6504.0f;
	transform.lutSize = 0.0f;
	transform.lutScale = 4.0f;
	return transform;
}

} // namespace glx

#endif // GLX_RENDER_IR_H
