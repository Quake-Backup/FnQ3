#ifndef GLX_RENDER_IR_H
#define GLX_RENDER_IR_H

#include "glx_types.h"
#include "../renderercommon/tr_glx_public.h"

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

struct FramePass {
	FramePassKind kind;
	int sequence;
	int sortStart;
	int sortEnd;
	unsigned int flags;
};

enum class UploadPlanKind {
	None,
	ClientMemory,
	TransientStream,
	StaticWorld,
	PostProcess,
	Readback
};

enum class UploadSyncPolicy {
	None,
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
	int tcGen0;
	int tcGen1;
	int texMods0;
	int texMods1;
	int materialCombine;
	qboolean fogPass;
	int shaderStagePasses;
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

struct OutputTransform {
	OutputTransfer transfer;
	int hdrMode;
	int renderScaleMode;
	float exposure;
	float paperWhiteNits;
	float maxOutputNits;
	float greyscale;
};

enum class PostNodeKind {
	None,
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
	if ( plan.kind == UploadPlanKind::None || plan.kind == UploadPlanKind::ClientMemory ) {
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
	return transform.exposure >= 0.0f && transform.paperWhiteNits >= 0.0f &&
		transform.maxOutputNits >= 0.0f ? qtrue : qfalse;
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
	case UploadPlanKind::None:
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
		case PostNodeKind::None:
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
	case PostNodeKind::None:
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
	plan.sync = UploadSyncPolicy::None;
	return plan;
}

static ID_INLINE MaterialIR GLX_RenderIR_MakeMaterial( int sort, int flags,
	unsigned int stateBits, int shaderStagePasses )
{
	MaterialIR material {};
	material.sort = sort;
	material.flags = flags;
	material.stateBits = stateBits;
	material.shaderStagePasses = shaderStagePasses;
	return material;
}

static ID_INLINE OutputTransform GLX_RenderIR_DefaultOutputTransform()
{
	OutputTransform transform {};
	transform.transfer = OutputTransfer::SdrSrgb;
	transform.exposure = 1.0f;
	transform.paperWhiteNits = 80.0f;
	transform.maxOutputNits = 80.0f;
	return transform;
}

} // namespace glx

#endif // GLX_RENDER_IR_H
