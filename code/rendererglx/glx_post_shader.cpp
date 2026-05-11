#include "glx_post_shader.h"
#include "glx_color_math.h"

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
#ifndef GL_PROGRAM
#define GL_PROGRAM 0x82E2
#endif

namespace glx {

static void GLX_PostShader_SetReason( PostShaderState *state, const char *reason )
{
	if ( !state ) {
		return;
	}

	std::snprintf( state->reason, sizeof( state->reason ), "%s", reason ? reason : "" );
	state->reason[sizeof( state->reason ) - 1] = '\0';
}

static void GLX_PostShader_SetLastError( PostShaderState *state, const char *error )
{
	if ( !state ) {
		return;
	}

	std::snprintf( state->lastError, sizeof( state->lastError ), "%s", error ? error : "" );
	state->lastError[sizeof( state->lastError ) - 1] = '\0';
}

static void *GLX_PostShader_GetProc( const char *name )
{
	return RI().GL_GetProcAddress ? RI().GL_GetProcAddress( name ) : nullptr;
}

static void GLX_PostShader_LoadFunctions( PostShaderState *state )
{
	if ( !state ) {
		return;
	}

	state->fns.CreateShader = reinterpret_cast<PFNGLXPOSTCREATESHADERPROC>(
		GLX_PostShader_GetProc( "glCreateShader" ) );
	state->fns.ShaderSource = reinterpret_cast<PFNGLXPOSTSHADERSOURCEPROC>(
		GLX_PostShader_GetProc( "glShaderSource" ) );
	state->fns.CompileShader = reinterpret_cast<PFNGLXPOSTCOMPILESHADERPROC>(
		GLX_PostShader_GetProc( "glCompileShader" ) );
	state->fns.GetShaderiv = reinterpret_cast<PFNGLXPOSTGETSHADERIVPROC>(
		GLX_PostShader_GetProc( "glGetShaderiv" ) );
	state->fns.GetShaderInfoLog = reinterpret_cast<PFNGLXPOSTGETSHADERINFOLOGPROC>(
		GLX_PostShader_GetProc( "glGetShaderInfoLog" ) );
	state->fns.CreateProgram = reinterpret_cast<PFNGLXPOSTCREATEPROGRAMPROC>(
		GLX_PostShader_GetProc( "glCreateProgram" ) );
	state->fns.AttachShader = reinterpret_cast<PFNGLXPOSTATTACHSHADERPROC>(
		GLX_PostShader_GetProc( "glAttachShader" ) );
	state->fns.LinkProgram = reinterpret_cast<PFNGLXPOSTLINKPROGRAMPROC>(
		GLX_PostShader_GetProc( "glLinkProgram" ) );
	state->fns.GetProgramiv = reinterpret_cast<PFNGLXPOSTGETPROGRAMIVPROC>(
		GLX_PostShader_GetProc( "glGetProgramiv" ) );
	state->fns.GetProgramInfoLog = reinterpret_cast<PFNGLXPOSTGETPROGRAMINFOLOGPROC>(
		GLX_PostShader_GetProc( "glGetProgramInfoLog" ) );
	state->fns.UseProgram = reinterpret_cast<PFNGLXPOSTUSEPROGRAMPROC>(
		GLX_PostShader_GetProc( "glUseProgram" ) );
	state->fns.GetUniformLocation = reinterpret_cast<PFNGLXPOSTGETUNIFORMLOCATIONPROC>(
		GLX_PostShader_GetProc( "glGetUniformLocation" ) );
	state->fns.Uniform1i = reinterpret_cast<PFNGLXPOSTUNIFORM1IPROC>(
		GLX_PostShader_GetProc( "glUniform1i" ) );
	state->fns.Uniform4f = reinterpret_cast<PFNGLXPOSTUNIFORM4FPROC>(
		GLX_PostShader_GetProc( "glUniform4f" ) );
	state->fns.DeleteProgram = reinterpret_cast<PFNGLXPOSTDELETEPROGRAMPROC>(
		GLX_PostShader_GetProc( "glDeleteProgram" ) );
	state->fns.DeleteShader = reinterpret_cast<PFNGLXPOSTDELETESHADERPROC>(
		GLX_PostShader_GetProc( "glDeleteShader" ) );
	state->fns.ObjectLabel = reinterpret_cast<PFNGLXPOSTOBJECTLABELPROC>(
		GLX_PostShader_GetProc( "glObjectLabel" ) );
}

static qboolean GLX_PostShader_FunctionsReady( const PostShaderState &state )
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
		state.fns.Uniform4f &&
		state.fns.DeleteProgram &&
		state.fns.DeleteShader ? qtrue : qfalse;
}

static void GLX_PostShader_ResetCounters( PostShaderState *state )
{
	if ( !state ) {
		return;
	}

	state->frames = 0;
	state->plansObserved = 0;
	state->validPlansObserved = 0;
	state->invalidPlansObserved = 0;
	state->cacheHits = 0;
	state->cacheMisses = 0;
	state->compileAttempts = 0;
	state->compileFailures = 0;
	state->linkFailures = 0;
	state->sourceFailures = 0;
	state->programLimitSkips = 0;
	state->precacheAttempts = 0;
	state->precacheFailures = 0;
	state->debugLabels = 0;
	state->contextlessDeletes = 0;
	state->directFinalCandidates = 0;
	state->directFinalEligibleFrames = 0;
	state->directFinalAttempts = 0;
	state->directFinalBinds = 0;
	state->directFinalFallbacks = 0;
	state->directFinalRejects = 0;
	state->directFinalProgramMisses = 0;
	state->directFinalUniformFailures = 0;
	state->lastPlanHash = 0;
	state->lastFeatureMask = 0;
	state->lastSourceHash = 0;
	state->lastProgram = 0;
	state->lastDirectFinalRejectMask = GLX_POST_SHADER_DIRECT_REJECT_NONE;
	state->lastSource = {};
	state->lastPlanValid = qfalse;
	state->lastDirectFinalEligible = qfalse;
	state->lastDirectFinalBound = qfalse;
	GLX_PostShader_SetLastError( state, "" );
}

static void GLX_PostShader_PrintObjectLog( const PostShaderState &state, GLuint object,
	qboolean program, printParm_t printLevel )
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

static GLuint GLX_PostShader_CompileShader( PostShaderState *state, GLenum shaderType,
	const char *source )
{
	GLuint shader;
	GLint ok = 0;
	const GLchar *sources[1];

	if ( !state || !source ) {
		return 0;
	}

	shader = state->fns.CreateShader( shaderType );
	if ( !shader ) {
		GLX_PostShader_SetLastError( state, "glCreateShader returned 0" );
		return 0;
	}

	sources[0] = source;
	state->fns.ShaderSource( shader, 1, sources, nullptr );
	state->fns.CompileShader( shader );
	state->fns.GetShaderiv( shader, GL_COMPILE_STATUS, &ok );

	if ( !ok ) {
		state->compileFailures++;
		GLX_PostShader_SetLastError( state,
			shaderType == GL_VERTEX_SHADER ? "vertex shader compile failed" :
			"fragment shader compile failed" );
		RI().Printf( PRINT_WARNING, "GLx post %s shader compile failed:\n",
			shaderType == GL_VERTEX_SHADER ? "vertex" : "fragment" );
		GLX_PostShader_PrintObjectLog( *state, shader, qfalse, PRINT_WARNING );
		if ( state->r_glxPostShaderDebug && state->r_glxPostShaderDebug->integer > 1 ) {
			RI().Printf( PRINT_ALL, "%s\n", source );
		}
		state->fns.DeleteShader( shader );
		return 0;
	}

	return shader;
}

static void GLX_PostShader_DeleteProgram( PostShaderState *state, PostShaderProgram *program )
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

static void GLX_PostShader_ResetRuntime( PostShaderState *state, qboolean deletePrograms )
{
	qboolean canDeletePrograms;

	if ( !state ) {
		return;
	}

	canDeletePrograms = deletePrograms && state->fns.DeleteProgram &&
		state->fns.DeleteShader ? qtrue : qfalse;

	if ( state->programCount > 0 && !canDeletePrograms ) {
		state->contextlessDeletes += static_cast<unsigned int>( state->programCount );
	}

	if ( canDeletePrograms ) {
		for ( int i = 0; i < state->programCount; i++ ) {
			GLX_PostShader_DeleteProgram( state, &state->programs[i] );
		}
	} else {
		state->currentProgram = 0;
		for ( int i = 0; i < state->programCount; i++ ) {
			state->programs[i] = {};
		}
	}

	for ( int i = state->programCount; i < GLX_POST_SHADER_PROGRAM_LIMIT; i++ ) {
		state->programs[i] = {};
	}

	state->fns = {};
	state->programCount = 0;
	state->currentProgram = 0;
	state->ready = qfalse;
	GLX_PostShader_SetReason( state, "not initialized" );
}

static qboolean GLX_PostShader_SameProgramShape( const PostShaderProgram &program,
	const PostShaderPlan &plan, const PostShaderSourceSummary &source )
{
	return program.valid &&
		program.plan.hash == plan.hash &&
		program.plan.featureMask == plan.featureMask &&
		program.source.sourceHash == source.sourceHash ? qtrue : qfalse;
}

static PostShaderProgram *GLX_PostShader_FindProgram( PostShaderState *state,
	const PostShaderPlan &plan, const PostShaderSourceSummary &source )
{
	if ( !state ) {
		return nullptr;
	}

	for ( int i = 0; i < state->programCount; i++ ) {
		if ( GLX_PostShader_SameProgramShape( state->programs[i], plan, source ) ) {
			state->cacheHits++;
			return &state->programs[i];
		}
	}

	state->cacheMisses++;
	return nullptr;
}

static PostShaderProgram *GLX_PostShader_FindProgramForUse( PostShaderState *state,
	const PostShaderPlan &plan, const PostShaderSourceSummary &source )
{
	if ( !state ) {
		return nullptr;
	}

	for ( int i = 0; i < state->programCount; i++ ) {
		if ( GLX_PostShader_SameProgramShape( state->programs[i], plan, source ) ) {
			return &state->programs[i];
		}
	}

	return nullptr;
}

static void GLX_PostShader_LabelProgram( PostShaderState *state, PostShaderProgram *program )
{
	char label[160];

	if ( !state || !program || !program->program || !state->fns.ObjectLabel ) {
		return;
	}

	std::snprintf( label, sizeof( label ), "GLx post shader 0x%08x features 0x%08x",
		program->source.sourceHash, program->plan.featureMask );
	label[sizeof( label ) - 1] = '\0';
	state->fns.ObjectLabel( GL_PROGRAM, program->program, static_cast<GLsizei>( -1 ), label );
	state->debugLabels++;
}

static PostShaderProgram *GLX_PostShader_CreateProgram( PostShaderState *state,
	const PostShaderPlan &plan, const PostShaderSourceSummary &source )
{
	char vertexSource[GLX_POST_SHADER_VERTEX_SOURCE_BYTES];
	char fragmentSource[GLX_POST_SHADER_FRAGMENT_SOURCE_BYTES];
	PostShaderProgram *program;
	GLint ok = 0;
	int ignoredBytes = 0;

	if ( !state ) {
		return nullptr;
	}

	if ( state->programCount >= GLX_POST_SHADER_PROGRAM_LIMIT ) {
		state->programLimitSkips++;
		GLX_PostShader_SetLastError( state, "post shader program cache is full" );
		return nullptr;
	}

	if ( !plan.valid || !source.valid ) {
		state->sourceFailures++;
		GLX_PostShader_SetLastError( state, "post shader source plan is invalid" );
		return nullptr;
	}

	if ( !GLX_PostShaderSource_WriteVertex( vertexSource, sizeof( vertexSource ), &ignoredBytes ) ||
		!GLX_PostShaderSource_WriteFragment( plan, fragmentSource, sizeof( fragmentSource ), &ignoredBytes ) ) {
		state->sourceFailures++;
		GLX_PostShader_SetLastError( state, "post shader source exceeded generator buffer" );
		return nullptr;
	}

	state->compileAttempts++;
	program = &state->programs[state->programCount];
	*program = {};
	program->plan = plan;
	program->source = source;
	program->sceneUniform = -1;
	program->lutUniform = -1;
	program->postParams0Uniform = -1;
	program->liftUniform = -1;
	program->invGammaUniform = -1;
	program->gainUniform = -1;
	program->whitePoint0Uniform = -1;
	program->whitePoint1Uniform = -1;
	program->whitePoint2Uniform = -1;
	program->lutParamsUniform = -1;

	program->vertexShader = GLX_PostShader_CompileShader( state, GL_VERTEX_SHADER, vertexSource );
	program->fragmentShader = GLX_PostShader_CompileShader( state, GL_FRAGMENT_SHADER, fragmentSource );
	if ( !program->vertexShader || !program->fragmentShader ) {
		GLX_PostShader_DeleteProgram( state, program );
		return nullptr;
	}

	program->program = state->fns.CreateProgram();
	if ( !program->program ) {
		GLX_PostShader_SetLastError( state, "glCreateProgram returned 0" );
		GLX_PostShader_DeleteProgram( state, program );
		return nullptr;
	}

	state->fns.AttachShader( program->program, program->vertexShader );
	state->fns.AttachShader( program->program, program->fragmentShader );
	state->fns.LinkProgram( program->program );
	state->fns.GetProgramiv( program->program, GL_LINK_STATUS, &ok );

	if ( !ok ) {
		state->linkFailures++;
		GLX_PostShader_SetLastError( state, "program link failed" );
		RI().Printf( PRINT_WARNING, "GLx post shader program link failed for source 0x%08x:\n",
			source.sourceHash );
		GLX_PostShader_PrintObjectLog( *state, program->program, qtrue, PRINT_WARNING );
		GLX_PostShader_DeleteProgram( state, program );
		return nullptr;
	}

	program->sceneUniform = state->fns.GetUniformLocation( program->program, "u_Scene" );
	program->lutUniform = state->fns.GetUniformLocation( program->program, "u_ColorGradeLut" );
	program->postParams0Uniform = state->fns.GetUniformLocation( program->program, "u_PostParams0" );
	program->liftUniform = state->fns.GetUniformLocation( program->program, "u_Lift" );
	program->invGammaUniform = state->fns.GetUniformLocation( program->program, "u_InvGamma" );
	program->gainUniform = state->fns.GetUniformLocation( program->program, "u_Gain" );
	program->whitePoint0Uniform = state->fns.GetUniformLocation( program->program, "u_WhitePoint0" );
	program->whitePoint1Uniform = state->fns.GetUniformLocation( program->program, "u_WhitePoint1" );
	program->whitePoint2Uniform = state->fns.GetUniformLocation( program->program, "u_WhitePoint2" );
	program->lutParamsUniform = state->fns.GetUniformLocation( program->program, "u_LutParams" );
	state->fns.UseProgram( program->program );
	if ( program->sceneUniform >= 0 ) {
		state->fns.Uniform1i( program->sceneUniform, 0 );
	}
	if ( program->lutUniform >= 0 ) {
		state->fns.Uniform1i( program->lutUniform, 2 );
	}
	state->fns.UseProgram( 0 );
	state->currentProgram = 0;

	program->valid = qtrue;
	GLX_PostShader_LabelProgram( state, program );
	state->programCount++;
	state->lastProgram = program->program;
	GLX_PostShader_SetLastError( state, "" );

	if ( state->r_glxPostShaderDebug && state->r_glxPostShaderDebug->integer ) {
		RI().Printf( PRINT_ALL,
			"GLx post shader compiled source 0x%08x features 0x%08x program %u.\n",
			source.sourceHash, plan.featureMask, program->program );
	}

	return program;
}

static qboolean GLX_PostShader_CacheProgram( PostShaderState *state,
	const PostShaderPlan &plan )
{
	const PostShaderSourceSummary source = GLX_PostShaderSource_BuildSummary( plan );
	PostShaderProgram *program;

	if ( !state ) {
		return qfalse;
	}

	state->lastPlanHash = plan.hash;
	state->lastFeatureMask = plan.featureMask;
	state->lastSource = source;
	state->lastSourceHash = source.sourceHash;
	state->lastPlanValid = plan.valid;

	if ( !plan.valid ) {
		state->invalidPlansObserved++;
		return qfalse;
	}
	state->validPlansObserved++;

	if ( !source.valid ) {
		state->sourceFailures++;
		GLX_PostShader_SetLastError( state, source.truncated ?
			"post shader source was truncated" : "post shader source invalid" );
		return qfalse;
	}

	program = GLX_PostShader_FindProgram( state, plan, source );
	if ( !program ) {
		program = GLX_PostShader_CreateProgram( state, plan, source );
	}
	if ( !program ) {
		return qfalse;
	}

	program->uses++;
	state->lastProgram = program->program;
	return qtrue;
}

static unsigned int GLX_PostShader_DirectFinalCompatibilityRejectMask(
	const PostShaderPlan &plan, const OutputTransform &output, float greyscale )
{
	unsigned int rejectMask = GLX_POST_SHADER_DIRECT_REJECT_NONE;

	if ( !plan.valid || !GLX_RenderIR_ValidateOutputTransform( output ) ) {
		rejectMask |= GLX_POST_SHADER_DIRECT_REJECT_INVALID_PLAN;
	}
	if ( !plan.key.sceneLinear ||
		output.sceneColorSpace != SceneColorSpace::SceneLinear ||
		output.hdrMode <= 0 ) {
		rejectMask |= GLX_POST_SHADER_DIRECT_REJECT_NOT_SCENE_LINEAR;
	}
	if ( plan.key.transfer != OutputTransfer::SdrSrgb ||
		output.transfer != OutputTransfer::SdrSrgb ) {
		rejectMask |= GLX_POST_SHADER_DIRECT_REJECT_TRANSFER;
	}
	if ( plan.key.outputPrimaries != OutputPrimaries::SrgbBt709 ||
		output.outputPrimaries != OutputPrimaries::SrgbBt709 ||
		plan.key.gamutMap != GamutMapMode::None ||
		output.gamutMap != GamutMapMode::None ) {
		rejectMask |= GLX_POST_SHADER_DIRECT_REJECT_OUTPUT_COLORIMETRY;
	}
	if ( greyscale > 0.0f || greyscale < 0.0f ) {
		rejectMask |= GLX_POST_SHADER_DIRECT_REJECT_GREYSCALE;
	}

	return rejectMask;
}

static void GLX_PostShader_Identity3x3( float matrix[9] )
{
	if ( !matrix ) {
		return;
	}
	matrix[0] = 1.0f; matrix[1] = 0.0f; matrix[2] = 0.0f;
	matrix[3] = 0.0f; matrix[4] = 1.0f; matrix[5] = 0.0f;
	matrix[6] = 0.0f; matrix[7] = 0.0f; matrix[8] = 1.0f;
}

static qboolean GLX_PostShader_SetOptionalVec4( PostShaderState *state,
	PostShaderProgram *program, GLint location, float x, float y, float z, float w,
	unsigned int requiredFeature )
{
	if ( !state || !program || !state->fns.Uniform4f ) {
		return qfalse;
	}
	if ( location < 0 ) {
		return ( program->plan.featureMask & requiredFeature ) != 0u ? qfalse : qtrue;
	}
	state->fns.Uniform4f( location, x, y, z, w );
	return qtrue;
}

static qboolean GLX_PostShader_SetDirectFinalUniforms( PostShaderState *state,
	PostShaderProgram *program, const OutputTransform &output )
{
	float whitePointMatrix[9];
	const qboolean lgg = GLX_PostShader_GradeUsesLiftGammaGain( output.grade );
	const qboolean lut = GLX_PostShader_LutActive( output );
	const float invGamma0 = output.gradeGamma[0] > 0.0001f ?
		1.0f / output.gradeGamma[0] : 1.0f;
	const float invGamma1 = output.gradeGamma[1] > 0.0001f ?
		1.0f / output.gradeGamma[1] : 1.0f;
	const float invGamma2 = output.gradeGamma[2] > 0.0001f ?
		1.0f / output.gradeGamma[2] : 1.0f;

	if ( !state || !program || !state->fns.Uniform4f ) {
		return qfalse;
	}
	if ( program->postParams0Uniform < 0 ) {
		GLX_PostShader_SetLastError( state, "post shader direct final missing u_PostParams0" );
		return qfalse;
	}
	if ( lut && program->lutUniform < 0 ) {
		GLX_PostShader_SetLastError( state, "post shader direct final missing u_ColorGradeLut" );
		return qfalse;
	}

	state->fns.Uniform4f( program->postParams0Uniform, output.exposure,
		output.paperWhiteNits, output.maxOutputNits, 0.0f );
	if ( lgg && output.whitePointSourceKelvin != output.whitePointTargetKelvin ) {
		GLX_ColorMath_BuildBradfordAdaptationMatrix( output.whitePointSourceKelvin,
			output.whitePointTargetKelvin, whitePointMatrix );
	} else {
		GLX_PostShader_Identity3x3( whitePointMatrix );
	}
	if ( !GLX_PostShader_SetOptionalVec4( state, program, program->liftUniform,
		output.gradeLift[0], output.gradeLift[1], output.gradeLift[2], 0.0f,
		GLX_POST_SHADER_FEATURE_LIFT_GAMMA_GAIN ) ||
		!GLX_PostShader_SetOptionalVec4( state, program, program->invGammaUniform,
		invGamma0, invGamma1, invGamma2, 1.0f,
		GLX_POST_SHADER_FEATURE_LIFT_GAMMA_GAIN ) ||
		!GLX_PostShader_SetOptionalVec4( state, program, program->gainUniform,
		output.gradeGain[0], output.gradeGain[1], output.gradeGain[2], 1.0f,
		GLX_POST_SHADER_FEATURE_LIFT_GAMMA_GAIN ) ||
		!GLX_PostShader_SetOptionalVec4( state, program, program->whitePoint0Uniform,
		whitePointMatrix[0], whitePointMatrix[1], whitePointMatrix[2], 0.0f,
		GLX_POST_SHADER_FEATURE_WHITE_POINT ) ||
		!GLX_PostShader_SetOptionalVec4( state, program, program->whitePoint1Uniform,
		whitePointMatrix[3], whitePointMatrix[4], whitePointMatrix[5], 0.0f,
		GLX_POST_SHADER_FEATURE_WHITE_POINT ) ||
		!GLX_PostShader_SetOptionalVec4( state, program, program->whitePoint2Uniform,
		whitePointMatrix[6], whitePointMatrix[7], whitePointMatrix[8], 0.0f,
		GLX_POST_SHADER_FEATURE_WHITE_POINT ) ) {
		GLX_PostShader_SetLastError( state, "post shader direct final missing grade uniform" );
		return qfalse;
	}
	if ( lut ) {
		const int lutSize = static_cast<int>( output.lutSize + 0.5f );
		const float lutScale = output.lutScale > 0.0f ? output.lutScale : 4.0f;
		if ( lutSize < 2 ) {
			GLX_PostShader_SetLastError( state, "post shader direct final LUT size is invalid" );
			return qfalse;
		}
		if ( program->lutParamsUniform < 0 ) {
			GLX_PostShader_SetLastError( state, "post shader direct final missing u_LutParams" );
			return qfalse;
		}
		state->fns.Uniform4f( program->lutParamsUniform, lutScale,
			static_cast<float>( lutSize - 1 ), 0.5f, 1.0f / lutScale );
	}
	return qtrue;
}

static qboolean GLX_PostShader_PrecachePrograms( PostShaderState *state )
{
	OutputTransform output;
	PostShaderPlan plan;
	qboolean ok = qtrue;

	if ( !state ) {
		return qfalse;
	}

	state->precacheAttempts++;

	output = GLX_RenderIR_DefaultOutputTransform();
	plan = GLX_PostShader_BuildPlan( output );
	ok = ( GLX_PostShader_CacheProgram( state, plan ) && ok ) ? qtrue : qfalse;

	output.sceneColorSpace = SceneColorSpace::SceneLinear;
	output.hdrMode = 1;
	output.precisionMode = 16;
	output.transfer = OutputTransfer::SdrSrgb;
	output.toneMap = ToneMapOperator::Aces;
	output.grade = ColorGradeMode::None;
	plan = GLX_PostShader_BuildPlan( output );
	ok = ( GLX_PostShader_CacheProgram( state, plan ) && ok ) ? qtrue : qfalse;

	output.transfer = OutputTransfer::Hdr10Pq;
	output.outputPrimaries = OutputPrimaries::Bt2020;
	output.gamutMap = GamutMapMode::CompressToOutput;
	output.paperWhiteNits = 203.0f;
	output.maxOutputNits = 1000.0f;
	plan = GLX_PostShader_BuildPlan( output );
	ok = ( GLX_PostShader_CacheProgram( state, plan ) && ok ) ? qtrue : qfalse;

	if ( !ok ) {
		state->precacheFailures++;
	}
	return ok;
}

void GLX_PostShader_RegisterCvars( PostShaderState *state )
{
	if ( !state ) {
		return;
	}

	state->r_glxPostShaderCache = RI().Cvar_Get( "r_glxPostShaderCache", "1",
		CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxPostShaderCache,
		"Compile and cache generated GLx post/output GLSL programs without enabling the owned final-pass executor." );

	state->r_glxPostShaderPrecache = RI().Cvar_Get( "r_glxPostShaderPrecache", "1",
		CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxPostShaderPrecache,
		"Compile representative GLx post/output shader shapes during OpenGL startup." );

	state->r_glxPostShaderExecute = RI().Cvar_Get( "r_glxPostShaderExecute", "0",
		CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxPostShaderExecute,
		"Experimentally bind the generated GLx GLSL shader for eligible scene-linear SDR direct final-pass output, including color grade/LUT uniforms. Falls back to the legacy ARB path when disabled or unsupported." );

	state->r_glxPostShaderDebug = RI().Cvar_Get( "r_glxPostShaderDebug", "0",
		CVAR_ARCHIVE_ND | CVAR_DEVELOPER );
	RI().Cvar_SetDescription( state->r_glxPostShaderDebug,
		"Print GLx post shader cache diagnostics. Set to 2 to also dump failed GLSL source." );
}

void GLX_PostShader_OnOpenGLReady( PostShaderState *state, const Capabilities &caps )
{
	if ( !state ) {
		return;
	}

	GLX_PostShader_Shutdown( state, qtrue );
	GLX_PostShader_ResetCounters( state );
	state->tier = caps.tier;
	GLX_PostShader_SetReason( state, "not initialized" );

	if ( caps.tier == RenderProductTier::GL12 ) {
		GLX_PostShader_SetReason( state, "GL12 fixed-function tier has no GLSL post shader cache" );
		return;
	}

	GLX_PostShader_LoadFunctions( state );
	if ( !GLX_PostShader_FunctionsReady( *state ) ) {
		GLX_PostShader_SetReason( state, "required GLSL program functions are unavailable" );
		return;
	}

	state->ready = qtrue;
	if ( ( !state->r_glxPostShaderPrecache || state->r_glxPostShaderPrecache->integer ) &&
		!GLX_PostShader_PrecachePrograms( state ) ) {
		state->ready = qfalse;
		GLX_PostShader_SetReason( state, "GLSL post shader precache failed" );
		return;
	}

	GLX_PostShader_SetReason( state, "GLSL post shader cache ready" );
}

void GLX_PostShader_Shutdown( PostShaderState *state, qboolean deletePrograms )
{
	if ( !state ) {
		return;
	}

	GLX_PostShader_ResetRuntime( state, deletePrograms );
}

void GLX_PostShader_FrameComplete( PostShaderState *state )
{
	if ( state ) {
		state->frames++;
	}
}

qboolean GLX_PostShader_Ready( const PostShaderState &state )
{
	return state.ready && state.r_glxPostShaderCache &&
		state.r_glxPostShaderCache->integer ? qtrue : qfalse;
}

qboolean GLX_PostShader_RecordPlan( PostShaderState *state, const PostShaderPlan &plan )
{
	if ( !state ) {
		return qfalse;
	}

	state->plansObserved++;
	if ( !GLX_PostShader_Ready( *state ) ) {
		state->lastPlanHash = plan.hash;
		state->lastFeatureMask = plan.featureMask;
		state->lastSource = GLX_PostShaderSource_BuildSummary( plan );
		state->lastSourceHash = state->lastSource.sourceHash;
		state->lastPlanValid = plan.valid;
		if ( plan.valid ) {
			state->validPlansObserved++;
		} else {
			state->invalidPlansObserved++;
		}
		return qfalse;
	}

	return GLX_PostShader_CacheProgram( state, plan );
}

qboolean GLX_PostShader_TryBindDirectFinal( PostShaderState *state,
	const PostShaderPlan &plan, const OutputTransform &output, float greyscale )
{
	PostShaderSourceSummary source;
	PostShaderProgram *program;
	unsigned int rejectMask;

	if ( !state ) {
		return qfalse;
	}

	state->directFinalCandidates++;
	state->lastDirectFinalBound = qfalse;
	rejectMask = GLX_PostShader_DirectFinalCompatibilityRejectMask( plan, output, greyscale );
	if ( !GLX_PostShader_Ready( *state ) ) {
		rejectMask |= GLX_POST_SHADER_DIRECT_REJECT_NOT_READY;
	}

	state->lastDirectFinalEligible = ( rejectMask == GLX_POST_SHADER_DIRECT_REJECT_NONE ) ?
		qtrue : qfalse;
	if ( state->lastDirectFinalEligible ) {
		state->directFinalEligibleFrames++;
	}

	if ( !state->r_glxPostShaderExecute || !state->r_glxPostShaderExecute->integer ) {
		rejectMask |= GLX_POST_SHADER_DIRECT_REJECT_DISABLED;
	}
	if ( rejectMask != GLX_POST_SHADER_DIRECT_REJECT_NONE ) {
		state->lastDirectFinalRejectMask = rejectMask;
		state->directFinalRejects++;
		state->directFinalFallbacks++;
		return qfalse;
	}

	state->directFinalAttempts++;
	source = GLX_PostShaderSource_BuildSummary( plan );
	program = GLX_PostShader_FindProgramForUse( state, plan, source );
	if ( !program ) {
		state->directFinalProgramMisses++;
		program = GLX_PostShader_CreateProgram( state, plan, source );
	}
	if ( !program ) {
		state->lastDirectFinalRejectMask = GLX_POST_SHADER_DIRECT_REJECT_PROGRAM;
		state->directFinalRejects++;
		state->directFinalFallbacks++;
		return qfalse;
	}

	state->fns.UseProgram( program->program );
	state->currentProgram = program->program;
	if ( !GLX_PostShader_SetDirectFinalUniforms( state, program, output ) ) {
		GLX_PostShader_Unbind( state );
		state->lastDirectFinalRejectMask = GLX_POST_SHADER_DIRECT_REJECT_UNIFORM;
		state->directFinalUniformFailures++;
		state->directFinalRejects++;
		state->directFinalFallbacks++;
		return qfalse;
	}

	program->uses++;
	state->lastProgram = program->program;
	state->lastDirectFinalRejectMask = GLX_POST_SHADER_DIRECT_REJECT_NONE;
	state->lastDirectFinalBound = qtrue;
	state->directFinalBinds++;
	GLX_PostShader_SetLastError( state, "" );
	return qtrue;
}

void GLX_PostShader_Unbind( PostShaderState *state )
{
	if ( !state || !state->fns.UseProgram ) {
		return;
	}
	if ( state->currentProgram ) {
		state->fns.UseProgram( 0 );
		state->currentProgram = 0;
	}
}

void GLX_PostShader_PrintInfo( const PostShaderState &state )
{
	RI().Printf( PRINT_ALL,
		"  post shader cache: ready %s, programs %i/%i, plans %u valid/%u invalid, cache %u hits/%u misses, compile %u attempts/%u failures, link failures %u, source failures %u, precache %u/%u failures, labels %u, contextless deletes %u\n",
		BoolName( GLX_PostShader_Ready( state ) ),
		state.programCount, GLX_POST_SHADER_PROGRAM_LIMIT,
		state.validPlansObserved, state.invalidPlansObserved,
		state.cacheHits, state.cacheMisses,
		state.compileAttempts, state.compileFailures,
		state.linkFailures, state.sourceFailures,
		state.precacheAttempts, state.precacheFailures,
		state.debugLabels, state.contextlessDeletes );
	RI().Printf( PRINT_ALL,
		"  post shader source: plan valid %s, features 0x%08x, plan hash 0x%08x, source hash 0x%08x, source valid %s, truncated %s, vertex bytes %i, fragment bytes %i, last program %u, reason: %s\n",
		BoolName( state.lastPlanValid ),
		state.lastFeatureMask,
		state.lastPlanHash,
		state.lastSourceHash,
		BoolName( state.lastSource.valid ),
		BoolName( state.lastSource.truncated ),
		state.lastSource.vertexBytes,
		state.lastSource.fragmentBytes,
		state.lastProgram,
		state.reason[0] ? state.reason : "none" );
	RI().Printf( PRINT_ALL,
		"  post shader direct-final: execute %s, eligible %s, bound %s, reject 0x%08x, candidates %u, eligible frames %u, attempts %u, binds %u, fallbacks %u, rejects %u, program misses %u, uniform failures %u\n",
		BoolName( state.r_glxPostShaderExecute && state.r_glxPostShaderExecute->integer ? qtrue : qfalse ),
		BoolName( state.lastDirectFinalEligible ),
		BoolName( state.lastDirectFinalBound ),
		state.lastDirectFinalRejectMask,
		state.directFinalCandidates,
		state.directFinalEligibleFrames,
		state.directFinalAttempts,
		state.directFinalBinds,
		state.directFinalFallbacks,
		state.directFinalRejects,
		state.directFinalProgramMisses,
		state.directFinalUniformFailures );
	if ( state.lastError[0] ) {
		RI().Printf( PRINT_ALL, "  post shader last error: %s\n", state.lastError );
	}
}

} // namespace glx
