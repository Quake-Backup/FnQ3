#include "glx_debug.h"

#ifndef GL_DEBUG_OUTPUT
#define GL_DEBUG_OUTPUT 0x92E0
#endif
#ifndef GL_DEBUG_OUTPUT_SYNCHRONOUS
#define GL_DEBUG_OUTPUT_SYNCHRONOUS 0x8242
#endif
#ifndef GL_DEBUG_SOURCE_API
#define GL_DEBUG_SOURCE_API 0x8246
#endif
#ifndef GL_DEBUG_SOURCE_WINDOW_SYSTEM
#define GL_DEBUG_SOURCE_WINDOW_SYSTEM 0x8247
#endif
#ifndef GL_DEBUG_SOURCE_SHADER_COMPILER
#define GL_DEBUG_SOURCE_SHADER_COMPILER 0x8248
#endif
#ifndef GL_DEBUG_SOURCE_THIRD_PARTY
#define GL_DEBUG_SOURCE_THIRD_PARTY 0x8249
#endif
#ifndef GL_DEBUG_SOURCE_APPLICATION
#define GL_DEBUG_SOURCE_APPLICATION 0x824A
#endif
#ifndef GL_DEBUG_SOURCE_OTHER
#define GL_DEBUG_SOURCE_OTHER 0x824B
#endif
#ifndef GL_DEBUG_TYPE_ERROR
#define GL_DEBUG_TYPE_ERROR 0x824C
#endif
#ifndef GL_DEBUG_TYPE_DEPRECATED_BEHAVIOR
#define GL_DEBUG_TYPE_DEPRECATED_BEHAVIOR 0x824D
#endif
#ifndef GL_DEBUG_TYPE_UNDEFINED_BEHAVIOR
#define GL_DEBUG_TYPE_UNDEFINED_BEHAVIOR 0x824E
#endif
#ifndef GL_DEBUG_TYPE_PORTABILITY
#define GL_DEBUG_TYPE_PORTABILITY 0x824F
#endif
#ifndef GL_DEBUG_TYPE_PERFORMANCE
#define GL_DEBUG_TYPE_PERFORMANCE 0x8250
#endif
#ifndef GL_DEBUG_TYPE_OTHER
#define GL_DEBUG_TYPE_OTHER 0x8251
#endif
#ifndef GL_DEBUG_TYPE_MARKER
#define GL_DEBUG_TYPE_MARKER 0x8268
#endif
#ifndef GL_DEBUG_TYPE_PUSH_GROUP
#define GL_DEBUG_TYPE_PUSH_GROUP 0x8269
#endif
#ifndef GL_DEBUG_TYPE_POP_GROUP
#define GL_DEBUG_TYPE_POP_GROUP 0x826A
#endif
#ifndef GL_DEBUG_SEVERITY_HIGH
#define GL_DEBUG_SEVERITY_HIGH 0x9146
#endif
#ifndef GL_DEBUG_SEVERITY_MEDIUM
#define GL_DEBUG_SEVERITY_MEDIUM 0x9147
#endif
#ifndef GL_DEBUG_SEVERITY_LOW
#define GL_DEBUG_SEVERITY_LOW 0x9148
#endif
#ifndef GL_DEBUG_SEVERITY_NOTIFICATION
#define GL_DEBUG_SEVERITY_NOTIFICATION 0x826B
#endif
#ifndef GL_DONT_CARE
#define GL_DONT_CARE 0x1100
#endif

namespace glx {

static const char *GLX_Debug_SourceName( GLenum source )
{
	switch ( source ) {
	case GL_DEBUG_SOURCE_API:
		return "api";
	case GL_DEBUG_SOURCE_WINDOW_SYSTEM:
		return "window-system";
	case GL_DEBUG_SOURCE_SHADER_COMPILER:
		return "shader-compiler";
	case GL_DEBUG_SOURCE_THIRD_PARTY:
		return "third-party";
	case GL_DEBUG_SOURCE_APPLICATION:
		return "application";
	case GL_DEBUG_SOURCE_OTHER:
		return "other";
	default:
		return "unknown";
	}
}

static const char *GLX_Debug_TypeName( GLenum type )
{
	switch ( type ) {
	case GL_DEBUG_TYPE_ERROR:
		return "error";
	case GL_DEBUG_TYPE_DEPRECATED_BEHAVIOR:
		return "deprecated";
	case GL_DEBUG_TYPE_UNDEFINED_BEHAVIOR:
		return "undefined";
	case GL_DEBUG_TYPE_PORTABILITY:
		return "portability";
	case GL_DEBUG_TYPE_PERFORMANCE:
		return "performance";
	case GL_DEBUG_TYPE_OTHER:
		return "other";
	case GL_DEBUG_TYPE_MARKER:
		return "marker";
	case GL_DEBUG_TYPE_PUSH_GROUP:
		return "push-group";
	case GL_DEBUG_TYPE_POP_GROUP:
		return "pop-group";
	default:
		return "unknown";
	}
}

static const char *GLX_Debug_SeverityName( GLenum severity )
{
	switch ( severity ) {
	case GL_DEBUG_SEVERITY_HIGH:
		return "high";
	case GL_DEBUG_SEVERITY_MEDIUM:
		return "medium";
	case GL_DEBUG_SEVERITY_LOW:
		return "low";
	case GL_DEBUG_SEVERITY_NOTIFICATION:
		return "notification";
	default:
		return "unknown";
	}
}

static void APIENTRY GLX_Debug_Callback( GLenum source, GLenum type, GLuint id, GLenum severity,
	GLsizei length, const GLchar *message, const void *userParam )
{
	const DebugState *state = static_cast<const DebugState *>( userParam );

	if ( severity == GL_DEBUG_SEVERITY_NOTIFICATION && state && !GLX_Debug_Verbose( *state ) ) {
		return;
	}

	if ( !ImportsReady() || !g_imports->Printf ) {
		return;
	}

	RI().Printf( PRINT_DEVELOPER, "GLx debug [%s/%s/%s #%u]: %.*s\n",
		GLX_Debug_SourceName( source ), GLX_Debug_TypeName( type ), GLX_Debug_SeverityName( severity ),
		static_cast<unsigned int>( id ), static_cast<int>( length ), message ? message : "" );
}

void GLX_Debug_RegisterCvars( DebugState *state )
{
	if ( !state ) {
		return;
	}

	state->r_glxDebug = RI().Cvar_Get( "r_glxDebug", "0", CVAR_ARCHIVE_ND | CVAR_LATCH | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxDebug, "Enable GLx KHR_debug callback wiring when the driver exposes it. Requires vid_restart." );

	state->r_glxDebugVerbose = RI().Cvar_Get( "r_glxDebugVerbose", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxDebugVerbose, "Print low-volume GLx debug notifications in addition to warnings and errors." );

	state->r_glxDebugGroups = RI().Cvar_Get( "r_glxDebugGroups", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxDebugGroups, "Wrap GLx-observed shader batches in KHR_debug groups when available." );
}

void GLX_Debug_OnOpenGLReady( DebugState *state, const Capabilities &caps )
{
	if ( !state ) {
		return;
	}

	state->fns = {};
	state->callbackInstalled = qfalse;
	state->groupsPushed = 0;

	if ( !caps.features.khrDebug || !RI().GL_GetProcAddress ) {
		return;
	}

	state->fns.Enable = reinterpret_cast<PFNGLXENABLEPROC>( RI().GL_GetProcAddress( "glEnable" ) );
	state->fns.DebugMessageCallback = reinterpret_cast<PFNGLXDEBUGMESSAGECALLBACKPROC>( RI().GL_GetProcAddress( "glDebugMessageCallback" ) );
	state->fns.DebugMessageControl = reinterpret_cast<PFNGLXDEBUGMESSAGECONTROLPROC>( RI().GL_GetProcAddress( "glDebugMessageControl" ) );
	state->fns.ObjectLabel = reinterpret_cast<PFNGLXOBJECTLABELPROC>( RI().GL_GetProcAddress( "glObjectLabel" ) );
	state->fns.PushDebugGroup = reinterpret_cast<PFNGLXPUSHDEBUGGROUPPROC>( RI().GL_GetProcAddress( "glPushDebugGroup" ) );
	state->fns.PopDebugGroup = reinterpret_cast<PFNGLXPOPDEBUGGROUPPROC>( RI().GL_GetProcAddress( "glPopDebugGroup" ) );

	if ( !state->r_glxDebug || !state->r_glxDebug->integer ) {
		return;
	}

	if ( !state->fns.Enable || !state->fns.DebugMessageCallback ) {
		RI().Printf( PRINT_WARNING, "GLx debug requested, but KHR_debug callback functions are unavailable.\n" );
		return;
	}

	state->fns.Enable( GL_DEBUG_OUTPUT );
	state->fns.Enable( GL_DEBUG_OUTPUT_SYNCHRONOUS );

	if ( state->fns.DebugMessageControl && !GLX_Debug_Verbose( *state ) ) {
		state->fns.DebugMessageControl( GL_DONT_CARE, GL_DONT_CARE, GL_DEBUG_SEVERITY_NOTIFICATION, 0, nullptr, GL_FALSE );
	}

	state->fns.DebugMessageCallback( GLX_Debug_Callback, state );
	state->callbackInstalled = qtrue;
}

void GLX_Debug_Shutdown( DebugState *state )
{
	if ( !state ) {
		return;
	}

	state->fns = {};
	state->callbackInstalled = qfalse;
	state->groupsPushed = 0;
}

qboolean GLX_Debug_CallbackInstalled( const DebugState &state )
{
	return state.callbackInstalled;
}

qboolean GLX_Debug_Verbose( const DebugState &state )
{
	return state.r_glxDebugVerbose && state.r_glxDebugVerbose->integer ? qtrue : qfalse;
}

void GLX_Debug_LabelObject( const DebugState &state, GLenum identifier, GLuint name, const char *label )
{
	if ( !state.fns.ObjectLabel || !name || !label || !*label ) {
		return;
	}

	state.fns.ObjectLabel( identifier, name, -1, label );
}

void GLX_Debug_PushGroup( DebugState *state, const char *label )
{
	if ( !state || !state->r_glxDebugGroups || !state->r_glxDebugGroups->integer ||
		!state->fns.PushDebugGroup || !label || !*label ) {
		return;
	}

	state->fns.PushDebugGroup( GL_DEBUG_SOURCE_APPLICATION, 0, -1, label );
	state->groupsPushed++;
}

void GLX_Debug_PopGroup( DebugState *state )
{
	if ( !state || !state->groupsPushed || !state->fns.PopDebugGroup ) {
		return;
	}

	state->fns.PopDebugGroup();
	state->groupsPushed--;
}

} // namespace glx
