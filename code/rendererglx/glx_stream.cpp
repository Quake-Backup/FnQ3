#include "glx_stream.h"
#include "glx_stream_logic.h"

#include <cstdio>
#include <cstring>

#ifndef GL_ARRAY_BUFFER
#define GL_ARRAY_BUFFER 0x8892
#endif
#ifndef GL_ARRAY_BUFFER_BINDING
#define GL_ARRAY_BUFFER_BINDING 0x8894
#endif
#ifndef GL_STREAM_DRAW
#define GL_STREAM_DRAW 0x88E0
#endif
#ifndef GL_MAP_WRITE_BIT
#define GL_MAP_WRITE_BIT 0x0002
#endif
#ifndef GL_MAP_INVALIDATE_BUFFER_BIT
#define GL_MAP_INVALIDATE_BUFFER_BIT 0x0008
#endif
#ifndef GL_MAP_INVALIDATE_RANGE_BIT
#define GL_MAP_INVALIDATE_RANGE_BIT 0x0004
#endif
#ifndef GL_MAP_FLUSH_EXPLICIT_BIT
#define GL_MAP_FLUSH_EXPLICIT_BIT 0x0010
#endif
#ifndef GL_MAP_UNSYNCHRONIZED_BIT
#define GL_MAP_UNSYNCHRONIZED_BIT 0x0020
#endif
#ifndef GL_MAP_PERSISTENT_BIT
#define GL_MAP_PERSISTENT_BIT 0x0040
#endif
#ifndef GL_MAP_COHERENT_BIT
#define GL_MAP_COHERENT_BIT 0x0080
#endif
#ifndef GL_DYNAMIC_STORAGE_BIT
#define GL_DYNAMIC_STORAGE_BIT 0x0100
#endif
#ifndef GL_NO_ERROR
#define GL_NO_ERROR 0
#endif
#ifndef GL_OUT_OF_MEMORY
#define GL_OUT_OF_MEMORY 0x0505
#endif
#ifndef GL_SYNC_GPU_COMMANDS_COMPLETE
#define GL_SYNC_GPU_COMMANDS_COMPLETE 0x9117
#endif
#ifndef GL_ALREADY_SIGNALED
#define GL_ALREADY_SIGNALED 0x911A
#endif
#ifndef GL_TIMEOUT_EXPIRED
#define GL_TIMEOUT_EXPIRED 0x911B
#endif
#ifndef GL_CONDITION_SATISFIED
#define GL_CONDITION_SATISFIED 0x911C
#endif
#ifndef GL_WAIT_FAILED
#define GL_WAIT_FAILED 0x911D
#endif
#ifndef GL_SYNC_FLUSH_COMMANDS_BIT
#define GL_SYNC_FLUSH_COMMANDS_BIT 0x00000001
#endif

namespace glx {

typedef void ( APIENTRY *PFNGLXGENBUFFERSPROC )( GLsizei n, GLuint *buffers );
typedef void ( APIENTRY *PFNGLXDELETEBUFFERSPROC )( GLsizei n, const GLuint *buffers );
typedef void ( APIENTRY *PFNGLXBINDBUFFERPROC )( GLenum target, GLuint buffer );
typedef void ( APIENTRY *PFNGLXBUFFERDATAPROC )( GLenum target, ptrdiff_t size, const void *data, GLenum usage );
typedef void ( APIENTRY *PFNGLXBUFFERSUBDATAPROC )( GLenum target, ptrdiff_t offset, ptrdiff_t size, const void *data );
typedef void ( APIENTRY *PFNGLXBUFFERSTORAGEPROC )( GLenum target, ptrdiff_t size, const void *data, GLbitfield flags );
typedef void *( APIENTRY *PFNGLXMAPBUFFERRANGEPROC )( GLenum target, ptrdiff_t offset, ptrdiff_t length, GLbitfield access );
typedef GLboolean ( APIENTRY *PFNGLXUNMAPBUFFERPROC )( GLenum target );
typedef void ( APIENTRY *PFNGLXGETINTEGERVPROC )( GLenum pname, GLint *params );
typedef GLenum ( APIENTRY *PFNGLXGETERRORPROC )( void );
typedef void *( APIENTRY *PFNGLXFENCESYNCPROC )( GLenum condition, GLbitfield flags );
typedef GLenum ( APIENTRY *PFNGLXCLIENTWAITSYNCPROC )( void *sync, GLbitfield flags, unsigned long long timeout );
typedef void ( APIENTRY *PFNGLXDELETESYNCPROC )( void *sync );

struct StreamFns {
	PFNGLXGENBUFFERSPROC GenBuffers;
	PFNGLXDELETEBUFFERSPROC DeleteBuffers;
	PFNGLXBINDBUFFERPROC BindBuffer;
	PFNGLXBUFFERDATAPROC BufferData;
	PFNGLXBUFFERSUBDATAPROC BufferSubData;
	PFNGLXBUFFERSTORAGEPROC BufferStorage;
	PFNGLXMAPBUFFERRANGEPROC MapBufferRange;
	PFNGLXUNMAPBUFFERPROC UnmapBuffer;
	PFNGLXGETINTEGERVPROC GetIntegerv;
	PFNGLXGETERRORPROC GetError;
	PFNGLXFENCESYNCPROC FenceSync;
	PFNGLXCLIENTWAITSYNCPROC ClientWaitSync;
	PFNGLXDELETESYNCPROC DeleteSync;
};

static StreamFns s_fns {};

static void *GLX_Stream_GetProc( const char *name, const char *fallbackName = nullptr )
{
	void *proc = RI().GL_GetProcAddress ? RI().GL_GetProcAddress( name ) : nullptr;

	if ( !proc && fallbackName ) {
		proc = RI().GL_GetProcAddress( fallbackName );
	}

	return proc;
}

static size_t GLX_Stream_AlignOffset( size_t offset, size_t alignment )
{
	if ( alignment <= 1 ) {
		return offset;
	}

	const size_t remainder = offset % alignment;
	if ( remainder == 0 ) {
		return offset;
	}

	return offset + alignment - remainder;
}

static int GLX_Stream_DrawKeyMode( const StreamState &state )
{
	int mode = state.r_glxStreamDrawKeyMode ? state.r_glxStreamDrawKeyMode->integer : 0;

	if ( mode < 0 ) {
		mode = 0;
	}
	if ( mode > 2 ) {
		mode = 2;
	}

	return mode;
}

static const char *GLX_Stream_DrawKeyModeName( int mode )
{
	switch ( mode ) {
	case 0:
		return "plain";
	case 1:
		return "computed";
	case 2:
		return "all-eligible";
	default:
		return "unknown";
	}
}

static void GLX_Stream_SetReason( StreamState *state, const char *reason )
{
	std::snprintf( state->reason, sizeof( state->reason ), "%s", reason ? reason : "" );
}

static void GLX_Stream_ResetRuntime( StreamState *state )
{
	if ( !state ) {
		return;
	}

	state->ringBytes = 0;
	state->writeOffset = 0;
	state->mappedPtr = nullptr;
	state->frameSync = nullptr;
	state->buffer = 0;
	state->ready = qfalse;
	state->persistentMapped = qfalse;
	state->syncReady = qfalse;
	state->frameTouched = qfalse;
}

static void GLX_Stream_ResetCounters( StreamState *state )
{
	if ( !state ) {
		return;
	}

	state->fallbackCount = 0;
	state->allocationFailures = 0;
	state->mapFailures = 0;
	state->unmapFailures = 0;
	state->reserveFailures = 0;
	state->uploadFailures = 0;
	state->reservations = 0;
	state->commits = 0;
	state->uploadCalls = 0;
	state->wraps = 0;
	state->sameFrameWrapRejects = 0;
	state->orphans = 0;
	state->syncInsertions = 0;
	state->syncWaits = 0;
	state->syncTimeouts = 0;
	state->syncFailures = 0;
	state->syncFenceSkips = 0;
	state->selfTests = 0;
	state->shadowTessUploads = 0;
	state->shadowTessSkips = 0;
	state->shadowTessFailures = 0;
	state->streamedDrawAttempts = 0;
	state->streamedDraws = 0;
	state->streamedDrawFallbacks = 0;
	state->streamedDrawSkips = 0;
	std::memset( state->streamedDrawSkipReasons, 0, sizeof( state->streamedDrawSkipReasons ) );
	state->streamedDrawMaterialAccepted = 0;
	state->streamedDrawMaterialRejected = 0;
	state->streamedDrawMultitextureDraws = 0;
	state->streamedDrawFogDraws = 0;
	state->streamedDrawDepthFragmentDraws = 0;
	state->streamedDrawTexModDraws = 0;
	state->streamedDrawTexModAccepted = 0;
	state->streamedDrawTexModRejected = 0;
	state->streamedDrawEnvironmentDraws = 0;
	state->streamedDrawEnvironmentAccepted = 0;
	state->streamedDrawEnvironmentRejected = 0;
	state->streamedDrawDynamicLightDraws = 0;
	state->streamedDrawDynamicLightAccepted = 0;
	state->streamedDrawDynamicLightRejected = 0;
	state->streamedDrawScreenMapDraws = 0;
	state->streamedDrawScreenMapAccepted = 0;
	state->streamedDrawScreenMapRejected = 0;
	state->streamedDrawVideoMapDraws = 0;
	state->streamedDrawVideoMapAccepted = 0;
	state->streamedDrawVideoMapRejected = 0;
	state->streamedDrawShadowDraws = 0;
	state->streamedDrawBeamDraws = 0;
	state->streamedDrawPostProcessDraws = 0;
	state->streamedDrawVertexes = 0;
	state->streamedDrawIndexes = 0;
	state->largestReservationBytes = 0;
	state->lastReservationBytes = 0;
	state->lastReservationOffset = 0;
	state->lastReservationStrategy = StreamStrategy::OrphanSubData;
	state->uploadBytes = 0;
	state->shadowTessBytes = 0;
	state->streamedDrawBytes = 0;
	state->streamedDrawIndexBytes = 0;
	state->streamedDrawTexcoord1Bytes = 0;
	state->frames = 0;
}

static qboolean GLX_Stream_FunctionsReady()
{
	if ( !RI().GL_GetProcAddress ) {
		return qfalse;
	}

	s_fns.GenBuffers = reinterpret_cast<PFNGLXGENBUFFERSPROC>( GLX_Stream_GetProc( "glGenBuffers", "glGenBuffersARB" ) );
	s_fns.DeleteBuffers = reinterpret_cast<PFNGLXDELETEBUFFERSPROC>( GLX_Stream_GetProc( "glDeleteBuffers", "glDeleteBuffersARB" ) );
	s_fns.BindBuffer = reinterpret_cast<PFNGLXBINDBUFFERPROC>( GLX_Stream_GetProc( "glBindBuffer", "glBindBufferARB" ) );
	s_fns.BufferData = reinterpret_cast<PFNGLXBUFFERDATAPROC>( GLX_Stream_GetProc( "glBufferData", "glBufferDataARB" ) );
	s_fns.BufferSubData = reinterpret_cast<PFNGLXBUFFERSUBDATAPROC>( GLX_Stream_GetProc( "glBufferSubData", "glBufferSubDataARB" ) );
	s_fns.BufferStorage = reinterpret_cast<PFNGLXBUFFERSTORAGEPROC>( GLX_Stream_GetProc( "glBufferStorage" ) );
	s_fns.MapBufferRange = reinterpret_cast<PFNGLXMAPBUFFERRANGEPROC>( GLX_Stream_GetProc( "glMapBufferRange", "glMapBufferRangeEXT" ) );
	s_fns.UnmapBuffer = reinterpret_cast<PFNGLXUNMAPBUFFERPROC>( GLX_Stream_GetProc( "glUnmapBuffer", "glUnmapBufferARB" ) );
	s_fns.GetIntegerv = reinterpret_cast<PFNGLXGETINTEGERVPROC>( GLX_Stream_GetProc( "glGetIntegerv" ) );
	s_fns.GetError = reinterpret_cast<PFNGLXGETERRORPROC>( GLX_Stream_GetProc( "glGetError" ) );

	return s_fns.GenBuffers && s_fns.DeleteBuffers && s_fns.BindBuffer && s_fns.BufferData ? qtrue : qfalse;
}

static qboolean GLX_Stream_SyncFunctionsReady()
{
	if ( !RI().GL_GetProcAddress ) {
		return qfalse;
	}

	s_fns.FenceSync = reinterpret_cast<PFNGLXFENCESYNCPROC>( GLX_Stream_GetProc( "glFenceSync" ) );
	s_fns.ClientWaitSync = reinterpret_cast<PFNGLXCLIENTWAITSYNCPROC>( GLX_Stream_GetProc( "glClientWaitSync" ) );
	s_fns.DeleteSync = reinterpret_cast<PFNGLXDELETESYNCPROC>( GLX_Stream_GetProc( "glDeleteSync" ) );

	return s_fns.FenceSync && s_fns.ClientWaitSync && s_fns.DeleteSync ? qtrue : qfalse;
}

static void GLX_Stream_ClearGLErrors()
{
	if ( !s_fns.GetError ) {
		return;
	}

	for ( int i = 0; i < 8 && s_fns.GetError() != GL_NO_ERROR; i++ ) {
	}
}

static GLenum GLX_Stream_GetGLError()
{
	return s_fns.GetError ? s_fns.GetError() : GL_NO_ERROR;
}

static void GLX_Stream_DeleteFrameFence( StreamState *state )
{
	if ( !state || !state->frameSync ) {
		return;
	}

	if ( s_fns.DeleteSync ) {
		s_fns.DeleteSync( state->frameSync );
	}
	state->frameSync = nullptr;
}

static qboolean GLX_Stream_WaitFrameFence( StreamState *state )
{
	GLenum result;

	if ( !state || !state->frameSync ) {
		return qtrue;
	}

	if ( !state->syncReady || !s_fns.ClientWaitSync || !s_fns.DeleteSync ) {
		state->syncFailures++;
		return qfalse;
	}

	result = s_fns.ClientWaitSync( state->frameSync, GL_SYNC_FLUSH_COMMANDS_BIT, 1000000000ULL );
	if ( result == GL_ALREADY_SIGNALED || result == GL_CONDITION_SATISFIED ) {
		state->syncWaits++;
		GLX_Stream_DeleteFrameFence( state );
		return qtrue;
	}

	if ( result == GL_TIMEOUT_EXPIRED ) {
		state->syncTimeouts++;
		return qfalse;
	}

	state->syncFailures++;
	return qfalse;
}

static void GLX_Stream_DeleteBuffer( StreamState *state )
{
	if ( !state ) {
		return;
	}

	GLX_Stream_DeleteFrameFence( state );

	if ( !state->buffer || !s_fns.DeleteBuffers ) {
		return;
	}

	GLint oldArrayBuffer = 0;
	if ( s_fns.GetIntegerv ) {
		s_fns.GetIntegerv( GL_ARRAY_BUFFER_BINDING, &oldArrayBuffer );
	}

	if ( state->mappedPtr && s_fns.UnmapBuffer && s_fns.BindBuffer ) {
		s_fns.BindBuffer( GL_ARRAY_BUFFER, state->buffer );
		s_fns.UnmapBuffer( GL_ARRAY_BUFFER );
	}

	s_fns.DeleteBuffers( 1, &state->buffer );

	if ( s_fns.BindBuffer ) {
		s_fns.BindBuffer( GL_ARRAY_BUFFER, static_cast<GLuint>( oldArrayBuffer ) );
	}

	GLX_Stream_ResetRuntime( state );
}

static void GLX_Stream_BindPreserving( GLuint buffer, GLint *oldArrayBuffer )
{
	*oldArrayBuffer = 0;
	if ( s_fns.GetIntegerv ) {
		s_fns.GetIntegerv( GL_ARRAY_BUFFER_BINDING, oldArrayBuffer );
	}

	s_fns.BindBuffer( GL_ARRAY_BUFFER, buffer );
}

static void GLX_Stream_RestoreBinding( GLint oldArrayBuffer )
{
	if ( s_fns.BindBuffer ) {
		s_fns.BindBuffer( GL_ARRAY_BUFFER, static_cast<GLuint>( oldArrayBuffer ) );
	}
}

static void GLX_Stream_OrphanBuffer( StreamState *state )
{
	if ( !state || !state->buffer || !s_fns.BufferData ) {
		return;
	}

	s_fns.BufferData( GL_ARRAY_BUFFER, static_cast<ptrdiff_t>( state->ringBytes ), nullptr, GL_STREAM_DRAW );
	state->orphans++;
}

static qboolean GLX_Stream_CreateBufferObject( StreamState *state )
{
	GLint oldArrayBuffer = 0;

	s_fns.GenBuffers( 1, &state->buffer );
	if ( !state->buffer ) {
		state->allocationFailures++;
		return qfalse;
	}

	GLX_Stream_BindPreserving( state->buffer, &oldArrayBuffer );
	GLX_Stream_ClearGLErrors();

	if ( state->strategy == StreamStrategy::PersistentMapped ) {
		if ( !s_fns.BufferStorage || !s_fns.MapBufferRange || !s_fns.UnmapBuffer ) {
			state->fallbackCount++;
			if ( s_fns.MapBufferRange ) {
				state->strategy = StreamStrategy::MapBufferRange;
				GLX_Stream_SetReason( state, "persistent functions unavailable, using map range" );
			} else {
				state->strategy = StreamStrategy::OrphanSubData;
				GLX_Stream_SetReason( state, "persistent functions unavailable, using orphan/subdata" );
			}
		} else {
			const GLbitfield storageFlags = GL_MAP_WRITE_BIT | GL_MAP_PERSISTENT_BIT | GL_MAP_COHERENT_BIT | GL_DYNAMIC_STORAGE_BIT;
			const GLbitfield mapFlags = GL_MAP_WRITE_BIT | GL_MAP_PERSISTENT_BIT | GL_MAP_COHERENT_BIT;
			s_fns.BufferStorage( GL_ARRAY_BUFFER, static_cast<ptrdiff_t>( state->ringBytes ), nullptr, storageFlags );

			const GLenum storageError = GLX_Stream_GetGLError();
			if ( storageError == GL_NO_ERROR ) {
				state->mappedPtr = s_fns.MapBufferRange( GL_ARRAY_BUFFER, 0, static_cast<ptrdiff_t>( state->ringBytes ), mapFlags );
				if ( state->mappedPtr ) {
					state->ready = qtrue;
					state->persistentMapped = qtrue;
				} else {
					state->mapFailures++;
				}
			} else {
				state->allocationFailures++;
				if ( storageError == GL_OUT_OF_MEMORY ) {
					RI().Printf( PRINT_DEVELOPER, "GLx stream persistent allocation hit GL_OUT_OF_MEMORY; falling back.\n" );
				}
			}

			if ( !state->ready ) {
				GLuint failedBuffer = state->buffer;
				if ( state->mappedPtr && s_fns.UnmapBuffer ) {
					s_fns.UnmapBuffer( GL_ARRAY_BUFFER );
				}
				state->mappedPtr = nullptr;
				s_fns.DeleteBuffers( 1, &failedBuffer );
				state->buffer = 0;
				state->fallbackCount++;
				if ( s_fns.MapBufferRange ) {
					state->strategy = StreamStrategy::MapBufferRange;
					GLX_Stream_SetReason( state, "persistent allocation unavailable, using map range" );
				} else {
					state->strategy = StreamStrategy::OrphanSubData;
					GLX_Stream_SetReason( state, "persistent allocation unavailable, using orphan/subdata" );
				}
				s_fns.GenBuffers( 1, &state->buffer );
				if ( state->buffer ) {
					s_fns.BindBuffer( GL_ARRAY_BUFFER, state->buffer );
					GLX_Stream_ClearGLErrors();
				}
			}
		}
	}

	if ( !state->ready && state->buffer ) {
		s_fns.BufferData( GL_ARRAY_BUFFER, static_cast<ptrdiff_t>( state->ringBytes ), nullptr, GL_STREAM_DRAW );
		if ( GLX_Stream_GetGLError() == GL_NO_ERROR ) {
			state->ready = qtrue;
		} else {
			state->allocationFailures++;
		}
	}

	GLX_Stream_RestoreBinding( oldArrayBuffer );

	if ( !state->ready ) {
		GLX_Stream_DeleteBuffer( state );
		return qfalse;
	}

	return qtrue;
}

static qboolean GLX_Stream_PrepareRange( StreamState *state, size_t bytes, size_t alignment, size_t *offset )
{
	size_t alignedOffset;

	if ( !state || !offset || !state->ready || !state->buffer || bytes == 0 || bytes > state->ringBytes ) {
		if ( state ) {
			state->reserveFailures++;
		}
		return qfalse;
	}

	alignedOffset = GLX_Stream_AlignOffset( state->writeOffset, alignment );
	if ( alignedOffset + bytes > state->ringBytes ) {
		state->wraps++;
		if ( state->frameTouched ) {
			state->sameFrameWrapRejects++;
			state->reserveFailures++;
			return qfalse;
		}
		alignedOffset = 0;
	}

	*offset = alignedOffset;
	state->writeOffset = alignedOffset + bytes;
	return qtrue;
}

void GLX_Stream_RegisterCvars( StreamState *state )
{
	if ( !state ) {
		return;
	}

	state->r_glxStreamMode = RI().Cvar_Get( "r_glxStreamMode", "auto", CVAR_ARCHIVE_ND | CVAR_LATCH | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamMode,
		"Select GLx dynamic geometry streaming strategy: auto, persistent, maprange, or orphan. Requires vid_restart." );

	state->r_glxStreamMegabytes = RI().Cvar_Get( "r_glxStreamMegabytes", "8", CVAR_ARCHIVE_ND | CVAR_LATCH | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamMegabytes, "Target GLx dynamic stream ring size in megabytes. Requires vid_restart." );

	state->r_glxStreamTess = RI().Cvar_Get( "r_glxStreamTess", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamTess,
		"Shadow-upload legacy tessellation vertex/index data through the GLx stream ring without drawing from it." );

	state->r_glxStreamDraw = RI().Cvar_Get( "r_glxStreamDraw", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDraw,
		"Draw eligible single-texture generic shader stages from the GLx stream ring. Experimental and off by default." );

	state->r_glxStreamDrawKeyMode = RI().Cvar_Get( "r_glxStreamDrawKeyMode", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawKeyMode,
		"Filter GLx streamed draw material keys: 0 plain plus explicit gates, 1 computed, 2 all eligible." );

	state->r_glxStreamDrawMultitexture = RI().Cvar_Get( "r_glxStreamDrawMultitexture", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawMultitexture,
		"Allow GLx streamed draws for eligible fixed-function multitexture shader stages. Experimental and off by default." );

	state->r_glxStreamDrawFog = RI().Cvar_Get( "r_glxStreamDrawFog", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawFog,
		"Allow GLx streamed draws for fog-only passes. Experimental and off by default." );

	state->r_glxStreamDrawDepthFragment = RI().Cvar_Get( "r_glxStreamDrawDepthFragment", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawDepthFragment,
		"Allow GLx streamed draws for eligible depthFragment stages. Experimental and off by default." );

	state->r_glxStreamDrawTexMods = RI().Cvar_Get( "r_glxStreamDrawTexMods", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawTexMods,
		"Allow GLx streamed draws for stages whose texture coordinates were modified by the legacy CPU texmod path." );

	state->r_glxStreamDrawEnvironment = RI().Cvar_Get( "r_glxStreamDrawEnvironment", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawEnvironment,
		"Allow GLx streamed draws for stages using legacy CPU-computed environment texture coordinates." );

	state->r_glxStreamDrawDynamicLights = RI().Cvar_Get( "r_glxStreamDrawDynamicLights", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawDynamicLights,
		"Allow GLx streamed draws for dynamic-light map stages. Experimental and off by default." );

	state->r_glxStreamDrawScreenMaps = RI().Cvar_Get( "r_glxStreamDrawScreenMaps", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawScreenMaps,
		"Allow GLx streamed draws for screen-map stages. Experimental and off by default." );

	state->r_glxStreamDrawVideoMaps = RI().Cvar_Get( "r_glxStreamDrawVideoMaps", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawVideoMaps,
		"Allow GLx streamed draws for video-map stages. Experimental and off by default." );

	state->r_glxStreamDrawShadows = RI().Cvar_Get( "r_glxStreamDrawShadows", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawShadows,
		"Allow GLx streamed draws for stencil shadow-volume passes. Experimental and off by default." );

	state->r_glxStreamDrawBeams = RI().Cvar_Get( "r_glxStreamDrawBeams", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawBeams,
		"Allow GLx streamed draws for immediate beam entity draw-array passes. Experimental and off by default." );

	state->r_glxStreamDrawPostProcess = RI().Cvar_Get( "r_glxStreamDrawPostProcess", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxStreamDrawPostProcess,
		"Allow GLx streamed draws for fullscreen postprocess draw-array passes. Experimental and off by default." );
}

void GLX_Stream_OnOpenGLReady( StreamState *state, const Capabilities &caps )
{
	if ( !state ) {
		return;
	}

	GLX_Stream_Shutdown( state );

	state->strategy = StreamStrategy::OrphanSubData;
	GLX_Stream_ResetCounters( state );
	state->ringMegabytes = state->r_glxStreamMegabytes ? state->r_glxStreamMegabytes->integer : 8;
	if ( state->ringMegabytes < 1 ) {
		state->ringMegabytes = 1;
	}
	if ( state->ringMegabytes > 128 ) {
		state->ringMegabytes = 128;
	}
	state->ringBytes = static_cast<size_t>( state->ringMegabytes ) * 1024u * 1024u;

	const char *requestedMode = state->r_glxStreamMode && state->r_glxStreamMode->string ?
		state->r_glxStreamMode->string : "auto";
	const StreamStrategySelection selection = GLX_Stream_SelectStrategy( requestedMode, caps.features );

	if ( !selection.knownMode ) {
		RI().Printf( PRINT_WARNING, "Unknown r_glxStreamMode '%s', using auto.\n",
			requestedMode ? requestedMode : "" );
	}

	state->strategy = selection.strategy;
	state->fallbackCount += selection.fallbackCount;
	GLX_Stream_SetReason( state, selection.reason );

	if ( !GLX_Stream_FunctionsReady() ) {
		GLX_Stream_SetReason( state, "buffer functions unavailable" );
		state->ready = qfalse;
		return;
	}

	const StreamRuntimeSupport runtimeSupport {
		state->strategy,
		caps.features.syncObjects,
		caps.features.syncObjects ? GLX_Stream_SyncFunctionsReady() : qfalse,
		caps.features.mapBufferRange,
		s_fns.MapBufferRange ? qtrue : qfalse,
		s_fns.BufferSubData ? qtrue : qfalse
	};
	const StreamRuntimeFallback runtimeFallback =
		GLX_Stream_ApplyRuntimeFunctionFallbacks( runtimeSupport );
	state->strategy = runtimeFallback.strategy;
	state->syncReady = runtimeFallback.syncReady;
	state->fallbackCount += runtimeFallback.fallbackCount;
	if ( runtimeFallback.reason ) {
		GLX_Stream_SetReason( state, runtimeFallback.reason );
	}
	if ( !runtimeFallback.ready ) {
		state->ready = qfalse;
		return;
	}

	if ( !GLX_Stream_CreateBufferObject( state ) ) {
		GLX_Stream_SetReason( state, "stream buffer allocation failed" );
		RI().Printf( PRINT_DEVELOPER, "GLx dynamic stream buffer allocation failed.\n" );
	}
}

void GLX_Stream_Shutdown( StreamState *state )
{
	if ( !state ) {
		return;
	}

	GLX_Stream_DeleteBuffer( state );
	s_fns = {};

	state->strategy = StreamStrategy::OrphanSubData;
	state->reason[0] = '\0';
	state->ringMegabytes = 0;
	GLX_Stream_ResetRuntime( state );
	GLX_Stream_ResetCounters( state );
}

void GLX_Stream_FrameComplete( StreamState *state )
{
	if ( !state ) {
		return;
	}

	if ( state->syncReady && state->frameTouched ) {
		if ( state->frameSync ) {
			state->syncFenceSkips++;
		} else if ( s_fns.FenceSync ) {
			state->frameSync = s_fns.FenceSync( GL_SYNC_GPU_COMMANDS_COMPLETE, 0 );
			if ( state->frameSync ) {
				state->syncInsertions++;
			} else {
				state->syncFailures++;
			}
		}
	}

	state->frames++;
	state->writeOffset = 0;
	state->frameTouched = qfalse;
}

qboolean GLX_Stream_Reserve( StreamState *state, size_t bytes, size_t alignment, StreamReservation *reservation )
{
	GLint oldArrayBuffer = 0;
	size_t offset = 0;

	if ( !reservation ) {
		if ( state ) {
			state->reserveFailures++;
		}
		return qfalse;
	}

	*reservation = {};

	if ( state && state->writeOffset == 0 && state->frameSync && !GLX_Stream_WaitFrameFence( state ) ) {
		state->reserveFailures++;
		return qfalse;
	}

	if ( !GLX_Stream_PrepareRange( state, bytes, alignment, &offset ) ) {
		return qfalse;
	}

	reservation->buffer = state->buffer;
	reservation->offset = offset;
	reservation->bytes = bytes;
	reservation->strategy = state->strategy;
	state->frameTouched = qtrue;
	state->lastReservationBytes = static_cast<unsigned int>( bytes > ~0u ? ~0u : bytes );
	state->lastReservationOffset = static_cast<unsigned int>( offset > ~0u ? ~0u : offset );
	state->lastReservationStrategy = state->strategy;
	if ( state->lastReservationBytes > state->largestReservationBytes ) {
		state->largestReservationBytes = state->lastReservationBytes;
	}

	if ( state->strategy == StreamStrategy::PersistentMapped ) {
		reservation->ptr = static_cast<byte *>( state->mappedPtr ) + offset;
		reservation->mapped = qtrue;
		state->reservations++;
		return qtrue;
	}

	GLX_Stream_BindPreserving( state->buffer, &oldArrayBuffer );

	if ( state->strategy == StreamStrategy::MapBufferRange && s_fns.MapBufferRange && s_fns.UnmapBuffer ) {
		GLbitfield access = GL_MAP_WRITE_BIT | GL_MAP_UNSYNCHRONIZED_BIT;
		access |= ( offset == 0 ) ? GL_MAP_INVALIDATE_BUFFER_BIT : GL_MAP_INVALIDATE_RANGE_BIT;

		reservation->ptr = s_fns.MapBufferRange( GL_ARRAY_BUFFER, static_cast<ptrdiff_t>( offset ),
			static_cast<ptrdiff_t>( bytes ), access );
		if ( reservation->ptr ) {
			reservation->mapped = qtrue;
		} else {
			state->mapFailures++;
			state->strategy = StreamStrategy::OrphanSubData;
			reservation->strategy = StreamStrategy::OrphanSubData;
			GLX_Stream_SetReason( state, "map range reservation failed, using orphan/subdata" );
		}
	}

	if ( reservation->strategy == StreamStrategy::OrphanSubData ) {
		if ( offset == 0 ) {
			GLX_Stream_OrphanBuffer( state );
		}
	}

	GLX_Stream_RestoreBinding( oldArrayBuffer );

	state->reservations++;
	return qtrue;
}

qboolean GLX_Stream_Upload( StreamState *state, StreamReservation *reservation, const void *data, size_t bytes )
{
	return GLX_Stream_UploadAt( state, reservation, 0, data, bytes );
}

qboolean GLX_Stream_UploadAt( StreamState *state, StreamReservation *reservation, size_t relativeOffset,
	const void *data, size_t bytes )
{
	GLint oldArrayBuffer = 0;

	if ( !state || !reservation || !data || bytes == 0 || relativeOffset > reservation->bytes ||
		bytes > reservation->bytes - relativeOffset || reservation->committed ) {
		if ( state ) {
			state->uploadFailures++;
		}
		return qfalse;
	}

	if ( reservation->mapped && reservation->ptr ) {
		std::memcpy( static_cast<byte *>( reservation->ptr ) + relativeOffset, data, bytes );
		state->uploadCalls++;
		state->uploadBytes += static_cast<unsigned long long>( bytes );
		return qtrue;
	}

	if ( !s_fns.BufferSubData ) {
		state->uploadFailures++;
		return qfalse;
	}

	GLX_Stream_BindPreserving( reservation->buffer, &oldArrayBuffer );
	s_fns.BufferSubData( GL_ARRAY_BUFFER, static_cast<ptrdiff_t>( reservation->offset + relativeOffset ),
		static_cast<ptrdiff_t>( bytes ), data );
	if ( GLX_Stream_GetGLError() != GL_NO_ERROR ) {
		state->uploadFailures++;
		GLX_Stream_RestoreBinding( oldArrayBuffer );
		return qfalse;
	}
	GLX_Stream_RestoreBinding( oldArrayBuffer );

	state->uploadCalls++;
	state->uploadBytes += static_cast<unsigned long long>( bytes );
	return qtrue;
}

void GLX_Stream_Commit( StreamState *state, StreamReservation *reservation )
{
	GLint oldArrayBuffer = 0;

	if ( !state || !reservation || reservation->committed ) {
		return;
	}

	if ( reservation->strategy == StreamStrategy::MapBufferRange && reservation->mapped && s_fns.UnmapBuffer ) {
		GLX_Stream_BindPreserving( reservation->buffer, &oldArrayBuffer );
		if ( !s_fns.UnmapBuffer( GL_ARRAY_BUFFER ) ) {
			state->unmapFailures++;
		}
		GLX_Stream_RestoreBinding( oldArrayBuffer );
	}

	reservation->committed = qtrue;
	state->commits++;
}

qboolean GLX_Stream_DrawEnabled( const StreamState &state )
{
	return state.ready && state.r_glxStreamDraw && state.r_glxStreamDraw->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawMultitextureEnabled( const StreamState &state )
{
	return GLX_Stream_DrawEnabled( state ) &&
		state.r_glxStreamDrawMultitexture && state.r_glxStreamDrawMultitexture->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawFogEnabled( const StreamState &state )
{
	return GLX_Stream_DrawEnabled( state ) &&
		state.r_glxStreamDrawFog && state.r_glxStreamDrawFog->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawDepthFragmentEnabled( const StreamState &state )
{
	return GLX_Stream_DrawEnabled( state ) &&
		state.r_glxStreamDrawDepthFragment && state.r_glxStreamDrawDepthFragment->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawTexModsEnabled( const StreamState &state )
{
	return GLX_Stream_DrawEnabled( state ) &&
		state.r_glxStreamDrawTexMods && state.r_glxStreamDrawTexMods->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawEnvironmentEnabled( const StreamState &state )
{
	return GLX_Stream_DrawEnabled( state ) &&
		state.r_glxStreamDrawEnvironment && state.r_glxStreamDrawEnvironment->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawDynamicLightsEnabled( const StreamState &state )
{
	return GLX_Stream_DrawEnabled( state ) &&
		state.r_glxStreamDrawDynamicLights && state.r_glxStreamDrawDynamicLights->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawScreenMapsEnabled( const StreamState &state )
{
	return GLX_Stream_DrawEnabled( state ) &&
		state.r_glxStreamDrawScreenMaps && state.r_glxStreamDrawScreenMaps->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawVideoMapsEnabled( const StreamState &state )
{
	return GLX_Stream_DrawEnabled( state ) &&
		state.r_glxStreamDrawVideoMaps && state.r_glxStreamDrawVideoMaps->integer ? qtrue : qfalse;
}

qboolean GLX_Stream_DrawShadowsEnabled( const StreamState &state )
{
	StreamSpecialDrawGateConfig config {};

	config.streamDraw = GLX_Stream_DrawEnabled( state );
	config.shadows = state.r_glxStreamDrawShadows && state.r_glxStreamDrawShadows->integer ? qtrue : qfalse;
	return GLX_Stream_EvaluateShadowDrawGate( config );
}

qboolean GLX_Stream_DrawBeamsEnabled( const StreamState &state )
{
	StreamSpecialDrawGateConfig config {};

	config.streamDraw = GLX_Stream_DrawEnabled( state );
	config.beams = state.r_glxStreamDrawBeams && state.r_glxStreamDrawBeams->integer ? qtrue : qfalse;
	return GLX_Stream_EvaluateBeamDrawGate( config );
}

qboolean GLX_Stream_DrawPostProcessEnabled( const StreamState &state )
{
	StreamSpecialDrawGateConfig config {};

	config.streamDraw = GLX_Stream_DrawEnabled( state );
	config.postprocess = state.r_glxStreamDrawPostProcess && state.r_glxStreamDrawPostProcess->integer ? qtrue : qfalse;
	return GLX_Stream_EvaluatePostProcessDrawGate( config );
}

static void GLX_Stream_RecordMaterialGate( StreamState *state, qboolean present, qboolean allowed,
	unsigned int *accepted, unsigned int *rejected )
{
	if ( !state || !present ) {
		return;
	}

	if ( allowed ) {
		( *accepted )++;
	} else {
		( *rejected )++;
	}
}

qboolean GLX_Stream_DrawAllowsMaterial( StreamState *state, int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int texMods0, int texMods1 )
{
	StreamMaterialGateConfig config {};
	StreamMaterialGateResult result;

	(void)stateBits;
	(void)rgbGen;
	(void)alphaGen;
	(void)tcGen0;

	if ( state ) {
		config.keyMode = GLX_Stream_DrawKeyMode( *state );
		config.multitexture = GLX_Stream_DrawMultitextureEnabled( *state );
		config.texMods = GLX_Stream_DrawTexModsEnabled( *state );
		config.environment = GLX_Stream_DrawEnvironmentEnabled( *state );
		config.dynamicLights = GLX_Stream_DrawDynamicLightsEnabled( *state );
		config.screenMaps = GLX_Stream_DrawScreenMapsEnabled( *state );
		config.videoMaps = GLX_Stream_DrawVideoMapsEnabled( *state );
	}
	result = GLX_Stream_EvaluateMaterialGate( flags, texMods0, texMods1, config );

	if ( state ) {
		GLX_Stream_RecordMaterialGate( state, result.hasTexMods, result.allowed,
			&state->streamedDrawTexModAccepted, &state->streamedDrawTexModRejected );
		GLX_Stream_RecordMaterialGate( state, result.hasEnvironment, result.allowed,
			&state->streamedDrawEnvironmentAccepted, &state->streamedDrawEnvironmentRejected );
		GLX_Stream_RecordMaterialGate( state, result.hasDynamicLight, result.allowed,
			&state->streamedDrawDynamicLightAccepted, &state->streamedDrawDynamicLightRejected );
		GLX_Stream_RecordMaterialGate( state, result.hasScreenMap, result.allowed,
			&state->streamedDrawScreenMapAccepted, &state->streamedDrawScreenMapRejected );
		GLX_Stream_RecordMaterialGate( state, result.hasVideoMap, result.allowed,
			&state->streamedDrawVideoMapAccepted, &state->streamedDrawVideoMapRejected );
		if ( result.allowed ) {
			state->streamedDrawMaterialAccepted++;
		} else {
			state->streamedDrawMaterialRejected++;
		}
	}

	return result.allowed;
}

void GLX_Stream_RecordDrawResult( StreamState *state, int numVertexes, int numIndexes,
	int totalBytes, int indexBytes, int texcoord1Bytes, qboolean multitexture, qboolean fog,
	qboolean depthFragment, int materialFlags, qboolean success )
{
	if ( !state ) {
		return;
	}

	state->streamedDrawAttempts++;
	if ( success ) {
		state->streamedDraws++;
		if ( numVertexes > 0 ) {
			state->streamedDrawVertexes += static_cast<unsigned int>( numVertexes );
		}
		if ( numIndexes > 0 ) {
			state->streamedDrawIndexes += static_cast<unsigned int>( numIndexes );
		}
		if ( totalBytes > 0 ) {
			state->streamedDrawBytes += static_cast<unsigned long long>( totalBytes );
		}
		if ( indexBytes > 0 ) {
			state->streamedDrawIndexBytes += static_cast<unsigned long long>( indexBytes );
		}
		if ( texcoord1Bytes > 0 ) {
			state->streamedDrawTexcoord1Bytes += static_cast<unsigned long long>( texcoord1Bytes );
		}
		if ( multitexture ) {
			state->streamedDrawMultitextureDraws++;
		}
		if ( fog ) {
			state->streamedDrawFogDraws++;
		}
		if ( depthFragment ) {
			state->streamedDrawDepthFragmentDraws++;
		}
		if ( materialFlags & GLX_STAGE_TEXMOD ) {
			state->streamedDrawTexModDraws++;
		}
		if ( materialFlags & GLX_STAGE_ENVIRONMENT ) {
			state->streamedDrawEnvironmentDraws++;
		}
		if ( materialFlags & GLX_STAGE_DLIGHT_MAP ) {
			state->streamedDrawDynamicLightDraws++;
		}
		if ( materialFlags & GLX_STAGE_SCREEN_MAP ) {
			state->streamedDrawScreenMapDraws++;
		}
		if ( materialFlags & GLX_STAGE_VIDEO_MAP ) {
			state->streamedDrawVideoMapDraws++;
		}
		if ( materialFlags & GLX_STAGE_SHADOW_PASS ) {
			state->streamedDrawShadowDraws++;
		}
		if ( materialFlags & GLX_STAGE_BEAM_PASS ) {
			state->streamedDrawBeamDraws++;
		}
		if ( materialFlags & GLX_STAGE_POSTPROCESS_PASS ) {
			state->streamedDrawPostProcessDraws++;
		}
	} else {
		state->streamedDrawFallbacks++;
	}
}

void GLX_Stream_RecordDrawSkip( StreamState *state, int reason )
{
	if ( !state ) {
		return;
	}

	state->streamedDrawSkips++;
	if ( reason >= 0 && reason < GLX_STREAM_SKIP_REASON_COUNT ) {
		state->streamedDrawSkipReasons[reason]++;
	}
}

void GLX_Stream_RunSelfTest( StreamState *state )
{
	byte payload[256];
	StreamReservation reservation;

	if ( !state || !state->ready ) {
		RI().Printf( PRINT_ALL, "GLx stream test: stream buffer is not ready.\n" );
		return;
	}

	for ( size_t i = 0; i < sizeof( payload ); i++ ) {
		payload[i] = static_cast<byte>( i ^ 0x5a );
	}

	state->selfTests++;
	if ( !GLX_Stream_Reserve( state, sizeof( payload ), 64, &reservation ) ) {
		RI().Printf( PRINT_WARNING, "GLx stream test: reservation failed.\n" );
		return;
	}

	if ( !GLX_Stream_Upload( state, &reservation, payload, sizeof( payload ) ) ) {
		RI().Printf( PRINT_WARNING, "GLx stream test: upload failed.\n" );
		GLX_Stream_Commit( state, &reservation );
		return;
	}

	GLX_Stream_Commit( state, &reservation );
	RI().Printf( PRINT_ALL, "GLx stream test: uploaded %u bytes at offset %u using %s.\n",
		static_cast<unsigned int>( reservation.bytes ),
		static_cast<unsigned int>( reservation.offset ),
		GLX_Stream_StrategyName( reservation.strategy ) );
}

void GLX_Stream_ShadowUploadTess( StreamState *state, int numVertexes, int numIndexes,
	const void *xyz, size_t xyzBytes, const void *indexes, size_t indexBytes )
{
	StreamReservation vertices;
	StreamReservation elements;
	qboolean ok = qtrue;

	if ( !state || !state->r_glxStreamTess || !state->r_glxStreamTess->integer ) {
		return;
	}

	if ( !state->ready || numVertexes <= 0 || numIndexes <= 0 || !xyz || !indexes || xyzBytes == 0 || indexBytes == 0 ) {
		if ( state ) {
			state->shadowTessSkips++;
		}
		return;
	}

	if ( !GLX_Stream_Reserve( state, xyzBytes, 64, &vertices ) ) {
		state->shadowTessFailures++;
		return;
	}

	if ( !GLX_Stream_Upload( state, &vertices, xyz, xyzBytes ) ) {
		ok = qfalse;
	}
	GLX_Stream_Commit( state, &vertices );

	if ( !GLX_Stream_Reserve( state, indexBytes, 64, &elements ) ) {
		state->shadowTessFailures++;
		return;
	}

	if ( !GLX_Stream_Upload( state, &elements, indexes, indexBytes ) ) {
		ok = qfalse;
	}
	GLX_Stream_Commit( state, &elements );

	if ( ok ) {
		state->shadowTessUploads++;
		state->shadowTessBytes += static_cast<unsigned long long>( xyzBytes + indexBytes );
	} else {
		state->shadowTessFailures++;
	}
}

const char *GLX_Stream_StrategyName( StreamStrategy strategy )
{
	switch ( strategy ) {
	case StreamStrategy::PersistentMapped:
		return "persistent-map";
	case StreamStrategy::MapBufferRange:
		return "map-range";
	case StreamStrategy::OrphanSubData:
		return "orphan-subdata";
	default:
		return "unknown";
	}
}

void GLX_Stream_PrintInfo( const StreamState &state )
{
	RI().Printf( PRINT_ALL, "  dynamic stream strategy: %s\n", GLX_Stream_StrategyName( state.strategy ) );
	RI().Printf( PRINT_ALL, "  dynamic stream reason: %s\n", state.reason[0] ? state.reason : "not initialized" );
	RI().Printf( PRINT_ALL, "  dynamic stream target ring: %i MB\n", state.ringMegabytes );
	RI().Printf( PRINT_ALL, "  dynamic stream buffer: %s%s\n", BoolName( state.ready ),
		state.persistentMapped ? " (persistent mapped)" : "" );
	RI().Printf( PRINT_ALL, "  dynamic stream forced fallbacks: %u\n", state.fallbackCount );
	RI().Printf( PRINT_ALL, "  dynamic stream allocation failures: %u\n", state.allocationFailures );
	RI().Printf( PRINT_ALL, "  dynamic stream map failures: %u\n", state.mapFailures );
	RI().Printf( PRINT_ALL, "  dynamic stream unmap failures: %u\n", state.unmapFailures );
	RI().Printf( PRINT_ALL, "  dynamic stream sync: %s, fences %u, waits %u, timeouts %u, failures %u, pending skips %u\n",
		BoolName( state.syncReady ), state.syncInsertions, state.syncWaits,
		state.syncTimeouts, state.syncFailures, state.syncFenceSkips );
	RI().Printf( PRINT_ALL, "  dynamic stream reservations: %u, commits: %u, wraps: %u, same-frame wrap rejects: %u, orphans: %u\n",
		state.reservations, state.commits, state.wraps, state.sameFrameWrapRejects, state.orphans );
	RI().Printf( PRINT_ALL, "  dynamic stream reservation shape: last %u bytes at %u using %s, largest %u bytes\n",
		state.lastReservationBytes, state.lastReservationOffset,
		GLX_Stream_StrategyName( state.lastReservationStrategy ),
		state.largestReservationBytes );
	RI().Printf( PRINT_ALL, "  dynamic stream uploads: %u calls, %.2f MB, failures %u\n",
		state.uploadCalls, static_cast<double>( state.uploadBytes ) / ( 1024.0 * 1024.0 ), state.uploadFailures );
	RI().Printf( PRINT_ALL, "  dynamic stream tess shadow uploads: %u batches, %.2f MB, skips %u, failures %u\n",
		state.shadowTessUploads, static_cast<double>( state.shadowTessBytes ) / ( 1024.0 * 1024.0 ),
		state.shadowTessSkips, state.shadowTessFailures );
	RI().Printf( PRINT_ALL, "  dynamic stream draw key mode: %i (%s), accepted %u, rejected %u\n",
		GLX_Stream_DrawKeyMode( state ), GLX_Stream_DrawKeyModeName( GLX_Stream_DrawKeyMode( state ) ),
		state.streamedDrawMaterialAccepted, state.streamedDrawMaterialRejected );
	RI().Printf( PRINT_ALL, "  dynamic stream texmod gate: %s, accepted %u, rejected %u\n",
		BoolName( GLX_Stream_DrawTexModsEnabled( state ) ),
		state.streamedDrawTexModAccepted, state.streamedDrawTexModRejected );
	RI().Printf( PRINT_ALL, "  dynamic stream environment gate: %s, accepted %u, rejected %u\n",
		BoolName( GLX_Stream_DrawEnvironmentEnabled( state ) ),
		state.streamedDrawEnvironmentAccepted, state.streamedDrawEnvironmentRejected );
	RI().Printf( PRINT_ALL, "  dynamic stream dynamic-light gate: %s, accepted %u, rejected %u\n",
		BoolName( GLX_Stream_DrawDynamicLightsEnabled( state ) ),
		state.streamedDrawDynamicLightAccepted, state.streamedDrawDynamicLightRejected );
	RI().Printf( PRINT_ALL, "  dynamic stream screen-map gate: %s, accepted %u, rejected %u\n",
		BoolName( GLX_Stream_DrawScreenMapsEnabled( state ) ),
		state.streamedDrawScreenMapAccepted, state.streamedDrawScreenMapRejected );
	RI().Printf( PRINT_ALL, "  dynamic stream video-map gate: %s, accepted %u, rejected %u\n",
		BoolName( GLX_Stream_DrawVideoMapsEnabled( state ) ),
		state.streamedDrawVideoMapAccepted, state.streamedDrawVideoMapRejected );
	RI().Printf( PRINT_ALL, "  dynamic stream shadow-volume gate: %s, draws %u\n",
		BoolName( GLX_Stream_DrawShadowsEnabled( state ) ),
		state.streamedDrawShadowDraws );
	RI().Printf( PRINT_ALL, "  dynamic stream beam gate: %s, draws %u\n",
		BoolName( GLX_Stream_DrawBeamsEnabled( state ) ),
		state.streamedDrawBeamDraws );
	RI().Printf( PRINT_ALL, "  dynamic stream postprocess gate: %s, draws %u\n",
		BoolName( GLX_Stream_DrawPostProcessEnabled( state ) ),
		state.streamedDrawPostProcessDraws );
	RI().Printf( PRINT_ALL, "  dynamic stream draws: %u/%u attempts, %u verts, %u indexes, %.2f MB, index %.2f MB, tex1 %.2f MB, mt %u, fog %u, depthfrag %u, texmod %u, env %u, dlight %u, screen %u, video %u, shadow %u, beam %u, post %u, fallbacks %u\n",
		state.streamedDraws, state.streamedDrawAttempts,
		state.streamedDrawVertexes, state.streamedDrawIndexes,
		static_cast<double>( state.streamedDrawBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( state.streamedDrawIndexBytes ) / ( 1024.0 * 1024.0 ),
		static_cast<double>( state.streamedDrawTexcoord1Bytes ) / ( 1024.0 * 1024.0 ),
		state.streamedDrawMultitextureDraws,
		state.streamedDrawFogDraws,
		state.streamedDrawDepthFragmentDraws,
		state.streamedDrawTexModDraws,
		state.streamedDrawEnvironmentDraws,
		state.streamedDrawDynamicLightDraws,
		state.streamedDrawScreenMapDraws,
		state.streamedDrawVideoMapDraws,
		state.streamedDrawShadowDraws,
		state.streamedDrawBeamDraws,
		state.streamedDrawPostProcessDraws,
		state.streamedDrawFallbacks );
	RI().Printf( PRINT_ALL, "  dynamic stream draw skips: %u (bind %u, input %u, mt %u, depthfrag %u, texcoord %u, empty %u, key %u, fog %u, program %u)\n",
		state.streamedDrawSkips,
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_NO_BIND_BUFFER],
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_BAD_INPUT],
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_MULTITEXTURE],
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_DEPTH_FRAGMENT],
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_NO_TEXCOORDS],
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_EMPTY_BATCH],
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_MATERIAL_KEY],
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_FOG],
		state.streamedDrawSkipReasons[GLX_STREAM_SKIP_MATERIAL_PROGRAM] );
	RI().Printf( PRINT_ALL, "  dynamic stream reservation failures: %u\n", state.reserveFailures );
	RI().Printf( PRINT_ALL, "  dynamic stream self-tests: %u\n", state.selfTests );
	RI().Printf( PRINT_ALL, "  dynamic stream frames observed: %u\n", state.frames );
}

} // namespace glx
