#include "glx_local.h"
#include "glx_caps.h"
#include "glx_debug.h"
#include "glx_material.h"
#include "glx_postprocess.h"
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

class RendererModule {
public:
	void RegisterCommands();
	void RemoveCommands();
	void OnOpenGLReady( const glconfig_t *config, const char *extensions );
	void Shutdown( refShutdownCode_t code );
	void BeginBackendTimer();
	void EndBackendTimer();
	void FrameComplete();
	void PrintCaps() const;
	void PrintInfo() const;
	void PrintMaterial() const;
	void PrintPostProcess() const;
	void PrintStaticWorld() const;
	void PrintFrameCounters() const;
	void StreamTest();
	void RecordDraw( int indexes, int path );
	void RecordShaderBatch( const char *shaderName, int sort, int numPasses, int numVertexes, int numIndexes, int flags );
	void RecordMaterialStage( int path, int flags, unsigned int stateBits, int rgbGen, int alphaGen,
		int tcGen0, int tcGen1, int texMods0, int texMods1, int numVertexes, int numIndexes );
	qboolean MaterialRendererActive() const;
	qboolean BindMaterialStage( int flags, unsigned int stateBits, int rgbGen, int alphaGen,
		int tcGen0, int tcGen1, int texMods0, int texMods1, int multitextureEnv, qboolean fogPass );
	qboolean BindFogMaterial();
	void UnbindMaterial();
	qboolean StreamDrawEnabled() const;
	qboolean StreamDrawMultitextureEnabled() const;
	qboolean StreamDrawFogEnabled() const;
	qboolean StreamDrawDepthFragmentEnabled() const;
	qboolean StreamDrawAllowsMaterial( int flags, unsigned int stateBits, int rgbGen, int alphaGen, int tcGen0, int texMods0 );
	qboolean StreamReserve( int bytes, int alignment, glxStreamReservation_t *reservation );
	qboolean StreamUploadAt( glxStreamReservation_t *reservation, int relativeOffset, const void *data, int bytes );
	void StreamCommit( glxStreamReservation_t *reservation );
	void RecordStreamDrawResult( int numVertexes, int numIndexes, int totalBytes, int indexBytes,
		int texcoord1Bytes, qboolean multitexture, qboolean fog, qboolean depthFragment, qboolean success );
	void RecordStreamDrawSkip( int reason );
	void RecordFboInit( qboolean requested, qboolean ready, qboolean programReady, qboolean framebufferFnsReady,
		int vidWidth, int vidHeight, int captureWidth, int captureHeight, int windowWidth, int windowHeight,
		int internalFormat, int textureFormat, int textureType, qboolean multiSampled, qboolean superSampled,
		qboolean windowAdjusted, int blitFilter, int hdrMode, int renderScaleMode, int bloomMode );
	void RecordFboShutdown();
	void RecordPostProcessFrame( qboolean minimized, qboolean bloomAvailable, qboolean programReady,
		int screenshotMask, qboolean windowAdjusted, int fboReadIndex, int hdrMode, int renderScaleMode,
		float greyscale );
	void RecordPostProcessResult( int result );
	void RecordBloomCreate( int result, int requestedPasses, int effectivePasses, int textureUnits );
	void RecordBloom( int result, qboolean finalStage, int bloomMode, int requestedPasses,
		int effectivePasses, int blendBase, int filterSize, int textureUnits, int thresholdMode,
		int modulate, float threshold, float intensity, float reflection );
	void RecordFboCopyScreen( int viewportWidth, int viewportHeight );
	void RecordFboBlit( int kind, qboolean depthOnly, int srcWidth, int srcHeight, int dstWidth, int dstHeight );
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
	Capabilities caps_ {};
	DebugState debug_ {};
	MaterialState material_ {};
	PostProcessState postprocess_ {};
	ProfilerState profiler_ {};
	StaticWorldStats staticWorld_ {};
	StreamState stream_ {};
};

RendererModule g_module;

void RendererModule::RegisterCommands()
{
	RI().Cmd_AddCommand( "glxinfo", GLX_Renderer_PrintInfo_f );
	RI().Cmd_AddCommand( "glxcaps", GLX_Renderer_PrintCaps_f );
	RI().Cmd_AddCommand( "glxmaterial", GLX_Renderer_Material_f );
	RI().Cmd_AddCommand( "glxpostprocess", GLX_Renderer_PostProcess_f );
	RI().Cmd_AddCommand( "glxstaticworld", GLX_Renderer_StaticWorld_f );
	RI().Cmd_AddCommand( "glxstreamtest", GLX_Renderer_StreamTest_f );

	GLX_Debug_RegisterCvars( &debug_ );
	GLX_Material_RegisterCvars( &material_ );
	GLX_PostProcess_RegisterCvars( &postprocess_ );
	GLX_Profiler_RegisterCvars( &profiler_ );
	GLX_StaticWorld_RegisterCvars( &staticWorld_ );
	GLX_Stream_RegisterCvars( &stream_ );
}

void RendererModule::RemoveCommands()
{
	RI().Cmd_RemoveCommand( "glxcaps" );
	RI().Cmd_RemoveCommand( "glxinfo" );
	RI().Cmd_RemoveCommand( "glxmaterial" );
	RI().Cmd_RemoveCommand( "glxpostprocess" );
	RI().Cmd_RemoveCommand( "glxstaticworld" );
	RI().Cmd_RemoveCommand( "glxstreamtest" );
}

void RendererModule::OnOpenGLReady( const glconfig_t *config, const char *extensions )
{
	GLX_Caps_Init( &caps_, config, extensions );
	GLX_Debug_OnOpenGLReady( &debug_, caps_ );
	GLX_Material_OnOpenGLReady( &material_, caps_ );
	GLX_PostProcess_OnOpenGLReady( &postprocess_, caps_ );
	GLX_Stream_OnOpenGLReady( &stream_, caps_ );
	GLX_StaticWorld_SetCapabilities( &staticWorld_, caps_.features.drawIndirect, caps_.features.multiDrawIndirect );
	GLX_Debug_LabelObject( debug_, GL_BUFFER, stream_.buffer, "GLx dynamic stream ring" );
	GLX_Profiler_OnOpenGLReady( &profiler_, caps_ );

	RI().Printf( PRINT_ALL, "GLx renderer bootstrap: tier %s, GL %i.%i, material %s, stream %s, timer query %s, KHR_debug %s\n",
		GLX_Caps_TierName( caps_.tier ), caps_.major, caps_.minor,
		BoolName( GLX_Material_Active( material_ ) ),
		GLX_Stream_StrategyName( stream_.strategy ),
		BoolName( GLX_Profiler_TimerReady( profiler_ ) ),
		BoolName( GLX_Debug_CallbackInstalled( debug_ ) ) );
}

void RendererModule::Shutdown( refShutdownCode_t code )
{
	(void)code;

	GLX_Material_Shutdown( &material_, qtrue );
	GLX_PostProcess_Shutdown( &postprocess_ );
	GLX_Profiler_Shutdown( &profiler_ );
	GLX_Debug_Shutdown( &debug_ );
	GLX_Stream_Shutdown( &stream_ );
	GLX_StaticWorld_Clear( &staticWorld_ );
	GLX_Caps_Reset( &caps_ );
}

void RendererModule::BeginBackendTimer()
{
	GLX_Profiler_BeginBackendTimer( &profiler_ );
}

void RendererModule::EndBackendTimer()
{
	GLX_Profiler_EndBackendTimer( &profiler_ );
}

void RendererModule::FrameComplete()
{
	GLX_Profiler_FrameComplete( &profiler_ );
	GLX_Material_FrameComplete( &material_ );
	GLX_Stream_FrameComplete( &stream_ );
}

void RendererModule::PrintCaps() const
{
	if ( !caps_.config ) {
		RI().Printf( PRINT_ALL, "GLx renderer bootstrap is loaded, but OpenGL is not initialized yet.\n" );
		return;
	}

	RI().Printf( PRINT_ALL, "\nGLx renderer bootstrap\n" );
	RI().Printf( PRINT_ALL, "  GL vendor: %s\n", caps_.config->vendor_string );
	RI().Printf( PRINT_ALL, "  GL renderer: %s\n", caps_.config->renderer_string );
	RI().Printf( PRINT_ALL, "  GL version: %s\n", caps_.config->version_string );
	RI().Printf( PRINT_ALL, "  capability tier: %s\n", GLX_Caps_TierName( caps_.tier ) );
	RI().Printf( PRINT_ALL, "  map buffer range: %s\n", BoolName( caps_.features.mapBufferRange ) );
	RI().Printf( PRINT_ALL, "  uniform buffers: %s\n", BoolName( caps_.features.uniformBufferObject ) );
	RI().Printf( PRINT_ALL, "  instanced arrays: %s\n", BoolName( caps_.features.instancedArrays ) );
	RI().Printf( PRINT_ALL, "  persistent buffers: %s\n", BoolName( caps_.features.bufferStorage ) );
	RI().Printf( PRINT_ALL, "  sync objects: %s\n", BoolName( caps_.features.syncObjects ) );
	RI().Printf( PRINT_ALL, "  draw indirect: %s\n", BoolName( caps_.features.drawIndirect ) );
	RI().Printf( PRINT_ALL, "  multi draw indirect: %s\n", BoolName( caps_.features.multiDrawIndirect ) );
	RI().Printf( PRINT_ALL, "  direct state access: %s\n", BoolName( caps_.features.directStateAccess ) );
	RI().Printf( PRINT_ALL, "  timer query feature: %s\n", BoolName( caps_.features.timerQuery ) );
	RI().Printf( PRINT_ALL, "  timer query active: %s\n", BoolName( GLX_Profiler_TimerReady( profiler_ ) ) );
	RI().Printf( PRINT_ALL, "  KHR_debug callback: %s\n", BoolName( GLX_Debug_CallbackInstalled( debug_ ) ) );
	RI().Printf( PRINT_ALL, "  KHR_debug groups: %s\n",
		BoolName( debug_.r_glxDebugGroups && debug_.r_glxDebugGroups->integer ? qtrue : qfalse ) );
	RI().Printf( PRINT_ALL, "  material renderer: %s, ready %s, GLSL %s, programs %i\n",
		material_.r_glxMaterialRenderer && material_.r_glxMaterialRenderer->integer ? "enabled" : "disabled",
		BoolName( material_.ready ),
		material_.glslVersion[0] ? material_.glslVersion : "unknown",
		material_.programCount );
	RI().Printf( PRINT_ALL, "  postprocess FBO: %s, render %ix%i, capture %ix%i, bloom %i, passes %i/%i, last %s\n",
		BoolName( postprocess_.fboReady ), postprocess_.vidWidth, postprocess_.vidHeight,
		postprocess_.captureWidth, postprocess_.captureHeight, postprocess_.bloomMode,
		postprocess_.lastBloomEffectivePasses, postprocess_.lastBloomRequestedPasses,
		GLX_PostProcess_ResultName( postprocess_.lastResult ) );
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
	RI().Printf( PRINT_ALL, "  dynamic stream draws: %u/%u attempts, %.2f MB, index %.2f MB, tex1 %.2f MB, mt %u, fog %u, depthfrag %u\n",
		stream_.streamedDraws, stream_.streamedDrawAttempts,
		static_cast<double>( stream_.streamedDrawBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( stream_.streamedDrawIndexBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( stream_.streamedDrawTexcoord1Bytes ) / ( 1024.0 * 1024.0 ),
		stream_.streamedDrawMultitextureDraws,
		stream_.streamedDrawFogDraws,
		stream_.streamedDrawDepthFragmentDraws );
	RI().Printf( PRINT_ALL, "  dynamic stream draw material keys: accepted %u, rejected %u\n",
		stream_.streamedDrawMaterialAccepted, stream_.streamedDrawMaterialRejected );
}

void RendererModule::PrintInfo() const
{
	PrintCaps();
	GLX_Material_PrintInfo( material_ );
	GLX_PostProcess_PrintInfo( postprocess_ );
	GLX_Profiler_PrintInfo( profiler_ );
	GLX_StaticWorld_PrintInfo( staticWorld_ );
	GLX_Stream_PrintInfo( stream_ );
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
	RI().Printf( PRINT_ALL, "glx: material stages %u generic/%u vbo/%u mt/%u blend/%u texmod/%u env/%u\n",
		profiler_.materialStages,
		profiler_.genericMaterialStages,
		profiler_.vboMaterialStages,
		profiler_.multitextureMaterialStages,
		profiler_.blendMaterialStages,
		profiler_.texmodMaterialStages,
		profiler_.environmentMaterialStages );
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
	RI().Printf( PRINT_ALL, "glx: stream draws %u/%u attempts, %u idx, %.2fMB/index %.2fMB/tex1 %.2fMB, mt %u, fog %u, depthfrag %u, fallbacks %u, skips %u\n",
		stream_.streamedDraws,
		stream_.streamedDrawAttempts,
		stream_.streamedDrawIndexes,
		static_cast<double>( stream_.streamedDrawBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( stream_.streamedDrawIndexBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( stream_.streamedDrawTexcoord1Bytes ) / ( 1024.0 * 1024.0 ),
		stream_.streamedDrawMultitextureDraws,
		stream_.streamedDrawFogDraws,
		stream_.streamedDrawDepthFragmentDraws,
		stream_.streamedDrawFallbacks,
		stream_.streamedDrawSkips );
	RI().Printf( PRINT_ALL, "glx: stream reservation last %u bytes at %u using %s, largest %u bytes, same-frame wrap rejects %u\n",
		stream_.lastReservationBytes,
		stream_.lastReservationOffset,
		GLX_Stream_StrategyName( stream_.lastReservationStrategy ),
		stream_.largestReservationBytes,
		stream_.sameFrameWrapRejects );
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

void RendererModule::RecordDraw( int indexes, int path )
{
	GLX_Profiler_RecordDraw( &profiler_, indexes, path );
}

void RendererModule::RecordShaderBatch( const char *shaderName, int sort, int numPasses, int numVertexes, int numIndexes, int flags )
{
	GLX_Profiler_RecordShaderBatch( &profiler_, shaderName, sort, numPasses, numVertexes, numIndexes, flags );
}

void RendererModule::RecordMaterialStage( int path, int flags, unsigned int stateBits, int rgbGen, int alphaGen,
	int tcGen0, int tcGen1, int texMods0, int texMods1, int numVertexes, int numIndexes )
{
	GLX_Profiler_RecordMaterialStage( &profiler_, path, flags, stateBits, rgbGen, alphaGen,
		tcGen0, tcGen1, texMods0, texMods1, numVertexes, numIndexes );
}

qboolean RendererModule::MaterialRendererActive() const
{
	return GLX_Material_Active( material_ );
}

qboolean RendererModule::BindMaterialStage( int flags, unsigned int stateBits, int rgbGen, int alphaGen,
	int tcGen0, int tcGen1, int texMods0, int texMods1, int multitextureEnv, qboolean fogPass )
{
	MaterialRequest request {};

	request.flags = flags;
	request.stateBits = stateBits;
	request.rgbGen = rgbGen;
	request.alphaGen = alphaGen;
	request.tcGen0 = tcGen0;
	request.tcGen1 = tcGen1;
	request.texMods0 = texMods0;
	request.texMods1 = texMods1;
	request.multitextureEnv = multitextureEnv;
	request.fogPass = fogPass;

	return GLX_Material_BindStage( &material_, request );
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

qboolean RendererModule::StreamDrawAllowsMaterial( int flags, unsigned int stateBits, int rgbGen, int alphaGen, int tcGen0, int texMods0 )
{
	return GLX_Stream_DrawAllowsMaterial( &stream_, flags, stateBits, rgbGen, alphaGen, tcGen0, texMods0 );
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

void RendererModule::RecordStreamDrawResult( int numVertexes, int numIndexes, int totalBytes, int indexBytes,
	int texcoord1Bytes, qboolean multitexture, qboolean fog, qboolean depthFragment, qboolean success )
{
	GLX_Stream_RecordDrawResult( &stream_, numVertexes, numIndexes, totalBytes, indexBytes,
		texcoord1Bytes, multitexture, fog, depthFragment, success );
}

void RendererModule::RecordStreamDrawSkip( int reason )
{
	GLX_Stream_RecordDrawSkip( &stream_, reason );
}

void RendererModule::RecordFboInit( qboolean requested, qboolean ready, qboolean programReady, qboolean framebufferFnsReady,
	int vidWidth, int vidHeight, int captureWidth, int captureHeight, int windowWidth, int windowHeight,
	int internalFormat, int textureFormat, int textureType, qboolean multiSampled, qboolean superSampled,
	qboolean windowAdjusted, int blitFilter, int hdrMode, int renderScaleMode, int bloomMode )
{
	GLX_PostProcess_RecordFboInit( &postprocess_, requested, ready, programReady, framebufferFnsReady,
		vidWidth, vidHeight, captureWidth, captureHeight, windowWidth, windowHeight,
		internalFormat, textureFormat, textureType, multiSampled, superSampled,
		windowAdjusted, blitFilter, hdrMode, renderScaleMode, bloomMode );
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
}

void RendererModule::RecordPostProcessResult( int result )
{
	GLX_PostProcess_RecordFrameResult( &postprocess_, result );
}

void RendererModule::RecordBloomCreate( int result, int requestedPasses, int effectivePasses, int textureUnits )
{
	GLX_PostProcess_RecordBloomCreate( &postprocess_, result, requestedPasses, effectivePasses, textureUnits );
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
	GLX_StaticWorld_RecordPacket( &staticWorld_, shaderName, sort,
		surfaces, vertexes, indexes, firstItem, itemCount, vertexOffset, vertexBytes,
		indexOffset, indexBytes, shaderStagePasses, flags );
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

extern "C" void GLX_Renderer_Shutdown( refShutdownCode_t code )
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
	int numVertexes, int numIndexes )
{
	glx::g_module.RecordMaterialStage( path, flags, stateBits, rgbGen, alphaGen,
		tcGen0, tcGen1, texMods0, texMods1, numVertexes, numIndexes );
}

extern "C" qboolean GLX_Renderer_MaterialRendererActive( void )
{
	return glx::g_module.MaterialRendererActive();
}

extern "C" qboolean GLX_Renderer_BindMaterialStage( int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	int multitextureEnv, qboolean fogPass )
{
	return glx::g_module.BindMaterialStage( flags, stateBits, rgbGen, alphaGen,
		tcGen0, tcGen1, texMods0, texMods1, multitextureEnv, fogPass );
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

extern "C" qboolean GLX_Renderer_StreamDrawAllowsMaterial( int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int texMods0 )
{
	return glx::g_module.StreamDrawAllowsMaterial( flags, stateBits, rgbGen, alphaGen, tcGen0, texMods0 );
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

extern "C" void GLX_Renderer_RecordStreamDrawResult( int numVertexes, int numIndexes,
	int totalBytes, int indexBytes, int texcoord1Bytes, qboolean multitexture, qboolean fog,
	qboolean depthFragment, qboolean success )
{
	glx::g_module.RecordStreamDrawResult( numVertexes, numIndexes, totalBytes, indexBytes,
		texcoord1Bytes, multitexture, fog, depthFragment, success );
}

extern "C" void GLX_Renderer_RecordStreamDrawSkip( int reason )
{
	glx::g_module.RecordStreamDrawSkip( reason );
}

extern "C" void GLX_Renderer_RecordFboInit( qboolean requested, qboolean ready,
	qboolean programReady, qboolean framebufferFnsReady, int vidWidth, int vidHeight,
	int captureWidth, int captureHeight, int windowWidth, int windowHeight,
	int internalFormat, int textureFormat, int textureType, qboolean multiSampled,
	qboolean superSampled, qboolean windowAdjusted, int blitFilter, int hdrMode,
	int renderScaleMode, int bloomMode )
{
	glx::g_module.RecordFboInit( requested, ready, programReady, framebufferFnsReady,
		vidWidth, vidHeight, captureWidth, captureHeight, windowWidth, windowHeight,
		internalFormat, textureFormat, textureType, multiSampled, superSampled,
		windowAdjusted, blitFilter, hdrMode, renderScaleMode, bloomMode );
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

extern "C" void GLX_Renderer_RecordPostProcessResult( int result )
{
	glx::g_module.RecordPostProcessResult( result );
}

extern "C" void GLX_Renderer_RecordBloomCreate( int result, int requestedPasses,
	int effectivePasses, int textureUnits )
{
	glx::g_module.RecordBloomCreate( result, requestedPasses, effectivePasses, textureUnits );
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
