#include "glx_material.h"

#include <cstdio>
#include <cstring>

#ifndef GL_VERTEX_SHADER
#define GL_VERTEX_SHADER 0x8B31
#endif
#ifndef GL_FRAGMENT_SHADER
#define GL_FRAGMENT_SHADER 0x8B30
#endif
#ifndef GL_COMPILE_STATUS
#define GL_COMPILE_STATUS 0x8B81
#endif
#ifndef GL_LINK_STATUS
#define GL_LINK_STATUS 0x8B82
#endif
#ifndef GL_INFO_LOG_LENGTH
#define GL_INFO_LOG_LENGTH 0x8B84
#endif
#ifndef GL_SHADING_LANGUAGE_VERSION
#define GL_SHADING_LANGUAGE_VERSION 0x8B8C
#endif
#ifndef GL_PROGRAM
#define GL_PROGRAM 0x82E2
#endif

namespace glx {

typedef const GLubyte *( APIENTRY *PFNGLXGETSTRINGPROC )( GLenum name );

static constexpr MaterialProgramMode kMaterialPrecacheModes[] = {
	MaterialProgramMode::SingleTexture,
	MaterialProgramMode::MultiModulate,
	MaterialProgramMode::MultiAdd,
	MaterialProgramMode::MultiReplace,
	MaterialProgramMode::MultiDecal,
	MaterialProgramMode::Fog
};

static constexpr unsigned int kMaterialPrecacheFeatures[] = {
	GLX_MATERIAL_FEATURE_NONE,
	GLX_MATERIAL_FEATURE_TEXMOD,
	GLX_MATERIAL_FEATURE_ENVIRONMENT,
	GLX_MATERIAL_FEATURE_TEXMOD | GLX_MATERIAL_FEATURE_ENVIRONMENT
};

static constexpr unsigned int kMaterialPrecacheSingleTextureFeatures[] = {
	GLX_MATERIAL_FEATURE_NONE,
	GLX_MATERIAL_FEATURE_TEXMOD,
	GLX_MATERIAL_FEATURE_ENVIRONMENT,
	GLX_MATERIAL_FEATURE_TEXMOD | GLX_MATERIAL_FEATURE_ENVIRONMENT,
	GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT,
	GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT | GLX_MATERIAL_FEATURE_TEXMOD,
	GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT | GLX_MATERIAL_FEATURE_ENVIRONMENT,
	GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT | GLX_MATERIAL_FEATURE_TEXMOD |
		GLX_MATERIAL_FEATURE_ENVIRONMENT
};

static void GLX_Material_FeatureName( unsigned int features, char *out, size_t outSize )
{
	char text[64] = "";

	if ( !out || outSize == 0 ) {
		return;
	}

	if ( features == GLX_MATERIAL_FEATURE_NONE ) {
		std::snprintf( out, outSize, "base" );
		out[outSize - 1] = '\0';
		return;
	}

	if ( features & GLX_MATERIAL_FEATURE_TEXMOD ) {
		std::snprintf( text + std::strlen( text ), sizeof( text ) - std::strlen( text ), "%stexmod",
			text[0] ? "+" : "" );
	}
	if ( features & GLX_MATERIAL_FEATURE_ENVIRONMENT ) {
		std::snprintf( text + std::strlen( text ), sizeof( text ) - std::strlen( text ), "%senvironment",
			text[0] ? "+" : "" );
	}
	if ( features & GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT ) {
		std::snprintf( text + std::strlen( text ), sizeof( text ) - std::strlen( text ), "%sdepth-fragment",
			text[0] ? "+" : "" );
	}

	std::snprintf( out, outSize, "%s", text[0] ? text : "unknown" );
	out[outSize - 1] = '\0';
}

static void GLX_Material_KeyName( const MaterialProgramKey &key, char *out, size_t outSize )
{
	char features[64];

	if ( !out || outSize == 0 ) {
		return;
	}

	GLX_Material_FeatureName( key.features, features, sizeof( features ) );
	std::snprintf( out, outSize, "%s/%s", GLX_Material_ModeName( key.mode ), features );
	out[outSize - 1] = '\0';
}

static const char *GLX_Material_VertexSource()
{
	return
		"#version 120\n"
		"varying vec4 v_Color;\n"
		"varying vec2 v_TexCoord0;\n"
		"varying vec2 v_TexCoord1;\n"
		"void main(void)\n"
		"{\n"
		"    gl_Position = ftransform();\n"
		"    v_Color = gl_Color;\n"
		"    v_TexCoord0 = gl_MultiTexCoord0.st;\n"
		"    v_TexCoord1 = gl_MultiTexCoord1.st;\n"
		"}\n";
}

static void GLX_Material_SetReason( MaterialState *state, const char *reason )
{
	if ( !state ) {
		return;
	}

	std::snprintf( state->reason, sizeof( state->reason ), "%s", reason ? reason : "" );
	state->reason[sizeof( state->reason ) - 1] = '\0';
}

static void GLX_Material_SetLastError( MaterialState *state, const char *error )
{
	if ( !state ) {
		return;
	}

	std::snprintf( state->lastError, sizeof( state->lastError ), "%s", error ? error : "" );
	state->lastError[sizeof( state->lastError ) - 1] = '\0';
}

static void *GLX_Material_GetProc( const char *name )
{
	return RI().GL_GetProcAddress ? RI().GL_GetProcAddress( name ) : nullptr;
}

static void GLX_Material_LoadFunctions( MaterialState *state )
{
	if ( !state ) {
		return;
	}

	state->fns.CreateShader = reinterpret_cast<PFNGLXCREATESHADERPROC>( GLX_Material_GetProc( "glCreateShader" ) );
	state->fns.ShaderSource = reinterpret_cast<PFNGLXSHADERSOURCEPROC>( GLX_Material_GetProc( "glShaderSource" ) );
	state->fns.CompileShader = reinterpret_cast<PFNGLXCOMPILESHADERPROC>( GLX_Material_GetProc( "glCompileShader" ) );
	state->fns.GetShaderiv = reinterpret_cast<PFNGLXGETSHADERIVPROC>( GLX_Material_GetProc( "glGetShaderiv" ) );
	state->fns.GetShaderInfoLog = reinterpret_cast<PFNGLXGETSHADERINFOLOGPROC>( GLX_Material_GetProc( "glGetShaderInfoLog" ) );
	state->fns.CreateProgram = reinterpret_cast<PFNGLXCREATEPROGRAMPROC>( GLX_Material_GetProc( "glCreateProgram" ) );
	state->fns.AttachShader = reinterpret_cast<PFNGLXATTACHSHADERPROC>( GLX_Material_GetProc( "glAttachShader" ) );
	state->fns.LinkProgram = reinterpret_cast<PFNGLXLINKPROGRAMPROC>( GLX_Material_GetProc( "glLinkProgram" ) );
	state->fns.GetProgramiv = reinterpret_cast<PFNGLXGETPROGRAMIVPROC>( GLX_Material_GetProc( "glGetProgramiv" ) );
	state->fns.GetProgramInfoLog = reinterpret_cast<PFNGLXGETPROGRAMINFOLOGPROC>( GLX_Material_GetProc( "glGetProgramInfoLog" ) );
	state->fns.UseProgram = reinterpret_cast<PFNGLXUSEPROGRAMPROC>( GLX_Material_GetProc( "glUseProgram" ) );
	state->fns.GetUniformLocation = reinterpret_cast<PFNGLXGETUNIFORMLOCATIONPROC>( GLX_Material_GetProc( "glGetUniformLocation" ) );
	state->fns.Uniform1i = reinterpret_cast<PFNGLXUNIFORM1IPROC>( GLX_Material_GetProc( "glUniform1i" ) );
	state->fns.DeleteProgram = reinterpret_cast<PFNGLXDELETEPROGRAMPROC>( GLX_Material_GetProc( "glDeleteProgram" ) );
	state->fns.DeleteShader = reinterpret_cast<PFNGLXDELETESHADERPROC>( GLX_Material_GetProc( "glDeleteShader" ) );
	state->fns.ObjectLabel = reinterpret_cast<PFNGLXMATERIALOBJECTLABELPROC>( GLX_Material_GetProc( "glObjectLabel" ) );
}

static qboolean GLX_Material_FunctionsReady( const MaterialState &state )
{
	return state.fns.CreateShader &&
		state.fns.ShaderSource &&
		state.fns.CompileShader &&
		state.fns.GetShaderiv &&
		state.fns.GetShaderInfoLog &&
		state.fns.CreateProgram &&
		state.fns.AttachShader &&
		state.fns.LinkProgram &&
		state.fns.GetProgramiv &&
		state.fns.GetProgramInfoLog &&
		state.fns.UseProgram &&
		state.fns.GetUniformLocation &&
		state.fns.Uniform1i &&
		state.fns.DeleteProgram &&
		state.fns.DeleteShader ? qtrue : qfalse;
}

static void GLX_Material_ResetCounters( MaterialState *state )
{
	if ( !state ) {
		return;
	}

	state->frames = 0;
	state->bindAttempts = 0;
	state->binds = 0;
	state->programSwitches = 0;
	state->unbinds = 0;
	state->cacheHits = 0;
	state->cacheMisses = 0;
	state->compileAttempts = 0;
	state->compileFailures = 0;
	state->linkFailures = 0;
	state->precacheAttempts = 0;
	state->precacheFailures = 0;
	state->bindFailures = 0;
	state->debugLabels = 0;
	state->contextlessDeletes = 0;
	state->unsupportedRequests = 0;
	state->disabledSkips = 0;
	state->notReadySkips = 0;
	state->programLimitSkips = 0;
	state->lastRequest = {};
	state->lastKey = { MaterialProgramMode::SingleTexture, GLX_MATERIAL_FEATURE_NONE };
	GLX_Material_SetLastError( state, "" );
}

static void GLX_Material_PrintObjectLog( const MaterialState &state, GLuint object, qboolean program, printParm_t printLevel )
{
	GLint length = 0;
	GLsizei written = 0;
	char smallLog[1024];
	char *log = smallLog;

	if ( program ) {
		state.fns.GetProgramiv( object, GL_INFO_LOG_LENGTH, &length );
	} else {
		state.fns.GetShaderiv( object, GL_INFO_LOG_LENGTH, &length );
	}

	if ( length <= 1 ) {
		return;
	}

	if ( length > static_cast<GLint>( sizeof( smallLog ) ) ) {
		log = static_cast<char *>( RI().Malloc( static_cast<size_t>( length ) ) );
		if ( !log ) {
			return;
		}
	}

	if ( program ) {
		state.fns.GetProgramInfoLog( object, length, &written, log );
	} else {
		state.fns.GetShaderInfoLog( object, length, &written, log );
	}
	log[length - 1] = '\0';

	RI().Printf( printLevel, "%s\n", log );

	if ( log != smallLog ) {
		RI().Free( log );
	}
}

static qboolean GLX_Material_ModeForRequest( const MaterialRequest &request, MaterialProgramMode *mode )
{
	return GLX_Material_ModeForInputs( request.flags, request.materialCombine, request.fogPass, mode );
}

static unsigned int GLX_Material_FeaturesForRequest( const MaterialRequest &request )
{
	return GLX_Material_FeaturesForInputs( request.flags, request.texMods0, request.texMods1, request.fogPass );
}

static qboolean GLX_Material_KeyForRequest( const MaterialRequest &request, MaterialProgramKey *key )
{
	MaterialProgramMode mode;

	if ( !key || !GLX_Material_ModeForRequest( request, &mode ) ) {
		return qfalse;
	}

	key->mode = mode;
	key->features = GLX_Material_FeaturesForRequest( request );
	if ( !GLX_Material_FeaturesAllowedForMode( key->mode, key->features ) ) {
		return qfalse;
	}
	return qtrue;
}

static void GLX_Material_FragmentSource( const MaterialProgramKey &key, char *out, size_t outSize )
{
	const char *body = "";

	switch ( key.mode ) {
	case MaterialProgramMode::SingleTexture:
	case MaterialProgramMode::Fog:
		body =
			"    vec4 base = texture2D(u_Texture0, v_TexCoord0);\n"
			"    gl_FragColor = base * v_Color;\n";
		break;
	case MaterialProgramMode::MultiModulate:
		body =
			"    vec4 base = texture2D(u_Texture0, v_TexCoord0) * v_Color;\n"
			"    vec4 layer = texture2D(u_Texture1, v_TexCoord1);\n"
			"    gl_FragColor = base * layer;\n";
		break;
	case MaterialProgramMode::MultiAdd:
		body =
			"    vec4 base = texture2D(u_Texture0, v_TexCoord0) * v_Color;\n"
			"    vec4 layer = texture2D(u_Texture1, v_TexCoord1);\n"
			"    gl_FragColor = min(base + layer, vec4(1.0));\n";
		break;
	case MaterialProgramMode::MultiReplace:
		body =
			"    gl_FragColor = texture2D(u_Texture1, v_TexCoord1);\n";
		break;
	case MaterialProgramMode::MultiDecal:
		body =
			"    vec4 base = texture2D(u_Texture0, v_TexCoord0) * v_Color;\n"
			"    vec4 layer = texture2D(u_Texture1, v_TexCoord1);\n"
			"    gl_FragColor = vec4(mix(base.rgb, layer.rgb, layer.a), base.a);\n";
		break;
	}

	std::snprintf( out, outSize,
		"#version 120\n"
		"#define GLX_MATERIAL_FEATURE_TEXMOD %u\n"
		"#define GLX_MATERIAL_FEATURE_ENVIRONMENT %u\n"
		"#define GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT %u\n"
		"uniform sampler2D u_Texture0;\n"
		"uniform sampler2D u_Texture1;\n"
		"varying vec4 v_Color;\n"
		"varying vec2 v_TexCoord0;\n"
		"varying vec2 v_TexCoord1;\n"
		"void main(void)\n"
		"{\n"
		"%s"
		"}\n",
		( key.features & GLX_MATERIAL_FEATURE_TEXMOD ) ? 1u : 0u,
		( key.features & GLX_MATERIAL_FEATURE_ENVIRONMENT ) ? 1u : 0u,
		( key.features & GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT ) ? 1u : 0u,
		body );
	out[outSize - 1] = '\0';
}

static GLuint GLX_Material_CompileShader( MaterialState *state, GLenum shaderType, const char *source )
{
	GLuint shader;
	GLint ok = 0;
	const GLchar *sources[1];

	if ( !state || !source ) {
		return 0;
	}

	shader = state->fns.CreateShader( shaderType );
	if ( !shader ) {
		GLX_Material_SetLastError( state, "glCreateShader returned 0" );
		return 0;
	}

	sources[0] = source;
	state->fns.ShaderSource( shader, 1, sources, nullptr );
	state->fns.CompileShader( shader );
	state->fns.GetShaderiv( shader, GL_COMPILE_STATUS, &ok );

	if ( !ok ) {
		state->compileFailures++;
		GLX_Material_SetLastError( state, shaderType == GL_VERTEX_SHADER ? "vertex shader compile failed" : "fragment shader compile failed" );
		RI().Printf( PRINT_WARNING, "GLx material %s shader compile failed:\n",
			shaderType == GL_VERTEX_SHADER ? "vertex" : "fragment" );
		GLX_Material_PrintObjectLog( *state, shader, qfalse, PRINT_WARNING );
		if ( state->r_glxMaterialDebug && state->r_glxMaterialDebug->integer > 1 ) {
			RI().Printf( PRINT_ALL, "%s\n", source );
		}
		state->fns.DeleteShader( shader );
		return 0;
	}

	return shader;
}

static void GLX_Material_DeleteProgram( MaterialState *state, MaterialProgram *program )
{
	if ( !state || !program ) {
		return;
	}

	if ( program->program && state->currentProgram == program->program && state->fns.UseProgram ) {
		state->fns.UseProgram( 0 );
		state->currentProgram = 0;
	}
	if ( program->program && state->fns.DeleteProgram ) {
		state->fns.DeleteProgram( program->program );
	}
	if ( program->vertexShader && state->fns.DeleteShader ) {
		state->fns.DeleteShader( program->vertexShader );
	}
	if ( program->fragmentShader && state->fns.DeleteShader ) {
		state->fns.DeleteShader( program->fragmentShader );
	}

	*program = {};
}

static void GLX_Material_ResetRuntime( MaterialState *state, qboolean deletePrograms )
{
	qboolean canDeletePrograms;

	if ( !state ) {
		return;
	}

	canDeletePrograms = deletePrograms && state->fns.DeleteProgram && state->fns.DeleteShader ? qtrue : qfalse;

	if ( state->programCount > 0 && !canDeletePrograms ) {
		state->contextlessDeletes += static_cast<unsigned int>( state->programCount );
	}

	if ( canDeletePrograms ) {
		for ( int i = 0; i < state->programCount; i++ ) {
			GLX_Material_DeleteProgram( state, &state->programs[i] );
		}
	} else {
		state->currentProgram = 0;
		for ( int i = 0; i < state->programCount; i++ ) {
			state->programs[i] = {};
		}
	}

	for ( int i = state->programCount; i < GLX_MATERIAL_PROGRAM_LIMIT; i++ ) {
		state->programs[i] = {};
	}

	state->fns = {};
	state->programCount = 0;
	state->currentProgram = 0;
	state->ready = qfalse;
	GLX_Material_SetReason( state, "not initialized" );
}

static MaterialProgram *GLX_Material_FindProgram( MaterialState *state, const MaterialProgramKey &key )
{
	if ( !state ) {
		return nullptr;
	}

	for ( int i = 0; i < state->programCount; i++ ) {
		if ( state->programs[i].valid && GLX_Material_KeyEquals( state->programs[i].key, key ) ) {
			state->cacheHits++;
			return &state->programs[i];
		}
	}

	state->cacheMisses++;
	return nullptr;
}

static void GLX_Material_LabelProgram( MaterialState *state, MaterialProgram *program )
{
	char label[64];
	char keyName[64];

	if ( !state || !program || !program->program || !state->fns.ObjectLabel ) {
		return;
	}

	GLX_Material_KeyName( program->key, keyName, sizeof( keyName ) );
	std::snprintf( label, sizeof( label ), "GLx material %s", keyName );
	label[sizeof( label ) - 1] = '\0';
	state->fns.ObjectLabel( GL_PROGRAM, program->program, static_cast<GLsizei>( -1 ), label );
	state->debugLabels++;
}

static MaterialProgram *GLX_Material_CreateProgram( MaterialState *state, const MaterialProgramKey &key )
{
	char fragmentSource[2048];
	char keyName[64];
	MaterialProgram *program;
	GLint ok = 0;

	if ( !state ) {
		return nullptr;
	}

	if ( state->programCount >= GLX_MATERIAL_PROGRAM_LIMIT ) {
		state->programLimitSkips++;
		GLX_Material_SetLastError( state, "material program cache is full" );
		return nullptr;
	}

	state->compileAttempts++;
	program = &state->programs[state->programCount];
	*program = {};
	program->key = key;
	GLX_Material_KeyName( key, keyName, sizeof( keyName ) );

	GLX_Material_FragmentSource( key, fragmentSource, sizeof( fragmentSource ) );
	program->vertexShader = GLX_Material_CompileShader( state, GL_VERTEX_SHADER, GLX_Material_VertexSource() );
	program->fragmentShader = GLX_Material_CompileShader( state, GL_FRAGMENT_SHADER, fragmentSource );
	if ( !program->vertexShader || !program->fragmentShader ) {
		GLX_Material_DeleteProgram( state, program );
		return nullptr;
	}

	program->program = state->fns.CreateProgram();
	if ( !program->program ) {
		GLX_Material_SetLastError( state, "glCreateProgram returned 0" );
		GLX_Material_DeleteProgram( state, program );
		return nullptr;
	}

	state->fns.AttachShader( program->program, program->vertexShader );
	state->fns.AttachShader( program->program, program->fragmentShader );
	state->fns.LinkProgram( program->program );
	state->fns.GetProgramiv( program->program, GL_LINK_STATUS, &ok );

	if ( !ok ) {
		state->linkFailures++;
		GLX_Material_SetLastError( state, "program link failed" );
		RI().Printf( PRINT_WARNING, "GLx material program link failed for %s:\n", keyName );
		GLX_Material_PrintObjectLog( *state, program->program, qtrue, PRINT_WARNING );
		GLX_Material_DeleteProgram( state, program );
		return nullptr;
	}

	program->texture0Uniform = state->fns.GetUniformLocation( program->program, "u_Texture0" );
	program->texture1Uniform = state->fns.GetUniformLocation( program->program, "u_Texture1" );
	state->fns.UseProgram( program->program );
	if ( program->texture0Uniform >= 0 ) {
		state->fns.Uniform1i( program->texture0Uniform, 0 );
	}
	if ( program->texture1Uniform >= 0 ) {
		state->fns.Uniform1i( program->texture1Uniform, 1 );
	}
	state->fns.UseProgram( 0 );
	state->currentProgram = 0;

	program->valid = qtrue;
	GLX_Material_LabelProgram( state, program );
	state->programCount++;
	GLX_Material_SetLastError( state, "" );

	if ( state->r_glxMaterialDebug && state->r_glxMaterialDebug->integer ) {
		RI().Printf( PRINT_ALL, "GLx material compiled %s program %u.\n",
			keyName, program->program );
	}

	return program;
}

static qboolean GLX_Material_PrecachePrograms( MaterialState *state )
{
	qboolean ok = qtrue;
	const size_t modeCount = sizeof( kMaterialPrecacheModes ) / sizeof( kMaterialPrecacheModes[0] );

	if ( !state ) {
		return qfalse;
	}

	state->precacheAttempts++;
	for ( size_t i = 0; i < modeCount; i++ ) {
		const MaterialProgramMode mode = kMaterialPrecacheModes[i];
		const unsigned int *features = kMaterialPrecacheFeatures;
		size_t featureCount = sizeof( kMaterialPrecacheFeatures ) / sizeof( kMaterialPrecacheFeatures[0] );

		if ( mode == MaterialProgramMode::SingleTexture ) {
			features = kMaterialPrecacheSingleTextureFeatures;
			featureCount = sizeof( kMaterialPrecacheSingleTextureFeatures ) /
				sizeof( kMaterialPrecacheSingleTextureFeatures[0] );
		} else if ( mode == MaterialProgramMode::Fog ) {
			featureCount = 1u;
		}

		for ( size_t featureIndex = 0; featureIndex < featureCount; featureIndex++ ) {
			MaterialProgramKey key { mode, features[featureIndex] };
			MaterialProgram *program = GLX_Material_FindProgram( state, key );

			if ( !program ) {
				program = GLX_Material_CreateProgram( state, key );
			}
			if ( !program || !program->valid ) {
				ok = qfalse;
			}
		}
	}

	if ( !ok ) {
		state->precacheFailures++;
	}

	return ok;
}

void GLX_Material_RegisterCvars( MaterialState *state )
{
	if ( !state ) {
		return;
	}

	state->r_glxMaterialRenderer = RI().Cvar_Get( "r_glxMaterialRenderer", "1", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxMaterialRenderer,
		"Use the independent GLx GLSL material renderer for GLx streamed draws when available." );

	state->r_glxMaterialDebug = RI().Cvar_Get( "r_glxMaterialDebug", "0", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxMaterialDebug,
		"Print GLx material renderer diagnostics. Set to 2 to also dump failed GLSL source." );

	state->r_glxMaterialPrecache = RI().Cvar_Get( "r_glxMaterialPrecache", "1", CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxMaterialPrecache,
		"Compile all GLx GLSL material programs during OpenGL startup so the material path fails closed." );
}

void GLX_Material_OnOpenGLReady( MaterialState *state, const Capabilities &caps )
{
	const GLubyte *version;
	PFNGLXGETSTRINGPROC GetString;

	if ( !state ) {
		return;
	}

	GLX_Material_Shutdown( state, qtrue );
	GLX_Material_ResetCounters( state );
	GLX_Material_SetReason( state, "not initialized" );
	state->lastKey = { MaterialProgramMode::SingleTexture, GLX_MATERIAL_FEATURE_NONE };

	GetString = reinterpret_cast<PFNGLXGETSTRINGPROC>( GLX_Material_GetProc( "glGetString" ) );
	version = GetString ? GetString( GL_SHADING_LANGUAGE_VERSION ) : nullptr;
	std::snprintf( state->glslVersion, sizeof( state->glslVersion ), "%s", version ? reinterpret_cast<const char *>( version ) : "unknown" );
	state->glslVersion[sizeof( state->glslVersion ) - 1] = '\0';

	if ( caps.tier == CapabilityTier::BelowFloor ) {
		GLX_Material_SetReason( state, "OpenGL version is below GLx shader floor" );
		return;
	}

	GLX_Material_LoadFunctions( state );
	if ( !GLX_Material_FunctionsReady( *state ) ) {
		GLX_Material_SetReason( state, "required GLSL program functions are unavailable" );
		return;
	}

	state->ready = qtrue;
	if ( ( !state->r_glxMaterialPrecache || state->r_glxMaterialPrecache->integer ) &&
		!GLX_Material_PrecachePrograms( state ) ) {
		state->ready = qfalse;
		GLX_Material_SetReason( state, "GLSL material program precache failed" );
		return;
	}

	GLX_Material_SetReason( state, "GLSL material program path ready" );
}

void GLX_Material_Shutdown( MaterialState *state, qboolean deletePrograms )
{
	if ( !state ) {
		return;
	}

	GLX_Material_ResetRuntime( state, deletePrograms );
}

void GLX_Material_FrameComplete( MaterialState *state )
{
	if ( state ) {
		state->frames++;
	}
}

qboolean GLX_Material_Active( const MaterialState &state )
{
	return state.ready && state.r_glxMaterialRenderer && state.r_glxMaterialRenderer->integer ? qtrue : qfalse;
}

qboolean GLX_Material_BindStage( MaterialState *state, const MaterialRequest &request )
{
	MaterialProgramKey key;
	MaterialProgram *program;

	if ( !state ) {
		return qfalse;
	}

	state->bindAttempts++;
	state->lastRequest = request;

	if ( !state->r_glxMaterialRenderer || !state->r_glxMaterialRenderer->integer ) {
		state->disabledSkips++;
		return qfalse;
	}
	if ( !state->ready ) {
		state->notReadySkips++;
		return qfalse;
	}
	if ( !GLX_Material_KeyForRequest( request, &key ) ) {
		state->unsupportedRequests++;
		GLX_Material_SetLastError( state, "unsupported material request" );
		return qfalse;
	}

	state->lastKey = key;
	program = GLX_Material_FindProgram( state, key );
	if ( !program ) {
		program = GLX_Material_CreateProgram( state, key );
	}
	if ( !program || !program->valid ) {
		state->bindFailures++;
		if ( !state->lastError[0] ) {
			GLX_Material_SetLastError( state, "material program unavailable" );
		}
		return qfalse;
	}

	if ( state->currentProgram != program->program ) {
		state->fns.UseProgram( program->program );
		state->currentProgram = program->program;
		state->programSwitches++;
	}

	program->binds++;
	state->binds++;
	GLX_Material_SetLastError( state, "" );
	return qtrue;
}

qboolean GLX_Material_BindFog( MaterialState *state )
{
	MaterialRequest request {};

	request.fogPass = qtrue;
	return GLX_Material_BindStage( state, request );
}

void GLX_Material_Unbind( MaterialState *state )
{
	if ( !state || !state->currentProgram || !state->fns.UseProgram ) {
		return;
	}

	state->fns.UseProgram( 0 );
	state->currentProgram = 0;
	state->unbinds++;
}

const char *GLX_Material_ModeName( MaterialProgramMode mode )
{
	switch ( mode ) {
	case MaterialProgramMode::SingleTexture:
		return "single";
	case MaterialProgramMode::MultiModulate:
		return "multi-modulate";
	case MaterialProgramMode::MultiAdd:
		return "multi-add";
	case MaterialProgramMode::MultiReplace:
		return "multi-replace";
	case MaterialProgramMode::MultiDecal:
		return "multi-decal";
	case MaterialProgramMode::Fog:
		return "fog";
	default:
		return "unknown";
	}
}

void GLX_Material_PrintInfo( const MaterialState &state )
{
	char lastKeyName[64];

	GLX_Material_KeyName( state.lastKey, lastKeyName, sizeof( lastKeyName ) );

	RI().Printf( PRINT_ALL, "  material renderer: %s, ready %s, GLSL %s\n",
		state.r_glxMaterialRenderer && state.r_glxMaterialRenderer->integer ? "enabled" : "disabled",
		BoolName( state.ready ), state.glslVersion[0] ? state.glslVersion : "unknown" );
	RI().Printf( PRINT_ALL, "  material reason: %s\n", state.reason[0] ? state.reason : "none" );
	RI().Printf( PRINT_ALL, "  material programs: %i/%i, attempts %u, binds %u, switches %u, unbinds %u, cache %u hits/%u misses\n",
		state.programCount, GLX_MATERIAL_PROGRAM_LIMIT, state.bindAttempts, state.binds,
		state.programSwitches, state.unbinds, state.cacheHits, state.cacheMisses );
	RI().Printf( PRINT_ALL, "  material compiles: %u attempts, %u compile failures, %u link failures, precache %u/%u, bind failures %u, labels %u\n",
		state.compileAttempts, state.compileFailures, state.linkFailures,
		state.precacheFailures, state.precacheAttempts, state.bindFailures, state.debugLabels );
	RI().Printf( PRINT_ALL, "  material fallbacks: unsupported %u, disabled %u, not-ready %u, full %u, discarded without GL delete %u\n",
		state.unsupportedRequests, state.disabledSkips, state.notReadySkips,
		state.programLimitSkips, state.contextlessDeletes );
	RI().Printf( PRINT_ALL, "  material last key: %s, flags 0x%x, state 0x%x, rgb %i alpha %i tc %i/%i texmods %i/%i combine %i fog %s\n",
		lastKeyName, state.lastRequest.flags, state.lastRequest.stateBits,
		state.lastRequest.rgbGen, state.lastRequest.alphaGen, state.lastRequest.tcGen0,
		state.lastRequest.tcGen1, state.lastRequest.texMods0, state.lastRequest.texMods1,
		state.lastRequest.materialCombine, BoolName( state.lastRequest.fogPass ) );
	if ( state.lastError[0] ) {
		RI().Printf( PRINT_ALL, "  material last error: %s\n", state.lastError );
	}

	for ( int i = 0; i < state.programCount; i++ ) {
		const MaterialProgram &program = state.programs[i];
		char keyName[64];

		if ( !program.valid ) {
			continue;
		}
		GLX_Material_KeyName( program.key, keyName, sizeof( keyName ) );
		RI().Printf( PRINT_ALL, "    program %u: %s, binds %u\n",
			program.program, keyName, program.binds );
	}
}

} // namespace glx
