/*
===========================================================================
Copyright (C) 1999-2005 Id Software, Inc.

This file is part of Quake III Arena source code.

Quake III Arena source code is free software; you can redistribute it
and/or modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the License,
or (at your option) any later version.

Quake III Arena source code is distributed in the hope that it will be
useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Quake III Arena source code; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
===========================================================================
*/

#ifndef TR_GLX_COMPAT_H
#define TR_GLX_COMPAT_H

#include "tr_local.h"
#include "../renderercommon/tr_glx_api.h"

#ifdef RENDERER_GLX
#ifndef GL_ARRAY_BUFFER_BINDING_ARB
#define GL_ARRAY_BUFFER_BINDING_ARB 0x8894
#endif
#ifndef GL_ELEMENT_ARRAY_BUFFER_BINDING_ARB
#define GL_ELEMENT_ARRAY_BUFFER_BINDING_ARB 0x8895
#endif
#endif

/*
 * The legacy OpenGL renderer is the temporary compatibility substrate for GLx.
 * Keep module calls behind this facade so legacy draw code does not reach
 * directly into GLx internals as that substrate is carved into explicit pieces.
 * Shared flag and payload vocabulary lives in renderercommon/tr_glx_public.h.
 */

static ID_INLINE int GLX_CompatAlignInt( int value, int alignment )
{
	const int remainder = value % alignment;

	if ( remainder == 0 ) {
		return value;
	}

	return value + alignment - remainder;
}

static ID_INLINE void GLX_CompatSetImports( refimport_t *imports )
{
#ifdef RENDERER_GLX
	GLX_Renderer_SetImports( imports );
#else
	(void)imports;
#endif
}

static ID_INLINE void GLX_CompatRegisterCommands( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RegisterCommands();
#endif
}

static ID_INLINE void GLX_CompatRemoveCommands( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RemoveCommands();
#endif
}

static ID_INLINE void GLX_CompatOnOpenGLReady( const glconfig_t *config, const char *extensions )
{
#ifdef RENDERER_GLX
	GLX_Renderer_OnOpenGLReady( config, extensions );
#else
	(void)config;
	(void)extensions;
#endif
}

static ID_INLINE void GLX_CompatShutdown( refShutdownCode_t code )
{
#ifdef RENDERER_GLX
	GLX_Renderer_Shutdown( code );
#else
	(void)code;
#endif
}

static ID_INLINE void GLX_CompatBeginBackendTimer( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_BeginBackendTimer();
#endif
}

static ID_INLINE void GLX_CompatEndBackendTimer( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_EndBackendTimer();
#endif
}

static ID_INLINE void GLX_CompatFrameComplete( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_FrameComplete();
#endif
}

static ID_INLINE void GLX_CompatPrintFrameCounters( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_PrintFrameCounters();
#endif
}

static ID_INLINE void GLX_CompatRecordDraw( int indexes, int path )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordDraw( indexes, path );
#else
	(void)indexes;
	(void)path;
#endif
}

static ID_INLINE void GLX_CompatRecordShaderBatch( const char *shaderName, int sort,
	int numPasses, int numVertexes, int numIndexes, int flags )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordShaderBatch( shaderName, sort, numPasses, numVertexes, numIndexes, flags );
#else
	(void)shaderName;
	(void)sort;
	(void)numPasses;
	(void)numVertexes;
	(void)numIndexes;
	(void)flags;
#endif
}

static ID_INLINE void GLX_CompatPushShaderDebugGroup( const char *shaderName,
	int numVertexes, int numIndexes, int numPasses )
{
#ifdef RENDERER_GLX
	GLX_Renderer_PushShaderDebugGroup( shaderName, numVertexes, numIndexes, numPasses );
#else
	(void)shaderName;
	(void)numVertexes;
	(void)numIndexes;
	(void)numPasses;
#endif
}

static ID_INLINE void GLX_CompatPopDebugGroup( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_PopDebugGroup();
#endif
}

static ID_INLINE void GLX_CompatShadowUploadTess( int numVertexes, int numIndexes,
	const void *xyz, int xyzBytes, const void *indexes, int indexBytes )
{
#ifdef RENDERER_GLX
	GLX_Renderer_ShadowUploadTess( numVertexes, numIndexes, xyz, xyzBytes, indexes, indexBytes );
#else
	(void)numVertexes;
	(void)numIndexes;
	(void)xyz;
	(void)xyzBytes;
	(void)indexes;
	(void)indexBytes;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamDrawEnabled( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamDrawEnabled();
#else
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamDrawMultitextureEnabled( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamDrawMultitextureEnabled();
#else
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamDrawFogEnabled( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamDrawFogEnabled();
#else
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamDrawDepthFragmentEnabled( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamDrawDepthFragmentEnabled();
#else
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamDrawShadowsEnabled( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamDrawShadowsEnabled();
#else
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamDrawBeamsEnabled( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamDrawBeamsEnabled();
#else
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamDrawPostProcessEnabled( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamDrawPostProcessEnabled();
#else
	return qfalse;
#endif
}

static ID_INLINE void GLX_CompatRecordStreamDrawSkip( int reason )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordStreamDrawSkip( reason );
#else
	(void)reason;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamReserve( int bytes, int alignment,
	glxStreamReservation_t *reservation )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamReserve( bytes, alignment, reservation );
#else
	(void)bytes;
	(void)alignment;
	(void)reservation;
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatStreamUploadAt( glxStreamReservation_t *reservation,
	int relativeOffset, const void *data, int bytes )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamUploadAt( reservation, relativeOffset, data, bytes );
#else
	(void)reservation;
	(void)relativeOffset;
	(void)data;
	(void)bytes;
	return qfalse;
#endif
}

static ID_INLINE void GLX_CompatStreamCommit( glxStreamReservation_t *reservation )
{
#ifdef RENDERER_GLX
	GLX_Renderer_StreamCommit( reservation );
#else
	(void)reservation;
#endif
}

static ID_INLINE void GLX_CompatRecordStreamDrawResult( int numVertexes, int numIndexes,
	int totalBytes, int indexBytes, int texcoord1Bytes, qboolean multitexture,
	qboolean fog, qboolean depthFragment, int materialFlags, qboolean success )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordStreamDrawResult( numVertexes, numIndexes, totalBytes, indexBytes,
		texcoord1Bytes, multitexture, fog, depthFragment, materialFlags, success );
#else
	(void)numVertexes;
	(void)numIndexes;
	(void)totalBytes;
	(void)indexBytes;
	(void)texcoord1Bytes;
	(void)multitexture;
	(void)fog;
	(void)depthFragment;
	(void)materialFlags;
	(void)success;
#endif
}

static ID_INLINE qboolean GLX_CompatTryStreamDrawArrayPass( int vertexCount,
	const void *xyz, int xyzStride, unsigned int primitive, int materialFlags )
{
#ifdef RENDERER_GLX
	glxStreamReservation_t reservation;
	qboolean ok = qtrue;
	int xyzBytes;
	int totalBytes;
	GLint oldArrayBuffer = 0;

	if ( !GLX_CompatStreamDrawEnabled() ) {
		return qfalse;
	}
	if ( !qglBindBufferARB ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_NO_BIND_BUFFER );
		return qfalse;
	}
	if ( vertexCount <= 0 || !xyz || xyzStride <= 0 ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_BAD_INPUT );
		return qfalse;
	}

	xyzBytes = vertexCount * xyzStride;
	totalBytes = GLX_CompatAlignInt( xyzBytes, 64 );

	if ( !GLX_CompatStreamReserve( totalBytes, 64, &reservation ) ) {
		GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
			totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qfalse );
		return qfalse;
	}

	if ( !GLX_CompatStreamUploadAt( &reservation, 0, xyz, xyzBytes ) ) {
		ok = qfalse;
	}
	GLX_CompatStreamCommit( &reservation );

	if ( !ok ) {
		GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
			totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qfalse );
		return qfalse;
	}

	qglGetIntegerv( GL_ARRAY_BUFFER_BINDING_ARB, &oldArrayBuffer );
	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, reservation.buffer );

	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_NONE );
	qglVertexPointer( 3, GL_FLOAT, xyzStride, (const GLvoid *)(intptr_t)( reservation.offset ) );

	GLX_CompatRecordDraw( vertexCount, GLX_DRAW_STREAM_GENERIC );
	qglDrawArrays( primitive, 0, vertexCount );

	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, 0 );
	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_NONE );
	qglVertexPointer( 3, GL_FLOAT, xyzStride, xyz );
	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, (GLuint)oldArrayBuffer );

	GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
		totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qtrue );
	return qtrue;
#else
	(void)vertexCount;
	(void)xyz;
	(void)xyzStride;
	(void)primitive;
	(void)materialFlags;
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatTryStreamDrawArrayTexcoordPass( int vertexCount,
	const void *xyz, int xyzStride, const void *texcoords, int texcoordStride,
	unsigned int primitive, int materialFlags )
{
#ifdef RENDERER_GLX
	glxStreamReservation_t reservation;
	qboolean ok = qtrue;
	int xyzBytes;
	int texcoordElementStride;
	int texcoordBytes;
	int texcoordOffset;
	int totalBytes;
	GLint oldArrayBuffer = 0;

	if ( !GLX_CompatStreamDrawEnabled() ) {
		return qfalse;
	}
	if ( !qglBindBufferARB ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_NO_BIND_BUFFER );
		return qfalse;
	}
	if ( vertexCount <= 0 || !xyz || xyzStride <= 0 || !texcoords || texcoordStride < 0 ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_BAD_INPUT );
		return qfalse;
	}

	xyzBytes = vertexCount * xyzStride;
	texcoordElementStride = texcoordStride > 0 ? texcoordStride : (int)( 2 * sizeof( float ) );
	texcoordBytes = vertexCount * texcoordElementStride;
	texcoordOffset = GLX_CompatAlignInt( xyzBytes, 64 );
	totalBytes = GLX_CompatAlignInt( texcoordOffset + texcoordBytes, 64 );

	if ( !GLX_CompatStreamReserve( totalBytes, 64, &reservation ) ) {
		GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
			totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qfalse );
		return qfalse;
	}

	if ( !GLX_CompatStreamUploadAt( &reservation, 0, xyz, xyzBytes ) ) {
		ok = qfalse;
	}
	if ( !GLX_CompatStreamUploadAt( &reservation, texcoordOffset, texcoords, texcoordBytes ) ) {
		ok = qfalse;
	}
	GLX_CompatStreamCommit( &reservation );

	if ( !ok ) {
		GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
			totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qfalse );
		return qfalse;
	}

	qglGetIntegerv( GL_ARRAY_BUFFER_BINDING_ARB, &oldArrayBuffer );
	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, reservation.buffer );

	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_TEXCOORD_ARRAY );
	qglVertexPointer( 3, GL_FLOAT, xyzStride, (const GLvoid *)(intptr_t)( reservation.offset ) );
	qglTexCoordPointer( 2, GL_FLOAT, texcoordStride,
		(const GLvoid *)(intptr_t)( reservation.offset + texcoordOffset ) );

	GLX_CompatRecordDraw( vertexCount, GLX_DRAW_STREAM_GENERIC );
	qglDrawArrays( primitive, 0, vertexCount );

	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, 0 );
	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_TEXCOORD_ARRAY );
	qglVertexPointer( 3, GL_FLOAT, xyzStride, xyz );
	qglTexCoordPointer( 2, GL_FLOAT, texcoordStride, texcoords );
	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, (GLuint)oldArrayBuffer );

	GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
		totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qtrue );
	return qtrue;
#else
	(void)vertexCount;
	(void)xyz;
	(void)xyzStride;
	(void)texcoords;
	(void)texcoordStride;
	(void)primitive;
	(void)materialFlags;
	return qfalse;
#endif
}

static ID_INLINE int GLX_CompatArrayElementBytes( int components, unsigned int type )
{
	if ( components <= 0 ) {
		return 0;
	}

	switch ( type ) {
	case GL_FLOAT:
		return components * (int)sizeof( float );
	case GL_UNSIGNED_BYTE:
		return components * (int)sizeof( byte );
	default:
		return 0;
	}
}

static ID_INLINE qboolean GLX_CompatTryStreamDrawArrayTexcoordColorPass( int vertexCount,
	const void *xyz, int xyzStride, const void *texcoords, int texcoordStride,
	const void *colors, int colorComponents, unsigned int colorType, int colorStride,
	unsigned int primitive, int materialFlags )
{
#ifdef RENDERER_GLX
	glxStreamReservation_t reservation;
	qboolean ok = qtrue;
	int xyzBytes;
	int texcoordElementStride;
	int texcoordBytes;
	int colorElementBytes;
	int colorElementStride;
	int colorBytes;
	int texcoordOffset;
	int colorOffset;
	int totalBytes;
	GLint oldArrayBuffer = 0;

	if ( !GLX_CompatStreamDrawEnabled() ) {
		return qfalse;
	}
	if ( !qglBindBufferARB ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_NO_BIND_BUFFER );
		return qfalse;
	}

	colorElementBytes = GLX_CompatArrayElementBytes( colorComponents, colorType );
	if ( vertexCount <= 0 || !xyz || xyzStride <= 0 || !texcoords || texcoordStride < 0 ||
		!colors || colorElementBytes <= 0 || colorStride < 0 ) {
		GLX_CompatRecordStreamDrawSkip( GLX_STREAM_SKIP_BAD_INPUT );
		return qfalse;
	}

	xyzBytes = vertexCount * xyzStride;
	texcoordElementStride = texcoordStride > 0 ? texcoordStride : (int)( 2 * sizeof( float ) );
	texcoordBytes = vertexCount * texcoordElementStride;
	colorElementStride = colorStride > 0 ? colorStride : colorElementBytes;
	colorBytes = vertexCount * colorElementStride;
	texcoordOffset = GLX_CompatAlignInt( xyzBytes, 64 );
	colorOffset = GLX_CompatAlignInt( texcoordOffset + texcoordBytes, 64 );
	totalBytes = GLX_CompatAlignInt( colorOffset + colorBytes, 64 );

	if ( !GLX_CompatStreamReserve( totalBytes, 64, &reservation ) ) {
		GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
			totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qfalse );
		return qfalse;
	}

	if ( !GLX_CompatStreamUploadAt( &reservation, 0, xyz, xyzBytes ) ) {
		ok = qfalse;
	}
	if ( !GLX_CompatStreamUploadAt( &reservation, texcoordOffset, texcoords, texcoordBytes ) ) {
		ok = qfalse;
	}
	if ( !GLX_CompatStreamUploadAt( &reservation, colorOffset, colors, colorBytes ) ) {
		ok = qfalse;
	}
	GLX_CompatStreamCommit( &reservation );

	if ( !ok ) {
		GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
			totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qfalse );
		return qfalse;
	}

	qglGetIntegerv( GL_ARRAY_BUFFER_BINDING_ARB, &oldArrayBuffer );
	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, reservation.buffer );

	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_TEXCOORD_ARRAY | CLS_COLOR_ARRAY );
	qglVertexPointer( 3, GL_FLOAT, xyzStride, (const GLvoid *)(intptr_t)( reservation.offset ) );
	qglTexCoordPointer( 2, GL_FLOAT, texcoordStride,
		(const GLvoid *)(intptr_t)( reservation.offset + texcoordOffset ) );
	qglColorPointer( colorComponents, colorType, colorStride,
		(const GLvoid *)(intptr_t)( reservation.offset + colorOffset ) );

	GLX_CompatRecordDraw( vertexCount, GLX_DRAW_STREAM_GENERIC );
	qglDrawArrays( primitive, 0, vertexCount );

	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, 0 );
	GL_ClientState( 1, CLS_NONE );
	GL_ClientState( 0, CLS_TEXCOORD_ARRAY | CLS_COLOR_ARRAY );
	qglVertexPointer( 3, GL_FLOAT, xyzStride, xyz );
	qglTexCoordPointer( 2, GL_FLOAT, texcoordStride, texcoords );
	qglColorPointer( colorComponents, colorType, colorStride, colors );
	qglBindBufferARB( GL_ARRAY_BUFFER_ARB, (GLuint)oldArrayBuffer );

	GLX_CompatRecordStreamDrawResult( vertexCount, vertexCount,
		totalBytes, 0, 0, qfalse, qfalse, qfalse, materialFlags, qtrue );
	return qtrue;
#else
	(void)vertexCount;
	(void)xyz;
	(void)xyzStride;
	(void)texcoords;
	(void)texcoordStride;
	(void)colors;
	(void)colorComponents;
	(void)colorType;
	(void)colorStride;
	(void)primitive;
	(void)materialFlags;
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatMaterialRendererActive( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_MaterialRendererActive();
#else
	return qfalse;
#endif
}

static ID_INLINE int GLX_CompatMaterialStageFlags( const shaderStage_t *pStage )
{
	int flags = 0;

#ifdef RENDERER_GLX
	if ( !pStage ) {
		return 0;
	}

	if ( pStage->mtEnv ) {
		flags |= GLX_STAGE_MULTITEXTURE;
	}
	if ( pStage->depthFragment ) {
		flags |= GLX_STAGE_DEPTH_FRAGMENT;
	}
	if ( pStage->stateBits & GLS_BLEND_BITS ) {
		flags |= GLX_STAGE_BLEND;
	}
	if ( pStage->stateBits & GLS_ATEST_BITS ) {
		flags |= GLX_STAGE_ALPHA_TEST;
	}
	if ( pStage->stateBits & GLS_DEPTHMASK_TRUE ) {
		flags |= GLX_STAGE_DEPTH_WRITE;
	}
	if ( pStage->bundle[0].lightmap != LIGHTMAP_INDEX_NONE ||
		pStage->bundle[1].lightmap != LIGHTMAP_INDEX_NONE ) {
		flags |= GLX_STAGE_LIGHTMAP;
	}
	if ( pStage->bundle[0].numImageAnimations > 1 ||
		pStage->bundle[1].numImageAnimations > 1 ) {
		flags |= GLX_STAGE_ANIMATED_IMAGE;
	}
	if ( pStage->bundle[0].isVideoMap || pStage->bundle[1].isVideoMap ) {
		flags |= GLX_STAGE_VIDEO_MAP;
	}
	if ( pStage->bundle[0].isScreenMap || pStage->bundle[1].isScreenMap ) {
		flags |= GLX_STAGE_SCREEN_MAP;
	}
	if ( pStage->bundle[0].dlight || pStage->bundle[1].dlight ) {
		flags |= GLX_STAGE_DLIGHT_MAP;
	}
	if ( pStage->bundle[0].numTexMods || pStage->bundle[1].numTexMods ) {
		flags |= GLX_STAGE_TEXMOD;
	}
	if ( pStage->tessFlags & ( TESS_ENV0 | TESS_ENV1 ) ) {
		flags |= GLX_STAGE_ENVIRONMENT;
	}
	if ( pStage->tessFlags & TESS_ST0 ) {
		flags |= GLX_STAGE_ST0;
	}
	if ( pStage->tessFlags & TESS_ST1 ) {
		flags |= GLX_STAGE_ST1;
	}
#else
	(void)pStage;
#endif

	return flags;
}

static ID_INLINE void GLX_CompatRecordMaterialStage( const shaderStage_t *pStage,
	int path, int numVertexes, int numIndexes )
{
#ifdef RENDERER_GLX
	if ( !pStage ) {
		return;
	}

	GLX_Renderer_RecordMaterialStage( path, GLX_CompatMaterialStageFlags( pStage ),
		pStage->stateBits, pStage->rgbGen, pStage->alphaGen,
		pStage->bundle[0].tcGen, pStage->bundle[1].tcGen,
		pStage->bundle[0].numTexMods, pStage->bundle[1].numTexMods,
		numVertexes, numIndexes );
#else
	(void)pStage;
	(void)path;
	(void)numVertexes;
	(void)numIndexes;
#endif
}

static ID_INLINE int GLX_CompatMaterialCombineForGLEnv( int mtEnv )
{
	switch ( mtEnv ) {
	case GL_MODULATE:
		return GLX_MATERIAL_COMBINE_MODULATE;
	case GL_ADD:
		return GLX_MATERIAL_COMBINE_ADD;
	case GL_REPLACE:
		return GLX_MATERIAL_COMBINE_REPLACE;
	case GL_DECAL:
		return GLX_MATERIAL_COMBINE_DECAL;
	default:
		return GLX_MATERIAL_COMBINE_INVALID;
	}
}

static ID_INLINE qboolean GLX_CompatStreamDrawAllowsMaterial( int flags,
	unsigned int stateBits, int rgbGen, int alphaGen, int tcGen0, int texMods0, int texMods1 )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StreamDrawAllowsMaterial( flags, stateBits, rgbGen, alphaGen,
		tcGen0, texMods0, texMods1 );
#else
	(void)flags;
	(void)stateBits;
	(void)rgbGen;
	(void)alphaGen;
	(void)tcGen0;
	(void)texMods0;
	(void)texMods1;
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatBindMaterialStage( int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	int multitextureEnv, qboolean fogPass )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_BindMaterialStage( flags, stateBits, rgbGen, alphaGen,
		tcGen0, tcGen1, texMods0, texMods1,
		GLX_CompatMaterialCombineForGLEnv( multitextureEnv ), fogPass );
#else
	(void)flags;
	(void)stateBits;
	(void)rgbGen;
	(void)alphaGen;
	(void)tcGen0;
	(void)tcGen1;
	(void)texMods0;
	(void)texMods1;
	(void)multitextureEnv;
	(void)fogPass;
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatBindFogMaterial( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_BindFogMaterial();
#else
	return qfalse;
#endif
}

static ID_INLINE void GLX_CompatUnbindMaterial( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_UnbindMaterial();
#endif
}

static ID_INLINE void GLX_CompatRecordFboInit( qboolean requested, qboolean ready,
	qboolean programReady, qboolean framebufferFnsReady, int vidWidth, int vidHeight,
	int captureWidth, int captureHeight, int windowWidth, int windowHeight,
	int internalFormat, int textureFormat, int textureType, qboolean multiSampled,
	qboolean superSampled, qboolean windowAdjusted, int blitFilter, int hdrMode,
	int renderScaleMode, int bloomMode )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordFboInit( requested, ready, programReady, framebufferFnsReady,
		vidWidth, vidHeight, captureWidth, captureHeight, windowWidth, windowHeight,
		internalFormat, textureFormat, textureType, multiSampled, superSampled,
		windowAdjusted, blitFilter, hdrMode, renderScaleMode, bloomMode );
#else
	(void)requested;
	(void)ready;
	(void)programReady;
	(void)framebufferFnsReady;
	(void)vidWidth;
	(void)vidHeight;
	(void)captureWidth;
	(void)captureHeight;
	(void)windowWidth;
	(void)windowHeight;
	(void)internalFormat;
	(void)textureFormat;
	(void)textureType;
	(void)multiSampled;
	(void)superSampled;
	(void)windowAdjusted;
	(void)blitFilter;
	(void)hdrMode;
	(void)renderScaleMode;
	(void)bloomMode;
#endif
}

static ID_INLINE void GLX_CompatRecordFboShutdown( void )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordFboShutdown();
#endif
}

static ID_INLINE void GLX_CompatRecordPostProcessFrame( qboolean minimized,
	qboolean bloomAvailable, qboolean programReady, int screenshotMask,
	qboolean windowAdjusted, int fboReadIndex, int hdrMode, int renderScaleMode,
	float greyscale )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordPostProcessFrame( minimized, bloomAvailable, programReady,
		screenshotMask, windowAdjusted, fboReadIndex, hdrMode, renderScaleMode, greyscale );
#else
	(void)minimized;
	(void)bloomAvailable;
	(void)programReady;
	(void)screenshotMask;
	(void)windowAdjusted;
	(void)fboReadIndex;
	(void)hdrMode;
	(void)renderScaleMode;
	(void)greyscale;
#endif
}

static ID_INLINE void GLX_CompatRecordPostProcessResult( int result )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordPostProcessResult( result );
#else
	(void)result;
#endif
}

static ID_INLINE void GLX_CompatRecordBloomCreate( int result, int requestedPasses,
	int effectivePasses, int textureUnits )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordBloomCreate( result, requestedPasses, effectivePasses, textureUnits );
#else
	(void)result;
	(void)requestedPasses;
	(void)effectivePasses;
	(void)textureUnits;
#endif
}

static ID_INLINE void GLX_CompatRecordBloom( int result, qboolean finalStage,
	int bloomMode, int requestedPasses, int effectivePasses, int blendBase,
	int filterSize, int textureUnits, int thresholdMode, int modulate,
	float threshold, float intensity, float reflection )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordBloom( result, finalStage, bloomMode, requestedPasses,
		effectivePasses, blendBase, filterSize, textureUnits, thresholdMode,
		modulate, threshold, intensity, reflection );
#else
	(void)result;
	(void)finalStage;
	(void)bloomMode;
	(void)requestedPasses;
	(void)effectivePasses;
	(void)blendBase;
	(void)filterSize;
	(void)textureUnits;
	(void)thresholdMode;
	(void)modulate;
	(void)threshold;
	(void)intensity;
	(void)reflection;
#endif
}

static ID_INLINE void GLX_CompatRecordFboCopyScreen( int viewportWidth, int viewportHeight )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordFboCopyScreen( viewportWidth, viewportHeight );
#else
	(void)viewportWidth;
	(void)viewportHeight;
#endif
}

static ID_INLINE void GLX_CompatRecordFboBlit( int kind, qboolean depthOnly,
	int srcWidth, int srcHeight, int dstWidth, int dstHeight )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordFboBlit( kind, depthOnly, srcWidth, srcHeight, dstWidth, dstHeight );
#else
	(void)kind;
	(void)depthOnly;
	(void)srcWidth;
	(void)srcHeight;
	(void)dstWidth;
	(void)dstHeight;
#endif
}

static ID_INLINE void GLX_CompatRecordStaticWorldCache( int surfaces, int vertexes,
	int indexes, int vertexBytes, int indexBytes )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordStaticWorldCache( surfaces, vertexes, indexes, vertexBytes, indexBytes );
#else
	(void)surfaces;
	(void)vertexes;
	(void)indexes;
	(void)vertexBytes;
	(void)indexBytes;
#endif
}

static ID_INLINE void GLX_CompatRecordStaticWorldBatches( int batches,
	int largestBatchSurfaces, int faceSurfaces, int gridSurfaces,
	int triangleSurfaces, int shaderStagePasses, int maxShaderStages )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordStaticWorldBatches( batches, largestBatchSurfaces,
		faceSurfaces, gridSurfaces, triangleSurfaces, shaderStagePasses,
		maxShaderStages );
#else
	(void)batches;
	(void)largestBatchSurfaces;
	(void)faceSurfaces;
	(void)gridSurfaces;
	(void)triangleSurfaces;
	(void)shaderStagePasses;
	(void)maxShaderStages;
#endif
}

static ID_INLINE void GLX_CompatRecordStaticWorldPacket( const char *shaderName, int sort,
	int surfaces, int vertexes, int indexes, int firstItem, int itemCount,
	int vertexOffset, int vertexBytes, int indexOffset, int indexBytes,
	int shaderStagePasses, int flags )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordStaticWorldPacket( shaderName, sort, surfaces, vertexes, indexes,
		firstItem, itemCount, vertexOffset, vertexBytes, indexOffset, indexBytes,
		shaderStagePasses, flags );
#else
	(void)shaderName;
	(void)sort;
	(void)surfaces;
	(void)vertexes;
	(void)indexes;
	(void)firstItem;
	(void)itemCount;
	(void)vertexOffset;
	(void)vertexBytes;
	(void)indexOffset;
	(void)indexBytes;
	(void)shaderStagePasses;
	(void)flags;
#endif
}

static ID_INLINE void GLX_CompatUploadStaticWorldArena( const void *vertexData,
	int vertexBytes, const void *indexData, int indexBytes )
{
#ifdef RENDERER_GLX
	GLX_Renderer_UploadStaticWorldArena( vertexData, vertexBytes, indexData, indexBytes );
#else
	(void)vertexData;
	(void)vertexBytes;
	(void)indexData;
	(void)indexBytes;
#endif
}

static ID_INLINE unsigned int GLX_CompatStaticWorldArenaVertexBuffer( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StaticWorldArenaVertexBuffer();
#else
	return 0;
#endif
}

static ID_INLINE unsigned int GLX_CompatStaticWorldArenaIndexBuffer( void )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StaticWorldArenaIndexBuffer();
#else
	return 0;
#endif
}

static ID_INLINE qboolean GLX_CompatStaticWorldDrawDeviceRun( int indexes,
	int offsetBytes, int firstItem, int itemCount, unsigned int indexType,
	int indexBytes, const char *shaderName, int sort, qboolean arenaBound )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StaticWorldDrawDeviceRun( indexes, offsetBytes,
		firstItem, itemCount, indexType, indexBytes, shaderName, sort, arenaBound );
#else
	(void)indexes;
	(void)offsetBytes;
	(void)firstItem;
	(void)itemCount;
	(void)indexType;
	(void)indexBytes;
	(void)shaderName;
	(void)sort;
	(void)arenaBound;
	return qfalse;
#endif
}

static ID_INLINE qboolean GLX_CompatStaticWorldDrawSoftIndexes( int indexes,
	const void *indexData, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StaticWorldDrawSoftIndexes( indexes, indexData, indexType,
		indexBytes, shaderName, sort, arenaBound );
#else
	(void)indexes;
	(void)indexData;
	(void)indexType;
	(void)indexBytes;
	(void)shaderName;
	(void)sort;
	(void)arenaBound;
	return qfalse;
#endif
}

static ID_INLINE int GLX_CompatStaticWorldDrawDeviceRunsFiltered( int runCount,
	const int *counts, const void *const *offsets, const int *firstItems,
	const int *itemCounts, int *drawnRuns, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound )
{
#ifdef RENDERER_GLX
	return GLX_Renderer_StaticWorldDrawDeviceRunsFiltered( runCount, counts, offsets,
		firstItems, itemCounts, drawnRuns, indexType, indexBytes, shaderName, sort,
		arenaBound );
#else
	(void)runCount;
	(void)counts;
	(void)offsets;
	(void)firstItems;
	(void)itemCounts;
	(void)drawnRuns;
	(void)indexType;
	(void)indexBytes;
	(void)shaderName;
	(void)sort;
	(void)arenaBound;
	return 0;
#endif
}

static ID_INLINE void GLX_CompatRecordStaticWorldQueue( int queuedItems,
	int queuedVertexes, int queuedIndexes, int deviceRuns, int deviceIndexes,
	int softIndexes, int largestDeviceRunIndexes )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordStaticWorldQueue( queuedItems, queuedVertexes, queuedIndexes,
		deviceRuns, deviceIndexes, softIndexes, largestDeviceRunIndexes );
#else
	(void)queuedItems;
	(void)queuedVertexes;
	(void)queuedIndexes;
	(void)deviceRuns;
	(void)deviceIndexes;
	(void)softIndexes;
	(void)largestDeviceRunIndexes;
#endif
}

static ID_INLINE void GLX_CompatRecordStaticWorldDeviceRuns( int runCount,
	const int *counts, const void *const *offsets, const int *firstItems,
	const int *itemCounts, int indexBytes, const char *shaderName, int sort )
{
#ifdef RENDERER_GLX
	GLX_Renderer_RecordStaticWorldDeviceRuns( runCount, counts, offsets,
		firstItems, itemCounts, indexBytes, shaderName, sort );
#else
	(void)runCount;
	(void)counts;
	(void)offsets;
	(void)firstItems;
	(void)itemCounts;
	(void)indexBytes;
	(void)shaderName;
	(void)sort;
#endif
}

#endif // TR_GLX_COMPAT_H
