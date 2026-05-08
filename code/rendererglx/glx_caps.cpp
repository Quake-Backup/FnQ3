#include "glx_caps.h"

#include <cctype>
#include <cstdlib>
#include <cstring>

#ifndef GL_CONTEXT_FLAGS
#define GL_CONTEXT_FLAGS 0x821E
#endif
#ifndef GL_CONTEXT_FLAG_DEBUG_BIT
#define GL_CONTEXT_FLAG_DEBUG_BIT 0x00000002
#endif

namespace glx {

typedef void ( APIENTRY *PFNGLXGETINTEGERVPROC )( GLenum pname, GLint *params );

static void GLX_Caps_ParseVersion( Capabilities *caps, const char *version )
{
	const char *scan = version ? version : "";

	while ( *scan && !std::isdigit( static_cast<unsigned char>( *scan ) ) ) {
		scan++;
	}

	if ( !*scan ) {
		return;
	}

	caps->major = std::atoi( scan );
	while ( *scan && *scan != '.' ) {
		scan++;
	}

	if ( *scan == '.' ) {
		scan++;
		caps->minor = std::atoi( scan );
	}
}

void GLX_Caps_Reset( Capabilities *caps )
{
	if ( !caps ) {
		return;
	}

	caps->config = nullptr;
	caps->extensions = "";
	caps->major = 0;
	caps->minor = 0;
	caps->tier = CapabilityTier::BelowFloor;
	caps->features = {};
}

void GLX_Caps_Init( Capabilities *caps, const glconfig_t *config, const char *extensions )
{
	if ( !caps ) {
		return;
	}

	GLX_Caps_Reset( caps );

	caps->config = config;
	caps->extensions = extensions ? extensions : "";

	GLX_Caps_ParseVersion( caps, config ? config->version_string : "" );

	caps->features.mapBufferRange = ToQBool( GLX_Caps_VersionAtLeast( *caps, 3, 0 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_map_buffer_range" ) );
	caps->features.uniformBufferObject = ToQBool( GLX_Caps_VersionAtLeast( *caps, 3, 1 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_uniform_buffer_object" ) );
	caps->features.instancedArrays = ToQBool( GLX_Caps_VersionAtLeast( *caps, 3, 3 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_instanced_arrays" ) );
	caps->features.bufferStorage = ToQBool( GLX_Caps_VersionAtLeast( *caps, 4, 4 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_buffer_storage" ) );
	caps->features.syncObjects = ToQBool( GLX_Caps_VersionAtLeast( *caps, 3, 2 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_sync" ) );
	caps->features.drawIndirect = ToQBool( GLX_Caps_VersionAtLeast( *caps, 4, 0 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_draw_indirect" ) || GLX_Caps_HasExtension( *caps, "GL_ARB_multi_draw_indirect" ) );
	caps->features.multiDrawIndirect = ToQBool( GLX_Caps_VersionAtLeast( *caps, 4, 3 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_multi_draw_indirect" ) );
	caps->features.directStateAccess = ToQBool( GLX_Caps_VersionAtLeast( *caps, 4, 5 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_direct_state_access" ) );
	caps->features.khrDebug = ToQBool( GLX_Caps_VersionAtLeast( *caps, 4, 3 ) || GLX_Caps_HasExtension( *caps, "GL_KHR_debug" ) );
	caps->features.debugOutput = ToQBool( caps->features.khrDebug || GLX_Caps_HasExtension( *caps, "GL_ARB_debug_output" ) );
	caps->features.timerQuery = ToQBool( GLX_Caps_VersionAtLeast( *caps, 3, 3 ) || GLX_Caps_HasExtension( *caps, "GL_ARB_timer_query" ) || GLX_Caps_HasExtension( *caps, "GL_EXT_timer_query" ) );
	if ( RI().GL_GetProcAddress && GLX_Caps_VersionAtLeast( *caps, 3, 0 ) ) {
		PFNGLXGETINTEGERVPROC getIntegerv =
			reinterpret_cast<PFNGLXGETINTEGERVPROC>( RI().GL_GetProcAddress( "glGetIntegerv" ) );
		GLint contextFlags = 0;

		if ( getIntegerv ) {
			getIntegerv( GL_CONTEXT_FLAGS, &contextFlags );
			caps->features.debugContext = ToQBool( ( contextFlags & GL_CONTEXT_FLAG_DEBUG_BIT ) != 0 );
		}
	}

	if ( !GLX_Caps_VersionAtLeast( *caps, 2, 1 ) ) {
		caps->tier = CapabilityTier::BelowFloor;
	} else if ( caps->features.bufferStorage && caps->features.syncObjects && caps->features.multiDrawIndirect ) {
		caps->tier = CapabilityTier::Advanced;
	} else if ( GLX_Caps_VersionAtLeast( *caps, 3, 3 ) ||
		( caps->features.mapBufferRange && caps->features.uniformBufferObject && caps->features.instancedArrays ) ) {
		caps->tier = CapabilityTier::Core;
	} else {
		caps->tier = CapabilityTier::Compat;
	}
}

qboolean GLX_Caps_HasExtension( const Capabilities &caps, const char *name )
{
	if ( !name || !*name || !caps.extensions || !*caps.extensions ) {
		return qfalse;
	}

	const size_t len = std::strlen( name );
	const char *scan = caps.extensions;

	while ( ( scan = std::strstr( scan, name ) ) != nullptr ) {
		const char before = ( scan == caps.extensions ) ? ' ' : scan[ -1 ];
		const char after = scan[ len ];

		if ( ( before == ' ' || before == '\0' ) && ( after == ' ' || after == '\0' ) ) {
			return qtrue;
		}

		scan += len;
	}

	return qfalse;
}

qboolean GLX_Caps_VersionAtLeast( const Capabilities &caps, int major, int minor )
{
	return ( caps.major > major || ( caps.major == major && caps.minor >= minor ) ) ? qtrue : qfalse;
}

const char *GLX_Caps_TierName( CapabilityTier tier )
{
	switch ( tier ) {
	case CapabilityTier::BelowFloor:
		return "below-floor";
	case CapabilityTier::Compat:
		return "compat";
	case CapabilityTier::Core:
		return "core";
	case CapabilityTier::Advanced:
		return "advanced";
	default:
		return "unknown";
	}
}

} // namespace glx
