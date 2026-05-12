#include "glx_local.h"
#include "glx_module.h"
#include "glx_caps.h"
#include "glx_debug.h"
#include "glx_executor.h"
#include "glx_material.h"
#include "glx_postprocess.h"
#include "glx_post_shader.h"
#include "glx_profiler.h"
#include "glx_static_world.h"
#include "glx_stream.h"

#include <cctype>
#include <cstdlib>
#include <cstdio>

#ifndef GL_BUFFER
#define GL_BUFFER 0x82E0
#endif

namespace glx {

refimport_t *g_imports = nullptr;

refimport_t &RI()
{
	return *g_imports;
}

qboolean ImportsReady()
{
	return g_imports ? qtrue : qfalse;
}

const char *BoolName( qboolean value )
{
	return value ? "yes" : "no";
}

qboolean ToQBool( bool value )
{
	return value ? qtrue : qfalse;
}

static int GLX_Module_Stricmp( const char *lhs, const char *rhs )
{
	if ( !lhs ) {
		lhs = "";
	}
	if ( !rhs ) {
		rhs = "";
	}

	while ( *lhs || *rhs ) {
		const int l = std::tolower( static_cast<unsigned char>( *lhs ) );
		const int r = std::tolower( static_cast<unsigned char>( *rhs ) );
		if ( l != r ) {
			return l - r;
		}
		if ( *lhs ) {
			lhs++;
		}
		if ( *rhs ) {
			rhs++;
		}
	}

	return 0;
}

static const char *GLX_Module_MdiSourceName( unsigned int source )
{
	switch ( source ) {
	case 1:
		return "static";
	case 2:
		return "compact";
	default:
		return "none";
	}
}

enum class GlxProfile {
	Off,
	Rc,
	Stress,
};

struct ProfileCvarSetting {
	const char *name;
	const char *offValue;
	const char *rcValue;
	const char *stressValue;
};

static const ProfileCvarSetting GLX_PROFILE_CVARS[] = {
	{ "r_fbo", "0", "1", "1" },
	{ "r_bloom", "0", "2", "2" },
	{ "r_bloom_passes", "5", "3", "3" },
	{ "r_hdrBloomFormat", "0", "0", "0" },
	{ "r_vbo", "0", "1", "1" },
	{ "r_glxWorldRenderer", "0", "1", "1" },
	{ "r_glxStreamDraw", "0", "1", "1" },
	{ "r_glxStreamDrawKeyMode", "0", "0", "0" },
	{ "r_glxStreamDrawMultitexture", "0", "1", "1" },
	{ "r_glxStreamDrawFog", "0", "1", "1" },
	{ "r_glxStreamDrawDepthFragment", "0", "1", "1" },
	{ "r_glxStreamDrawTexMods", "0", "1", "1" },
	{ "r_glxStreamDrawEnvironment", "0", "1", "1" },
	{ "r_glxStreamDrawDynamicLights", "0", "0", "0" },
	{ "r_glxStreamDrawScreenMaps", "0", "0", "0" },
	{ "r_glxStreamDrawVideoMaps", "0", "0", "0" },
	{ "r_glxStreamDrawShadows", "0", "1", "1" },
	{ "r_glxStreamDrawBeams", "0", "1", "1" },
	{ "r_glxStreamDrawPostProcess", "0", "1", "1" },
	{ "r_glxMaterialRenderer", "0", "1", "1" },
	{ "r_glxMaterialPrecache", "0", "1", "1" },
	{ "r_glxGpuTiming", "0", "1", "1" },
	{ "r_glxGpuPassTiming", "0", "1", "1" },
	{ "r_glxStaticWorldArena", "0", "1", "1" },
	{ "r_glxStaticWorldArenaDraw", "0", "1", "1" },
	{ "r_glxStaticWorldDraw", "0", "1", "1" },
	{ "r_glxStaticWorldSoftDraw", "0", "1", "1" },
	{ "r_glxStaticWorldDrawPolicy", "full", "full", "full" },
	{ "r_glxStaticWorldMultiDraw", "0", "1", "1" },
	{ "r_glxStaticWorldPacketBatch", "0", "1", "1" },
	{ "r_glxStaticWorldIndirectBuffer", "0", "1", "1" },
	{ "r_glxStaticWorldIndirectDraw", "0", "1", "1" },
	{ "r_glxStaticWorldMultiDrawIndirect", "0", "1", "1" },
	{ "r_glxStaticWorldMultiDrawIndirectCompact", "0", "0", "1" },
	{ "r_glxStaticWorldMultiDrawIndirectSpans", "0", "1", "1" },
};

static const char *GLX_Module_ProfileName( GlxProfile profile )
{
	switch ( profile ) {
	case GlxProfile::Off:
		return "off";
	case GlxProfile::Rc:
		return "rc";
	case GlxProfile::Stress:
		return "stress";
	default:
		return "custom";
	}
}

static const char *GLX_Module_ProfileValue( const ProfileCvarSetting &setting, GlxProfile profile )
{
	switch ( profile ) {
	case GlxProfile::Off:
		return setting.offValue;
	case GlxProfile::Rc:
		return setting.rcValue;
	case GlxProfile::Stress:
		return setting.stressValue;
	default:
		return "";
	}
}

static qboolean GLX_Module_ParseProfile( const char *name, GlxProfile *profile )
{
	if ( !name || !name[0] ) {
		return qfalse;
	}

	if ( !GLX_Module_Stricmp( name, "off" ) ||
		!GLX_Module_Stricmp( name, "baseline" ) ||
		!GLX_Module_Stricmp( name, "compat" ) ) {
		if ( profile ) {
			*profile = GlxProfile::Off;
		}
		return qtrue;
	}

	if ( !GLX_Module_Stricmp( name, "rc" ) ||
		!GLX_Module_Stricmp( name, "parity" ) ||
		!GLX_Module_Stricmp( name, "candidate" ) ) {
		if ( profile ) {
			*profile = GlxProfile::Rc;
		}
		return qtrue;
	}

	if ( !GLX_Module_Stricmp( name, "stress" ) ) {
		if ( profile ) {
			*profile = GlxProfile::Stress;
		}
		return qtrue;
	}

	return qfalse;
}

static void GLX_Module_CurrentCvarValue( const char *name, char *buffer, int bufferSize )
{
	if ( !buffer || bufferSize <= 0 ) {
		return;
	}

	buffer[0] = '\0';
	if ( RI().Cvar_VariableStringBuffer ) {
		RI().Cvar_VariableStringBuffer( name, buffer, bufferSize );
	}
}

static qboolean GLX_Module_ProfileMatches( GlxProfile profile )
{
	char current[64];

	for ( unsigned int i = 0; i < sizeof( GLX_PROFILE_CVARS ) / sizeof( GLX_PROFILE_CVARS[0] ); i++ ) {
		const ProfileCvarSetting &setting = GLX_PROFILE_CVARS[i];
		const char *expected = GLX_Module_ProfileValue( setting, profile );

		GLX_Module_CurrentCvarValue( setting.name, current, sizeof( current ) );
		if ( GLX_Module_Stricmp( current, expected ) ) {
			return qfalse;
		}
	}

	return qtrue;
}

static const char *GLX_Module_DetectedProfileName()
{
	if ( GLX_Module_ProfileMatches( GlxProfile::Rc ) ) {
		return "rc";
	}
	if ( GLX_Module_ProfileMatches( GlxProfile::Stress ) ) {
		return "stress";
	}
	if ( GLX_Module_ProfileMatches( GlxProfile::Off ) ) {
		return "off";
	}

	return "custom";
}

static void GLX_Module_PrintProfileUsage()
{
	RI().Printf( PRINT_ALL, "usage: glxprofile [off|rc|stress|manual|status]\n" );
	RI().Printf( PRINT_ALL, "  off     restore compatibility defaults for the cvars owned by the GLx profile\n" );
	RI().Printf( PRINT_ALL, "  rc      conservative release-candidate profile: world, stream, dynamic scene, material, bloom, timing\n" );
	RI().Printf( PRINT_ALL, "  stress  rc profile plus indirect static-world stress paths\n" );
	RI().Printf( PRINT_ALL, "  manual  clear r_glxProfile without changing the current cvars\n" );
}

static StreamReservation GLX_Module_FromPublicReservation( const glxStreamReservation_t &reservation )
{
	StreamReservation streamReservation {};

	streamReservation.buffer = reservation.buffer;
	streamReservation.offset = reservation.offset;
	streamReservation.bytes = reservation.bytes;
	streamReservation.ptr = reservation.ptr;
	streamReservation.strategy = static_cast<StreamStrategy>( reservation.strategy );
	streamReservation.mapped = reservation.mapped ? qtrue : qfalse;
	streamReservation.committed = reservation.committed ? qtrue : qfalse;

	return streamReservation;
}

static void GLX_Module_ToPublicReservation( const StreamReservation &streamReservation, glxStreamReservation_t *reservation )
{
	if ( !reservation ) {
		return;
	}

	reservation->buffer = streamReservation.buffer;
	reservation->offset = static_cast<unsigned int>( streamReservation.offset );
	reservation->bytes = static_cast<unsigned int>( streamReservation.bytes );
	reservation->ptr = streamReservation.ptr;
	reservation->strategy = static_cast<int>( streamReservation.strategy );
	reservation->mapped = streamReservation.mapped;
	reservation->committed = streamReservation.committed;
}

static UploadPlan GLX_Module_ClientMemoryUploadPlan()
{
	return GLX_RenderIR_MakeUploadPlan( UploadPlanKind::ClientMemory, -1, 0, 0, 0 );
}

static UploadPlan GLX_Module_StreamUploadPlan( int totalBytes, int vertexBytes, int indexBytes )
{
	UploadPlan plan = GLX_RenderIR_MakeUploadPlan( UploadPlanKind::TransientStream,
		-1, totalBytes > 0 ? static_cast<unsigned int>( totalBytes ) : 0,
		vertexBytes > 0 ? static_cast<unsigned int>( vertexBytes ) : 0,
		indexBytes > 0 ? static_cast<unsigned int>( indexBytes ) : 0 );
	plan.alignment = 64;
	plan.sync = UploadSyncPolicy::FrameFence;
	return plan;
}

static MaterialIR GLX_Module_DrawMaterialIR( int profilerPath )
{
	MaterialIR material = GLX_RenderIR_MakeMaterial( 0, 0, 0, 0 );
	if ( profilerPath == GLX_DRAW_DEBUG ) {
		material.flags = GLX_STAGE_DETAIL;
	}
	return material;
}

static MaterialIR GLX_Module_StageMaterialIR( int sort, int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	unsigned int texModTypes0, unsigned int texModTypes1,
	unsigned int texModSequence0, unsigned int texModSequence1,
	int rgbWaveFunc, int alphaWaveFunc,
	unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1,
	int fogAdjust, int materialCombine, qboolean fogPass )
{
	MaterialIR material = GLX_RenderIR_MakeMaterial( sort, flags, stateBits, 1 );
	material.rgbGen = rgbGen;
	material.alphaGen = alphaGen;
	material.rgbWaveFunc = rgbWaveFunc;
	material.alphaWaveFunc = alphaWaveFunc;
	material.tcGen0 = tcGen0;
	material.tcGen1 = tcGen1;
	material.texMods0 = texMods0;
	material.texMods1 = texMods1;
	material.texModTypes0 = texModTypes0;
	material.texModTypes1 = texModTypes1;
	material.texModSequence0 = texModSequence0;
	material.texModSequence1 = texModSequence1;
	material.texModWaveFuncs0 = texModWaveFuncs0;
	material.texModWaveFuncs1 = texModWaveFuncs1;
	material.fogAdjust = fogAdjust;
	material.materialCombine = materialCombine;
	material.fogPass = fogPass;
	return material;
}

static DynamicDraw GLX_Module_IndexedDrawIR( unsigned int mode, int count, unsigned int type,
	const void *indices, int legacyReason, int profilerPath )
{
	DynamicDraw draw {};
	draw.kind = DynamicDrawKind::Indexed;
	draw.pass = FramePassKind::DynamicScene;
	draw.primitive = mode;
	draw.count = count;
	draw.indexType = type;
	draw.indices = indices;
	draw.legacyReason = legacyReason;
	draw.profilerPath = profilerPath;
	draw.material = GLX_Module_DrawMaterialIR( profilerPath );
	draw.upload = legacyReason >= 0 ? GLX_Module_ClientMemoryUploadPlan() :
		GLX_Module_StreamUploadPlan( count > 0 ? count : 0, 0, count > 0 ? count : 0 );
	return draw;
}

static DynamicDraw GLX_Module_ArrayDrawIR( unsigned int mode, int first, int count,
	int legacyReason, int profilerPath )
{
	DynamicDraw draw {};
	draw.kind = DynamicDrawKind::Arrays;
	draw.pass = FramePassKind::DynamicScene;
	draw.primitive = mode;
	draw.first = first;
	draw.count = count;
	draw.legacyReason = legacyReason;
	draw.profilerPath = profilerPath;
	draw.material = GLX_Module_DrawMaterialIR( profilerPath );
	draw.upload = legacyReason >= 0 ? GLX_Module_ClientMemoryUploadPlan() :
		GLX_Module_StreamUploadPlan( count > 0 ? count : 0, count > 0 ? count : 0, 0 );
	return draw;
}

static WorldPacket GLX_Module_WorldPacketIR( int packetIndex, int sort,
	int surfaces, int vertexes, int indexes, int firstItem, int itemCount,
	int vertexOffset, int vertexBytes, int indexOffset, int indexBytes,
	int shaderStagePasses, int flags )
{
	WorldPacket packet {};
	packet.packetIndex = packetIndex;
	packet.pass = FramePassKind::SkyAndOpaqueWorld;
	packet.surfaces = surfaces;
	packet.vertexes = vertexes;
	packet.indexes = indexes;
	packet.firstItem = firstItem;
	packet.itemCount = itemCount;
	packet.vertexOffset = vertexOffset;
	packet.indexOffset = indexOffset;
	packet.material = GLX_RenderIR_MakeMaterial( sort, flags, 0, shaderStagePasses );
	packet.upload = GLX_RenderIR_MakeUploadPlan( UploadPlanKind::StaticWorld, -1,
		static_cast<unsigned int>( ( vertexBytes > 0 ? vertexBytes : 0 ) +
			( indexBytes > 0 ? indexBytes : 0 ) ),
		vertexBytes > 0 ? static_cast<unsigned int>( vertexBytes ) : 0,
		indexBytes > 0 ? static_cast<unsigned int>( indexBytes ) : 0 );
	return packet;
}

static OutputTransform GLX_Module_OutputTransformIR( const PostProcessState &postprocess )
{
	if ( GLX_RenderIR_ValidateOutputTransform( postprocess.lastOutput ) ) {
		return postprocess.lastOutput;
	}
	return GLX_RenderIR_DefaultOutputTransform();
}

static qboolean GLX_Module_PostOutputPlanHasNode( const PostOutputPlan &plan,
	PostNodeKind kind )
{
	for ( int i = 0; i < plan.nodeCount && i < GLX_RENDER_IR_MAX_POST_OUTPUT_NODES; i++ ) {
		if ( plan.nodes[i].kind == kind ) {
			return qtrue;
		}
	}
	return qfalse;
}

static unsigned int GLX_Module_PostOutputExpectedShaderBinds( const PostOutputPlan &plan )
{
	unsigned int binds = 0u;

	for ( int i = 0; i < plan.nodeCount && i < GLX_RENDER_IR_MAX_POST_OUTPUT_NODES; i++ ) {
		switch ( plan.nodes[i].kind ) {
		case PostNodeKind::BloomPrefinal:
		case PostNodeKind::BloomFinal:
		case PostNodeKind::GammaDirect:
		case PostNodeKind::GammaBlit:
			binds++;
			break;
		default:
			break;
		}
	}
	return binds;
}

static PostShaderPlan GLX_Module_PostShaderPlanForOutputPlan(
	const OutputTransform &output, const PostOutputPlan &plan )
{
	const qboolean bloomFinal = GLX_Module_PostOutputPlanHasNode( plan,
		PostNodeKind::BloomFinal );
	return GLX_PostShader_BuildPlanForOutput( output, bloomFinal );
}

static qboolean GLX_Module_EmitFrameSchedule( FramePass *passes, int capacity, int *count )
{
	return GLX_RenderIR_DefaultPassSchedule( passes, capacity, count );
}

class RendererModule {
public:
	void RegisterCommands();
	void RemoveCommands();
	void OnOpenGLReady( const glconfig_t *config, const char *extensions );
	void Shutdown( int code );
	void BeginBackendTimer();
	void EndBackendTimer();
	void BeginGpuPassTimer( int pass );
	void EndGpuPassTimer( int pass );
	void FrameComplete();
	void PrintCaps() const;
	void PrintInfo() const;
	void PrintProfile() const;
	void ProfileCommand();
	void PrintMaterial() const;
	void PrintPostProcess() const;
	void PrintStaticWorld() const;
	void PrintFrameCounters() const;
	void StreamTest();
	qboolean DrawElements( unsigned int mode, int count, unsigned int type,
		const void *indices, int legacyReason, int profilerPath );
	qboolean DrawArrays( unsigned int mode, int first, int count,
		int legacyReason, int profilerPath );
	void RecordDraw( int indexes, int path );
	void RecordShaderBatch( const char *shaderName, int sort, int numPasses, int numVertexes, int numIndexes, int flags );
	void RecordMaterialStage( int path, int flags, unsigned int stateBits, int rgbGen, int alphaGen,
		int tcGen0, int tcGen1, int texMods0, int texMods1,
		unsigned int texModTypes0, unsigned int texModTypes1,
		unsigned int texModSequence0, unsigned int texModSequence1,
		int rgbWaveFunc, int alphaWaveFunc,
		unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1,
		int fogAdjust, int materialCombine, qboolean fogPass,
		int numVertexes, int numIndexes );
	qboolean MaterialRendererActive() const;
	qboolean BindMaterialStage( int flags, unsigned int stateBits, int rgbGen, int alphaGen,
		int tcGen0, int tcGen1, int texMods0, int texMods1,
		unsigned int texModTypes0, unsigned int texModTypes1,
		unsigned int texModSequence0, unsigned int texModSequence1,
		int rgbWaveFunc, int alphaWaveFunc,
		unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1, int fogAdjust,
		int materialCombine, qboolean fogPass );
	qboolean BindFogMaterial();
	void UnbindMaterial();
	qboolean StreamDrawEnabled() const;
	qboolean StreamDrawMultitextureEnabled() const;
	qboolean StreamDrawFogEnabled() const;
	qboolean StreamDrawDepthFragmentEnabled() const;
	qboolean StreamDrawShadowsEnabled() const;
	qboolean StreamDrawBeamsEnabled() const;
	qboolean StreamDrawPostProcessEnabled() const;
	qboolean StreamDrawAllowsMaterial( int flags, unsigned int stateBits,
		int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
		unsigned int texModTypes0, unsigned int texModTypes1,
		unsigned int texModSequence0, unsigned int texModSequence1,
		int rgbWaveFunc, int alphaWaveFunc,
		unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1,
		int fogAdjust, int materialCombine, qboolean fogPass );
	qboolean StreamReserve( int bytes, int alignment, glxStreamReservation_t *reservation );
	qboolean StreamUploadAt( glxStreamReservation_t *reservation, int relativeOffset, const void *data, int bytes );
	void StreamCommit( glxStreamReservation_t *reservation );
	GLuint BindStreamArrayBuffer( GLuint buffer );
	void RestoreStreamArrayBuffer( GLuint buffer );
	GLuint BindStreamElementArrayBuffer( GLuint buffer );
	void RestoreStreamElementArrayBuffer( GLuint buffer );
	void RecordStreamBufferBind( unsigned int target, GLuint buffer );
	void RecordStreamDrawResult( int numVertexes, int numIndexes, int totalBytes, int indexBytes,
		int texcoord1Bytes, qboolean multitexture, qboolean fog, qboolean depthFragment, int materialFlags,
		unsigned int categoryMask, qboolean success );
	void RecordStreamDrawSkip( int reason );
	void ResetImageColorAudit();
	void RecordImageColorAudit( int colorSpace, qboolean srgbDecode );
	void RecordFboInit( qboolean requested, qboolean ready, qboolean programReady, qboolean framebufferFnsReady,
		int vidWidth, int vidHeight, int captureWidth, int captureHeight, int windowWidth, int windowHeight,
		int internalFormat, int textureFormat, int textureType, qboolean multiSampled, qboolean superSampled,
		qboolean windowAdjusted, int blitFilter, int hdrMode, int renderScaleMode, int bloomMode,
		qboolean textureSrgbAvailable, qboolean framebufferSrgbAvailable, qboolean framebufferSrgbEnabled );
	void RecordFboShutdown();
	void RecordPostProcessFrame( qboolean minimized, qboolean bloomAvailable, qboolean programReady,
		int screenshotMask, qboolean windowAdjusted, int fboReadIndex, int hdrMode, int renderScaleMode,
		float greyscale );
	qboolean AutoExposureNeedsSamples( int *width, int *height ) const;
	float UpdateAutoExposure( float manualExposure, const float *rgba, int width,
		int height );
	qboolean TryBindPostShaderFinal( qboolean bloomComposite, qboolean outputTransform,
		float bloomIntensity );
	qboolean TryBindPostShaderDirectFinal();
	void UnbindPostShader();
	void RecordPostProcessResult( int result );
	void RecordColorGradeLut( qboolean active, int size, float scale );
	void RecordBloomCreate( int result, int requestedPasses, int effectivePasses,
		int textureUnits, int formatMode, int internalFormat, int textureFormat,
		int textureType );
	void RecordBloom( int result, qboolean finalStage, int bloomMode, int requestedPasses,
		int effectivePasses, int blendBase, int filterSize, int textureUnits, int thresholdMode,
		int modulate, float threshold, float intensity, float reflection );
	void RecordFboCopyScreen( int viewportWidth, int viewportHeight );
	void RecordFboBlit( int kind, qboolean depthOnly, int srcWidth, int srcHeight, int dstWidth, int dstHeight );
	void RecordFboBind();
	void RecordPostClear();
	void RecordFullscreenPass();
	void PushShaderDebugGroup( const char *shaderName, int numVertexes, int numIndexes, int numPasses );
	void PopDebugGroup();
	void ShadowUploadTess( int numVertexes, int numIndexes, const void *xyz, int xyzBytes, const void *indexes, int indexBytes );
	void RecordStaticWorldCache( int surfaces, int vertexes, int indexes, int vertexBytes, int indexBytes );
	void RecordStaticWorldBatches( int batches, int largestBatchSurfaces, int faceSurfaces,
		int gridSurfaces, int triangleSurfaces, int shaderStagePasses, int maxShaderStages );
	void RecordStaticWorldPacket( const char *shaderName, int sort,
		int surfaces, int vertexes, int indexes, int firstItem, int itemCount, int vertexOffset, int vertexBytes,
		int indexOffset, int indexBytes, int shaderStagePasses, int flags );
	void UploadStaticWorldArena( const void *vertexData, int vertexBytes, const void *indexData, int indexBytes );
	GLuint StaticWorldArenaVertexBuffer();
	GLuint StaticWorldArenaIndexBuffer();
	qboolean StaticWorldDrawDeviceRun( int indexes, int offsetBytes,
		int firstItem, int itemCount, unsigned int indexType, int indexBytes,
		const char *shaderName, int sort, qboolean arenaBound );
	qboolean StaticWorldDrawDeviceRuns( int runCount, const int *counts, const void *const *offsets,
		const int *firstItems, const int *itemCounts, unsigned int indexType, int indexBytes,
		const char *shaderName, int sort, qboolean arenaBound );
	qboolean StaticWorldDrawSoftIndexes( int indexes, const void *indexData,
		unsigned int indexType, int indexBytes, const char *shaderName, int sort, qboolean arenaBound );
	int StaticWorldDrawDeviceRunsFiltered( int runCount, const int *counts, const void *const *offsets,
		const int *firstItems, const int *itemCounts, int *drawnRuns, unsigned int indexType, int indexBytes,
		const char *shaderName, int sort, qboolean arenaBound );
	void RecordStaticWorldQueue( int queuedItems, int queuedVertexes, int queuedIndexes,
		int deviceRuns, int deviceIndexes, int softIndexes, int largestDeviceRunIndexes );
	void RecordStaticWorldDeviceRuns( int runCount, const int *counts, const void *const *offsets,
		const int *firstItems, const int *itemCounts, int indexBytes, const char *shaderName, int sort );

private:
	void ApplyProfile( GlxProfile profile, qboolean rememberProfile, qboolean startupProfile );
	void ApplyStartupProfile();

	Capabilities caps_ {};
	DebugState debug_ {};
	ExecutorState executor_ {};
	MaterialState material_ {};
	PostProcessState postprocess_ {};
	PostShaderState postShader_ {};
	unsigned int postShaderBindBaseline_ {};
	unsigned int postShaderExpectedBinds_ {};
	ProfilerState profiler_ {};
	cvar_t *profile_ {};
	cvar_t *requireOwnership_ {};
	StaticWorldStats staticWorld_ {};
	StreamState stream_ {};
};

RendererModule g_module;

void RendererModule::RegisterCommands()
{
	RI().Cmd_AddCommand( "glxinfo", GLX_Renderer_PrintInfo_f );
	RI().Cmd_AddCommand( "glxcaps", GLX_Renderer_PrintCaps_f );
	RI().Cmd_AddCommand( "glxprofile", GLX_Renderer_Profile_f );
	RI().Cmd_AddCommand( "glxmaterial", GLX_Renderer_Material_f );
	RI().Cmd_AddCommand( "glxpostprocess", GLX_Renderer_PostProcess_f );
	RI().Cmd_AddCommand( "glxstaticworld", GLX_Renderer_StaticWorld_f );
	RI().Cmd_AddCommand( "glxstreamtest", GLX_Renderer_StreamTest_f );

	profile_ = RI().Cvar_Get( "r_glxProfile", "", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( profile_,
		"Apply a named GLx startup profile during renderer registration: off, rc, stress, manual, or blank for manual cvars." );
	requireOwnership_ = RI().Cvar_Get( "r_glxRequireOwnership", "0", CVAR_ARCHIVE_ND );
	RI().Cvar_SetDescription( requireOwnership_,
		"Reject GLx legacy-delegation draw submissions so ownership-proof runs cannot pass through compatibility draw paths." );

	GLX_Debug_RegisterCvars( &debug_ );
	GLX_Material_RegisterCvars( &material_ );
	GLX_PostProcess_RegisterCvars( &postprocess_ );
	GLX_PostShader_RegisterCvars( &postShader_ );
	GLX_Profiler_RegisterCvars( &profiler_ );
	GLX_StaticWorld_RegisterCvars( &staticWorld_ );
	GLX_Stream_RegisterCvars( &stream_ );

	ApplyStartupProfile();
}

void RendererModule::RemoveCommands()
{
	RI().Cmd_RemoveCommand( "glxcaps" );
	RI().Cmd_RemoveCommand( "glxinfo" );
	RI().Cmd_RemoveCommand( "glxprofile" );
	RI().Cmd_RemoveCommand( "glxmaterial" );
	RI().Cmd_RemoveCommand( "glxpostprocess" );
	RI().Cmd_RemoveCommand( "glxstaticworld" );
	RI().Cmd_RemoveCommand( "glxstreamtest" );
}

void RendererModule::OnOpenGLReady( const glconfig_t *config, const char *extensions )
{
	FramePass frameSchedule[GLX_RENDER_IR_PASS_COUNT];
	int frameScheduleCount = 0;

	GLX_Caps_Init( &caps_, config, extensions );
	GLX_Executor_Init( &executor_, caps_ );
	if ( !GLX_Module_EmitFrameSchedule( frameSchedule, GLX_RENDER_IR_PASS_COUNT, &frameScheduleCount ) ||
		!GLX_Executor_ConsumeFrameSchedule( &executor_, frameSchedule, frameScheduleCount ) ) {
		RI().Error( ERR_DROP, "GLx front-end pass schedule is invalid" );
	}
	GLX_Debug_OnOpenGLReady( &debug_, caps_ );
	GLX_Material_OnOpenGLReady( &material_, caps_ );
	GLX_PostProcess_OnOpenGLReady( &postprocess_, caps_ );
	GLX_PostShader_OnOpenGLReady( &postShader_, caps_ );
	GLX_Stream_OnOpenGLReady( &stream_, caps_ );
	GLX_StaticWorld_SetCapabilities( &staticWorld_, caps_.features.drawIndirect, caps_.features.multiDrawIndirect );
	GLX_Debug_LabelObject( debug_, GL_BUFFER, stream_.buffer, "GLx dynamic stream ring" );
	GLX_Profiler_OnOpenGLReady( &profiler_, caps_ );

	RI().Printf( PRINT_ALL, "GLx renderer bootstrap: product tier %s, hint %s, executor %s/%s, GL %i.%i, material %s, post-shader %s, stream %s, timer query %s, debug output %s\n",
		GLX_Caps_TierName( caps_.tier ), GLX_Caps_HintName( caps_.hint ),
		GLX_Executor_TierName( executor_ ), GLX_Executor_ModeName( executor_ ),
		caps_.major, caps_.minor,
		BoolName( GLX_Material_Active( material_ ) ),
		BoolName( GLX_PostShader_Ready( postShader_ ) ),
		GLX_Stream_StrategyName( stream_.strategy ),
		BoolName( GLX_Profiler_TimerReady( profiler_ ) ),
		BoolName( GLX_Debug_CallbackInstalled( debug_ ) ) );
	RI().Printf( PRINT_ALL, "GLx pass schedule: %s %i/%08x %s\n",
		executor_.frameScheduleValid ? "valid" : "invalid",
		executor_.frameScheduleCount,
		executor_.frameScheduleHash,
		executor_.frameScheduleText[0] ? executor_.frameScheduleText : "none" );
}

void RendererModule::Shutdown( int code )
{
	(void)code;

	GLX_Material_Shutdown( &material_, qtrue );
	GLX_PostShader_Shutdown( &postShader_, qtrue );
	if ( code == REF_KEEP_CONTEXT ) {
		postprocess_.glReady = qfalse;
	} else {
		GLX_PostProcess_Shutdown( &postprocess_ );
	}
	GLX_Profiler_Shutdown( &profiler_ );
	GLX_Debug_Shutdown( &debug_ );
	GLX_Executor_Shutdown( &executor_ );
	GLX_Stream_Shutdown( &stream_ );
	GLX_StaticWorld_Clear( &staticWorld_ );
	GLX_Caps_Reset( &caps_ );
}

void RendererModule::ApplyProfile( GlxProfile profile, qboolean rememberProfile, qboolean startupProfile )
{
	const char *profileName = GLX_Module_ProfileName( profile );

	if ( rememberProfile && profile_ ) {
		RI().Cvar_Set( profile_->name, profileName );
	}

	for ( unsigned int i = 0; i < sizeof( GLX_PROFILE_CVARS ) / sizeof( GLX_PROFILE_CVARS[0] ); i++ ) {
		const ProfileCvarSetting &setting = GLX_PROFILE_CVARS[i];
		RI().Cvar_Set( setting.name, GLX_Module_ProfileValue( setting, profile ) );
	}

	if ( startupProfile ) {
		RI().Printf( PRINT_ALL, "glxprofile: applied %s startup profile\n", profileName );
	} else {
		RI().Printf( PRINT_ALL, "glxprofile: applied %s profile\n", profileName );
		RI().Printf( PRINT_ALL, "glxprofile: FBO and stream settings apply automatically; reload the map for VBO/static-world resources.\n" );
	}
}

void RendererModule::ApplyStartupProfile()
{
	GlxProfile profile;

	if ( !profile_ || !profile_->string || !profile_->string[0] ) {
		return;
	}

	if ( !GLX_Module_Stricmp( profile_->string, "manual" ) ||
		!GLX_Module_Stricmp( profile_->string, "custom" ) ) {
		return;
	}

	if ( !GLX_Module_ParseProfile( profile_->string, &profile ) ) {
		RI().Printf( PRINT_WARNING, "glxprofile: unknown r_glxProfile '%s'; expected off, rc, stress, manual, or blank\n",
			profile_->string );
		return;
	}

	ApplyProfile( profile, qfalse, qtrue );
}

void RendererModule::BeginBackendTimer()
{
	GLX_Profiler_BeginBackendTimer( &profiler_ );
}

void RendererModule::EndBackendTimer()
{
	GLX_Profiler_EndBackendTimer( &profiler_ );
}

void RendererModule::BeginGpuPassTimer( int pass )
{
	GLX_Profiler_BeginGpuPassTimer( &profiler_, pass );
}

void RendererModule::EndGpuPassTimer( int pass )
{
	GLX_Profiler_EndGpuPassTimer( &profiler_, pass );
}

void RendererModule::FrameComplete()
{
	GLX_Profiler_FrameComplete( &profiler_ );
	GLX_Material_FrameComplete( &material_ );
	GLX_PostShader_FrameComplete( &postShader_ );
	GLX_Stream_FrameComplete( &stream_ );
	GLX_Debug_UpdateCvars( &debug_, caps_ );
	GLX_Stream_UpdateCvars( &stream_, caps_ );
}

void RendererModule::PrintCaps() const
{
	if ( !caps_.config ) {
		RI().Printf( PRINT_ALL, "GLx renderer bootstrap is loaded, but OpenGL is not initialized yet.\n" );
		return;
	}

	RI().Printf( PRINT_ALL, "\nGLx renderer bootstrap\n" );
	RI().Printf( PRINT_ALL, "  profile: %s (startup %s)\n",
		GLX_Module_DetectedProfileName(),
		profile_ && profile_->string && profile_->string[0] ? profile_->string : "manual" );
	RI().Printf( PRINT_ALL, "  GL vendor: %s\n", caps_.config->vendor_string );
	RI().Printf( PRINT_ALL, "  GL renderer: %s\n", caps_.config->renderer_string );
	RI().Printf( PRINT_ALL, "  GL version: %s\n", caps_.config->version_string );
	RI().Printf( PRINT_ALL, "  product tier: %s\n", GLX_Caps_TierName( caps_.tier ) );
	RI().Printf( PRINT_ALL, "  capability hint: %s\n", GLX_Caps_HintName( caps_.hint ) );
	RI().Printf( PRINT_ALL, "  render IR executor tier: %s\n", GLX_Executor_TierName( executor_ ) );
	RI().Printf( PRINT_ALL, "  render IR executor mode: %s\n", GLX_Executor_ModeName( executor_ ) );
	RI().Printf( PRINT_ALL, "  map buffer range: %s\n", BoolName( caps_.features.mapBufferRange ) );
	RI().Printf( PRINT_ALL, "  uniform buffers: %s\n", BoolName( caps_.features.uniformBufferObject ) );
	RI().Printf( PRINT_ALL, "  instanced arrays: %s\n", BoolName( caps_.features.instancedArrays ) );
	RI().Printf( PRINT_ALL, "  persistent buffers: %s\n", BoolName( caps_.features.bufferStorage ) );
	RI().Printf( PRINT_ALL, "  sync objects: %s\n", BoolName( caps_.features.syncObjects ) );
	RI().Printf( PRINT_ALL, "  draw indirect: %s\n", BoolName( caps_.features.drawIndirect ) );
	RI().Printf( PRINT_ALL, "  multi draw indirect: %s\n", BoolName( caps_.features.multiDrawIndirect ) );
	RI().Printf( PRINT_ALL, "  direct state access: %s\n", BoolName( caps_.features.directStateAccess ) );
	RI().Printf( PRINT_ALL, "  debug context: %s\n", BoolName( caps_.features.debugContext ) );
	RI().Printf( PRINT_ALL, "  debug output: %s\n", BoolName( caps_.features.debugOutput ) );
	RI().Printf( PRINT_ALL, "  KHR_debug labels/groups: %s\n", BoolName( caps_.features.khrDebug ) );
	RI().Printf( PRINT_ALL, "  timer query feature: %s\n", BoolName( caps_.features.timerQuery ) );
	RI().Printf( PRINT_ALL, "  timer query active: %s\n", BoolName( GLX_Profiler_TimerReady( profiler_ ) ) );
	RI().Printf( PRINT_ALL, "  debug output callback: %s\n", BoolName( GLX_Debug_CallbackInstalled( debug_ ) ) );
	RI().Printf( PRINT_ALL, "  KHR_debug groups: %s requested, %s available\n",
		BoolName( debug_.r_glxDebugGroups && debug_.r_glxDebugGroups->integer ? qtrue : qfalse ),
		BoolName( debug_.fns.PushDebugGroup && debug_.fns.PopDebugGroup ? qtrue : qfalse ) );
	RI().Printf( PRINT_ALL, "  material renderer: %s, ready %s, GLSL %s, programs %i\n",
		material_.r_glxMaterialRenderer && material_.r_glxMaterialRenderer->integer ? "enabled" : "disabled",
		BoolName( material_.ready ),
		material_.glslVersion[0] ? material_.glslVersion : "unknown",
		material_.programCount );
	RI().Printf( PRINT_ALL, "  post shader cache: ready %s, programs %i/%i, compile %u attempts/%u failures, link failures %u, source hash 0x%08x, target %s, evictions %u\n",
		BoolName( GLX_PostShader_Ready( postShader_ ) ),
		postShader_.programCount, GLX_POST_SHADER_PROGRAM_LIMIT,
		postShader_.compileAttempts, postShader_.compileFailures,
		postShader_.linkFailures, postShader_.lastSourceHash,
		GLX_PostShaderSource_TargetName( postShader_.activeTarget ),
		postShader_.cacheEvictions );
	RI().Printf( PRINT_ALL, "  postprocess FBO: %s, render %ix%i, capture %ix%i, bloom %i, passes %i/%i, last %s\n",
		BoolName( postprocess_.fboReady ), postprocess_.vidWidth, postprocess_.vidHeight,
		postprocess_.captureWidth, postprocess_.captureHeight, postprocess_.bloomMode,
		postprocess_.lastBloomEffectivePasses, postprocess_.lastBloomRequestedPasses,
		GLX_PostProcess_ResultName( postprocess_.lastResult ) );
	RI().Printf( PRINT_ALL, "  post/output ownership: mode %s, post nodes %u, outputs %u, legacy fallback %s, executable nodes %u, executable outputs %u, post hash 0x%08x, output hash 0x%08x, plan hash 0x%08x, fallback 0x%08x\n",
		GLX_PostProcess_PostOutputModeName( postprocess_.lastPostOutputGlxOwned ),
		executor_.postNodes,
		executor_.outputTransforms,
		BoolName( postprocess_.lastPostOutputGlxOwned ? qfalse : qtrue ),
		postprocess_.lastPostOutputExecutableNodeCount,
		postprocess_.lastPostOutputExecutableOutputCount,
		executor_.lastPostNodeHash,
		executor_.lastOutputTransformHash,
		postprocess_.lastPostOutputPlanHash,
		postprocess_.lastPostOutputFallbackReasons );
	RI().Printf( PRINT_ALL, "  post shader plan: valid %s, features 0x%08x, hash 0x%08x, textures %u, uniforms %u, frames %u, invalid %u\n",
		BoolName( postprocess_.lastPostShaderPlanValid ),
		postprocess_.lastPostShaderFeatureMask,
		postprocess_.lastPostShaderPlanHash,
		postprocess_.lastPostShaderTextureCount,
		postprocess_.lastPostShaderUniformVec4Count,
		postprocess_.postShaderPlanFrames,
		postprocess_.postShaderPlanInvalidFrames );
	RI().Printf( PRINT_ALL, "  post shader source: valid %s, truncated %s, hash 0x%08x, vertex bytes %i, fragment bytes %i, last program %u\n",
		BoolName( postShader_.lastSource.valid ),
		BoolName( postShader_.lastSource.truncated ),
		postShader_.lastSourceHash,
		postShader_.lastSource.vertexBytes,
		postShader_.lastSource.fragmentBytes,
		postShader_.lastProgram );
	RI().Printf( PRINT_ALL, "  post shader direct-final: execute %s, eligible %s, bound %s, reject 0x%08x, candidates %u, eligible frames %u, attempts %u, binds %u, fallbacks %u, rejects %u\n",
		BoolName( postShader_.r_glxPostShaderExecute && postShader_.r_glxPostShaderExecute->integer ? qtrue : qfalse ),
		BoolName( postShader_.lastDirectFinalEligible ),
		BoolName( postShader_.lastDirectFinalBound ),
		postShader_.lastDirectFinalRejectMask,
		postShader_.directFinalCandidates,
		postShader_.directFinalEligibleFrames,
		postShader_.directFinalAttempts,
		postShader_.directFinalBinds,
		postShader_.directFinalFallbacks,
		postShader_.directFinalRejects );
	RI().Printf( PRINT_ALL, "  static world GLx arena: %s, %.2f MB\n",
		BoolName( staticWorld_.arenaReady ),
		( staticWorld_.arenaVertexBytes + staticWorld_.arenaIndexBytes ) / ( 1024.0f * 1024.0f ) );
	RI().Printf( PRINT_ALL, "  static world GLx renderer: %s, arena draw %s\n",
		BoolName( staticWorld_.r_glxWorldRenderer && staticWorld_.r_glxWorldRenderer->integer ? qtrue : qfalse ),
		BoolName( ( staticWorld_.r_glxWorldRenderer && staticWorld_.r_glxWorldRenderer->integer ) ||
			( staticWorld_.r_glxStaticWorldArenaDraw && staticWorld_.r_glxStaticWorldArenaDraw->integer ) ? qtrue : qfalse ) );
	RI().Printf( PRINT_ALL, "  static world GLx draw: %s, soft %s, policy %s, %u/%u calls, packets %u full/%u partial/%u miss\n",
		BoolName( ( staticWorld_.r_glxWorldRenderer && staticWorld_.r_glxWorldRenderer->integer ) ||
			( staticWorld_.r_glxStaticWorldDraw && staticWorld_.r_glxStaticWorldDraw->integer ) ? qtrue : qfalse ),
		BoolName( ( staticWorld_.r_glxWorldRenderer && staticWorld_.r_glxWorldRenderer->integer ) ||
			( staticWorld_.r_glxStaticWorldSoftDraw && staticWorld_.r_glxStaticWorldSoftDraw->integer ) ? qtrue : qfalse ),
		staticWorld_.r_glxWorldRenderer && staticWorld_.r_glxWorldRenderer->integer ? "all" :
			staticWorld_.r_glxStaticWorldDrawPolicy && staticWorld_.r_glxStaticWorldDrawPolicy->string ?
			staticWorld_.r_glxStaticWorldDrawPolicy->string : "full",
		staticWorld_.drawCalls, staticWorld_.drawAttempts,
		staticWorld_.drawPacketFullHits, staticWorld_.drawPacketPartialHits, staticWorld_.drawPacketMisses );
	RI().Printf( PRINT_ALL, "  static world GLx packet lookup: %u mapped, hits %u, fallbacks %u\n",
		staticWorld_.itemLookupMappedItems, staticWorld_.itemLookupHits,
		staticWorld_.itemLookupFallbacks );
	RI().Printf( PRINT_ALL, "  static world GLx indirect packets: %u commands, %u bytes\n",
		staticWorld_.indirectPacketCount, staticWorld_.indirectPacketBytes );
	RI().Printf( PRINT_ALL, "  static world GLx indirect caps: draw %s, multidraw %s\n",
		BoolName( staticWorld_.drawIndirectAvailable ),
		BoolName( staticWorld_.multiDrawIndirectAvailable ) );
	RI().Printf( PRINT_ALL, "  static world GLx indirect buffer: %s, %u commands, %u bytes\n",
		BoolName( staticWorld_.indirectBufferReady ), staticWorld_.indirectBufferCommands,
		staticWorld_.indirectBufferBytes );
	RI().Printf( PRINT_ALL, "  static world GLx indirect draw: %s, %u/%u calls\n",
		BoolName( staticWorld_.r_glxStaticWorldIndirectDraw &&
			staticWorld_.r_glxStaticWorldIndirectDraw->integer ? qtrue : qfalse ),
		staticWorld_.indirectDrawCalls, staticWorld_.indirectDrawAttempts );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw: %s, %u calls, %u runs\n",
		BoolName( ( staticWorld_.r_glxWorldRenderer && staticWorld_.r_glxWorldRenderer->integer ) ||
			( staticWorld_.r_glxStaticWorldMultiDraw && staticWorld_.r_glxStaticWorldMultiDraw->integer ) ? qtrue : qfalse ),
		staticWorld_.multiDrawCalls, staticWorld_.multiDrawRuns );
	RI().Printf( PRINT_ALL, "  static world GLx packet batch: %s, %u batches, %u packet runs, %u fallback runs\n",
		BoolName( staticWorld_.r_glxStaticWorldPacketBatch &&
			staticWorld_.r_glxStaticWorldPacketBatch->integer ? qtrue : qfalse ),
		staticWorld_.packetBatchBatches,
		staticWorld_.packetBatchRuns,
		staticWorld_.packetBatchFallbackRuns );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect: %s, %u/%u calls\n",
		BoolName( staticWorld_.r_glxStaticWorldMultiDrawIndirect &&
			staticWorld_.r_glxStaticWorldMultiDrawIndirect->integer ? qtrue : qfalse ),
		staticWorld_.multiDrawIndirectCalls, staticWorld_.multiDrawIndirectAttempts );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect shape: last %s %u runs/%u indexes, largest %u runs/%u indexes\n",
		GLX_Module_MdiSourceName( staticWorld_.multiDrawIndirectLastSource ),
		staticWorld_.multiDrawIndirectLastRuns,
		staticWorld_.multiDrawIndirectLastIndexes,
		staticWorld_.multiDrawIndirectLargestRun,
		staticWorld_.multiDrawIndirectLargestIndexes );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect sources: static %u, compact %s/%u calls, uploads %u, subdata %u, orphans %u\n",
		staticWorld_.multiDrawIndirectStaticCalls,
		BoolName( staticWorld_.r_glxStaticWorldMultiDrawIndirectCompact &&
			staticWorld_.r_glxStaticWorldMultiDrawIndirectCompact->integer ? qtrue : qfalse ),
		staticWorld_.multiDrawIndirectCompactCalls,
		staticWorld_.multiDrawIndirectCompactUploads,
		staticWorld_.multiDrawIndirectCompactSubDatas,
		staticWorld_.multiDrawIndirectCompactOrphans );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect last reject: %s, %u runs/%u indexes, command %i\n",
		GLX_StaticWorld_MdiRejectName( staticWorld_.multiDrawIndirectLastRejectReason ),
		staticWorld_.multiDrawIndirectLastRejectRuns,
		staticWorld_.multiDrawIndirectLastRejectIndexes,
		staticWorld_.multiDrawIndirectLastRejectCommand );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect spans: %s, batches %u, mdi runs %u, fallback runs %u, singles %u, single draws %u/%u indirect\n",
		BoolName( staticWorld_.r_glxStaticWorldMultiDrawIndirectSpans &&
			staticWorld_.r_glxStaticWorldMultiDrawIndirectSpans->integer ? qtrue : qfalse ),
		staticWorld_.multiDrawIndirectSpanBatches,
		staticWorld_.multiDrawIndirectSpanMdiRuns,
		staticWorld_.multiDrawIndirectSpanFallbackRuns,
		staticWorld_.multiDrawIndirectSpanSingles,
		staticWorld_.multiDrawIndirectSpanSingleDraws,
		staticWorld_.multiDrawIndirectSpanSingleIndirectDraws );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect span shape: last %u segments, %u mdi runs, %u fallback runs, %u singles, largest %u segments\n",
		staticWorld_.multiDrawIndirectSpanLastSegments,
		staticWorld_.multiDrawIndirectSpanLastMdiRuns,
		staticWorld_.multiDrawIndirectSpanLastFallbackRuns,
		staticWorld_.multiDrawIndirectSpanLastSingles,
		staticWorld_.multiDrawIndirectSpanLargestSegments );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect command spans: batches %u, mdi runs %u, fallback runs %u, singleton draws %u/%u indirect, singleton blocks %u\n",
		staticWorld_.multiDrawIndirectCommandSpanBatches,
		staticWorld_.multiDrawIndirectCommandSpanMdiRuns,
		staticWorld_.multiDrawIndirectCommandSpanFallbackRuns,
		staticWorld_.multiDrawIndirectCommandSpanSingletonDraws,
		staticWorld_.multiDrawIndirectCommandSpanSingletonIndirectDraws,
		staticWorld_.multiDrawIndirectCommandSpanSingletons );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect command span shape: last %u segments, %u mdi runs, %u fallback runs, largest %u segments\n",
		staticWorld_.multiDrawIndirectCommandSpanLastSegments,
		staticWorld_.multiDrawIndirectCommandSpanLastMdiRuns,
		staticWorld_.multiDrawIndirectCommandSpanLastFallbackRuns,
		staticWorld_.multiDrawIndirectCommandSpanLargestSegments );
	RI().Printf( PRINT_ALL, "  static world GLx multidraw indirect reasons: unsupported %u, nonmanifest %u, missing %u, noncontiguous %u\n",
		staticWorld_.multiDrawIndirectUnsupported, staticWorld_.multiDrawIndirectNonManifest,
		staticWorld_.multiDrawIndirectMissingCommand, staticWorld_.multiDrawIndirectNonContiguous );
	RI().Printf( PRINT_ALL, "  dynamic stream strategy: %s\n", GLX_Stream_StrategyName( stream_.strategy ) );
	RI().Printf( PRINT_ALL, "  dynamic stream ring: %i MB\n", stream_.ringMegabytes );
	RI().Printf( PRINT_ALL, "  dynamic stream buffer: %s\n", BoolName( stream_.ready ) );
	RI().Printf( PRINT_ALL, "  dynamic stream sync: %s, fences %u, waits %u, timeouts %u\n",
		BoolName( stream_.syncReady ), stream_.syncInsertions, stream_.syncWaits, stream_.syncTimeouts );
	RI().Printf( PRINT_ALL, "  dynamic stream uploads: %.2f MB, wraps %u, same-frame rejects %u\n",
		static_cast<double>( stream_.uploadBytes ) / ( 1024.0 * 1024.0 ),
		stream_.wraps, stream_.sameFrameWrapRejects );
	RI().Printf( PRINT_ALL, "  dynamic stream tess shadow: %u batches, %.2f MB\n",
		stream_.shadowTessUploads,
		static_cast<double>( stream_.shadowTessBytes ) / ( 1024.0 * 1024.0 ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw enabled: %s\n", BoolName( GLX_Stream_DrawEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw multitexture: %s\n",
		BoolName( GLX_Stream_DrawMultitextureEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw fog: %s\n",
		BoolName( GLX_Stream_DrawFogEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw depthFragment: %s\n",
		BoolName( GLX_Stream_DrawDepthFragmentEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw texmods: %s\n",
		BoolName( GLX_Stream_DrawTexModsEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw environment: %s\n",
		BoolName( GLX_Stream_DrawEnvironmentEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw dynamic lights: %s\n",
		BoolName( GLX_Stream_DrawDynamicLightsEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw screen maps: %s\n",
		BoolName( GLX_Stream_DrawScreenMapsEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw video maps: %s\n",
		BoolName( GLX_Stream_DrawVideoMapsEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw shadows: %s\n",
		BoolName( GLX_Stream_DrawShadowsEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw beams: %s\n",
		BoolName( GLX_Stream_DrawBeamsEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draw postprocess: %s\n",
		BoolName( GLX_Stream_DrawPostProcessEnabled( stream_ ) ) );
	RI().Printf( PRINT_ALL, "  dynamic stream draws: %u/%u attempts, %.2f MB, index %.2f MB, tex1 %.2f MB, mt %u, fog %u, depthfrag %u, texmod %u, env %u, dlight %u, screen %u, video %u, shadow %u, beam %u, post %u\n",
		stream_.streamedDraws, stream_.streamedDrawAttempts,
		static_cast<double>( stream_.streamedDrawBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( stream_.streamedDrawIndexBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( stream_.streamedDrawTexcoord1Bytes ) / ( 1024.0 * 1024.0 ),
		stream_.streamedDrawMultitextureDraws,
		stream_.streamedDrawFogDraws,
		stream_.streamedDrawDepthFragmentDraws,
		stream_.streamedDrawTexModDraws,
		stream_.streamedDrawEnvironmentDraws,
		stream_.streamedDrawDynamicLightDraws,
		stream_.streamedDrawScreenMapDraws,
		stream_.streamedDrawVideoMapDraws,
		stream_.streamedDrawShadowDraws,
		stream_.streamedDrawBeamDraws,
		stream_.streamedDrawPostProcessDraws );
	RI().Printf( PRINT_ALL, "  dynamic stream categories: entity %u/%u, particle %u/%u, poly %u/%u, mark %u/%u, weapon %u/%u, ui %u/%u, beam %u/%u, special %u/%u\n",
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_ENTITY],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_ENTITY],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_PARTICLE],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_PARTICLE],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_POLY],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_POLY],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_MARK],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_MARK],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_WEAPON],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_WEAPON],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_UI],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_UI],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_BEAM],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_BEAM],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_SPECIAL],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_SPECIAL] );
	RI().Printf( PRINT_ALL, "  dynamic stream draw material keys: accepted %u, rejected %u, mt accepted %u, mt rejected %u, depthfrag accepted %u, depthfrag rejected %u, texmod accepted %u, texmod rejected %u, env accepted %u, env rejected %u, dlight accepted %u, dlight rejected %u, screen accepted %u, screen rejected %u, video accepted %u, video rejected %u\n",
		stream_.streamedDrawMaterialAccepted, stream_.streamedDrawMaterialRejected,
		stream_.streamedDrawMultitextureAccepted, stream_.streamedDrawMultitextureRejected,
		stream_.streamedDrawDepthFragmentAccepted, stream_.streamedDrawDepthFragmentRejected,
		stream_.streamedDrawTexModAccepted, stream_.streamedDrawTexModRejected,
		stream_.streamedDrawEnvironmentAccepted, stream_.streamedDrawEnvironmentRejected,
		stream_.streamedDrawDynamicLightAccepted, stream_.streamedDrawDynamicLightRejected,
		stream_.streamedDrawScreenMapAccepted, stream_.streamedDrawScreenMapRejected,
		stream_.streamedDrawVideoMapAccepted, stream_.streamedDrawVideoMapRejected );
}

void RendererModule::PrintInfo() const
{
	PrintCaps();
	GLX_Material_PrintInfo( material_ );
	GLX_PostShader_PrintInfo( postShader_ );
	GLX_PostProcess_PrintInfo( postprocess_ );
	GLX_Executor_PrintInfo( executor_ );
	GLX_Profiler_PrintInfo( profiler_ );
	GLX_StaticWorld_PrintInfo( staticWorld_ );
	GLX_Stream_PrintInfo( stream_ );
}

void RendererModule::PrintProfile() const
{
	char current[64];

	RI().Printf( PRINT_ALL, "glxprofile: active %s, startup %s\n",
		GLX_Module_DetectedProfileName(),
		profile_ && profile_->string && profile_->string[0] ? profile_->string : "manual" );

	for ( unsigned int i = 0; i < sizeof( GLX_PROFILE_CVARS ) / sizeof( GLX_PROFILE_CVARS[0] ); i++ ) {
		const ProfileCvarSetting &setting = GLX_PROFILE_CVARS[i];

		GLX_Module_CurrentCvarValue( setting.name, current, sizeof( current ) );
		RI().Printf( PRINT_ALL, "  %-42s %s\n", setting.name, current[0] ? current : "<unset>" );
	}
}

void RendererModule::ProfileCommand()
{
	GlxProfile profile;

	if ( !RI().Cmd_Argc || RI().Cmd_Argc() < 2 ) {
		PrintProfile();
		GLX_Module_PrintProfileUsage();
		return;
	}

	const char *arg = RI().Cmd_Argv( 1 );

	if ( !GLX_Module_Stricmp( arg, "status" ) ||
		!GLX_Module_Stricmp( arg, "current" ) ) {
		PrintProfile();
		return;
	}

	if ( !GLX_Module_Stricmp( arg, "list" ) ||
		!GLX_Module_Stricmp( arg, "help" ) ) {
		GLX_Module_PrintProfileUsage();
		return;
	}

	if ( !GLX_Module_Stricmp( arg, "manual" ) ||
		!GLX_Module_Stricmp( arg, "custom" ) ||
		!GLX_Module_Stricmp( arg, "clear" ) ) {
		if ( profile_ ) {
			RI().Cvar_Set( profile_->name, "" );
		}
		RI().Printf( PRINT_ALL, "glxprofile: startup profile cleared; current cvars unchanged\n" );
		return;
	}

	if ( !GLX_Module_ParseProfile( arg, &profile ) ) {
		RI().Printf( PRINT_WARNING, "glxprofile: unknown profile '%s'\n", arg ? arg : "" );
		GLX_Module_PrintProfileUsage();
		return;
	}

	ApplyProfile( profile, qtrue, qfalse );
}

void RendererModule::PrintMaterial() const
{
	GLX_Material_PrintInfo( material_ );
}

void RendererModule::PrintPostProcess() const
{
	GLX_PostProcess_PrintInfo( postprocess_ );
}

void RendererModule::PrintStaticWorld() const
{
	int limit = 16;
	qboolean hot = qfalse;
	qboolean commands = qfalse;
	qboolean spans = qfalse;

	if ( RI().Cmd_Argc && RI().Cmd_Argc() > 1 ) {
		const char *arg = RI().Cmd_Argv( 1 );

		if ( arg && ( !GLX_Module_Stricmp( arg, "hot" ) || !GLX_Module_Stricmp( arg, "top" ) ) ) {
			hot = qtrue;
			if ( RI().Cmd_Argc() > 2 ) {
				limit = std::atoi( RI().Cmd_Argv( 2 ) );
			}
		} else if ( arg && ( !GLX_Module_Stricmp( arg, "commands" ) || !GLX_Module_Stricmp( arg, "cmds" ) ) ) {
			commands = qtrue;
			if ( RI().Cmd_Argc() > 2 ) {
				limit = std::atoi( RI().Cmd_Argv( 2 ) );
			}
		} else if ( arg && ( !GLX_Module_Stricmp( arg, "spans" ) || !GLX_Module_Stricmp( arg, "mdi" ) ) ) {
			spans = qtrue;
			if ( RI().Cmd_Argc() > 2 ) {
				limit = std::atoi( RI().Cmd_Argv( 2 ) );
			}
		} else {
			limit = std::atoi( arg );
		}
	}
	if ( limit < 0 ) {
		limit = 0;
	}
	if ( limit > 128 ) {
		limit = 128;
	}

	if ( hot ) {
		GLX_StaticWorld_PrintHotPackets( staticWorld_, limit );
	} else if ( commands ) {
		GLX_StaticWorld_PrintIndirectCommands( staticWorld_, limit );
	} else if ( spans ) {
		GLX_StaticWorld_PrintSpanDiagnostics( staticWorld_, limit );
	} else {
		GLX_StaticWorld_PrintPackets( staticWorld_, limit );
	}
}

void RendererModule::PrintFrameCounters() const
{
	if ( !caps_.config ) {
		RI().Printf( PRINT_ALL, "glx: no OpenGL context\n" );
		return;
	}

	RI().Printf( PRINT_ALL, "glx: tier %s, batches %u, draws %u/%u idx, stream %s/%s %.2fMB/%uwraps/%urejects shadow %u, frames %u, backend queries %u, gpu %s, static %i batches/%i packets/%i surfaces/%i verts/%i indexes %.2f MB, arena %s %.2f MB\n",
		GLX_Caps_TierName( caps_.tier ),
		profiler_.shaderBatches,
		profiler_.drawCalls,
		profiler_.drawIndexes,
		GLX_Stream_StrategyName( stream_.strategy ),
		stream_.ready ? "ready" : "off",
		static_cast<double>( stream_.uploadBytes ) / ( 1024.0 * 1024.0 ),
		stream_.wraps,
		stream_.sameFrameWrapRejects,
		stream_.shadowTessUploads,
		profiler_.frames,
		profiler_.backendQueries,
		GLX_Profiler_LastGpuTimeText( profiler_ ),
		staticWorld_.batches,
		staticWorld_.packetCount,
		staticWorld_.surfaces,
		staticWorld_.vertexes,
		staticWorld_.indexes,
		GLX_StaticWorld_TotalMegabytes( staticWorld_ ),
		staticWorld_.arenaReady ? "ready" : "off",
		( staticWorld_.arenaVertexBytes + staticWorld_.arenaIndexBytes ) / ( 1024.0f * 1024.0f ) );
	RI().Printf( PRINT_ALL, "glx: pass counters blits %u, binds %u, clears %u, fullscreen %u, pass queries %u, unavailable %u, ring skips %u\n",
		profiler_.postBlits,
		profiler_.postBinds,
		profiler_.postClears,
		profiler_.postFullscreenPasses,
		profiler_.gpuPassQueries,
		profiler_.passQueryUnavailableFrames,
		profiler_.passQueryRingFullSkips );
	RI().Printf( PRINT_ALL, "glx: pass gpu:" );
	for ( int i = 0; i < GLX_GPU_PASS_COUNT; i++ ) {
		const GpuPassStats &stats = profiler_.gpuPassStats[i];
		RI().Printf( PRINT_ALL, " %s=%s/%u",
			GLX_Profiler_GpuPassName( i ),
			stats.samples ? stats.lastText : "n/a",
			stats.samples );
	}
	RI().Printf( PRINT_ALL, "\n" );
	RI().Printf( PRINT_ALL, "glx: material stages %u generic/%u vbo/%u mt/%u blend/%u texmod/%u env/%u\n",
		profiler_.materialStages,
		profiler_.genericMaterialStages,
		profiler_.vboMaterialStages,
		profiler_.multitextureMaterialStages,
		profiler_.blendMaterialStages,
		profiler_.texmodMaterialStages,
		profiler_.environmentMaterialStages );
	RI().Printf( PRINT_ALL, "glx: render IR executor %s/%s passes %u world %u dynamic %u draws/%u idx/%u verts materials %u uploads %u post %u outputs %u rejects %u\n",
		GLX_Executor_TierName( executor_ ),
		GLX_Executor_ModeName( executor_ ),
		executor_.framePasses,
		executor_.worldPackets,
		executor_.dynamicDraws,
		executor_.dynamicIndexes,
		executor_.dynamicVertices,
		executor_.materialPlans,
		executor_.uploadPlans,
		executor_.postNodes,
		executor_.outputTransforms,
		executor_.rejectedProducts );
	RI().Printf( PRINT_ALL, "glx: post/output ownership mode %s, post nodes %u, outputs %u, legacy fallback %s, executable nodes %u, executable outputs %u, post hash 0x%08x, output hash 0x%08x, plan hash 0x%08x, fallback 0x%08x\n",
		GLX_PostProcess_PostOutputModeName( postprocess_.lastPostOutputGlxOwned ),
		executor_.postNodes,
		executor_.outputTransforms,
		BoolName( postprocess_.lastPostOutputGlxOwned ? qfalse : qtrue ),
		postprocess_.lastPostOutputExecutableNodeCount,
		postprocess_.lastPostOutputExecutableOutputCount,
		executor_.lastPostNodeHash,
		executor_.lastOutputTransformHash,
		postprocess_.lastPostOutputPlanHash,
		postprocess_.lastPostOutputFallbackReasons );
	RI().Printf( PRINT_ALL, "glx: post shader plan valid %s, features 0x%08x, hash 0x%08x, textures %u, uniforms %u, frames %u, invalid %u\n",
		BoolName( postprocess_.lastPostShaderPlanValid ),
		postprocess_.lastPostShaderFeatureMask,
		postprocess_.lastPostShaderPlanHash,
		postprocess_.lastPostShaderTextureCount,
		postprocess_.lastPostShaderUniformVec4Count,
		postprocess_.postShaderPlanFrames,
		postprocess_.postShaderPlanInvalidFrames );
	RI().Printf( PRINT_ALL, "glx: post shader cache ready %s, programs %i/%i, plans %u valid/%u invalid, cache %u hits/%u misses, compile %u attempts/%u failures, link failures %u, source failures %u, source hash 0x%08x, program %u, target %s, preferred %s, evictions %u, target fallbacks %u\n",
		BoolName( GLX_PostShader_Ready( postShader_ ) ),
		postShader_.programCount,
		GLX_POST_SHADER_PROGRAM_LIMIT,
		postShader_.validPlansObserved,
		postShader_.invalidPlansObserved,
		postShader_.cacheHits,
		postShader_.cacheMisses,
		postShader_.compileAttempts,
		postShader_.compileFailures,
		postShader_.linkFailures,
		postShader_.sourceFailures,
		postShader_.lastSourceHash,
		postShader_.lastProgram,
		GLX_PostShaderSource_TargetName( postShader_.activeTarget ),
		GLX_PostShaderSource_TargetName( postShader_.preferredTarget ),
		postShader_.cacheEvictions,
		postShader_.targetFallbacks );
	RI().Printf( PRINT_ALL, "glx: post shader direct-final execute %s, eligible %s, bound %s, reject 0x%08x, candidates %u, eligible frames %u, attempts %u, binds %u, fallbacks %u, rejects %u, program misses %u, uniform failures %u\n",
		BoolName( postShader_.r_glxPostShaderExecute && postShader_.r_glxPostShaderExecute->integer ? qtrue : qfalse ),
		BoolName( postShader_.lastDirectFinalEligible ),
		BoolName( postShader_.lastDirectFinalBound ),
		postShader_.lastDirectFinalRejectMask,
		postShader_.directFinalCandidates,
		postShader_.directFinalEligibleFrames,
		postShader_.directFinalAttempts,
		postShader_.directFinalBinds,
		postShader_.directFinalFallbacks,
		postShader_.directFinalRejects,
		postShader_.directFinalProgramMisses,
		postShader_.directFinalUniformFailures );
	if ( caps_.tier == RenderProductTier::GL12 ) {
		RI().Printf( PRINT_ALL, "glx: GL12 fixed-function draws %u client-memory %u unsupported stream %u post %u output %u\n",
			executor_.fixedFunctionDraws,
			executor_.clientMemoryDraws,
			executor_.unsupportedStreamUploads,
			executor_.unsupportedPostNodes,
			executor_.unsupportedOutputTransforms );
	}
	if ( caps_.tier == RenderProductTier::GL2X ) {
		RI().Printf( PRINT_ALL, "glx: GL2X programmable draws %u stream %u materials %u post-lite %u unsupported advanced-upload %u post %u output %u\n",
			executor_.programmableDraws,
			executor_.streamUploadDraws,
			executor_.programmableMaterialPlans,
			executor_.postprocessLiteNodes,
			executor_.unsupportedAdvancedUploads,
			executor_.unsupportedPostNodes,
			executor_.unsupportedOutputTransforms );
	}
	if ( caps_.tier == RenderProductTier::GL3X ) {
		RI().Printf( PRINT_ALL, "glx: GL3X performance draws %u sync-uploads %u static-buffers %u dynamic-buffers %u materials %u fbo-post %u unsupported persistent-upload %u\n",
			executor_.performanceDraws,
			executor_.syncUploadPlans,
			executor_.staticBufferProducts,
			executor_.dynamicBufferProducts,
			executor_.performanceMaterialPlans,
			executor_.fboPostNodes,
			executor_.unsupportedPersistentUploads );
	}
	if ( caps_.tier == RenderProductTier::GL41 ) {
		RI().Printf( PRINT_ALL, "glx: GL41 mac-modern draws %u sync-uploads %u static-buffers %u dynamic-buffers %u materials %u post %u unsupported persistent-upload %u gl43-required 0 gl44-required 0 gl45-required 0\n",
			executor_.macModernDraws,
			executor_.macModernSyncUploadPlans,
			executor_.macModernStaticBufferProducts,
			executor_.macModernDynamicBufferProducts,
			executor_.macModernMaterialPlans,
			executor_.macModernPostNodes,
			executor_.unsupportedPersistentUploads );
	}
	if ( caps_.tier == RenderProductTier::GL46 ) {
		RI().Printf( PRINT_ALL, "glx: GL46 high-end draws %u persistent-uploads %u sync-uploads %u dsa-products %u mdi-products %u aggressive-static %u materials %u post %u gpu-counters %u static-mdi %u/%u calls/%u idx\n",
			executor_.highEndDraws,
			executor_.highEndPersistentUploads,
			executor_.highEndSyncUploads,
			executor_.highEndDsaProducts,
			executor_.highEndMdiProducts,
			executor_.highEndAggressiveStaticProducts,
			executor_.highEndMaterialPlans,
			executor_.highEndPostNodes,
			profiler_.backendQueries,
			staticWorld_.multiDrawIndirectCalls,
			staticWorld_.multiDrawIndirectAttempts,
			staticWorld_.multiDrawIndirectIndexes );
	}
	RI().Printf( PRINT_ALL, "glx: pass schedule %s %i/%08x %s\n",
		executor_.frameScheduleValid ? "valid" : "invalid",
		executor_.frameScheduleCount,
		executor_.frameScheduleHash,
		executor_.frameScheduleText[0] ? executor_.frameScheduleText : "none" );
	RI().Printf( PRINT_ALL, "glx: ownership legacy delegation %u calls/%u items, generic %u, vbo-device %u, vbo-soft %u, arrays %u\n",
		profiler_.legacyDelegationCalls,
		profiler_.legacyDelegationItems,
		profiler_.legacyDelegationReasonCalls[GLX_LEGACY_DELEGATION_GENERIC],
		profiler_.legacyDelegationReasonCalls[GLX_LEGACY_DELEGATION_VBO_DEVICE],
		profiler_.legacyDelegationReasonCalls[GLX_LEGACY_DELEGATION_VBO_SOFT],
		profiler_.legacyDelegationReasonCalls[GLX_LEGACY_DELEGATION_DRAW_ARRAY] );
	RI().Printf( PRINT_ALL, "glx: material renderer %s/%s programs %i, binds %u/%u attempts, switches %u, cache %u/%u, failures %u compile/%u link/%u precache/%u bind, labels %u\n",
		material_.r_glxMaterialRenderer && material_.r_glxMaterialRenderer->integer ? "on" : "off",
		material_.ready ? "ready" : "not-ready",
		material_.programCount,
		material_.binds,
		material_.bindAttempts,
		material_.programSwitches,
		material_.cacheHits,
		material_.cacheMisses,
		material_.compileFailures,
		material_.linkFailures,
		material_.precacheFailures,
		material_.bindFailures,
		material_.debugLabels );
	RI().Printf( PRINT_ALL, "glx: material parameters blocks %u invalid %u hash 0x%08x, last sort %i passes %i features 0x%x flags 0x%x state 0x%x\n",
		material_.parameterBlocks,
		material_.invalidParameterBlocks,
		material_.lastParameterBlockHash,
		material_.lastParameterBlock.frame.sort,
		material_.lastParameterBlock.frame.shaderStagePasses,
		material_.lastParameterBlock.frame.featureMask,
		material_.lastParameterBlock.material.flags,
		material_.lastParameterBlock.material.stateBits );
	RI().Printf( PRINT_ALL, "glx: postprocess fbo %s %ix%i capture %ix%i bloom %i, frames %u final %u prefinal %u gamma %u/%u, copies %u, msaa %u, ssaa %u, last %s\n",
		postprocess_.fboReady ? "ready" : "off",
		postprocess_.vidWidth,
		postprocess_.vidHeight,
		postprocess_.captureWidth,
		postprocess_.captureHeight,
		postprocess_.bloomMode,
		postprocess_.frames,
		postprocess_.bloomFinalPasses,
		postprocess_.bloomIntermediatePasses,
		postprocess_.gammaDirectFrames,
		postprocess_.gammaBlitFrames,
		postprocess_.copyScreenCalls,
		postprocess_.msaaBlits,
		postprocess_.ssaaBlits,
		GLX_PostProcess_ResultName( postprocess_.lastResult ) );
	RI().Printf( PRINT_ALL, "glx: bloom storage policy %s format 0x%04x (0x%04x:0x%04x)\n",
		GLX_PostProcess_BloomFormatModeName( postprocess_.lastBloomFormatMode ),
		postprocess_.lastBloomInternalFormat,
		postprocess_.lastBloomTextureFormat,
		postprocess_.lastBloomTextureType );
	RI().Printf( PRINT_ALL, "glx: color pipeline %s precision %i transfer %s tone-map %s exposure %.2f bloom-threshold %.2f/%i knee %.2f grade %s paper-white %.0f max %.0f\n",
		GLX_RenderIR_SceneColorSpaceName( postprocess_.lastOutput.sceneColorSpace ),
		postprocess_.lastOutput.precisionMode,
		GLX_RenderIR_OutputTransferName( postprocess_.lastOutput.transfer ),
		GLX_RenderIR_ToneMapName( postprocess_.lastOutput.toneMap ),
		postprocess_.lastOutput.exposure,
		postprocess_.lastOutput.bloomThreshold,
		postprocess_.bloomThresholdMode,
		postprocess_.lastOutput.bloomSoftKnee,
		GLX_RenderIR_ColorGradeName( postprocess_.lastOutput.grade ),
		postprocess_.lastOutput.paperWhiteNits,
		postprocess_.lastOutput.maxOutputNits );
	RI().Printf( PRINT_ALL, "glx: auto exposure mode %i algorithm %s enabled %s fallback %s samples %i/%ix%i percentile %.1f target-luma %.3f measured-log2 %.3f measured-luma %.4f manual %.2f scale %.3f target %.2f frames %u histogram %u simple %u sample-failures %u\n",
		postprocess_.lastAutoExposureMode,
		GLX_RenderIR_ExposureReductionName( postprocess_.lastExposureAlgorithm ),
		BoolName( postprocess_.lastAutoExposureEnabled ),
		BoolName( postprocess_.lastAutoExposureFallback ),
		postprocess_.lastAutoExposureSampleCount,
		postprocess_.lastAutoExposureSampleWidth,
		postprocess_.lastAutoExposureSampleHeight,
		postprocess_.lastAutoExposurePercentile,
		postprocess_.lastAutoExposureTargetLuma,
		postprocess_.lastAutoExposureLogLuma,
		postprocess_.lastAutoExposureLuma,
		postprocess_.lastManualExposure,
		postprocess_.lastAutoExposureScale,
		postprocess_.lastAutoExposureTargetExposure,
		postprocess_.autoExposureFrames,
		postprocess_.autoExposureHistogramFrames,
		postprocess_.autoExposureSimpleFrames,
		postprocess_.autoExposureSampleFailures );
	RI().Printf( PRINT_ALL, "glx: output colorimetry primaries %s gamut-map %s precision-request %i precision-resolved %i\n",
		GLX_RenderIR_OutputPrimariesName( postprocess_.lastOutput.outputPrimaries ),
		GLX_RenderIR_GamutMapName( postprocess_.lastOutput.gamutMap ),
		postprocess_.lastOutput.requestedPrecisionMode,
		postprocess_.lastOutput.precisionMode );
	RI().Printf( PRINT_ALL, "glx: output backend request %s selected %s native %s hardware %s experimental %s display-hdr %s headroom %.2f sdr-white %.0f display-max %.0f icc %s/%i\n",
		RendererOutputRequestName( postprocess_.lastOutput.requestedBackend ),
		RendererOutputBackendName( postprocess_.lastOutput.selectedBackend ),
		RendererOutputBackendName( postprocess_.lastOutput.nativeBackend ),
		BoolName( postprocess_.lastOutput.outputHardwareActive ),
		BoolName( postprocess_.lastOutput.outputExperimental ),
		BoolName( postprocess_.lastOutput.displayHdrEnabled ),
		postprocess_.lastOutput.displayHdrHeadroom,
		postprocess_.lastOutput.displaySdrWhiteNits,
		postprocess_.lastOutput.displayMaxNits,
		BoolName( postprocess_.lastOutput.displayIccProfileAvailable ),
		postprocess_.lastOutput.displayIccProfileBytes );
	RI().Printf( PRINT_ALL, "glx: display state queries %u changes %u capability %u backend %u hdr %u headroom %u luminance %u icc %u last-frame %u flags 0x%08x hash 0x%08x previous 0x%08x\n",
		postprocess_.displayOutputQueries,
		postprocess_.displayOutputStateChanges,
		postprocess_.displayOutputCapabilityChanges,
		postprocess_.displayOutputBackendChanges,
		postprocess_.displayOutputHdrChanges,
		postprocess_.displayOutputHeadroomChanges,
		postprocess_.displayOutputLuminanceChanges,
		postprocess_.displayOutputIccChanges,
		postprocess_.lastDisplayOutputChangeFrame,
		postprocess_.lastDisplayOutputChangeMask,
		postprocess_.lastDisplayOutputHash,
		postprocess_.previousDisplayOutputHash );
	RI().Printf( PRINT_ALL, "glx: color grade mode %s lift %.2f/%.2f/%.2f gamma %.2f/%.2f/%.2f gain %.2f/%.2f/%.2f white-point %.0f->%.0f lut-size %.0f lut-scale %.2f\n",
		GLX_RenderIR_ColorGradeName( postprocess_.lastOutput.grade ),
		postprocess_.lastGradeLift[0], postprocess_.lastGradeLift[1], postprocess_.lastGradeLift[2],
		postprocess_.lastGradeGamma[0], postprocess_.lastGradeGamma[1], postprocess_.lastGradeGamma[2],
		postprocess_.lastGradeGain[0], postprocess_.lastGradeGain[1], postprocess_.lastGradeGain[2],
		postprocess_.lastWhitePointSourceKelvin, postprocess_.lastWhitePointTargetKelvin,
		postprocess_.lastColorGradeLutSize, postprocess_.lastColorGradeLutScale );
	RI().Printf( PRINT_ALL, "glx: color audit srgb-decode %s requested %s available %s framebuffer-srgb %s requested %s available %s capture %s capture-request %s capture-hdr-aware %s capture-supported %s target-float %s final-encode %s contract %s texture-consistent %s stale-srgb-decode %u\n",
		BoolName( postprocess_.textureSrgbDecode ),
		BoolName( postprocess_.r_srgbTextures && postprocess_.r_srgbTextures->integer ? qtrue : qfalse ),
		BoolName( postprocess_.textureSrgbAvailable ),
		BoolName( postprocess_.framebufferSrgbEnabled ),
		BoolName( postprocess_.r_framebufferSRGB && postprocess_.r_framebufferSRGB->integer ? qtrue : qfalse ),
		BoolName( postprocess_.framebufferSrgbAvailable ),
		GLX_RenderIR_CaptureExportPolicyName( postprocess_.lastCaptureSelected ),
		GLX_RenderIR_CaptureExportPolicyName( postprocess_.lastCaptureRequest ),
		BoolName( postprocess_.lastCaptureHdrAware ),
		BoolName( postprocess_.lastCaptureSupported ),
		BoolName( postprocess_.sceneTargetFloat ),
		postprocess_.finalShaderSrgbEncode ? "shader-srgb" : "none",
		BoolName( postprocess_.outputContractValid ),
		BoolName( postprocess_.textureSrgbDecodeConsistent ),
		postprocess_.textureSrgbStaleDecode );
	RI().Printf( PRINT_ALL, "glx: capture policy request %s selected %s hdr-aware %s supported %s sdr-frames %u hdr-requests %u unsupported-requests %u\n",
		GLX_RenderIR_CaptureExportPolicyName( postprocess_.lastCaptureRequest ),
		GLX_RenderIR_CaptureExportPolicyName( postprocess_.lastCaptureSelected ),
		BoolName( postprocess_.lastCaptureHdrAware ),
		BoolName( postprocess_.lastCaptureSupported ),
		postprocess_.captureSdrFrames,
		postprocess_.captureHdrRequestFrames,
		postprocess_.captureUnsupportedRequestFrames );
	RI().Printf( PRINT_ALL, "glx: texture audit srgb %u decode %u, linear %u decode %u, data %u decode %u, unknown %u decode %u, missing-srgb-decode %u, unexpected-decode %u\n",
		postprocess_.imageColorSpaceCounts[GLX_IMAGE_COLORSPACE_SRGB],
		postprocess_.imageSrgbDecodeCounts[GLX_IMAGE_COLORSPACE_SRGB],
		postprocess_.imageColorSpaceCounts[GLX_IMAGE_COLORSPACE_LINEAR],
		postprocess_.imageSrgbDecodeCounts[GLX_IMAGE_COLORSPACE_LINEAR],
		postprocess_.imageColorSpaceCounts[GLX_IMAGE_COLORSPACE_DATA],
		postprocess_.imageSrgbDecodeCounts[GLX_IMAGE_COLORSPACE_DATA],
		postprocess_.imageColorSpaceCounts[GLX_IMAGE_COLORSPACE_UNKNOWN],
		postprocess_.imageSrgbDecodeCounts[GLX_IMAGE_COLORSPACE_UNKNOWN],
		postprocess_.textureSrgbMissingDecode,
		postprocess_.imageUnexpectedSrgbDecode );
	RI().Printf( PRINT_ALL, "glx: stream draws %u/%u attempts, %u idx, %.2fMB/index %.2fMB/tex1 %.2fMB, mt %u, fog %u, depthfrag %u, texmod %u, env %u, dlight %u, screen %u, video %u, shadow %u, beam %u, post %u, fallbacks %u, skips %u\n",
		stream_.streamedDraws,
		stream_.streamedDrawAttempts,
		stream_.streamedDrawIndexes,
		static_cast<double>( stream_.streamedDrawBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( stream_.streamedDrawIndexBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( stream_.streamedDrawTexcoord1Bytes ) / ( 1024.0 * 1024.0 ),
		stream_.streamedDrawMultitextureDraws,
		stream_.streamedDrawFogDraws,
		stream_.streamedDrawDepthFragmentDraws,
		stream_.streamedDrawTexModDraws,
		stream_.streamedDrawEnvironmentDraws,
		stream_.streamedDrawDynamicLightDraws,
		stream_.streamedDrawScreenMapDraws,
		stream_.streamedDrawVideoMapDraws,
		stream_.streamedDrawShadowDraws,
		stream_.streamedDrawBeamDraws,
		stream_.streamedDrawPostProcessDraws,
		stream_.streamedDrawFallbacks,
		stream_.streamedDrawSkips );
	RI().Printf( PRINT_ALL, "glx: stream categories entity %u/%u, particle %u/%u, poly %u/%u, mark %u/%u, weapon %u/%u, ui %u/%u, beam %u/%u, special %u/%u\n",
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_ENTITY],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_ENTITY],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_PARTICLE],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_PARTICLE],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_POLY],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_POLY],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_MARK],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_MARK],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_WEAPON],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_WEAPON],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_UI],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_UI],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_BEAM],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_BEAM],
		stream_.streamedDrawCategoryDraws[GLX_DYNAMIC_CATEGORY_SPECIAL],
		stream_.streamedDrawCategoryAttempts[GLX_DYNAMIC_CATEGORY_SPECIAL] );
	RI().Printf( PRINT_ALL, "glx: stream reservation last %u bytes at %u using %s, largest %u bytes, same-frame wrap rejects %u\n",
		stream_.lastReservationBytes,
		stream_.lastReservationOffset,
		GLX_Stream_StrategyName( stream_.lastReservationStrategy ),
		stream_.largestReservationBytes,
		stream_.sameFrameWrapRejects );
	RI().Printf( PRINT_ALL, "glx: stream binding cache queries %u hits %u restores %u invalidations %u external %u array-known %s array-buffer %u element-known %s element-buffer %u\n",
		stream_.arrayBufferBindingQueries,
		stream_.arrayBufferBindingCacheHits,
		stream_.arrayBufferBindingRestores,
		stream_.arrayBufferBindingInvalidations,
		stream_.bufferBindingExternalUpdates,
		BoolName( stream_.arrayBufferBindingKnown ),
		stream_.arrayBufferBinding,
		BoolName( stream_.elementArrayBufferBindingKnown ),
		stream_.elementArrayBufferBinding );
	RI().Printf( PRINT_ALL, "glx: static queues %u, last %u items/%u idx, device %u idx in %u runs, soft %u idx, largest run %u idx\n",
		staticWorld_.queueBatches,
		staticWorld_.lastQueueItems,
		staticWorld_.lastQueueIndexes,
		staticWorld_.lastQueueDeviceIndexes,
		staticWorld_.lastQueueDeviceRuns,
		staticWorld_.lastQueueSoftIndexes,
		staticWorld_.lastQueueLargestDeviceRunIndexes );
	RI().Printf( PRINT_ALL, "glx: static queue packets last %u full/%u partial/%u miss/%u mismatch, total %u full/%u partial/%u miss\n",
		staticWorld_.lastQueueDeviceFullPacketRuns,
		staticWorld_.lastQueueDevicePartialPacketRuns,
		staticWorld_.lastQueueDevicePacketMisses,
		staticWorld_.lastQueueDeviceItemMismatches,
		staticWorld_.queueDeviceFullPacketRuns,
		staticWorld_.queueDevicePartialPacketRuns,
		staticWorld_.queueDevicePacketMisses );
	RI().Printf( PRINT_ALL, "glx: static indirect queue last %u commands/%u runs/%u idx/%u breaks, largest %u cmds/%u idx, spans %u+%u overflow; total %u commands/%u runs/%u idx/%u breaks, largest %u idx\n",
		staticWorld_.lastQueueDeviceIndirectCommands,
		staticWorld_.lastQueueDeviceIndirectCommandRuns,
		staticWorld_.lastQueueDeviceIndirectIndexes,
		staticWorld_.lastQueueDeviceIndirectBreaks,
		staticWorld_.lastQueueLargestIndirectCommandRun,
		staticWorld_.lastQueueLargestIndirectCommandSpanIndexes,
		staticWorld_.lastQueueCommandSpanCount,
		staticWorld_.lastQueueCommandSpanOverflow,
		staticWorld_.queueDeviceIndirectCommands,
		staticWorld_.queueDeviceIndirectCommandRuns,
		staticWorld_.queueDeviceIndirectIndexes,
		staticWorld_.queueDeviceIndirectBreaks,
		staticWorld_.largestIndirectCommandSpanIndexes );
	RI().Printf( PRINT_ALL, "glx: static packet lookup %u mapped/max %i, hits %u, misses %u, fallbacks %u, mismatches %u, overflows %u\n",
		staticWorld_.itemLookupMappedItems,
		staticWorld_.itemLookupMaxItem,
		staticWorld_.itemLookupHits,
		staticWorld_.itemLookupMisses,
		staticWorld_.itemLookupFallbacks,
		staticWorld_.itemLookupMismatches,
		staticWorld_.itemLookupOverflows );
	RI().Printf( PRINT_ALL, "glx: static indirect packets %u commands/%u idx/%u bytes, invalid %u, misaligned %u\n",
		staticWorld_.indirectPacketCount,
		staticWorld_.indirectPacketIndexes,
		staticWorld_.indirectPacketBytes,
		staticWorld_.indirectPacketInvalid,
		staticWorld_.indirectPacketMisaligned );
	RI().Printf( PRINT_ALL, "glx: static indirect caps draw %s, multidraw %s\n",
		BoolName( staticWorld_.drawIndirectAvailable ),
		BoolName( staticWorld_.multiDrawIndirectAvailable ) );
	RI().Printf( PRINT_ALL, "glx: static indirect buffer %s, builds %u, skips %u, unsupported %u, failures %u, %u commands/%u bytes\n",
		staticWorld_.indirectBufferReady ? "ready" : "off",
		staticWorld_.indirectBufferBuilds,
		staticWorld_.indirectBufferSkips,
		staticWorld_.indirectBufferUnsupported,
		staticWorld_.indirectBufferFailures,
		staticWorld_.indirectBufferCommands,
		staticWorld_.indirectBufferBytes );
	RI().Printf( PRINT_ALL, "glx: static indirect draw %u/%u calls, %u idx, fallbacks %u, skips %u, no-command %u, errors %u\n",
		staticWorld_.indirectDrawCalls,
		staticWorld_.indirectDrawAttempts,
		staticWorld_.indirectDrawIndexes,
		staticWorld_.indirectDrawFallbacks,
		staticWorld_.indirectDrawSkips,
		staticWorld_.indirectDrawNoCommand,
		staticWorld_.indirectDrawErrors );
	RI().Printf( PRINT_ALL, "glx: static draw %u/%u calls, %u idx, packets %u full/%u partial/%u miss, manifest %u/%u idx, soft %u/%u calls/%u idx, arena %u, legacy %u, fallbacks %u, policy skips %u\n",
		staticWorld_.drawCalls,
		staticWorld_.drawAttempts,
		staticWorld_.drawIndexes,
		staticWorld_.drawPacketFullHits,
		staticWorld_.drawPacketPartialHits,
		staticWorld_.drawPacketMisses,
		staticWorld_.drawManifestPacketCalls,
		staticWorld_.drawManifestPacketIndexes,
		staticWorld_.softDrawCalls,
		staticWorld_.softDrawAttempts,
		staticWorld_.softDrawIndexes,
		staticWorld_.drawArenaCalls,
		staticWorld_.drawLegacyBufferCalls,
		staticWorld_.drawFallbacks,
		staticWorld_.drawPolicySkips );
	RI().Printf( PRINT_ALL, "glx: static multidraw %u calls/%u runs/%u idx, attempts %u, fallbacks %u\n",
		staticWorld_.multiDrawCalls,
		staticWorld_.multiDrawRuns,
		staticWorld_.multiDrawIndexes,
		staticWorld_.multiDrawAttempts,
		staticWorld_.multiDrawFallbacks );
	RI().Printf( PRINT_ALL, "glx: static filtered multidraw attempts %u, batches %u, runs %u, candidates %u, skips %u\n",
		staticWorld_.multiDrawFilteredAttempts,
		staticWorld_.multiDrawFilteredBatches,
		staticWorld_.multiDrawFilteredRuns,
		staticWorld_.multiDrawFilteredCandidates,
		staticWorld_.multiDrawFilteredSkips );
	RI().Printf( PRINT_ALL, "glx: static filtered multidraw barriers %u, invalid %u, policy %u, last %s at run %i\n",
		staticWorld_.multiDrawFilteredOrderBarriers,
		staticWorld_.multiDrawFilteredInvalidBarriers,
		staticWorld_.multiDrawFilteredPolicyBarriers,
		GLX_StaticWorld_FilteredBarrierName( staticWorld_.multiDrawFilteredLastBarrierReason ),
		staticWorld_.multiDrawFilteredLastBarrierRun );
	RI().Printf( PRINT_ALL, "glx: static MDI %u/%u calls, %u runs/%u idx, fallbacks %u, skips %u, errors %u, largest %u\n",
		staticWorld_.multiDrawIndirectCalls,
		staticWorld_.multiDrawIndirectAttempts,
		staticWorld_.multiDrawIndirectRuns,
		staticWorld_.multiDrawIndirectIndexes,
		staticWorld_.multiDrawIndirectFallbacks,
		staticWorld_.multiDrawIndirectSkips,
		staticWorld_.multiDrawIndirectErrors,
		staticWorld_.multiDrawIndirectLargestRun );
	RI().Printf( PRINT_ALL, "glx: static MDI shape last %s %u runs/%u idx/first %i, largest %u idx\n",
		GLX_Module_MdiSourceName( staticWorld_.multiDrawIndirectLastSource ),
		staticWorld_.multiDrawIndirectLastRuns,
		staticWorld_.multiDrawIndirectLastIndexes,
		staticWorld_.multiDrawIndirectLastFirstCommand,
		staticWorld_.multiDrawIndirectLargestIndexes );
	RI().Printf( PRINT_ALL, "glx: static MDI sources static %u, compact %u calls/%u uploads/%u subdata/%u orphan/%u grow/%u bytes, failures %u, buffer %u/%u\n",
		staticWorld_.multiDrawIndirectStaticCalls,
		staticWorld_.multiDrawIndirectCompactCalls,
		staticWorld_.multiDrawIndirectCompactUploads,
		staticWorld_.multiDrawIndirectCompactSubDatas,
		staticWorld_.multiDrawIndirectCompactOrphans,
		staticWorld_.multiDrawIndirectCompactGrows,
		staticWorld_.multiDrawIndirectCompactBytes,
		staticWorld_.multiDrawIndirectCompactFailures,
		staticWorld_.indirectCompactBufferBytes,
		staticWorld_.indirectCompactBufferCapacityBytes );
	RI().Printf( PRINT_ALL, "glx: static MDI last reject %s, %u runs/%u idx, command %i\n",
		GLX_StaticWorld_MdiRejectName( staticWorld_.multiDrawIndirectLastRejectReason ),
		staticWorld_.multiDrawIndirectLastRejectRuns,
		staticWorld_.multiDrawIndirectLastRejectIndexes,
		staticWorld_.multiDrawIndirectLastRejectCommand );
	RI().Printf( PRINT_ALL, "glx: static MDI spans attempts %u, batches %u, mdi runs %u, fallback runs %u, singles %u, single draws %u/%u indirect\n",
		staticWorld_.multiDrawIndirectSpanAttempts,
		staticWorld_.multiDrawIndirectSpanBatches,
		staticWorld_.multiDrawIndirectSpanMdiRuns,
		staticWorld_.multiDrawIndirectSpanFallbackRuns,
		staticWorld_.multiDrawIndirectSpanSingles,
		staticWorld_.multiDrawIndirectSpanSingleDraws,
		staticWorld_.multiDrawIndirectSpanSingleIndirectDraws );
	RI().Printf( PRINT_ALL, "glx: static MDI span shape last %u seg/%u mdi/%u fallback/%u single, largest %u seg\n",
		staticWorld_.multiDrawIndirectSpanLastSegments,
		staticWorld_.multiDrawIndirectSpanLastMdiRuns,
		staticWorld_.multiDrawIndirectSpanLastFallbackRuns,
		staticWorld_.multiDrawIndirectSpanLastSingles,
		staticWorld_.multiDrawIndirectSpanLargestSegments );
	RI().Printf( PRINT_ALL, "glx: static MDI command spans attempts %u, batches %u, mdi runs %u, fallback runs %u, singleton draws %u/%u indirect, singleton blocks %u\n",
		staticWorld_.multiDrawIndirectCommandSpanAttempts,
		staticWorld_.multiDrawIndirectCommandSpanBatches,
		staticWorld_.multiDrawIndirectCommandSpanMdiRuns,
		staticWorld_.multiDrawIndirectCommandSpanFallbackRuns,
		staticWorld_.multiDrawIndirectCommandSpanSingletonDraws,
		staticWorld_.multiDrawIndirectCommandSpanSingletonIndirectDraws,
		staticWorld_.multiDrawIndirectCommandSpanSingletons );
	RI().Printf( PRINT_ALL, "glx: static MDI command span shape last %u seg/%u mdi/%u fallback/%u singleton, largest %u seg\n",
		staticWorld_.multiDrawIndirectCommandSpanLastSegments,
		staticWorld_.multiDrawIndirectCommandSpanLastMdiRuns,
		staticWorld_.multiDrawIndirectCommandSpanLastFallbackRuns,
		staticWorld_.multiDrawIndirectCommandSpanLastSingletonDraws,
		staticWorld_.multiDrawIndirectCommandSpanLargestSegments );
	RI().Printf( PRINT_ALL, "glx: static MDI reasons unsupported %u, short %u, nonmanifest %u, missing %u, noncontiguous %u\n",
		staticWorld_.multiDrawIndirectUnsupported,
		staticWorld_.multiDrawIndirectShortBatches,
		staticWorld_.multiDrawIndirectNonManifest,
		staticWorld_.multiDrawIndirectMissingCommand,
		staticWorld_.multiDrawIndirectNonContiguous );
}

void RendererModule::StreamTest()
{
	GLX_Stream_RunSelfTest( &stream_ );
}

qboolean RendererModule::DrawElements( unsigned int mode, int count, unsigned int type,
	const void *indices, int legacyReason, int profilerPath )
{
	DynamicDraw draw = GLX_Module_IndexedDrawIR( mode, count, type, indices, legacyReason, profilerPath );

	if ( legacyReason >= 0 ) {
		GLX_Profiler_RecordLegacyDelegation( &profiler_, legacyReason, count );
		if ( requireOwnership_ && requireOwnership_->integer ) {
			return qfalse;
		}
	}

	if ( !GLX_Executor_ExecuteDynamicDraw( &executor_, draw ) ) {
		return qfalse;
	}
	if ( profilerPath >= 0 ) {
		GLX_Profiler_RecordDraw( &profiler_, count, profilerPath );
	}
	return qtrue;
}

qboolean RendererModule::DrawArrays( unsigned int mode, int first, int count,
	int legacyReason, int profilerPath )
{
	DynamicDraw draw = GLX_Module_ArrayDrawIR( mode, first, count, legacyReason, profilerPath );

	if ( legacyReason >= 0 ) {
		GLX_Profiler_RecordLegacyDelegation( &profiler_, legacyReason, count );
		if ( requireOwnership_ && requireOwnership_->integer ) {
			return qfalse;
		}
	}

	if ( !GLX_Executor_ExecuteDynamicDraw( &executor_, draw ) ) {
		return qfalse;
	}
	if ( profilerPath >= 0 ) {
		GLX_Profiler_RecordDraw( &profiler_, count, profilerPath );
	}
	return qtrue;
}

void RendererModule::RecordDraw( int indexes, int path )
{
	GLX_Profiler_RecordDraw( &profiler_, indexes, path );
}

void RendererModule::RecordShaderBatch( const char *shaderName, int sort, int numPasses, int numVertexes, int numIndexes, int flags )
{
	GLX_Profiler_RecordShaderBatch( &profiler_, shaderName, sort, numPasses, numVertexes, numIndexes, flags );
}

void RendererModule::RecordMaterialStage( int path, int flags, unsigned int stateBits, int rgbGen, int alphaGen,
	int tcGen0, int tcGen1, int texMods0, int texMods1,
	unsigned int texModTypes0, unsigned int texModTypes1,
	unsigned int texModSequence0, unsigned int texModSequence1,
	int rgbWaveFunc, int alphaWaveFunc,
	unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1,
	int fogAdjust, int materialCombine, qboolean fogPass,
	int numVertexes, int numIndexes )
{
	MaterialIR material = GLX_Module_StageMaterialIR( 0, flags, stateBits,
		rgbGen, alphaGen, tcGen0, tcGen1, texMods0, texMods1,
		texModTypes0, texModTypes1, texModSequence0, texModSequence1,
		rgbWaveFunc, alphaWaveFunc, texModWaveFuncs0, texModWaveFuncs1,
		fogAdjust, materialCombine, fogPass );

	GLX_Profiler_RecordMaterialStage( &profiler_, path, flags, stateBits, rgbGen, alphaGen,
		tcGen0, tcGen1, texMods0, texMods1, numVertexes, numIndexes );
	GLX_Executor_ConsumeMaterial( &executor_, material );
}

qboolean RendererModule::MaterialRendererActive() const
{
	return GLX_Material_Active( material_ );
}

qboolean RendererModule::BindMaterialStage( int flags, unsigned int stateBits, int rgbGen, int alphaGen,
	int tcGen0, int tcGen1, int texMods0, int texMods1,
	unsigned int texModTypes0, unsigned int texModTypes1,
	unsigned int texModSequence0, unsigned int texModSequence1,
	int rgbWaveFunc, int alphaWaveFunc,
	unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1, int fogAdjust,
	int materialCombine, qboolean fogPass )
{
	MaterialRequest request {};
	MaterialIR material = GLX_Module_StageMaterialIR( 0, flags, stateBits,
		rgbGen, alphaGen, tcGen0, tcGen1, texMods0, texMods1,
		texModTypes0, texModTypes1, texModSequence0, texModSequence1,
		rgbWaveFunc, alphaWaveFunc, texModWaveFuncs0, texModWaveFuncs1,
		fogAdjust, materialCombine, fogPass );

	request.flags = flags;
	request.stateBits = stateBits;
	request.rgbGen = rgbGen;
	request.alphaGen = alphaGen;
	request.rgbWaveFunc = rgbWaveFunc;
	request.alphaWaveFunc = alphaWaveFunc;
	request.tcGen0 = tcGen0;
	request.tcGen1 = tcGen1;
	request.texMods0 = texMods0;
	request.texMods1 = texMods1;
	request.texModTypes0 = texModTypes0;
	request.texModTypes1 = texModTypes1;
	request.texModSequence0 = texModSequence0;
	request.texModSequence1 = texModSequence1;
	request.texModWaveFuncs0 = texModWaveFuncs0;
	request.texModWaveFuncs1 = texModWaveFuncs1;
	request.fogAdjust = fogAdjust;
	request.materialCombine = materialCombine;
	request.fogPass = fogPass;

	material_.lastRequest = request;
	return GLX_Material_BindIR( &material_, material );
}

qboolean RendererModule::BindFogMaterial()
{
	return GLX_Material_BindFog( &material_ );
}

void RendererModule::UnbindMaterial()
{
	GLX_Material_Unbind( &material_ );
}

qboolean RendererModule::StreamDrawEnabled() const
{
	return GLX_Stream_DrawEnabled( stream_ );
}

qboolean RendererModule::StreamDrawMultitextureEnabled() const
{
	return GLX_Stream_DrawMultitextureEnabled( stream_ );
}

qboolean RendererModule::StreamDrawFogEnabled() const
{
	return GLX_Stream_DrawFogEnabled( stream_ );
}

qboolean RendererModule::StreamDrawDepthFragmentEnabled() const
{
	return GLX_Stream_DrawDepthFragmentEnabled( stream_ );
}

qboolean RendererModule::StreamDrawShadowsEnabled() const
{
	return GLX_Stream_DrawShadowsEnabled( stream_ );
}

qboolean RendererModule::StreamDrawBeamsEnabled() const
{
	return GLX_Stream_DrawBeamsEnabled( stream_ );
}

qboolean RendererModule::StreamDrawPostProcessEnabled() const
{
	return GLX_Stream_DrawPostProcessEnabled( stream_ );
}

qboolean RendererModule::StreamDrawAllowsMaterial( int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	unsigned int texModTypes0, unsigned int texModTypes1,
	unsigned int texModSequence0, unsigned int texModSequence1,
	int rgbWaveFunc, int alphaWaveFunc,
	unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1,
	int fogAdjust, int materialCombine, qboolean fogPass )
{
	const MaterialIR material = GLX_Module_StageMaterialIR( 0, flags, stateBits,
		rgbGen, alphaGen, tcGen0, tcGen1, texMods0, texMods1,
		texModTypes0, texModTypes1, texModSequence0, texModSequence1,
		rgbWaveFunc, alphaWaveFunc, texModWaveFuncs0, texModWaveFuncs1,
		fogAdjust, materialCombine, fogPass );
	return GLX_Stream_DrawAllowsMaterial( &stream_, material );
}

qboolean RendererModule::StreamReserve( int bytes, int alignment, glxStreamReservation_t *reservation )
{
	StreamReservation streamReservation;

	if ( bytes <= 0 || alignment <= 0 || !reservation ) {
		stream_.reserveFailures++;
		return qfalse;
	}

	if ( !GLX_Stream_Reserve( &stream_, static_cast<size_t>( bytes ), static_cast<size_t>( alignment ), &streamReservation ) ) {
		return qfalse;
	}

	GLX_Module_ToPublicReservation( streamReservation, reservation );
	return qtrue;
}

qboolean RendererModule::StreamUploadAt( glxStreamReservation_t *reservation, int relativeOffset, const void *data, int bytes )
{
	StreamReservation streamReservation;
	qboolean ok;

	if ( !reservation || relativeOffset < 0 || bytes <= 0 ) {
		stream_.uploadFailures++;
		return qfalse;
	}

	streamReservation = GLX_Module_FromPublicReservation( *reservation );
	ok = GLX_Stream_UploadAt( &stream_, &streamReservation, static_cast<size_t>( relativeOffset ), data, static_cast<size_t>( bytes ) );
	GLX_Module_ToPublicReservation( streamReservation, reservation );
	return ok;
}

void RendererModule::StreamCommit( glxStreamReservation_t *reservation )
{
	StreamReservation streamReservation;

	if ( !reservation ) {
		return;
	}

	streamReservation = GLX_Module_FromPublicReservation( *reservation );
	GLX_Stream_Commit( &stream_, &streamReservation );
	GLX_Module_ToPublicReservation( streamReservation, reservation );
}

GLuint RendererModule::BindStreamArrayBuffer( GLuint buffer )
{
	return GLX_Stream_BindArrayBufferCached( &stream_, buffer );
}

void RendererModule::RestoreStreamArrayBuffer( GLuint buffer )
{
	GLX_Stream_RestoreArrayBufferCached( &stream_, buffer );
}

GLuint RendererModule::BindStreamElementArrayBuffer( GLuint buffer )
{
	return GLX_Stream_BindElementArrayBufferCached( &stream_, buffer );
}

void RendererModule::RestoreStreamElementArrayBuffer( GLuint buffer )
{
	GLX_Stream_RestoreElementArrayBufferCached( &stream_, buffer );
}

void RendererModule::RecordStreamBufferBind( unsigned int target, GLuint buffer )
{
	GLX_Stream_RecordExternalBufferBind( &stream_, target, buffer );
}

void RendererModule::RecordStreamDrawResult( int numVertexes, int numIndexes, int totalBytes, int indexBytes,
	int texcoord1Bytes, qboolean multitexture, qboolean fog, qboolean depthFragment, int materialFlags,
	unsigned int categoryMask, qboolean success )
{
	UploadPlan upload = GLX_Module_StreamUploadPlan( totalBytes,
		totalBytes > indexBytes + texcoord1Bytes ? totalBytes - indexBytes - texcoord1Bytes : 0,
		indexBytes );
	upload.texcoordBytes = texcoord1Bytes > 0 ? static_cast<unsigned int>( texcoord1Bytes ) : 0;

	GLX_Stream_RecordDrawResult( &stream_, numVertexes, numIndexes, totalBytes, indexBytes,
		texcoord1Bytes, multitexture, fog, depthFragment, materialFlags, categoryMask, success );
	GLX_Executor_ConsumeUploadPlan( &executor_, upload );
}

void RendererModule::RecordStreamDrawSkip( int reason )
{
	GLX_Stream_RecordDrawSkip( &stream_, reason );
}

void RendererModule::ResetImageColorAudit()
{
	GLX_PostProcess_ResetImageColorAudit( &postprocess_ );
}

void RendererModule::RecordImageColorAudit( int colorSpace, qboolean srgbDecode )
{
	GLX_PostProcess_RecordImageColorAudit( &postprocess_, colorSpace, srgbDecode );
}

void RendererModule::RecordFboInit( qboolean requested, qboolean ready, qboolean programReady, qboolean framebufferFnsReady,
	int vidWidth, int vidHeight, int captureWidth, int captureHeight, int windowWidth, int windowHeight,
	int internalFormat, int textureFormat, int textureType, qboolean multiSampled, qboolean superSampled,
	qboolean windowAdjusted, int blitFilter, int hdrMode, int renderScaleMode, int bloomMode,
	qboolean textureSrgbAvailable, qboolean framebufferSrgbAvailable, qboolean framebufferSrgbEnabled )
{
	GLX_PostProcess_RecordFboInit( &postprocess_, requested, ready, programReady, framebufferFnsReady,
		vidWidth, vidHeight, captureWidth, captureHeight, windowWidth, windowHeight,
		internalFormat, textureFormat, textureType, multiSampled, superSampled,
		windowAdjusted, blitFilter, hdrMode, renderScaleMode, bloomMode,
		textureSrgbAvailable, framebufferSrgbAvailable, framebufferSrgbEnabled );
}

void RendererModule::RecordFboShutdown()
{
	GLX_PostProcess_RecordFboShutdown( &postprocess_ );
}

void RendererModule::RecordPostProcessFrame( qboolean minimized, qboolean bloomAvailable, qboolean programReady,
	int screenshotMask, qboolean windowAdjusted, int fboReadIndex, int hdrMode, int renderScaleMode,
	float greyscale )
{
	GLX_PostProcess_RecordFrame( &postprocess_, minimized, bloomAvailable, programReady,
		screenshotMask, windowAdjusted, fboReadIndex, hdrMode, renderScaleMode, greyscale );
	OutputTransform output = GLX_Module_OutputTransformIR( postprocess_ );
	PostOutputPlanInputs inputs {};
	inputs.tier = caps_.tier;
	inputs.output = output;
	inputs.captureRequest = postprocess_.lastCaptureRequest;
	inputs.fboReady = postprocess_.fboReady;
	inputs.programReady = programReady;
	inputs.framebufferFnsReady = postprocess_.framebufferFnsReady;
	inputs.outputContractValid = postprocess_.outputContractValid;
	inputs.bloomAvailable = bloomAvailable;
	inputs.postShaderExecutorEnabled = GLX_PostShader_ExecutionEnabled( postShader_ );
	inputs.minimized = minimized;
	inputs.windowAdjusted = windowAdjusted;
	inputs.screenshotMask = screenshotMask;
	inputs.fboReadIndex = fboReadIndex;
	inputs.sequenceBase = static_cast<int>( postprocess_.frames ? postprocess_.frames - 1 : 0 );
	inputs.flags = ( minimized ? 0x1u : 0u ) | ( programReady ? 0x2u : 0u ) |
		( windowAdjusted ? 0x4u : 0u ) | ( screenshotMask ? 0x8u : 0u );

	PostOutputPlan plan = GLX_RenderIR_BuildPostOutputPlan( inputs );
	PostShaderPlan shaderPlan = GLX_Module_PostShaderPlanForOutputPlan( output, plan );
	if ( GLX_Module_PostOutputPlanHasNode( plan, PostNodeKind::BloomPrefinal ) ) {
		GLX_PostShader_RecordPlan( &postShader_,
			GLX_PostShader_BuildPlanForPass( output, qtrue, qfalse ) );
	}
	GLX_PostShader_RecordPlan( &postShader_, shaderPlan );
	postShaderBindBaseline_ = postShader_.directFinalBinds;
	postShaderExpectedBinds_ = plan.glxOwned ?
		GLX_Module_PostOutputExpectedShaderBinds( plan ) : 0u;
	qboolean consumed = qtrue;
	for ( int i = 0; i < plan.nodeCount; i++ ) {
		if ( !GLX_Executor_ConsumePostNode( &executor_, plan.nodes[i] ) ) {
			consumed = qfalse;
		}
	}
	if ( plan.outputTransformPresent && !GLX_Executor_ConsumeOutputTransform( &executor_, plan.output ) ) {
		consumed = qfalse;
	}
	GLX_PostProcess_RecordPostOutputPlan( &postprocess_, plan, consumed );
	GLX_PostProcess_RecordPostShaderPlan( &postprocess_, shaderPlan );
}

qboolean RendererModule::AutoExposureNeedsSamples( int *width, int *height ) const
{
	return GLX_PostProcess_AutoExposureNeedsSamples( &postprocess_, width, height );
}

float RendererModule::UpdateAutoExposure( float manualExposure, const float *rgba,
	int width, int height )
{
	return GLX_PostProcess_UpdateAutoExposure( &postprocess_, manualExposure,
		rgba, width, height );
}

qboolean RendererModule::TryBindPostShaderFinal( qboolean bloomComposite,
	qboolean outputTransform, float bloomIntensity )
{
	const OutputTransform output = GLX_Module_OutputTransformIR( postprocess_ );
	const PostShaderPlan shaderPlan = GLX_PostShader_BuildPlanForPass( output,
		bloomComposite, outputTransform );

	return GLX_PostShader_TryBindFinal( &postShader_, shaderPlan, output,
		bloomComposite, outputTransform, bloomIntensity );
}

qboolean RendererModule::TryBindPostShaderDirectFinal()
{
	return TryBindPostShaderFinal( qfalse, qtrue, 0.0f );
}

void RendererModule::UnbindPostShader()
{
	GLX_PostShader_Unbind( &postShader_ );
}

void RendererModule::RecordPostProcessResult( int result )
{
	PostNode node {};
	node.pass = FramePassKind::PostProcess;
	node.sequence = static_cast<int>( postprocess_.frames );
	node.output = GLX_Module_OutputTransformIR( postprocess_ );

	switch ( result ) {
	case GLX_POSTPROCESS_RESULT_BLOOM_FINAL:
		node.kind = PostNodeKind::BloomFinal;
		break;
	case GLX_POSTPROCESS_RESULT_GAMMA_DIRECT:
		node.kind = PostNodeKind::GammaDirect;
		break;
	case GLX_POSTPROCESS_RESULT_GAMMA_BLIT:
		node.kind = PostNodeKind::GammaBlit;
		break;
	default:
		node.kind = PostNodeKind::Resolve;
		break;
	}

	GLX_PostProcess_RecordFrameResult( &postprocess_, result );
	GLX_Executor_ConsumePostNode( &executor_, node );
	if ( postShaderExpectedBinds_ > 0u &&
		postShader_.directFinalBinds - postShaderBindBaseline_ < postShaderExpectedBinds_ ) {
		GLX_PostProcess_RecordPostOutputExecutionFallback( &postprocess_,
			GLX_POST_OUTPUT_FALLBACK_EXECUTOR_NOT_BOUND );
	}
	postShaderBindBaseline_ = postShader_.directFinalBinds;
	postShaderExpectedBinds_ = 0u;
}

void RendererModule::RecordColorGradeLut( qboolean active, int size, float scale )
{
	GLX_PostProcess_RecordColorGradeLut( &postprocess_, active, size, scale );
}

void RendererModule::RecordBloomCreate( int result, int requestedPasses, int effectivePasses,
	int textureUnits, int formatMode, int internalFormat, int textureFormat,
	int textureType )
{
	GLX_PostProcess_RecordBloomCreate( &postprocess_, result, requestedPasses,
		effectivePasses, textureUnits, formatMode, internalFormat,
		textureFormat, textureType );
}

void RendererModule::RecordBloom( int result, qboolean finalStage, int bloomMode, int requestedPasses,
	int effectivePasses, int blendBase, int filterSize, int textureUnits, int thresholdMode,
	int modulate, float threshold, float intensity, float reflection )
{
	GLX_PostProcess_RecordBloom( &postprocess_, result, finalStage, bloomMode, requestedPasses,
		effectivePasses, blendBase, filterSize, textureUnits, thresholdMode, modulate,
		threshold, intensity, reflection );
}

void RendererModule::RecordFboCopyScreen( int viewportWidth, int viewportHeight )
{
	GLX_PostProcess_RecordCopyScreen( &postprocess_, viewportWidth, viewportHeight );
}

void RendererModule::RecordFboBlit( int kind, qboolean depthOnly, int srcWidth, int srcHeight, int dstWidth, int dstHeight )
{
	GLX_PostProcess_RecordBlit( &postprocess_, kind, depthOnly, srcWidth, srcHeight, dstWidth, dstHeight );
	GLX_Profiler_RecordPostBlit( &profiler_ );
}

void RendererModule::RecordFboBind()
{
	GLX_Profiler_RecordPostBind( &profiler_ );
}

void RendererModule::RecordPostClear()
{
	GLX_Profiler_RecordPostClear( &profiler_ );
}

void RendererModule::RecordFullscreenPass()
{
	GLX_Profiler_RecordFullscreenPass( &profiler_ );
}

void RendererModule::PushShaderDebugGroup( const char *shaderName, int numVertexes, int numIndexes, int numPasses )
{
	char label[192];

	if ( !shaderName || !*shaderName ) {
		shaderName = "<unnamed>";
	}

	std::snprintf( label, sizeof( label ), "shader %s verts %i indexes %i passes %i",
		shaderName, numVertexes, numIndexes, numPasses );
	GLX_Debug_PushGroup( &debug_, label );
}

void RendererModule::PopDebugGroup()
{
	GLX_Debug_PopGroup( &debug_ );
}

void RendererModule::ShadowUploadTess( int numVertexes, int numIndexes, const void *xyz, int xyzBytes, const void *indexes, int indexBytes )
{
	if ( xyzBytes <= 0 || indexBytes <= 0 ) {
		return;
	}

	GLX_Stream_ShadowUploadTess( &stream_, numVertexes, numIndexes,
		xyz, static_cast<size_t>( xyzBytes ), indexes, static_cast<size_t>( indexBytes ) );
}

void RendererModule::RecordStaticWorldCache( int surfaces, int vertexes, int indexes, int vertexBytes, int indexBytes )
{
	GLX_StaticWorld_Record( &staticWorld_, surfaces, vertexes, indexes, vertexBytes, indexBytes );
}

void RendererModule::RecordStaticWorldBatches( int batches, int largestBatchSurfaces, int faceSurfaces,
	int gridSurfaces, int triangleSurfaces, int shaderStagePasses, int maxShaderStages )
{
	GLX_StaticWorld_RecordBatches( &staticWorld_, batches, largestBatchSurfaces, faceSurfaces,
		gridSurfaces, triangleSurfaces, shaderStagePasses, maxShaderStages );
}

void RendererModule::RecordStaticWorldPacket( const char *shaderName, int sort,
	int surfaces, int vertexes, int indexes, int firstItem, int itemCount, int vertexOffset, int vertexBytes,
	int indexOffset, int indexBytes, int shaderStagePasses, int flags )
{
	WorldPacket packet = GLX_Module_WorldPacketIR( staticWorld_.packetCount, sort,
		surfaces, vertexes, indexes, firstItem, itemCount, vertexOffset, vertexBytes,
		indexOffset, indexBytes, shaderStagePasses, flags );

	GLX_StaticWorld_RecordPacket( &staticWorld_, shaderName, sort,
		surfaces, vertexes, indexes, firstItem, itemCount, vertexOffset, vertexBytes,
		indexOffset, indexBytes, shaderStagePasses, flags );
	GLX_Executor_ConsumeWorldPacket( &executor_, packet );
}

void RendererModule::UploadStaticWorldArena( const void *vertexData, int vertexBytes, const void *indexData, int indexBytes )
{
	GLX_StaticWorld_UploadArena( &staticWorld_, vertexData, vertexBytes, indexData, indexBytes );
	GLX_StaticWorld_UploadIndirectCommands( &staticWorld_, caps_.features.drawIndirect );
	GLX_Debug_LabelObject( debug_, GL_BUFFER, staticWorld_.arenaVertexBuffer, "GLx static world vertex arena" );
	GLX_Debug_LabelObject( debug_, GL_BUFFER, staticWorld_.arenaIndexBuffer, "GLx static world index arena" );
	GLX_Debug_LabelObject( debug_, GL_BUFFER, staticWorld_.indirectCommandBuffer, "GLx static world indirect commands" );
}

GLuint RendererModule::StaticWorldArenaVertexBuffer()
{
	return GLX_StaticWorld_ArenaVertexBufferForDraw( &staticWorld_ );
}

GLuint RendererModule::StaticWorldArenaIndexBuffer()
{
	return GLX_StaticWorld_ArenaIndexBufferForDraw( &staticWorld_ );
}

qboolean RendererModule::StaticWorldDrawDeviceRun( int indexes, int offsetBytes,
	int firstItem, int itemCount, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound )
{
	if ( GLX_StaticWorld_DrawDeviceRun( &staticWorld_, indexes, offsetBytes,
		firstItem, itemCount, static_cast<GLenum>( indexType ), indexBytes,
		shaderName, sort, arenaBound ) ) {
		GLX_Profiler_RecordDraw( &profiler_, indexes, GLX_DRAW_VBO_DEVICE );
		return qtrue;
	}

	return qfalse;
}

qboolean RendererModule::StaticWorldDrawDeviceRuns( int runCount, const int *counts, const void *const *offsets,
	const int *firstItems, const int *itemCounts, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound )
{
	unsigned int totalIndexes = 0;

	if ( GLX_StaticWorld_DrawDeviceRuns( &staticWorld_, runCount, counts, offsets, firstItems, itemCounts,
		static_cast<GLenum>( indexType ), indexBytes, shaderName, sort, arenaBound ) ) {
		for ( int i = 0; i < runCount; i++ ) {
			if ( counts && counts[i] > 0 ) {
				totalIndexes += static_cast<unsigned int>( counts[i] );
			}
		}
		GLX_Profiler_RecordDraw( &profiler_, static_cast<int>( totalIndexes ), GLX_DRAW_VBO_DEVICE );
		return qtrue;
	}

	return qfalse;
}

qboolean RendererModule::StaticWorldDrawSoftIndexes( int indexes, const void *indexData,
	unsigned int indexType, int indexBytes, const char *shaderName, int sort, qboolean arenaBound )
{
	if ( GLX_StaticWorld_DrawSoftIndexes( &staticWorld_, indexes, indexData,
		static_cast<GLenum>( indexType ), indexBytes, shaderName, sort, arenaBound ) ) {
		GLX_Profiler_RecordDraw( &profiler_, indexes, GLX_DRAW_VBO_SOFT );
		return qtrue;
	}

	return qfalse;
}

int RendererModule::StaticWorldDrawDeviceRunsFiltered( int runCount, const int *counts, const void *const *offsets,
	const int *firstItems, const int *itemCounts, int *drawnRuns, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound )
{
	int drawnIndexes = 0;
	int drawnRunsCount;

	drawnRunsCount = GLX_StaticWorld_DrawDeviceRunsFiltered( &staticWorld_, runCount, counts, offsets,
		firstItems, itemCounts, drawnRuns, static_cast<GLenum>( indexType ), indexBytes,
		shaderName, sort, arenaBound );
	GLX_Debug_LabelObject( debug_, GL_BUFFER, staticWorld_.indirectCompactCommandBuffer,
		"GLx static world compact indirect commands" );
	if ( drawnRunsCount <= 0 ) {
		return 0;
	}

	for ( int i = 0; i < runCount; i++ ) {
		if ( drawnRuns && drawnRuns[i] && counts && counts[i] > 0 ) {
			drawnIndexes += counts[i];
		}
	}
	GLX_Profiler_RecordDraw( &profiler_, drawnIndexes, GLX_DRAW_VBO_DEVICE );
	return drawnRunsCount;
}

void RendererModule::RecordStaticWorldQueue( int queuedItems, int queuedVertexes, int queuedIndexes,
	int deviceRuns, int deviceIndexes, int softIndexes, int largestDeviceRunIndexes )
{
	GLX_StaticWorld_RecordQueue( &staticWorld_, queuedItems, queuedVertexes, queuedIndexes,
		deviceRuns, deviceIndexes, softIndexes, largestDeviceRunIndexes );
}

void RendererModule::RecordStaticWorldDeviceRuns( int runCount, const int *counts, const void *const *offsets,
	const int *firstItems, const int *itemCounts, int indexBytes, const char *shaderName, int sort )
{
	GLX_StaticWorld_RecordDeviceRuns( &staticWorld_, runCount, counts, offsets,
		firstItems, itemCounts, indexBytes, shaderName, sort );
}

} // namespace glx

extern "C" void GLX_Renderer_RegisterCommands( void )
{
	glx::g_module.RegisterCommands();
}

extern "C" void GLX_Renderer_RemoveCommands( void )
{
	glx::g_module.RemoveCommands();
}

extern "C" void GLX_Renderer_SetImports( refimport_t *imports )
{
	glx::g_imports = imports;
}

extern "C" void GLX_Renderer_OnOpenGLReady( const glconfig_t *config, const char *extensions )
{
	glx::g_module.OnOpenGLReady( config, extensions );
}

extern "C" void GLX_Renderer_Shutdown( int code )
{
	glx::g_module.Shutdown( code );
}

extern "C" void GLX_Renderer_BeginBackendTimer( void )
{
	glx::g_module.BeginBackendTimer();
}

extern "C" void GLX_Renderer_EndBackendTimer( void )
{
	glx::g_module.EndBackendTimer();
}

extern "C" void GLX_Renderer_BeginGpuPassTimer( int pass )
{
	glx::g_module.BeginGpuPassTimer( pass );
}

extern "C" void GLX_Renderer_EndGpuPassTimer( int pass )
{
	glx::g_module.EndGpuPassTimer( pass );
}

extern "C" void GLX_Renderer_FrameComplete( void )
{
	glx::g_module.FrameComplete();
}

extern "C" void GLX_Renderer_PrintCaps_f( void )
{
	glx::g_module.PrintCaps();
}

extern "C" void GLX_Renderer_PrintInfo_f( void )
{
	glx::g_module.PrintInfo();
}

extern "C" void GLX_Renderer_Profile_f( void )
{
	glx::g_module.ProfileCommand();
}

extern "C" void GLX_Renderer_Material_f( void )
{
	glx::g_module.PrintMaterial();
}

extern "C" void GLX_Renderer_PostProcess_f( void )
{
	glx::g_module.PrintPostProcess();
}

extern "C" void GLX_Renderer_StaticWorld_f( void )
{
	glx::g_module.PrintStaticWorld();
}

extern "C" void GLX_Renderer_StreamTest_f( void )
{
	glx::g_module.StreamTest();
}

extern "C" void GLX_Renderer_PrintFrameCounters( void )
{
	glx::g_module.PrintFrameCounters();
}

extern "C" qboolean GLX_Renderer_DrawElements( unsigned int mode, int count,
	unsigned int type, const void *indices, int legacyReason, int profilerPath )
{
	return glx::g_module.DrawElements( mode, count, type, indices, legacyReason, profilerPath );
}

extern "C" qboolean GLX_Renderer_DrawArrays( unsigned int mode, int first, int count,
	int legacyReason, int profilerPath )
{
	return glx::g_module.DrawArrays( mode, first, count, legacyReason, profilerPath );
}

extern "C" void GLX_Renderer_RecordDraw( int indexes, int path )
{
	glx::g_module.RecordDraw( indexes, path );
}

extern "C" void GLX_Renderer_RecordShaderBatch( const char *shaderName, int sort, int numPasses,
	int numVertexes, int numIndexes, int flags )
{
	glx::g_module.RecordShaderBatch( shaderName, sort, numPasses, numVertexes, numIndexes, flags );
}

extern "C" void GLX_Renderer_RecordMaterialStage( int path, int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	unsigned int texModTypes0, unsigned int texModTypes1,
	unsigned int texModSequence0, unsigned int texModSequence1,
	int rgbWaveFunc, int alphaWaveFunc,
	unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1,
	int fogAdjust, int materialCombine, qboolean fogPass,
	int numVertexes, int numIndexes )
{
	glx::g_module.RecordMaterialStage( path, flags, stateBits, rgbGen, alphaGen,
		tcGen0, tcGen1, texMods0, texMods1, texModTypes0, texModTypes1,
		texModSequence0, texModSequence1, rgbWaveFunc, alphaWaveFunc,
		texModWaveFuncs0, texModWaveFuncs1, fogAdjust, materialCombine, fogPass,
		numVertexes, numIndexes );
}

extern "C" qboolean GLX_Renderer_MaterialRendererActive( void )
{
	return glx::g_module.MaterialRendererActive();
}

extern "C" qboolean GLX_Renderer_BindMaterialStage( int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	unsigned int texModTypes0, unsigned int texModTypes1,
	unsigned int texModSequence0, unsigned int texModSequence1,
	int rgbWaveFunc, int alphaWaveFunc,
	unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1, int fogAdjust,
	int materialCombine, qboolean fogPass )
{
	return glx::g_module.BindMaterialStage( flags, stateBits, rgbGen, alphaGen,
		tcGen0, tcGen1, texMods0, texMods1, texModTypes0, texModTypes1,
		texModSequence0, texModSequence1, rgbWaveFunc, alphaWaveFunc,
		texModWaveFuncs0, texModWaveFuncs1, fogAdjust,
		materialCombine, fogPass );
}

extern "C" qboolean GLX_Renderer_BindFogMaterial( void )
{
	return glx::g_module.BindFogMaterial();
}

extern "C" void GLX_Renderer_UnbindMaterial( void )
{
	glx::g_module.UnbindMaterial();
}

extern "C" qboolean GLX_Renderer_StreamDrawEnabled( void )
{
	return glx::g_module.StreamDrawEnabled();
}

extern "C" qboolean GLX_Renderer_StreamDrawMultitextureEnabled( void )
{
	return glx::g_module.StreamDrawMultitextureEnabled();
}

extern "C" qboolean GLX_Renderer_StreamDrawFogEnabled( void )
{
	return glx::g_module.StreamDrawFogEnabled();
}

extern "C" qboolean GLX_Renderer_StreamDrawDepthFragmentEnabled( void )
{
	return glx::g_module.StreamDrawDepthFragmentEnabled();
}

extern "C" qboolean GLX_Renderer_StreamDrawShadowsEnabled( void )
{
	return glx::g_module.StreamDrawShadowsEnabled();
}

extern "C" qboolean GLX_Renderer_StreamDrawBeamsEnabled( void )
{
	return glx::g_module.StreamDrawBeamsEnabled();
}

extern "C" qboolean GLX_Renderer_StreamDrawPostProcessEnabled( void )
{
	return glx::g_module.StreamDrawPostProcessEnabled();
}

extern "C" qboolean GLX_Renderer_StreamDrawAllowsMaterial( int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	unsigned int texModTypes0, unsigned int texModTypes1,
	unsigned int texModSequence0, unsigned int texModSequence1,
	int rgbWaveFunc, int alphaWaveFunc,
	unsigned int texModWaveFuncs0, unsigned int texModWaveFuncs1,
	int fogAdjust, int materialCombine, qboolean fogPass )
{
	return glx::g_module.StreamDrawAllowsMaterial( flags, stateBits, rgbGen, alphaGen,
		tcGen0, tcGen1, texMods0, texMods1, texModTypes0, texModTypes1,
		texModSequence0, texModSequence1, rgbWaveFunc, alphaWaveFunc,
		texModWaveFuncs0, texModWaveFuncs1, fogAdjust, materialCombine, fogPass );
}

extern "C" qboolean GLX_Renderer_StreamReserve( int bytes, int alignment, glxStreamReservation_t *reservation )
{
	return glx::g_module.StreamReserve( bytes, alignment, reservation );
}

extern "C" qboolean GLX_Renderer_StreamUploadAt( glxStreamReservation_t *reservation, int relativeOffset,
	const void *data, int bytes )
{
	return glx::g_module.StreamUploadAt( reservation, relativeOffset, data, bytes );
}

extern "C" void GLX_Renderer_StreamCommit( glxStreamReservation_t *reservation )
{
	glx::g_module.StreamCommit( reservation );
}

extern "C" unsigned int GLX_Renderer_BindStreamArrayBuffer( unsigned int buffer )
{
	return glx::g_module.BindStreamArrayBuffer( static_cast<GLuint>( buffer ) );
}

extern "C" void GLX_Renderer_RestoreStreamArrayBuffer( unsigned int buffer )
{
	glx::g_module.RestoreStreamArrayBuffer( static_cast<GLuint>( buffer ) );
}

extern "C" unsigned int GLX_Renderer_BindStreamElementArrayBuffer( unsigned int buffer )
{
	return glx::g_module.BindStreamElementArrayBuffer( static_cast<GLuint>( buffer ) );
}

extern "C" void GLX_Renderer_RestoreStreamElementArrayBuffer( unsigned int buffer )
{
	glx::g_module.RestoreStreamElementArrayBuffer( static_cast<GLuint>( buffer ) );
}

extern "C" void GLX_Renderer_RecordStreamBufferBind( unsigned int target, unsigned int buffer )
{
	glx::g_module.RecordStreamBufferBind( target, static_cast<GLuint>( buffer ) );
}

extern "C" void GLX_Renderer_RecordStreamDrawResult( int numVertexes, int numIndexes,
	int totalBytes, int indexBytes, int texcoord1Bytes, qboolean multitexture, qboolean fog,
	qboolean depthFragment, int materialFlags, unsigned int categoryMask, qboolean success )
{
	glx::g_module.RecordStreamDrawResult( numVertexes, numIndexes, totalBytes, indexBytes,
		texcoord1Bytes, multitexture, fog, depthFragment, materialFlags, categoryMask, success );
}

extern "C" void GLX_Renderer_RecordStreamDrawSkip( int reason )
{
	glx::g_module.RecordStreamDrawSkip( reason );
}

extern "C" void GLX_Renderer_ResetImageColorAudit( void )
{
	glx::g_module.ResetImageColorAudit();
}

extern "C" void GLX_Renderer_RecordImageColorAudit( int colorSpace, qboolean srgbDecode )
{
	glx::g_module.RecordImageColorAudit( colorSpace, srgbDecode );
}

extern "C" void GLX_Renderer_RecordFboInit( qboolean requested, qboolean ready,
	qboolean programReady, qboolean framebufferFnsReady, int vidWidth, int vidHeight,
	int captureWidth, int captureHeight, int windowWidth, int windowHeight,
	int internalFormat, int textureFormat, int textureType, qboolean multiSampled,
	qboolean superSampled, qboolean windowAdjusted, int blitFilter, int hdrMode,
	int renderScaleMode, int bloomMode, qboolean textureSrgbAvailable,
	qboolean framebufferSrgbAvailable, qboolean framebufferSrgbEnabled )
{
	glx::g_module.RecordFboInit( requested, ready, programReady, framebufferFnsReady,
		vidWidth, vidHeight, captureWidth, captureHeight, windowWidth, windowHeight,
		internalFormat, textureFormat, textureType, multiSampled, superSampled,
		windowAdjusted, blitFilter, hdrMode, renderScaleMode, bloomMode,
		textureSrgbAvailable, framebufferSrgbAvailable, framebufferSrgbEnabled );
}

extern "C" void GLX_Renderer_RecordFboShutdown( void )
{
	glx::g_module.RecordFboShutdown();
}

extern "C" void GLX_Renderer_RecordPostProcessFrame( qboolean minimized, qboolean bloomAvailable,
	qboolean programReady, int screenshotMask, qboolean windowAdjusted, int fboReadIndex,
	int hdrMode, int renderScaleMode, float greyscale )
{
	glx::g_module.RecordPostProcessFrame( minimized, bloomAvailable, programReady,
		screenshotMask, windowAdjusted, fboReadIndex, hdrMode, renderScaleMode, greyscale );
}

extern "C" qboolean GLX_Renderer_AutoExposureNeedsSamples( int *width, int *height )
{
	return glx::g_module.AutoExposureNeedsSamples( width, height );
}

extern "C" float GLX_Renderer_UpdateAutoExposure( float manualExposure,
	const float *rgba, int width, int height )
{
	return glx::g_module.UpdateAutoExposure( manualExposure, rgba, width, height );
}

extern "C" qboolean GLX_Renderer_TryBindPostShaderDirectFinal( void )
{
	return glx::g_module.TryBindPostShaderDirectFinal();
}

extern "C" qboolean GLX_Renderer_TryBindPostShaderFinal( qboolean bloomComposite,
	qboolean outputTransform, float bloomIntensity )
{
	return glx::g_module.TryBindPostShaderFinal( bloomComposite, outputTransform,
		bloomIntensity );
}

extern "C" void GLX_Renderer_UnbindPostShader( void )
{
	glx::g_module.UnbindPostShader();
}

extern "C" void GLX_Renderer_RecordPostProcessResult( int result )
{
	glx::g_module.RecordPostProcessResult( result );
}

extern "C" void GLX_Renderer_RecordColorGradeLut( qboolean active, int size, float scale )
{
	glx::g_module.RecordColorGradeLut( active, size, scale );
}

extern "C" void GLX_Renderer_RecordBloomCreate( int result, int requestedPasses,
	int effectivePasses, int textureUnits, int formatMode, int internalFormat,
	int textureFormat, int textureType )
{
	glx::g_module.RecordBloomCreate( result, requestedPasses, effectivePasses,
		textureUnits, formatMode, internalFormat, textureFormat, textureType );
}

extern "C" void GLX_Renderer_RecordBloom( int result, qboolean finalStage, int bloomMode,
	int requestedPasses, int effectivePasses, int blendBase, int filterSize,
	int textureUnits, int thresholdMode, int modulate, float threshold, float intensity,
	float reflection )
{
	glx::g_module.RecordBloom( result, finalStage, bloomMode, requestedPasses,
		effectivePasses, blendBase, filterSize, textureUnits, thresholdMode,
		modulate, threshold, intensity, reflection );
}

extern "C" void GLX_Renderer_RecordFboCopyScreen( int viewportWidth, int viewportHeight )
{
	glx::g_module.RecordFboCopyScreen( viewportWidth, viewportHeight );
}

extern "C" void GLX_Renderer_RecordFboBlit( int kind, qboolean depthOnly,
	int srcWidth, int srcHeight, int dstWidth, int dstHeight )
{
	glx::g_module.RecordFboBlit( kind, depthOnly, srcWidth, srcHeight, dstWidth, dstHeight );
}

extern "C" void GLX_Renderer_RecordFboBind( void )
{
	glx::g_module.RecordFboBind();
}

extern "C" void GLX_Renderer_RecordPostClear( void )
{
	glx::g_module.RecordPostClear();
}

extern "C" void GLX_Renderer_RecordFullscreenPass( void )
{
	glx::g_module.RecordFullscreenPass();
}

extern "C" void GLX_Renderer_PushShaderDebugGroup( const char *shaderName, int numVertexes, int numIndexes, int numPasses )
{
	glx::g_module.PushShaderDebugGroup( shaderName, numVertexes, numIndexes, numPasses );
}

extern "C" void GLX_Renderer_PopDebugGroup( void )
{
	glx::g_module.PopDebugGroup();
}

extern "C" void GLX_Renderer_ShadowUploadTess( int numVertexes, int numIndexes,
	const void *xyz, int xyzBytes, const void *indexes, int indexBytes )
{
	glx::g_module.ShadowUploadTess( numVertexes, numIndexes, xyz, xyzBytes, indexes, indexBytes );
}

extern "C" void GLX_Renderer_RecordStaticWorldCache( int surfaces, int vertexes, int indexes, int vertexBytes, int indexBytes )
{
	glx::g_module.RecordStaticWorldCache( surfaces, vertexes, indexes, vertexBytes, indexBytes );
}

extern "C" void GLX_Renderer_RecordStaticWorldBatches( int batches, int largestBatchSurfaces,
	int faceSurfaces, int gridSurfaces, int triangleSurfaces, int shaderStagePasses, int maxShaderStages )
{
	glx::g_module.RecordStaticWorldBatches( batches, largestBatchSurfaces, faceSurfaces,
		gridSurfaces, triangleSurfaces, shaderStagePasses, maxShaderStages );
}

extern "C" void GLX_Renderer_RecordStaticWorldPacket( const char *shaderName, int sort,
	int surfaces, int vertexes, int indexes, int firstItem, int itemCount, int vertexOffset, int vertexBytes,
	int indexOffset, int indexBytes, int shaderStagePasses, int flags )
{
	glx::g_module.RecordStaticWorldPacket( shaderName, sort, surfaces, vertexes, indexes,
		firstItem, itemCount, vertexOffset, vertexBytes, indexOffset, indexBytes, shaderStagePasses, flags );
}

extern "C" void GLX_Renderer_UploadStaticWorldArena( const void *vertexData, int vertexBytes,
	const void *indexData, int indexBytes )
{
	glx::g_module.UploadStaticWorldArena( vertexData, vertexBytes, indexData, indexBytes );
}

extern "C" unsigned int GLX_Renderer_StaticWorldArenaVertexBuffer( void )
{
	return glx::g_module.StaticWorldArenaVertexBuffer();
}

extern "C" unsigned int GLX_Renderer_StaticWorldArenaIndexBuffer( void )
{
	return glx::g_module.StaticWorldArenaIndexBuffer();
}

extern "C" qboolean GLX_Renderer_StaticWorldDrawDeviceRun( int indexes, int offsetBytes,
	int firstItem, int itemCount, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound )
{
	return glx::g_module.StaticWorldDrawDeviceRun( indexes, offsetBytes,
		firstItem, itemCount, indexType, indexBytes, shaderName, sort, arenaBound );
}

extern "C" qboolean GLX_Renderer_StaticWorldDrawDeviceRuns( int runCount, const int *counts,
	const void *const *offsets, const int *firstItems, const int *itemCounts,
	unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound )
{
	return glx::g_module.StaticWorldDrawDeviceRuns( runCount, counts, offsets, firstItems, itemCounts,
		indexType, indexBytes, shaderName, sort, arenaBound );
}

extern "C" qboolean GLX_Renderer_StaticWorldDrawSoftIndexes( int indexes, const void *indexData,
	unsigned int indexType, int indexBytes, const char *shaderName, int sort, qboolean arenaBound )
{
	return glx::g_module.StaticWorldDrawSoftIndexes( indexes, indexData,
		indexType, indexBytes, shaderName, sort, arenaBound );
}

extern "C" int GLX_Renderer_StaticWorldDrawDeviceRunsFiltered( int runCount, const int *counts,
	const void *const *offsets, const int *firstItems, const int *itemCounts,
	int *drawnRuns, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound )
{
	return glx::g_module.StaticWorldDrawDeviceRunsFiltered( runCount, counts, offsets,
		firstItems, itemCounts, drawnRuns, indexType, indexBytes, shaderName, sort, arenaBound );
}

extern "C" void GLX_Renderer_RecordStaticWorldQueue( int queuedItems, int queuedVertexes, int queuedIndexes,
	int deviceRuns, int deviceIndexes, int softIndexes, int largestDeviceRunIndexes )
{
	glx::g_module.RecordStaticWorldQueue( queuedItems, queuedVertexes, queuedIndexes,
		deviceRuns, deviceIndexes, softIndexes, largestDeviceRunIndexes );
}

extern "C" void GLX_Renderer_RecordStaticWorldDeviceRuns( int runCount, const int *counts,
	const void *const *offsets, const int *firstItems, const int *itemCounts,
	int indexBytes, const char *shaderName, int sort )
{
	glx::g_module.RecordStaticWorldDeviceRuns( runCount, counts, offsets,
		firstItems, itemCounts, indexBytes, shaderName, sort );
}
