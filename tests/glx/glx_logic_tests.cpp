/*
===========================================================================
Copyright (C) 2026

This file is part of FnQuake3.

FnQuake3 is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
===========================================================================
*/

#include "glx_material_key.h"
#include "glx_caps_logic.h"
#include "glx_render_ir.h"
#include "glx_static_world_logic.h"
#include "glx_stream_logic.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

bool Check( bool condition, const char *test, int line, const char *expression )
{
	if ( condition ) {
		return true;
	}

	std::fprintf( stderr, "%s:%d: check failed: %s\n", test, line, expression );
	return false;
}

#define CHECK( expression ) do { if ( !Check( ( expression ), __func__, __LINE__, #expression ) ) return false; } while ( 0 )

bool MaterialKeysClassifyRcShapes()
{
	glx::MaterialProgramKey key {};

	CHECK( glx::GLX_Material_KeyForInputs( 0, 0, 0, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_NONE );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_TEXMOD, 0, 2, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_TEXMOD );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_ENVIRONMENT, 0, 0, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_ENVIRONMENT );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT,
		0, 1, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == ( glx::GLX_MATERIAL_FEATURE_TEXMOD | glx::GLX_MATERIAL_FEATURE_ENVIRONMENT ) );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_DEPTH_FRAGMENT,
		0, 0, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_DEPTH_FRAGMENT | GLX_STAGE_TEXMOD |
		GLX_STAGE_ENVIRONMENT, 0, 2, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == ( glx::GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT |
		glx::GLX_MATERIAL_FEATURE_TEXMOD | glx::GLX_MATERIAL_FEATURE_ENVIRONMENT ) );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE,
		GLX_MATERIAL_COMBINE_MODULATE, 0, 0,
		qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::MultiModulate );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_NONE );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE | GLX_STAGE_TEXMOD,
		GLX_MATERIAL_COMBINE_ADD, 0, 1, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::MultiAdd );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_TEXMOD );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE | GLX_STAGE_DEPTH_FRAGMENT,
		GLX_MATERIAL_COMBINE_MODULATE, 0, 0,
		qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::MultiModulate );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE,
		GLX_MATERIAL_COMBINE_REPLACE, 0, 0,
		qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::MultiReplace );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE,
		GLX_MATERIAL_COMBINE_DECAL, 0, 0,
		qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::MultiDecal );

	return true;
}

bool MaterialKeysRejectUnsupportedCombines()
{
	glx::MaterialProgramKey key {};

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE, 0x1234, 0, 0,
		qfalse, &key ) == qfalse );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT,
		GLX_MATERIAL_COMBINE_ADD, 4, 4, qtrue, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::Fog );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_NONE );

	return true;
}

bool MaterialKeysTreatSpecialSceneFlagsAsGates()
{
	glx::MaterialProgramKey key {};

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_DLIGHT_MAP | GLX_STAGE_SCREEN_MAP,
		0, 0, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_NONE );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_VIDEO_MAP | GLX_STAGE_TEXMOD,
		0, 1, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_TEXMOD );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_SHADOW_PASS | GLX_STAGE_BEAM_PASS |
		GLX_STAGE_POSTPROCESS_PASS,
		0, 0, 0, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::SingleTexture );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_NONE );

	return true;
}

bool MaterialStageKeysCoverPreparedIdTech3StageLanguage()
{
	glx::MaterialStageKey key {};
	const int rgbGens[] = {
		GLX_MATERIAL_RGBGEN_BAD,
		GLX_MATERIAL_RGBGEN_IDENTITY_LIGHTING,
		GLX_MATERIAL_RGBGEN_IDENTITY,
		GLX_MATERIAL_RGBGEN_ENTITY,
		GLX_MATERIAL_RGBGEN_ONE_MINUS_ENTITY,
		GLX_MATERIAL_RGBGEN_EXACT_VERTEX,
		GLX_MATERIAL_RGBGEN_VERTEX,
		GLX_MATERIAL_RGBGEN_ONE_MINUS_VERTEX,
		GLX_MATERIAL_RGBGEN_WAVEFORM,
		GLX_MATERIAL_RGBGEN_LIGHTING_DIFFUSE,
		GLX_MATERIAL_RGBGEN_FOG,
		GLX_MATERIAL_RGBGEN_CONST
	};
	const int alphaGens[] = {
		GLX_MATERIAL_ALPHAGEN_IDENTITY,
		GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_ALPHAGEN_ENTITY,
		GLX_MATERIAL_ALPHAGEN_ONE_MINUS_ENTITY,
		GLX_MATERIAL_ALPHAGEN_VERTEX,
		GLX_MATERIAL_ALPHAGEN_ONE_MINUS_VERTEX,
		GLX_MATERIAL_ALPHAGEN_LIGHTING_SPECULAR,
		GLX_MATERIAL_ALPHAGEN_WAVEFORM,
		GLX_MATERIAL_ALPHAGEN_PORTAL,
		GLX_MATERIAL_ALPHAGEN_CONST
	};
	const int tcGens[] = {
		GLX_MATERIAL_TCGEN_BAD,
		GLX_MATERIAL_TCGEN_IDENTITY,
		GLX_MATERIAL_TCGEN_LIGHTMAP,
		GLX_MATERIAL_TCGEN_TEXTURE,
		GLX_MATERIAL_TCGEN_ENVIRONMENT_MAPPED,
		GLX_MATERIAL_TCGEN_ENVIRONMENT_MAPPED_FP,
		GLX_MATERIAL_TCGEN_FOG,
		GLX_MATERIAL_TCGEN_VECTOR
	};
	const int waveFuncs[] = {
		GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_WAVEFUNC_SIN,
		GLX_MATERIAL_WAVEFUNC_SQUARE,
		GLX_MATERIAL_WAVEFUNC_TRIANGLE,
		GLX_MATERIAL_WAVEFUNC_SAWTOOTH,
		GLX_MATERIAL_WAVEFUNC_INVERSE_SAWTOOTH,
		GLX_MATERIAL_WAVEFUNC_NOISE
	};
	const unsigned int allTexMods = GLX_MATERIAL_TMOD_NONE_BIT |
		GLX_MATERIAL_TMOD_TRANSFORM_BIT |
		GLX_MATERIAL_TMOD_TURBULENT_BIT |
		GLX_MATERIAL_TMOD_SCROLL_BIT |
		GLX_MATERIAL_TMOD_SCALE_BIT |
		GLX_MATERIAL_TMOD_STRETCH_BIT |
		GLX_MATERIAL_TMOD_ROTATE_BIT |
		GLX_MATERIAL_TMOD_ENTITY_TRANSLATE_BIT |
		GLX_MATERIAL_TMOD_OFFSET_BIT |
		GLX_MATERIAL_TMOD_SCALE_OFFSET_BIT |
		GLX_MATERIAL_TMOD_OFFSET_SCALE_BIT;
	unsigned int fiveTexModSequence = 0;
	unsigned int fiveTexModMask;

	fiveTexModSequence = glx::GLX_Material_TexModSequenceSetSlot( fiveTexModSequence, 0,
		GLX_MATERIAL_TMOD_OPCODE_TRANSFORM );
	fiveTexModSequence = glx::GLX_Material_TexModSequenceSetSlot( fiveTexModSequence, 1,
		GLX_MATERIAL_TMOD_OPCODE_TURBULENT );
	fiveTexModSequence = glx::GLX_Material_TexModSequenceSetSlot( fiveTexModSequence, 2,
		GLX_MATERIAL_TMOD_OPCODE_SCROLL );
	fiveTexModSequence = glx::GLX_Material_TexModSequenceSetSlot( fiveTexModSequence, 3,
		GLX_MATERIAL_TMOD_OPCODE_SCALE );
	fiveTexModSequence = glx::GLX_Material_TexModSequenceSetSlot( fiveTexModSequence, 4,
		GLX_MATERIAL_TMOD_OPCODE_ROTATE );
	fiveTexModMask = glx::GLX_Material_TexModSequenceMask(
		glx::GLX_MATERIAL_MAX_TEXMODS_PER_BUNDLE, fiveTexModSequence );

	for ( int rgbGen : rgbGens ) {
		CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
			rgbGen, GLX_MATERIAL_ALPHAGEN_SKIP,
			GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
			0, 0, 0, 0, qfalse, &key ) == qtrue );
		CHECK( key.rgbGen == rgbGen );
		CHECK( key.program.mode == glx::MaterialProgramMode::SingleTexture );
	}

	for ( int alphaGen : alphaGens ) {
		CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
			GLX_MATERIAL_RGBGEN_IDENTITY, alphaGen,
			GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
			0, 0, 0, 0, qfalse, &key ) == qtrue );
		CHECK( key.alphaGen == alphaGen );
	}

	for ( int tcGen : tcGens ) {
		CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
			GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
			tcGen, GLX_MATERIAL_TCGEN_BAD,
			0, 0, 0, 0, qfalse, &key ) == qtrue );
		CHECK( key.tcGen0 == tcGen );
	}

	for ( int waveFunc : waveFuncs ) {
		CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
			GLX_MATERIAL_RGBGEN_WAVEFORM, GLX_MATERIAL_ALPHAGEN_SKIP,
			waveFunc, GLX_MATERIAL_WAVEFUNC_NONE,
			GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
			0, 0, 0, 0, 0, 0, 0, 0,
			GLX_MATERIAL_FOG_ADJUST_NONE, qfalse, &key ) == qtrue );
		CHECK( key.rgbWaveFunc == waveFunc );

		CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
			GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_WAVEFORM,
			GLX_MATERIAL_WAVEFUNC_NONE, waveFunc,
			GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
			0, 0, 0, 0, 0, 0, 0, 0,
			GLX_MATERIAL_FOG_ADJUST_NONE, qfalse, &key ) == qtrue );
		CHECK( key.alphaWaveFunc == waveFunc );
	}

	CHECK( glx::GLX_Material_StageKeyForInputsFull(
		GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT | GLX_STAGE_DEPTH_FRAGMENT,
		0x1234, 0,
		GLX_MATERIAL_RGBGEN_WAVEFORM, GLX_MATERIAL_ALPHAGEN_PORTAL,
		GLX_MATERIAL_WAVEFUNC_SAWTOOTH, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_VECTOR, GLX_MATERIAL_TCGEN_LIGHTMAP,
		glx::GLX_MATERIAL_MAX_TEXMODS_PER_BUNDLE,
		glx::GLX_MATERIAL_MAX_TEXMODS_PER_BUNDLE,
		fiveTexModMask, fiveTexModMask, fiveTexModSequence, fiveTexModSequence,
		0, 0, GLX_MATERIAL_FOG_ADJUST_MODULATE_RGB, qfalse, &key ) == qtrue );
	CHECK( key.flags == ( GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT | GLX_STAGE_DEPTH_FRAGMENT ) );
	CHECK( key.stateBits == 0x1234u );
	CHECK( key.rgbWaveFunc == GLX_MATERIAL_WAVEFUNC_SAWTOOTH );
	CHECK( key.alphaWaveFunc == GLX_MATERIAL_WAVEFUNC_NONE );
	CHECK( key.texModTypes0 == fiveTexModMask );
	CHECK( key.texModTypes1 == fiveTexModMask );
	CHECK( key.texModSequence0 == fiveTexModSequence );
	CHECK( key.texModSequence1 == fiveTexModSequence );
	CHECK( key.fogAdjust == GLX_MATERIAL_FOG_ADJUST_MODULATE_RGB );
	CHECK( key.program.features == ( glx::GLX_MATERIAL_FEATURE_TEXMOD |
		glx::GLX_MATERIAL_FEATURE_ENVIRONMENT | glx::GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT ) );
	CHECK( glx::GLX_Material_StageKeyEquals( key, key ) == qtrue );

	glx::MaterialStageKey entityColorKey {};
	glx::MaterialStageKey vertexColorKey {};
	CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_ENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, qfalse, &entityColorKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_VERTEX, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, qfalse, &vertexColorKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( entityColorKey.program, vertexColorKey.program ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyEquals( entityColorKey, vertexColorKey ) == qfalse );

	glx::MaterialStageKey scrollKey {};
	glx::MaterialStageKey rotateKey {};
	CHECK( glx::GLX_Material_StageKeyForInputs( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		1, 0, GLX_MATERIAL_TMOD_SCROLL_BIT, 0, qfalse, &scrollKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputs( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		1, 0, GLX_MATERIAL_TMOD_ROTATE_BIT, 0, qfalse, &rotateKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( scrollKey.program, rotateKey.program ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyEquals( scrollKey, rotateKey ) == qfalse );

	glx::MaterialStageKey scrollScaleKey {};
	glx::MaterialStageKey scaleScrollKey {};
	unsigned int scrollScaleSequence = 0;
	unsigned int scaleScrollSequence = 0;
	const unsigned int scrollScaleMask = GLX_MATERIAL_TMOD_SCROLL_BIT |
		GLX_MATERIAL_TMOD_SCALE_BIT;

	scrollScaleSequence = glx::GLX_Material_TexModSequenceSetSlot( scrollScaleSequence, 0,
		GLX_MATERIAL_TMOD_OPCODE_SCROLL );
	scrollScaleSequence = glx::GLX_Material_TexModSequenceSetSlot( scrollScaleSequence, 1,
		GLX_MATERIAL_TMOD_OPCODE_SCALE );
	scaleScrollSequence = glx::GLX_Material_TexModSequenceSetSlot( scaleScrollSequence, 0,
		GLX_MATERIAL_TMOD_OPCODE_SCALE );
	scaleScrollSequence = glx::GLX_Material_TexModSequenceSetSlot( scaleScrollSequence, 1,
		GLX_MATERIAL_TMOD_OPCODE_SCROLL );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		2, 0, scrollScaleMask, 0, scrollScaleSequence, 0,
		0, 0, GLX_MATERIAL_FOG_ADJUST_NONE, qfalse,
		&scrollScaleKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		2, 0, scrollScaleMask, 0, scaleScrollSequence, 0,
		0, 0, GLX_MATERIAL_FOG_ADJUST_NONE, qfalse,
		&scaleScrollKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( scrollScaleKey.program, scaleScrollKey.program ) == qtrue );
	CHECK( scrollScaleKey.texModTypes0 == scaleScrollKey.texModTypes0 );
	CHECK( glx::GLX_Material_StageKeyEquals( scrollScaleKey, scaleScrollKey ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		2, 0, scrollScaleMask, 0, scrollScaleSequence | ( 1u << 12 ), 0,
		0, 0, GLX_MATERIAL_FOG_ADJUST_NONE, qfalse, &scrollScaleKey ) == qfalse );

	glx::MaterialStageKey sineRgbWaveKey {};
	glx::MaterialStageKey squareRgbWaveKey {};
	CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_WAVEFORM, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_SIN, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, 0, 0, 0, 0,
		GLX_MATERIAL_FOG_ADJUST_NONE, qfalse, &sineRgbWaveKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_WAVEFORM, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_SQUARE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, 0, 0, 0, 0,
		GLX_MATERIAL_FOG_ADJUST_NONE, qfalse, &squareRgbWaveKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( sineRgbWaveKey.program, squareRgbWaveKey.program ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyEquals( sineRgbWaveKey, squareRgbWaveKey ) == qfalse );

	glx::MaterialStageKey sineStretchKey {};
	glx::MaterialStageKey triangleStretchKey {};
	unsigned int stretchSequence = 0;
	unsigned int sineStretchWave = 0;
	unsigned int triangleStretchWave = 0;

	stretchSequence = glx::GLX_Material_TexModSequenceSetSlot( stretchSequence, 0,
		GLX_MATERIAL_TMOD_OPCODE_STRETCH );
	sineStretchWave = glx::GLX_Material_TexModWaveFuncSetSlot( sineStretchWave, 0,
		GLX_MATERIAL_WAVEFUNC_SIN );
	triangleStretchWave = glx::GLX_Material_TexModWaveFuncSetSlot( triangleStretchWave, 0,
		GLX_MATERIAL_WAVEFUNC_TRIANGLE );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		1, 0, GLX_MATERIAL_TMOD_STRETCH_BIT, 0, stretchSequence, 0,
		sineStretchWave, 0, GLX_MATERIAL_FOG_ADJUST_NONE, qfalse,
		&sineStretchKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		1, 0, GLX_MATERIAL_TMOD_STRETCH_BIT, 0, stretchSequence, 0,
		triangleStretchWave, 0, GLX_MATERIAL_FOG_ADJUST_NONE, qfalse,
		&triangleStretchKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( sineStretchKey.program, triangleStretchKey.program ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyEquals( sineStretchKey, triangleStretchKey ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		1, 0, GLX_MATERIAL_TMOD_SCROLL_BIT, 0,
		glx::GLX_Material_TexModSequenceSetSlot( 0, 0, GLX_MATERIAL_TMOD_OPCODE_SCROLL ),
		0, sineStretchWave, 0, GLX_MATERIAL_FOG_ADJUST_NONE, qfalse,
		&sineStretchKey ) == qfalse );

	glx::MaterialStageKey noDetailKey {};
	glx::MaterialStageKey detailKey {};
	CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, qfalse, &noDetailKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputs( GLX_STAGE_DETAIL, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, qfalse, &detailKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( noDetailKey.program, detailKey.program ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyEquals( noDetailKey, detailKey ) == qfalse );

	glx::MaterialStageKey fogRgbAdjustKey {};
	glx::MaterialStageKey fogAlphaAdjustKey {};
	CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, 0, 0, 0, 0,
		GLX_MATERIAL_FOG_ADJUST_MODULATE_RGB, qfalse, &fogRgbAdjustKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, 0, 0, 0, 0,
		GLX_MATERIAL_FOG_ADJUST_MODULATE_ALPHA, qfalse, &fogAlphaAdjustKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( fogRgbAdjustKey.program, fogAlphaAdjustKey.program ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyEquals( fogRgbAdjustKey, fogAlphaAdjustKey ) == qfalse );

	glx::MaterialStageKey blendStateKey {};
	glx::MaterialStageKey alphaStateKey {};
	CHECK( glx::GLX_Material_StageKeyForInputs( GLX_STAGE_BLEND,
		GLX_MATERIAL_STATE_SRCBLEND_SRC_ALPHA |
			GLX_MATERIAL_STATE_DSTBLEND_ONE_MINUS_SRC_ALPHA,
		0, GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, qfalse, &blendStateKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputs( GLX_STAGE_ALPHA_TEST,
		GLX_MATERIAL_STATE_ATEST_GE_80,
		0, GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, qfalse, &alphaStateKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( blendStateKey.program, alphaStateKey.program ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyEquals( blendStateKey, alphaStateKey ) == qfalse );
	CHECK( glx::GLX_Material_StateUnknownBits( blendStateKey.stateBits ) == 0 );
	CHECK( glx::GLX_Material_StateUnknownBits( 0x80000000u ) == 0x80000000u );

	CHECK( glx::GLX_Material_StageKeyForInputs(
		GLX_STAGE_MULTITEXTURE | GLX_STAGE_DEPTH_FRAGMENT | GLX_STAGE_BLEND |
			GLX_STAGE_ALPHA_TEST | GLX_STAGE_DEPTH_WRITE | GLX_STAGE_LIGHTMAP |
			GLX_STAGE_ANIMATED_IMAGE | GLX_STAGE_VIDEO_MAP | GLX_STAGE_SCREEN_MAP |
			GLX_STAGE_DLIGHT_MAP | GLX_STAGE_DETAIL | GLX_STAGE_ST0 | GLX_STAGE_ST1,
		0xabcd, GLX_MATERIAL_COMBINE_MODULATE,
		GLX_MATERIAL_RGBGEN_LIGHTING_DIFFUSE, GLX_MATERIAL_ALPHAGEN_LIGHTING_SPECULAR,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_LIGHTMAP,
		0, 0, 0, 0, qfalse, &key ) == qtrue );
	CHECK( key.program.mode == glx::MaterialProgramMode::MultiModulate );
	CHECK( key.program.features == glx::GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT );
	CHECK( ( key.flags & GLX_STAGE_DLIGHT_MAP ) != 0 );
	CHECK( ( key.flags & GLX_STAGE_DETAIL ) != 0 );
	CHECK( ( key.flags & GLX_STAGE_SCREEN_MAP ) != 0 );
	CHECK( ( key.flags & GLX_STAGE_VIDEO_MAP ) != 0 );

	CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
		999, GLX_MATERIAL_ALPHAGEN_SKIP, GLX_MATERIAL_TCGEN_TEXTURE,
		GLX_MATERIAL_TCGEN_BAD, 0, 0, 0, 0, qfalse, &key ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, 999, GLX_MATERIAL_TCGEN_TEXTURE,
		GLX_MATERIAL_TCGEN_BAD, 0, 0, 0, 0, qfalse, &key ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputs( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP, 999,
		GLX_MATERIAL_TCGEN_BAD, 0, 0, 0, 0, qfalse, &key ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputs( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		glx::GLX_MATERIAL_MAX_TEXMODS_PER_BUNDLE + 1, 0,
		allTexMods, 0, qfalse, &key ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputs( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		1, 0, 0, 0, qfalse, &key ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputs( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		1, 0, GLX_MATERIAL_TMOD_UNKNOWN_BIT, 0, qfalse, &key ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_SIN, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, 0, 0, 0, 0,
		GLX_MATERIAL_FOG_ADJUST_NONE, qfalse, &key ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_WAVEFORM, GLX_MATERIAL_ALPHAGEN_SKIP,
		99, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, 0, 0, 0, 0,
		GLX_MATERIAL_FOG_ADJUST_NONE, qfalse, &key ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( 0, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_WAVEFUNC_NONE, GLX_MATERIAL_WAVEFUNC_NONE,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		0, 0, 0, 0, 0, 0, 0, 0,
		99, qfalse, &key ) == qfalse );

	return true;
}

bool MaterialIRCompilesToProgramStatePlans()
{
	glx::MaterialIR material = glx::GLX_RenderIR_MakeMaterial(
		17,
		GLX_STAGE_MULTITEXTURE | GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT |
			GLX_STAGE_BLEND | GLX_STAGE_ST0 | GLX_STAGE_ST1,
		GLX_MATERIAL_STATE_SRCBLEND_SRC_ALPHA |
			GLX_MATERIAL_STATE_DSTBLEND_ONE_MINUS_SRC_ALPHA,
		2 );
	glx::MaterialStatePlan plan {};
	unsigned int reasons = 0;
	unsigned int texModSequence0 = 0;
	unsigned int texModSequence1 = 0;

	texModSequence0 = glx::GLX_Material_TexModSequenceSetSlot( texModSequence0, 0,
		GLX_MATERIAL_TMOD_OPCODE_SCROLL );
	texModSequence0 = glx::GLX_Material_TexModSequenceSetSlot( texModSequence0, 1,
		GLX_MATERIAL_TMOD_OPCODE_SCALE );
	texModSequence1 = glx::GLX_Material_TexModSequenceSetSlot( texModSequence1, 0,
		GLX_MATERIAL_TMOD_OPCODE_ROTATE );

	material.rgbGen = GLX_MATERIAL_RGBGEN_WAVEFORM;
	material.alphaGen = GLX_MATERIAL_ALPHAGEN_VERTEX;
	material.rgbWaveFunc = GLX_MATERIAL_WAVEFUNC_SIN;
	material.alphaWaveFunc = GLX_MATERIAL_WAVEFUNC_NONE;
	material.tcGen0 = GLX_MATERIAL_TCGEN_TEXTURE;
	material.tcGen1 = GLX_MATERIAL_TCGEN_LIGHTMAP;
	material.texMods0 = 2;
	material.texMods1 = 1;
	material.texModTypes0 = GLX_MATERIAL_TMOD_SCROLL_BIT | GLX_MATERIAL_TMOD_SCALE_BIT;
	material.texModTypes1 = GLX_MATERIAL_TMOD_ROTATE_BIT;
	material.texModSequence0 = texModSequence0;
	material.texModSequence1 = texModSequence1;
	material.fogAdjust = GLX_MATERIAL_FOG_ADJUST_MODULATE_RGB;
	material.materialCombine = GLX_MATERIAL_COMBINE_MODULATE;

	CHECK( glx::GLX_Material_StatePlanForIR( material, &plan, &reasons ) == qtrue );
	CHECK( reasons == glx::GLX_MATERIAL_UNSUPPORTED_NONE );
	CHECK( plan.tier == glx::RenderProductTier::GL2X );
	CHECK( plan.programmable == qtrue );
	CHECK( plan.sort == 17 );
	CHECK( plan.stage.program.mode == glx::MaterialProgramMode::MultiModulate );
	CHECK( plan.stage.program.features == ( glx::GLX_MATERIAL_FEATURE_TEXMOD |
		glx::GLX_MATERIAL_FEATURE_ENVIRONMENT ) );
	CHECK( plan.stage.stateBits == material.stateBits );
	CHECK( plan.stage.rgbGen == GLX_MATERIAL_RGBGEN_WAVEFORM );
	CHECK( plan.stage.rgbWaveFunc == GLX_MATERIAL_WAVEFUNC_SIN );
	CHECK( plan.stage.texModSequence0 == texModSequence0 );
	CHECK( plan.stage.texModSequence1 == texModSequence1 );

	CHECK( glx::GLX_Material_StatePlanForTierAndIR( glx::RenderProductTier::GL12,
		material, &plan, &reasons ) == qtrue );
	CHECK( plan.tier == glx::RenderProductTier::GL12 );
	CHECK( plan.programmable == qfalse );

	glx::MaterialIR badCombine = material;
	badCombine.materialCombine = 99;
	CHECK( glx::GLX_Material_StatePlanForIR( badCombine, &plan, &reasons ) == qfalse );
	CHECK( ( reasons & glx::GLX_MATERIAL_UNSUPPORTED_INVALID_COMBINE ) != 0 );
	CHECK( std::strcmp( glx::GLX_Material_UnsupportedReasonName( reasons ),
		"invalid multitexture combine" ) == 0 );

	glx::MaterialIR badSequence = material;
	badSequence.texModSequence0 = glx::GLX_Material_TexModSequenceSetSlot(
		badSequence.texModSequence0, 2, GLX_MATERIAL_TMOD_OPCODE_ROTATE );
	CHECK( glx::GLX_Material_StatePlanForIR( badSequence, &plan, &reasons ) == qfalse );
	CHECK( ( reasons & glx::GLX_MATERIAL_UNSUPPORTED_TEXMOD_SEQUENCE ) != 0 );

	glx::MaterialIR badWave = material;
	badWave.rgbWaveFunc = 99;
	CHECK( glx::GLX_Material_StatePlanForIR( badWave, &plan, &reasons ) == qfalse );
	CHECK( ( reasons & glx::GLX_MATERIAL_UNSUPPORTED_RGB_WAVE ) != 0 );

	return true;
}

bool MaterialParameterBlocksMirrorNativeRenderInputs()
{
	glx::MaterialIR material = glx::GLX_RenderIR_MakeMaterial(
		9,
		GLX_STAGE_MULTITEXTURE | GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT |
			GLX_STAGE_DEPTH_FRAGMENT | GLX_STAGE_SCREEN_MAP,
		GLX_MATERIAL_STATE_SRCBLEND_SRC_ALPHA |
			GLX_MATERIAL_STATE_DSTBLEND_ONE_MINUS_SRC_ALPHA,
		3 );
	unsigned int texModSequence = 0;

	texModSequence = glx::GLX_Material_TexModSequenceSetSlot( texModSequence, 0,
		GLX_MATERIAL_TMOD_OPCODE_SCROLL );
	material.rgbGen = GLX_MATERIAL_RGBGEN_VERTEX;
	material.alphaGen = GLX_MATERIAL_ALPHAGEN_WAVEFORM;
	material.rgbWaveFunc = GLX_MATERIAL_WAVEFUNC_NONE;
	material.alphaWaveFunc = GLX_MATERIAL_WAVEFUNC_SIN;
	material.tcGen0 = GLX_MATERIAL_TCGEN_TEXTURE;
	material.tcGen1 = GLX_MATERIAL_TCGEN_LIGHTMAP;
	material.texMods0 = 1;
	material.texModTypes0 = GLX_MATERIAL_TMOD_SCROLL_BIT;
	material.texModSequence0 = texModSequence;
	material.fogAdjust = GLX_MATERIAL_FOG_ADJUST_MODULATE_RGB;
	material.materialCombine = GLX_MATERIAL_COMBINE_MODULATE;

	glx::MaterialParameterBlock block =
		glx::GLX_RenderIR_MakeMaterialParameterBlock( material );
	const unsigned int hash = glx::GLX_RenderIR_HashMaterialParameterBlock( block );
	CHECK( glx::GLX_RenderIR_ValidateMaterialParameterBlock( block ) == qtrue );
	CHECK( hash != 0 );
	CHECK( block.frame.sort == 9 );
	CHECK( block.frame.shaderStagePasses == 3 );
	CHECK( ( block.frame.featureMask & GLX_STAGE_MULTITEXTURE ) != 0 );
	CHECK( ( block.frame.featureMask & GLX_STAGE_TEXMOD ) != 0 );
	CHECK( ( block.frame.featureMask & GLX_STAGE_SCREEN_MAP ) != 0 );
	CHECK( block.object.rgbGen == GLX_MATERIAL_RGBGEN_VERTEX );
	CHECK( block.object.alphaGen == GLX_MATERIAL_ALPHAGEN_WAVEFORM );
	CHECK( block.object.alphaWaveFunc == GLX_MATERIAL_WAVEFUNC_SIN );
	CHECK( block.object.tcGen1 == GLX_MATERIAL_TCGEN_LIGHTMAP );
	CHECK( block.material.flags == material.flags );
	CHECK( block.material.stateBits == material.stateBits );
	CHECK( block.material.texModSequence0 == texModSequence );
	CHECK( block.material.fogAdjust == GLX_MATERIAL_FOG_ADJUST_MODULATE_RGB );
	CHECK( block.material.materialCombine == GLX_MATERIAL_COMBINE_MODULATE );

	glx::MaterialParameterBlock changedBlock = block;
	changedBlock.object.tcGen1 = GLX_MATERIAL_TCGEN_TEXTURE;
	CHECK( glx::GLX_RenderIR_HashMaterialParameterBlock( changedBlock ) != hash );

	glx::MaterialStatePlan irPlan {};
	glx::MaterialStatePlan blockPlan {};
	unsigned int irReasons = 0;
	unsigned int blockReasons = 0;
	CHECK( glx::GLX_Material_StatePlanForTierAndIR( glx::RenderProductTier::GL2X,
		material, &irPlan, &irReasons ) == qtrue );
	CHECK( glx::GLX_Material_StatePlanForTierAndParameterBlock( glx::RenderProductTier::GL2X,
		block, &blockPlan, &blockReasons ) == qtrue );
	CHECK( irReasons == glx::GLX_MATERIAL_UNSUPPORTED_NONE );
	CHECK( blockReasons == glx::GLX_MATERIAL_UNSUPPORTED_NONE );
	CHECK( blockPlan.sort == material.sort );
	CHECK( blockPlan.programmable == qtrue );
	CHECK( glx::GLX_Material_StageKeyEquals( irPlan.stage, blockPlan.stage ) == qtrue );

	block.material.texMods0 = -1;
	CHECK( glx::GLX_RenderIR_ValidateMaterialParameterBlock( block ) == qfalse );
	blockReasons = glx::GLX_MATERIAL_UNSUPPORTED_NONE;
	CHECK( glx::GLX_Material_StatePlanForTierAndParameterBlock( glx::RenderProductTier::GL2X,
		block, &blockPlan, &blockReasons ) == qfalse );
	CHECK( ( blockReasons & glx::GLX_MATERIAL_UNSUPPORTED_INVALID_IR ) != 0 );

	return true;
}

bool StreamGatesMatchRcAllowlist()
{
	glx::StreamMaterialGateConfig rc {};
	glx::StreamMaterialGateResult result;

	rc.keyMode = 0;
	rc.multitexture = qtrue;
	rc.depthFragment = qtrue;
	rc.texMods = qtrue;
	rc.environment = qtrue;
	rc.dynamicLights = qfalse;
	rc.screenMaps = qfalse;
	rc.videoMaps = qfalse;

	result = glx::GLX_Stream_EvaluateMaterialGate( 0, 0, 0, rc );
	CHECK( result.allowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_TEXMOD, 1, 0, rc );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasTexMods == qtrue );
	CHECK( result.texModsGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_ENVIRONMENT, 0, 0, rc );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasEnvironment == qtrue );
	CHECK( result.environmentGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_MULTITEXTURE | GLX_STAGE_ST1,
		0, 0, rc );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasMultitexture == qtrue );
	CHECK( result.multitextureGateAllowed == qtrue );
	CHECK( result.hasSecondTexcoord == qtrue );
	CHECK( result.secondTexcoordGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DEPTH_FRAGMENT, 0, 0, rc );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasDepthFragment == qtrue );
	CHECK( result.depthFragmentGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate(
		GLX_STAGE_DEPTH_FRAGMENT | GLX_STAGE_MULTITEXTURE | GLX_STAGE_ST1, 0, 0, rc );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasDepthFragment == qtrue );
	CHECK( result.depthFragmentGateAllowed == qtrue );
	CHECK( result.hasMultitexture == qtrue );
	CHECK( result.multitextureGateAllowed == qtrue );
	CHECK( result.hasSecondTexcoord == qtrue );
	CHECK( result.secondTexcoordGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_ST1, 0, 0, rc );
	CHECK( result.allowed == qfalse );
	CHECK( result.secondTexcoordGateAllowed == qfalse );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DLIGHT_MAP, 0, 0, rc );
	CHECK( result.allowed == qfalse );
	CHECK( result.dynamicLightGateAllowed == qfalse );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_SCREEN_MAP, 0, 0, rc );
	CHECK( result.allowed == qfalse );
	CHECK( result.screenMapGateAllowed == qfalse );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_VIDEO_MAP, 0, 0, rc );
	CHECK( result.allowed == qfalse );
	CHECK( result.videoMapGateAllowed == qfalse );

	return true;
}

bool StreamBroadKeyModeRemainsDeveloperEscapeHatch()
{
	glx::StreamMaterialGateConfig config {};
	glx::StreamMaterialGateResult result;

	config.keyMode = 2;

	result = glx::GLX_Stream_EvaluateMaterialGate(
		GLX_STAGE_ENVIRONMENT | GLX_STAGE_DLIGHT_MAP | GLX_STAGE_SCREEN_MAP |
			GLX_STAGE_VIDEO_MAP,
		2, 3, config );

	CHECK( result.allowed == qtrue );
	CHECK( result.hasEnvironment == qtrue );
	CHECK( result.environmentGateAllowed == qtrue );
	CHECK( result.hasDynamicLight == qtrue );
	CHECK( result.dynamicLightGateAllowed == qtrue );
	CHECK( result.hasScreenMap == qtrue );
	CHECK( result.screenMapGateAllowed == qtrue );
	CHECK( result.hasVideoMap == qtrue );
	CHECK( result.videoMapGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_MULTITEXTURE | GLX_STAGE_ST1,
		0, 0, config );
	CHECK( result.allowed == qfalse );
	CHECK( result.hasMultitexture == qtrue );
	CHECK( result.multitextureGateAllowed == qfalse );
	CHECK( result.hasSecondTexcoord == qtrue );
	CHECK( result.secondTexcoordGateAllowed == qfalse );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DEPTH_FRAGMENT, 0, 0, config );
	CHECK( result.allowed == qfalse );
	CHECK( result.hasDepthFragment == qtrue );
	CHECK( result.depthFragmentGateAllowed == qfalse );

	return true;
}

bool StreamSpecialSceneGatesAreExplicit()
{
	glx::StreamMaterialGateConfig config {};
	glx::StreamMaterialGateResult result;

	config.keyMode = 0;
	config.dynamicLights = qtrue;

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_MULTITEXTURE, 0, 0, config );
	CHECK( result.allowed == qfalse );
	CHECK( result.hasMultitexture == qtrue );
	CHECK( result.multitextureGateAllowed == qfalse );

	config.multitexture = qtrue;
	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_MULTITEXTURE, 0, 0, config );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasMultitexture == qtrue );
	CHECK( result.multitextureGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DEPTH_FRAGMENT, 0, 0, config );
	CHECK( result.allowed == qfalse );
	CHECK( result.hasDepthFragment == qtrue );
	CHECK( result.depthFragmentGateAllowed == qfalse );

	config.depthFragment = qtrue;
	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DEPTH_FRAGMENT, 0, 0, config );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasDepthFragment == qtrue );
	CHECK( result.depthFragmentGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DLIGHT_MAP, 0, 0, config );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasDynamicLight == qtrue );
	CHECK( result.dynamicLightGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DLIGHT_MAP | GLX_STAGE_SCREEN_MAP,
		0, 0, config );
	CHECK( result.allowed == qfalse );
	CHECK( result.hasDynamicLight == qtrue );
	CHECK( result.dynamicLightGateAllowed == qtrue );
	CHECK( result.hasScreenMap == qtrue );
	CHECK( result.screenMapGateAllowed == qfalse );

	config.screenMaps = qtrue;
	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DLIGHT_MAP | GLX_STAGE_SCREEN_MAP,
		0, 0, config );
	CHECK( result.allowed == qtrue );
	CHECK( result.dynamicLightGateAllowed == qtrue );
	CHECK( result.screenMapGateAllowed == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_VIDEO_MAP, 0, 0, config );
	CHECK( result.allowed == qfalse );
	CHECK( result.hasVideoMap == qtrue );
	CHECK( result.videoMapGateAllowed == qfalse );

	config.videoMaps = qtrue;
	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_VIDEO_MAP, 0, 0, config );
	CHECK( result.allowed == qtrue );
	CHECK( result.videoMapGateAllowed == qtrue );

	config.keyMode = 1;
	config.dynamicLights = qfalse;
	config.screenMaps = qfalse;
	config.videoMaps = qfalse;
	result = glx::GLX_Stream_EvaluateMaterialGate(
		GLX_STAGE_DLIGHT_MAP | GLX_STAGE_SCREEN_MAP | GLX_STAGE_VIDEO_MAP,
		0, 0, config );
	CHECK( result.allowed == qfalse );
	CHECK( result.hasDynamicLight == qtrue );
	CHECK( result.dynamicLightGateAllowed == qfalse );
	CHECK( result.hasScreenMap == qtrue );
	CHECK( result.screenMapGateAllowed == qfalse );
	CHECK( result.hasVideoMap == qtrue );
	CHECK( result.videoMapGateAllowed == qfalse );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_TEXMOD | GLX_STAGE_DLIGHT_MAP,
		2, 0, config );
	CHECK( result.allowed == qfalse );
	CHECK( result.hasTexMods == qtrue );
	CHECK( result.texModsGateAllowed == qtrue );
	CHECK( result.hasDynamicLight == qtrue );
	CHECK( result.dynamicLightGateAllowed == qfalse );

	return true;
}

bool StreamShadowGateIsExplicit()
{
	glx::StreamSpecialDrawGateConfig config {};

	config.streamDraw = qtrue;
	config.shadows = qfalse;
	CHECK( glx::GLX_Stream_EvaluateShadowDrawGate( config ) == qfalse );

	config.streamDraw = qfalse;
	config.shadows = qtrue;
	CHECK( glx::GLX_Stream_EvaluateShadowDrawGate( config ) == qfalse );

	config.streamDraw = qtrue;
	config.shadows = qtrue;
	CHECK( glx::GLX_Stream_EvaluateShadowDrawGate( config ) == qtrue );

	return true;
}

bool StreamBeamGateIsExplicit()
{
	glx::StreamSpecialDrawGateConfig config {};

	config.streamDraw = qtrue;
	config.beams = qfalse;
	CHECK( glx::GLX_Stream_EvaluateBeamDrawGate( config ) == qfalse );

	config.streamDraw = qfalse;
	config.beams = qtrue;
	CHECK( glx::GLX_Stream_EvaluateBeamDrawGate( config ) == qfalse );

	config.streamDraw = qtrue;
	config.beams = qtrue;
	CHECK( glx::GLX_Stream_EvaluateBeamDrawGate( config ) == qtrue );

	return true;
}

bool StreamPostProcessGateIsExplicit()
{
	glx::StreamSpecialDrawGateConfig config {};

	config.streamDraw = qtrue;
	config.postprocess = qfalse;
	CHECK( glx::GLX_Stream_EvaluatePostProcessDrawGate( config ) == qfalse );

	config.streamDraw = qfalse;
	config.postprocess = qtrue;
	CHECK( glx::GLX_Stream_EvaluatePostProcessDrawGate( config ) == qfalse );

	config.streamDraw = qtrue;
	config.postprocess = qtrue;
	CHECK( glx::GLX_Stream_EvaluatePostProcessDrawGate( config ) == qtrue );

	return true;
}

bool StreamDynamicCategoriesNormalizeToSceneProducts()
{
	CHECK( glx::GLX_Stream_NormalizeDynamicCategoryMask(
		GLX_DYNAMIC_CATEGORY_MASK_ENTITY, 0 ) == GLX_DYNAMIC_CATEGORY_MASK_ENTITY );
	CHECK( glx::GLX_Stream_NormalizeDynamicCategoryMask(
		GLX_DYNAMIC_CATEGORY_MASK_PARTICLE | GLX_DYNAMIC_CATEGORY_MASK_MARK, 0 ) ==
		( GLX_DYNAMIC_CATEGORY_MASK_PARTICLE | GLX_DYNAMIC_CATEGORY_MASK_MARK ) );
	CHECK( glx::GLX_Stream_NormalizeDynamicCategoryMask( 0,
		GLX_STAGE_BEAM_PASS ) == GLX_DYNAMIC_CATEGORY_MASK_BEAM );
	CHECK( glx::GLX_Stream_NormalizeDynamicCategoryMask( 0,
		GLX_STAGE_SHADOW_PASS ) == GLX_DYNAMIC_CATEGORY_MASK_SPECIAL );
	CHECK( glx::GLX_Stream_NormalizeDynamicCategoryMask( 0,
		GLX_STAGE_POSTPROCESS_PASS ) == GLX_DYNAMIC_CATEGORY_MASK_SPECIAL );
	CHECK( glx::GLX_Stream_NormalizeDynamicCategoryMask( 0,
		GLX_STAGE_DLIGHT_MAP ) == GLX_DYNAMIC_CATEGORY_MASK_SPECIAL );
	CHECK( glx::GLX_Stream_NormalizeDynamicCategoryMask( 0, 0 ) ==
		GLX_DYNAMIC_CATEGORY_MASK_SPECIAL );

	return true;
}

bool CapabilityLogicClassifiesTiersAndExtensions()
{
	int major = 0;
	int minor = 0;

	glx::GLX_Caps_ParseVersionString( "OpenGL 4.6.0 Compatibility Profile", &major, &minor );
	CHECK( major == 4 );
	CHECK( minor == 6 );

	glx::GLX_Caps_ParseVersionString( "driver-without-version", &major, &minor );
	CHECK( major == 0 );
	CHECK( minor == 0 );

	CHECK( glx::GLX_Caps_ExtensionListHas( "GL_ARB_sync GL_ARB_timer_query", "GL_ARB_sync" ) == qtrue );
	CHECK( glx::GLX_Caps_ExtensionListHas( "GL_ARB_sync2 GL_ARB_timer_query", "GL_ARB_sync" ) == qfalse );

	glx::FeatureSet gl12 = glx::GLX_Caps_FeaturesForVersionAndExtensions( 1, 2, "" );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 1, 2, gl12 ) == glx::RenderProductTier::GL12 );
	CHECK( glx::GLX_Caps_HintForTierAndFeatures( glx::RenderProductTier::GL12, gl12 ) == glx::CapabilityHint::FixedFunction );

	glx::FeatureSet gl2x = glx::GLX_Caps_FeaturesForVersionAndExtensions( 2, 1, "" );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 2, 1, gl2x ) == glx::RenderProductTier::GL2X );
	CHECK( glx::GLX_Caps_HintForTierAndFeatures( glx::RenderProductTier::GL2X, gl2x ) == glx::CapabilityHint::Programmable );

	glx::FeatureSet gl3x = glx::GLX_Caps_FeaturesForVersionAndExtensions( 3, 3, "" );
	CHECK( gl3x.mapBufferRange == qtrue );
	CHECK( gl3x.timerQuery == qtrue );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 3, 3, gl3x ) == glx::RenderProductTier::GL3X );
	CHECK( glx::GLX_Caps_HintForTierAndFeatures( glx::RenderProductTier::GL3X, gl3x ) == glx::CapabilityHint::Modern );

	glx::FeatureSet extensionCore = glx::GLX_Caps_FeaturesForVersionAndExtensions( 2, 1,
		"GL_ARB_map_buffer_range GL_ARB_uniform_buffer_object GL_ARB_instanced_arrays" );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 2, 1, extensionCore ) == glx::RenderProductTier::GL2X );
	CHECK( glx::GLX_Caps_HintForTierAndFeatures( glx::RenderProductTier::GL2X, extensionCore ) == glx::CapabilityHint::Modern );

	glx::FeatureSet gl41 = glx::GLX_Caps_FeaturesForVersionAndExtensions( 4, 1, "" );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 4, 1, gl41 ) == glx::RenderProductTier::GL41 );
	CHECK( glx::GLX_Caps_HintForTierAndFeatures( glx::RenderProductTier::GL41, gl41 ) == glx::CapabilityHint::Modern );

	glx::FeatureSet gl46 = glx::GLX_Caps_FeaturesForVersionAndExtensions( 4, 6, "" );
	CHECK( gl46.drawIndirect == qtrue );
	CHECK( gl46.multiDrawIndirect == qtrue );
	CHECK( gl46.bufferStorage == qtrue );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 4, 6, gl46 ) == glx::RenderProductTier::GL46 );
	CHECK( glx::GLX_Caps_HintForTierAndFeatures( glx::RenderProductTier::GL46, gl46 ) == glx::CapabilityHint::HighEnd );
	CHECK( std::strcmp( glx::GLX_RenderProductTierName( glx::RenderProductTier::GL46 ), "GL46" ) == 0 );
	CHECK( std::strcmp( glx::GLX_CapabilityHintName( glx::CapabilityHint::HighEnd ), "high-end" ) == 0 );

	return true;
}

bool StreamStrategySelectionFollowsFallbackLadder()
{
	glx::FeatureSet features {};
	glx::StreamStrategySelection selection;
	glx::StreamRuntimeFallback runtime;

	selection = glx::GLX_Stream_SelectStrategy( "auto", features );
	CHECK( selection.knownMode == qtrue );
	CHECK( selection.strategy == glx::StreamStrategy::OrphanSubData );
	CHECK( selection.fallbackCount == 0 );

	features.mapBufferRange = qtrue;
	selection = glx::GLX_Stream_SelectStrategy( "auto", features );
	CHECK( selection.strategy == glx::StreamStrategy::MapBufferRange );
	CHECK( selection.fallbackCount == 0 );

	selection = glx::GLX_Stream_SelectStrategy( "persistent", features );
	CHECK( selection.strategy == glx::StreamStrategy::MapBufferRange );
	CHECK( selection.fallbackCount == 1 );

	selection = glx::GLX_Stream_SelectStrategy( "maprange", glx::FeatureSet {} );
	CHECK( selection.strategy == glx::StreamStrategy::OrphanSubData );
	CHECK( selection.fallbackCount == 1 );

	features.bufferStorage = qtrue;
	features.syncObjects = qtrue;
	selection = glx::GLX_Stream_SelectStrategy( "auto", features );
	CHECK( selection.strategy == glx::StreamStrategy::PersistentMapped );
	CHECK( selection.fallbackCount == 0 );

	selection = glx::GLX_Stream_SelectStrategy( "mystery", features );
	CHECK( selection.knownMode == qfalse );
	CHECK( selection.strategy == glx::StreamStrategy::PersistentMapped );

	runtime = glx::GLX_Stream_ApplyRuntimeFunctionFallbacks( {
		glx::StreamStrategy::PersistentMapped,
		qtrue,
		qfalse,
		qtrue,
		qtrue,
		qtrue
	} );
	CHECK( runtime.strategy == glx::StreamStrategy::MapBufferRange );
	CHECK( runtime.ready == qtrue );
	CHECK( runtime.fallbackCount == 1 );

	runtime = glx::GLX_Stream_ApplyRuntimeFunctionFallbacks( {
		glx::StreamStrategy::MapBufferRange,
		qfalse,
		qfalse,
		qtrue,
		qfalse,
		qtrue
	} );
	CHECK( runtime.strategy == glx::StreamStrategy::OrphanSubData );
	CHECK( runtime.ready == qtrue );
	CHECK( runtime.fallbackCount == 1 );

	runtime = glx::GLX_Stream_ApplyRuntimeFunctionFallbacks( {
		glx::StreamStrategy::OrphanSubData,
		qfalse,
		qfalse,
		qfalse,
		qfalse,
		qfalse
	} );
	CHECK( runtime.strategy == glx::StreamStrategy::OrphanSubData );
	CHECK( runtime.ready == qfalse );

	return true;
}

bool StaticWorldPacketLogicClassifiesRunsAndPolicies()
{
	const glx::StaticWorldPacketView packet {
		"textures/base_floor/test",
		7,
		100,
		4,
		200,
		24
	};
	glx::StaticWorldRunPacket result;

	result = glx::GLX_StaticWorld_ClassifyRunAgainstPacketView( packet, 3,
		200, 24, 100, 4, "textures/base_floor/test", 7 );
	CHECK( result.match == glx::StaticWorldPacketMatch::Full );
	CHECK( result.packetIndex == 3 );

	result = glx::GLX_StaticWorld_ClassifyRunAgainstPacketView( packet, 3,
		204, 8, 101, 2, "textures/base_floor/test", 7 );
	CHECK( result.match == glx::StaticWorldPacketMatch::Partial );

	result = glx::GLX_StaticWorld_ClassifyRunAgainstPacketView( packet, 3,
		204, 8, 99, 2, "textures/base_floor/test", 7 );
	CHECK( result.match == glx::StaticWorldPacketMatch::ItemMismatch );

	result = glx::GLX_StaticWorld_ClassifyRunAgainstPacketView( packet, 3,
		200, 24, 100, 4, "textures/other", 7 );
	CHECK( result.match == glx::StaticWorldPacketMatch::NoMatch );

	result = glx::GLX_StaticWorld_ClassifyRunAgainstPacketView( packet, 3,
		200, 24, 100, 4, "textures/base_floor/test", 8 );
	CHECK( result.match == glx::StaticWorldPacketMatch::NoMatch );

	CHECK( glx::GLX_StaticWorld_DrawPolicyFromString( "full" ) == glx::StaticWorldDrawPolicy::FullPackets );
	CHECK( glx::GLX_StaticWorld_DrawPolicyFromString( "packet" ) == glx::StaticWorldDrawPolicy::ContainedPackets );
	CHECK( glx::GLX_StaticWorld_DrawPolicyFromString( "legacy" ) == glx::StaticWorldDrawPolicy::AllRuns );
	CHECK( glx::GLX_StaticWorld_DrawPolicyFromString( "unknown" ) == glx::StaticWorldDrawPolicy::FullPackets );

	CHECK( glx::GLX_StaticWorld_DrawPolicyAllows( glx::StaticWorldDrawPolicy::FullPackets,
		glx::StaticWorldPacketMatch::Full ) == qtrue );
	CHECK( glx::GLX_StaticWorld_DrawPolicyAllows( glx::StaticWorldDrawPolicy::FullPackets,
		glx::StaticWorldPacketMatch::Partial ) == qfalse );
	CHECK( glx::GLX_StaticWorld_DrawPolicyAllows( glx::StaticWorldDrawPolicy::ContainedPackets,
		glx::StaticWorldPacketMatch::Partial ) == qtrue );
	CHECK( glx::GLX_StaticWorld_DrawPolicyAllows( glx::StaticWorldDrawPolicy::ContainedPackets,
		glx::StaticWorldPacketMatch::ItemMismatch ) == qfalse );
	CHECK( glx::GLX_StaticWorld_DrawPolicyAllows( glx::StaticWorldDrawPolicy::AllRuns,
		glx::StaticWorldPacketMatch::NoMatch ) == qtrue );

	return true;
}

bool RenderIRDefaultPassScheduleIsDeterministic()
{
	glx::FramePass passes[glx::GLX_RENDER_IR_PASS_COUNT];
	char schedule[glx::GLX_RENDER_IR_PASS_SCHEDULE_TEXT_BYTES];
	int count = 0;

	CHECK( glx::GLX_RenderIR_DefaultPassSchedule( passes, glx::GLX_RENDER_IR_PASS_COUNT, &count ) == qtrue );
	CHECK( count == glx::GLX_RENDER_IR_PASS_COUNT );
	CHECK( glx::GLX_RenderIR_ValidatePassSchedule( passes, count ) == qtrue );
	CHECK( glx::GLX_RenderIR_FormatPassSchedule( passes, count, schedule,
		glx::GLX_RENDER_IR_PASS_SCHEDULE_TEXT_BYTES ) > 0 );
	CHECK( std::strcmp( schedule,
		"frame-setup>sky-opaque-world>opaque-entities>dynamic-scene>transparent-layers>"
		"first-person-weapon>hud-2d>postprocess>output-export" ) == 0 );
	CHECK( glx::GLX_RenderIR_PassScheduleHash( passes, count ) != 0 );
	CHECK( passes[0].kind == glx::FramePassKind::FrameSetup );
	CHECK( passes[1].kind == glx::FramePassKind::SkyAndOpaqueWorld );
	CHECK( passes[3].kind == glx::FramePassKind::DynamicScene );
	CHECK( passes[7].kind == glx::FramePassKind::PostProcess );
	CHECK( passes[8].kind == glx::FramePassKind::OutputExport );

	CHECK( glx::GLX_RenderIR_DefaultPassSchedule( nullptr, 0, &count ) == qfalse );
	CHECK( count == glx::GLX_RENDER_IR_PASS_COUNT );

	passes[3].sequence = 4;
	CHECK( glx::GLX_RenderIR_ValidatePassSchedule( passes, glx::GLX_RENDER_IR_PASS_COUNT ) == qfalse );

	return true;
}

bool RenderIRProductsValidate()
{
	glx::UploadPlan upload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::TransientStream, 1, 128, 64, 32 );
	upload.texcoordBytes = 16;
	upload.alignment = 64;
	upload.sync = glx::UploadSyncPolicy::FrameFence;

	glx::MaterialIR material = glx::GLX_RenderIR_MakeMaterial(
		7, GLX_STAGE_ST0 | GLX_STAGE_TEXMOD, GLX_MATERIAL_STATE_DEPTHMASK_TRUE, 2 );
	material.rgbGen = GLX_MATERIAL_RGBGEN_VERTEX;
	material.alphaGen = GLX_MATERIAL_ALPHAGEN_VERTEX;
	material.tcGen0 = GLX_MATERIAL_TCGEN_TEXTURE;
	material.texMods0 = 1;

	glx::WorldPacket packet {};
	packet.packetIndex = 3;
	packet.pass = glx::FramePassKind::SkyAndOpaqueWorld;
	packet.surfaces = 4;
	packet.vertexes = 64;
	packet.indexes = 96;
	packet.firstItem = 10;
	packet.itemCount = 4;
	packet.vertexOffset = 128;
	packet.indexOffset = 256;
	packet.material = material;
	packet.upload = upload;

	glx::DynamicDraw draw {};
	draw.kind = glx::DynamicDrawKind::Indexed;
	draw.pass = glx::FramePassKind::DynamicScene;
	draw.primitive = 0x0004;
	draw.count = 96;
	draw.indexType = 0x1403;
	draw.indices = reinterpret_cast<const void *>( static_cast<uintptr_t>( 0x40 ) );
	draw.legacyReason = GLX_LEGACY_DELEGATION_NONE;
	draw.profilerPath = GLX_DRAW_STREAM_GENERIC;
	draw.material = material;
	draw.upload = upload;

	glx::OutputTransform output = glx::GLX_RenderIR_DefaultOutputTransform();
	CHECK( output.sceneColorSpace == glx::SceneColorSpace::DisplayReferredSdr );
	CHECK( output.toneMap == glx::ToneMapOperator::Legacy );
	CHECK( output.grade == glx::ColorGradeMode::None );
	CHECK( output.precisionMode == 8 );
	CHECK( output.bloomThreshold == 0.75f );
	CHECK( output.bloomSoftKnee == 0.0f );
	CHECK( output.gradeLift[0] == 0.0f );
	CHECK( output.gradeLift[1] == 0.0f );
	CHECK( output.gradeLift[2] == 0.0f );
	CHECK( output.gradeGamma[0] == 1.0f );
	CHECK( output.gradeGamma[1] == 1.0f );
	CHECK( output.gradeGamma[2] == 1.0f );
	CHECK( output.gradeGain[0] == 1.0f );
	CHECK( output.gradeGain[1] == 1.0f );
	CHECK( output.gradeGain[2] == 1.0f );
	CHECK( output.whitePointSourceKelvin == 6504.0f );
	CHECK( output.whitePointTargetKelvin == 6504.0f );
	CHECK( output.lutSize == 0.0f );
	CHECK( output.lutScale == 4.0f );
	CHECK( output.requestedBackend == ROUTPUT_REQUEST_AUTO );
	CHECK( output.selectedBackend == ROUTPUT_BACKEND_SDR_SRGB );
	CHECK( output.nativeBackend == ROUTPUT_BACKEND_SDR_SRGB );
	CHECK( output.outputHardwareActive == qfalse );
	CHECK( output.displayHdrHeadroom == 1.0f );
	CHECK( output.displaySdrWhiteNits == 203.0f );
	CHECK( output.displayMaxNits == 203.0f );
	CHECK( std::strcmp( RendererOutputRequestName( ROUTPUT_REQUEST_HDR10_PQ ), "hdr10-pq" ) == 0 );
	CHECK( std::strcmp( RendererOutputBackendName( ROUTPUT_BACKEND_MACOS_EDR ), "macos-edr" ) == 0 );
	CHECK( std::strcmp( glx::GLX_RenderIR_SceneColorSpaceName( output.sceneColorSpace ), "display-referred-sdr" ) == 0 );
	CHECK( std::strcmp( glx::GLX_RenderIR_ToneMapName( glx::ToneMapOperator::Aces ), "aces" ) == 0 );
	CHECK( std::strcmp( glx::GLX_RenderIR_ColorGradeName( glx::ColorGradeMode::LiftGammaGainLut3D ), "lgg-lut3d" ) == 0 );

	glx::PostNode post {};
	post.kind = glx::PostNodeKind::BloomFinal;
	post.pass = glx::FramePassKind::PostProcess;
	post.sequence = 1;
	post.output = output;

	CHECK( glx::GLX_RenderIR_ValidateUploadPlan( upload ) == qtrue );
	CHECK( glx::GLX_RenderIR_ValidateMaterial( material ) == qtrue );
	CHECK( glx::GLX_RenderIR_ValidateWorldPacket( packet ) == qtrue );
	CHECK( glx::GLX_RenderIR_ValidateDynamicDraw( draw ) == qtrue );
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qtrue );
	CHECK( glx::GLX_RenderIR_ValidatePostNode( post ) == qtrue );
	const unsigned int outputHash = glx::GLX_RenderIR_HashOutputTransform( output );
	const unsigned int postHash = glx::GLX_RenderIR_HashPostNode( post );
	CHECK( outputHash != 0 );
	CHECK( postHash != 0 );
	glx::OutputTransform changedOutput = output;
	changedOutput.exposure = 1.25f;
	CHECK( glx::GLX_RenderIR_HashOutputTransform( changedOutput ) != outputHash );
	glx::PostNode changedPost = post;
	changedPost.sequence++;
	CHECK( glx::GLX_RenderIR_HashPostNode( changedPost ) != postHash );

	CHECK( glx::GLX_RenderIR_ValidateUploadPlan(
		glx::GLX_RenderIR_MakeUploadPlan( glx::UploadPlanKind::ClientMemory, -1, 0, 0, 0 ) ) == qtrue );
	upload.bytes = 0;
	CHECK( glx::GLX_RenderIR_ValidateUploadPlan( upload ) == qfalse );
	draw.count = 0;
	CHECK( glx::GLX_RenderIR_ValidateDynamicDraw( draw ) == qfalse );
	output.exposure = -1.0f;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qfalse );
	output = glx::GLX_RenderIR_DefaultOutputTransform();
	output.precisionMode = 0;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qfalse );
	output = glx::GLX_RenderIR_DefaultOutputTransform();
	output.bloomSoftKnee = 1.1f;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qfalse );
	output = glx::GLX_RenderIR_DefaultOutputTransform();
	output.sceneColorSpace = glx::SceneColorSpace::SceneLinear;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qfalse );
	output.hdrMode = 1;
	output.precisionMode = 16;
	output.toneMap = glx::ToneMapOperator::Aces;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qtrue );
	output.selectedBackend = ROUTPUT_BACKEND_HDR10_PQ;
	output.outputHardwareActive = qtrue;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qtrue );
	output.grade = glx::ColorGradeMode::LiftGammaGainLut3D;
	output.gradeGamma[0] = 1.1f;
	output.whitePointTargetKelvin = 6000.0f;
	output.lutSize = 16.0f;
	output.lutScale = 4.0f;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qtrue );
	output.gradeGamma[1] = 0.0f;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qfalse );
	output.gradeGamma[1] = 1.0f;
	output.lutSize = -1.0f;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qfalse );
	output = glx::GLX_RenderIR_DefaultOutputTransform();
	output.outputHardwareActive = qtrue;
	CHECK( glx::GLX_RenderIR_ValidateOutputTransform( output ) == qfalse );

	return true;
}

bool RenderIRTierMappingKeepsSingleProductContract()
{
	glx::FeatureSet features {};

	CHECK( glx::GLX_RenderIR_TierForVersionAndFeatures( 1, 2, features ) == glx::RenderProductTier::GL12 );
	CHECK( glx::GLX_RenderIR_TierForVersionAndFeatures( 2, 1, features ) == glx::RenderProductTier::GL2X );
	CHECK( glx::GLX_RenderIR_TierForVersionAndFeatures( 3, 3, features ) == glx::RenderProductTier::GL3X );
	CHECK( glx::GLX_RenderIR_TierForVersionAndFeatures( 4, 1, features ) == glx::RenderProductTier::GL41 );
	CHECK( glx::GLX_RenderIR_TierForVersionAndFeatures( 4, 6, features ) == glx::RenderProductTier::GL46 );

	features.bufferStorage = qtrue;
	features.syncObjects = qtrue;
	features.directStateAccess = qtrue;
	CHECK( glx::GLX_RenderIR_TierForVersionAndFeatures( 4, 6, features ) == glx::RenderProductTier::GL46 );

	const glx::RenderProductTier tiers[] = {
		glx::RenderProductTier::GL12,
		glx::RenderProductTier::GL2X,
		glx::RenderProductTier::GL3X,
		glx::RenderProductTier::GL41,
		glx::RenderProductTier::GL46
	};
	const glx::RenderProductKind products[] = {
		glx::RenderProductKind::FramePass,
		glx::RenderProductKind::WorldPacket,
		glx::RenderProductKind::DynamicDraw,
		glx::RenderProductKind::MaterialIR,
		glx::RenderProductKind::UploadPlan,
		glx::RenderProductKind::PostNode,
		glx::RenderProductKind::OutputTransform
	};

	for ( const glx::RenderProductTier tier : tiers ) {
		for ( const glx::RenderProductKind product : products ) {
			CHECK( glx::GLX_RenderIR_TierConsumesProduct( tier, product ) == qtrue );
		}
	}
	CHECK( glx::GLX_RenderIR_TierName( glx::RenderProductTier::GL46 )[0] == 'G' );

	return true;
}

bool GL12ExecutorPolicyIsFixedFunctionAndSdrOnly()
{
	const glx::TierExecutionPolicy policy =
		glx::GLX_RenderIR_TierExecutionPolicy( glx::RenderProductTier::GL12 );

	CHECK( std::strcmp( policy.executorName, "fixed-function" ) == 0 );
	CHECK( policy.fixedFunction == qtrue );
	CHECK( policy.clientMemoryDraws == qtrue );
	CHECK( policy.streamUploads == qfalse );
	CHECK( policy.materialCompiler == qfalse );
	CHECK( policy.modernPostChain == qfalse );
	CHECK( policy.sceneLinearOutput == qfalse );
	CHECK( policy.fboPostProcess == qfalse );
	CHECK( policy.uboFrameObjectConstants == qfalse );
	CHECK( policy.timerQueries == qfalse );
	CHECK( policy.syncAwareUploads == qfalse );
	CHECK( policy.staticBufferOwnership == qfalse );
	CHECK( policy.dynamicBufferOwnership == qfalse );
	CHECK( policy.persistentUploads == qfalse );
	CHECK( policy.indirectSubmission == qfalse );
	CHECK( policy.directStateAccess == qfalse );
	CHECK( policy.lightmaps == qtrue );
	CHECK( policy.multitexture == qtrue );
	CHECK( policy.fog == qtrue );
	CHECK( policy.sprites == qtrue );
	CHECK( policy.beams == qtrue );
	CHECK( policy.dynamicLights == qtrue );
	CHECK( policy.stencilShadowsIfAvailable == qtrue );
	CHECK( policy.screenshots == qtrue );
	CHECK( policy.demos == qtrue );
	CHECK( std::strstr( policy.unavailable, "GLSL material compiler" ) != nullptr );

	glx::UploadPlan clientUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::ClientMemory, -1, 0, 0, 0 );
	glx::UploadPlan streamUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::TransientStream, 1, 128, 64, 32 );
	glx::UploadPlan staticUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::StaticWorld, -1, 128, 64, 32 );

	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL12, clientUpload ) == qtrue );
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL12, staticUpload ) == qtrue );
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL12, streamUpload ) == qfalse );
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL2X, streamUpload ) == qtrue );

	glx::MaterialIR material = glx::GLX_RenderIR_MakeMaterial(
		0, GLX_STAGE_LIGHTMAP | GLX_STAGE_MULTITEXTURE |
			GLX_STAGE_SHADOW_PASS | GLX_STAGE_BEAM_PASS,
		GLX_MATERIAL_STATE_DEPTHMASK_TRUE, 2 );
	material.fogPass = qtrue;

	glx::DynamicDraw draw {};
	draw.kind = glx::DynamicDrawKind::Indexed;
	draw.pass = glx::FramePassKind::DynamicScene;
	draw.primitive = 0x0004;
	draw.count = 6;
	draw.indexType = 0x1403;
	draw.indices = reinterpret_cast<const void *>( static_cast<uintptr_t>( 0x20 ) );
	draw.legacyReason = GLX_LEGACY_DELEGATION_GENERIC;
	draw.profilerPath = GLX_DRAW_GENERIC;
	draw.material = material;
	draw.upload = clientUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL12, draw ) == qtrue );
	draw.upload = streamUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL12, draw ) == qfalse );

	glx::WorldPacket packet {};
	packet.pass = glx::FramePassKind::SkyAndOpaqueWorld;
	packet.surfaces = 1;
	packet.vertexes = 4;
	packet.indexes = 6;
	packet.itemCount = 1;
	packet.material = material;
	packet.upload = staticUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsWorldPacket( glx::RenderProductTier::GL12, packet ) == qtrue );

	glx::OutputTransform output = glx::GLX_RenderIR_DefaultOutputTransform();
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL12, output ) == qtrue );
	output.transfer = glx::OutputTransfer::Hdr10Pq;
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL12, output ) == qfalse );

	glx::PostNode post {};
	post.kind = glx::PostNodeKind::GammaDirect;
	post.pass = glx::FramePassKind::PostProcess;
	post.sequence = 0;
	post.output = glx::GLX_RenderIR_DefaultOutputTransform();
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL12, post ) == qtrue );
	post.kind = glx::PostNodeKind::BloomFinal;
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL12, post ) == qfalse );

	return true;
}

bool GL2XExecutorPolicyIsProgrammableAndAvoidsLaterRequirements()
{
	const glx::TierExecutionPolicy policy =
		glx::GLX_RenderIR_TierExecutionPolicy( glx::RenderProductTier::GL2X );

	CHECK( std::strcmp( policy.executorName, "programmable" ) == 0 );
	CHECK( policy.fixedFunction == qfalse );
	CHECK( policy.clientMemoryDraws == qtrue );
	CHECK( policy.streamUploads == qtrue );
	CHECK( policy.materialCompiler == qtrue );
	CHECK( policy.commonMaterials == qtrue );
	CHECK( policy.dynamicEntities == qtrue );
	CHECK( policy.postProcessLite == qtrue );
	CHECK( policy.modernPostChain == qfalse );
	CHECK( policy.sceneLinearOutput == qfalse );
	CHECK( policy.fboPostProcess == qfalse );
	CHECK( policy.uboFrameObjectConstants == qfalse );
	CHECK( policy.timerQueries == qfalse );
	CHECK( policy.syncAwareUploads == qfalse );
	CHECK( policy.staticBufferOwnership == qfalse );
	CHECK( policy.dynamicBufferOwnership == qfalse );
	CHECK( policy.persistentUploads == qfalse );
	CHECK( policy.indirectSubmission == qfalse );
	CHECK( policy.directStateAccess == qfalse );
	CHECK( policy.lightmaps == qtrue );
	CHECK( policy.multitexture == qtrue );
	CHECK( policy.fog == qtrue );
	CHECK( policy.sprites == qtrue );
	CHECK( policy.beams == qtrue );
	CHECK( policy.dynamicLights == qtrue );
	CHECK( policy.screenshots == qtrue );
	CHECK( policy.demos == qtrue );
	CHECK( std::strstr( policy.unavailable, "persistent uploads" ) != nullptr );

	glx::UploadPlan streamUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::TransientStream, static_cast<int>( glx::StreamStrategy::MapBufferRange ),
		192, 96, 48 );
	streamUpload.texcoordBytes = 24;
	streamUpload.sync = glx::UploadSyncPolicy::FrameFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL2X, streamUpload ) == qtrue );

	glx::UploadPlan persistentUpload = streamUpload;
	persistentUpload.strategy = static_cast<int>( glx::StreamStrategy::PersistentMapped );
	persistentUpload.sync = glx::UploadSyncPolicy::PersistentFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL2X, persistentUpload ) == qfalse );
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL46, persistentUpload ) == qtrue );

	glx::MaterialIR material = glx::GLX_RenderIR_MakeMaterial(
		0, GLX_STAGE_LIGHTMAP | GLX_STAGE_MULTITEXTURE | GLX_STAGE_TEXMOD |
			GLX_STAGE_DEPTH_FRAGMENT | GLX_STAGE_ENVIRONMENT,
		GLX_MATERIAL_STATE_DEPTHMASK_TRUE | GLX_MATERIAL_STATE_ATEST_GE_80, 2 );
	material.rgbGen = GLX_MATERIAL_RGBGEN_VERTEX;
	material.alphaGen = GLX_MATERIAL_ALPHAGEN_VERTEX;
	material.tcGen0 = GLX_MATERIAL_TCGEN_TEXTURE;
	material.tcGen1 = GLX_MATERIAL_TCGEN_LIGHTMAP;
	material.texMods0 = 1;
	material.materialCombine = GLX_MATERIAL_COMBINE_MODULATE;
	CHECK( glx::GLX_RenderIR_TierSupportsMaterial( glx::RenderProductTier::GL2X, material ) == qtrue );

	glx::DynamicDraw draw {};
	draw.kind = glx::DynamicDrawKind::Indexed;
	draw.pass = glx::FramePassKind::DynamicScene;
	draw.primitive = 0x0004;
	draw.count = 96;
	draw.indexType = 0x1403;
	draw.indices = reinterpret_cast<const void *>( static_cast<uintptr_t>( 0x40 ) );
	draw.legacyReason = GLX_LEGACY_DELEGATION_NONE;
	draw.profilerPath = GLX_DRAW_STREAM_GENERIC;
	draw.material = material;
	draw.upload = streamUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL2X, draw ) == qtrue );
	draw.upload = persistentUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL2X, draw ) == qfalse );

	glx::PostNode post {};
	post.kind = glx::PostNodeKind::BloomFinal;
	post.pass = glx::FramePassKind::PostProcess;
	post.sequence = 1;
	post.output = glx::GLX_RenderIR_DefaultOutputTransform();
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL2X, post ) == qtrue );
	post.kind = glx::PostNodeKind::ToneMap;
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL2X, post ) == qfalse );

	glx::OutputTransform output = glx::GLX_RenderIR_DefaultOutputTransform();
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL2X, output ) == qtrue );
	output.transfer = glx::OutputTransfer::Hdr10Pq;
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL2X, output ) == qfalse );

	return true;
}

bool GL3XExecutorPolicyIsPerformanceAndAvoidsGL4OnlyRequirements()
{
	const glx::TierExecutionPolicy policy =
		glx::GLX_RenderIR_TierExecutionPolicy( glx::RenderProductTier::GL3X );

	CHECK( std::strcmp( policy.executorName, "performance" ) == 0 );
	CHECK( policy.fixedFunction == qfalse );
	CHECK( policy.streamUploads == qtrue );
	CHECK( policy.materialCompiler == qtrue );
	CHECK( policy.commonMaterials == qtrue );
	CHECK( policy.dynamicEntities == qtrue );
	CHECK( policy.modernPostChain == qtrue );
	CHECK( policy.sceneLinearOutput == qtrue );
	CHECK( policy.fboPostProcess == qtrue );
	CHECK( policy.uboFrameObjectConstants == qtrue );
	CHECK( policy.timerQueries == qtrue );
	CHECK( policy.syncAwareUploads == qtrue );
	CHECK( policy.staticBufferOwnership == qtrue );
	CHECK( policy.dynamicBufferOwnership == qtrue );
	CHECK( policy.highQualitySdrOutput == qtrue );
	CHECK( policy.optionalHardwareHdrOutput == qtrue );
	CHECK( policy.persistentUploads == qfalse );
	CHECK( policy.indirectSubmission == qfalse );
	CHECK( policy.directStateAccess == qfalse );
	CHECK( policy.screenshots == qtrue );
	CHECK( policy.demos == qtrue );
	CHECK( std::strstr( policy.unavailable, "persistent" ) != nullptr );
	CHECK( std::strstr( policy.unavailable, "direct-state access" ) != nullptr );

	glx::UploadPlan staticUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::StaticWorld, static_cast<int>( glx::StreamStrategy::MapBufferRange ),
		4096, 3072, 1024 );
	staticUpload.sync = glx::UploadSyncPolicy::FrameFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL3X, staticUpload ) == qtrue );

	glx::UploadPlan streamUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::TransientStream, static_cast<int>( glx::StreamStrategy::MapBufferRange ),
		512, 256, 128 );
	streamUpload.texcoordBytes = 64;
	streamUpload.sync = glx::UploadSyncPolicy::FrameFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL3X, streamUpload ) == qtrue );

	glx::UploadPlan postUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::PostProcess, static_cast<int>( glx::StreamStrategy::MapBufferRange ),
		128, 64, 32 );
	postUpload.sync = glx::UploadSyncPolicy::FrameFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL3X, postUpload ) == qtrue );

	glx::UploadPlan persistentUpload = streamUpload;
	persistentUpload.strategy = static_cast<int>( glx::StreamStrategy::PersistentMapped );
	persistentUpload.sync = glx::UploadSyncPolicy::PersistentFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL3X, persistentUpload ) == qfalse );
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL46, persistentUpload ) == qtrue );

	glx::MaterialIR material = glx::GLX_RenderIR_MakeMaterial(
		0, GLX_STAGE_LIGHTMAP | GLX_STAGE_MULTITEXTURE | GLX_STAGE_TEXMOD |
			GLX_STAGE_DEPTH_FRAGMENT | GLX_STAGE_ENVIRONMENT,
		GLX_MATERIAL_STATE_DEPTHMASK_TRUE | GLX_MATERIAL_STATE_ATEST_GE_80, 2 );
	material.rgbGen = GLX_MATERIAL_RGBGEN_VERTEX;
	material.alphaGen = GLX_MATERIAL_ALPHAGEN_VERTEX;
	CHECK( glx::GLX_RenderIR_TierSupportsMaterial( glx::RenderProductTier::GL3X, material ) == qtrue );

	glx::WorldPacket packet {};
	packet.pass = glx::FramePassKind::SkyAndOpaqueWorld;
	packet.surfaces = 4;
	packet.vertexes = 128;
	packet.indexes = 192;
	packet.itemCount = 4;
	packet.material = material;
	packet.upload = staticUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsWorldPacket( glx::RenderProductTier::GL3X, packet ) == qtrue );
	packet.upload = persistentUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsWorldPacket( glx::RenderProductTier::GL3X, packet ) == qfalse );

	glx::DynamicDraw draw {};
	draw.kind = glx::DynamicDrawKind::Indexed;
	draw.pass = glx::FramePassKind::DynamicScene;
	draw.primitive = 0x0004;
	draw.count = 96;
	draw.indexType = 0x1403;
	draw.indices = reinterpret_cast<const void *>( static_cast<uintptr_t>( 0x80 ) );
	draw.legacyReason = GLX_LEGACY_DELEGATION_NONE;
	draw.profilerPath = GLX_DRAW_STREAM_GENERIC;
	draw.material = material;
	draw.upload = streamUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL3X, draw ) == qtrue );
	draw.upload = persistentUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL3X, draw ) == qfalse );

	glx::OutputTransform output = glx::GLX_RenderIR_DefaultOutputTransform();
	output.transfer = glx::OutputTransfer::LinearSrgb;
	output.sceneColorSpace = glx::SceneColorSpace::SceneLinear;
	output.hdrMode = 1;
	output.precisionMode = 16;
	output.toneMap = glx::ToneMapOperator::Aces;
	output.bloomSoftKnee = 0.5f;
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL3X, output ) == qtrue );
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL2X, output ) == qfalse );

	glx::PostNode post {};
	post.kind = glx::PostNodeKind::ToneMap;
	post.pass = glx::FramePassKind::PostProcess;
	post.sequence = 2;
	post.output = output;
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL3X, post ) == qtrue );
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL2X, post ) == qfalse );
	post.kind = glx::PostNodeKind::Grade;
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL3X, post ) == qtrue );

	return true;
}

bool PostOutputPlansRequireModernOwnedContract()
{
	glx::OutputTransform output = glx::GLX_RenderIR_DefaultOutputTransform();
	output.sceneColorSpace = glx::SceneColorSpace::SceneLinear;
	output.transfer = glx::OutputTransfer::SdrSrgb;
	output.toneMap = glx::ToneMapOperator::Aces;
	output.grade = glx::ColorGradeMode::LiftGammaGain;
	output.hdrMode = 1;
	output.precisionMode = 16;
	output.paperWhiteNits = 203.0f;
	output.maxOutputNits = 203.0f;

	glx::PostOutputPlanInputs inputs {};
	inputs.tier = glx::RenderProductTier::GL3X;
	inputs.output = output;
	inputs.fboReady = qtrue;
	inputs.programReady = qtrue;
	inputs.framebufferFnsReady = qtrue;
	inputs.outputContractValid = qtrue;
	inputs.bloomAvailable = qfalse;
	inputs.minimized = qfalse;
	inputs.windowAdjusted = qfalse;
	inputs.screenshotMask = 0;
	inputs.fboReadIndex = 2;
	inputs.sequenceBase = 7;
	inputs.flags = 0x2u;

	glx::PostOutputPlan plan = glx::GLX_RenderIR_BuildPostOutputPlan( inputs );
	CHECK( plan.glxOwned == qtrue );
	CHECK( plan.fallbackReasons == glx::GLX_POST_OUTPUT_FALLBACK_NONE );
	CHECK( plan.outputTransformPresent == qtrue );
	CHECK( plan.predictedResult == GLX_POSTPROCESS_RESULT_GAMMA_DIRECT );
	CHECK( plan.nodeCount == 3 );
	CHECK( plan.nodes[0].kind == glx::PostNodeKind::Grade );
	CHECK( plan.nodes[1].kind == glx::PostNodeKind::ToneMap );
	CHECK( plan.nodes[2].kind == glx::PostNodeKind::GammaDirect );
	CHECK( plan.nodes[0].sequence == 7 );
	CHECK( plan.nodes[2].outputTarget == 0 );
	CHECK( plan.hash != 0u );
	for ( int i = 0; i < plan.nodeCount; i++ ) {
		CHECK( glx::GLX_RenderIR_TierSupportsPostNode( inputs.tier, plan.nodes[i] ) == qtrue );
	}
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( inputs.tier, plan.output ) == qtrue );

	inputs.tier = glx::RenderProductTier::GL2X;
	plan = glx::GLX_RenderIR_BuildPostOutputPlan( inputs );
	CHECK( plan.glxOwned == qfalse );
	CHECK( ( plan.fallbackReasons & glx::GLX_POST_OUTPUT_FALLBACK_TIER ) != 0u );
	CHECK( plan.predictedResult == GLX_POSTPROCESS_RESULT_GAMMA_DIRECT );

	inputs.tier = glx::RenderProductTier::GL46;
	inputs.minimized = qtrue;
	plan = glx::GLX_RenderIR_BuildPostOutputPlan( inputs );
	CHECK( plan.glxOwned == qfalse );
	CHECK( ( plan.fallbackReasons & glx::GLX_POST_OUTPUT_FALLBACK_MINIMIZED ) != 0u );
	CHECK( plan.predictedResult == GLX_POSTPROCESS_RESULT_MINIMIZED );

	inputs.minimized = qfalse;
	inputs.outputContractValid = qfalse;
	plan = glx::GLX_RenderIR_BuildPostOutputPlan( inputs );
	CHECK( plan.glxOwned == qfalse );
	CHECK( ( plan.fallbackReasons & glx::GLX_POST_OUTPUT_FALLBACK_OUTPUT_CONTRACT ) != 0u );

	inputs.outputContractValid = qtrue;
	inputs.bloomAvailable = qtrue;
	inputs.windowAdjusted = qtrue;
	output.toneMap = glx::ToneMapOperator::Legacy;
	output.grade = glx::ColorGradeMode::None;
	inputs.output = output;
	plan = glx::GLX_RenderIR_BuildPostOutputPlan( inputs );
	CHECK( plan.glxOwned == qtrue );
	CHECK( plan.predictedResult == GLX_POSTPROCESS_RESULT_GAMMA_BLIT );
	CHECK( plan.nodeCount == 2 );
	CHECK( plan.nodes[0].kind == glx::PostNodeKind::BloomPrefinal );
	CHECK( plan.nodes[1].kind == glx::PostNodeKind::GammaBlit );

	return true;
}

bool GL41ExecutorPolicyIsMacModernAndAvoidsUnavailableAppleFeatures()
{
	const glx::TierExecutionPolicy policy =
		glx::GLX_RenderIR_TierExecutionPolicy( glx::RenderProductTier::GL41 );

	CHECK( std::strcmp( policy.executorName, "mac-modern" ) == 0 );
	CHECK( policy.fixedFunction == qfalse );
	CHECK( policy.streamUploads == qtrue );
	CHECK( policy.materialCompiler == qtrue );
	CHECK( policy.commonMaterials == qtrue );
	CHECK( policy.dynamicEntities == qtrue );
	CHECK( policy.modernPostChain == qtrue );
	CHECK( policy.sceneLinearOutput == qtrue );
	CHECK( policy.fboPostProcess == qtrue );
	CHECK( policy.uboFrameObjectConstants == qtrue );
	CHECK( policy.timerQueries == qtrue );
	CHECK( policy.syncAwareUploads == qtrue );
	CHECK( policy.staticBufferOwnership == qtrue );
	CHECK( policy.dynamicBufferOwnership == qtrue );
	CHECK( policy.macOS41Ceiling == qtrue );
	CHECK( policy.highQualitySdrOutput == qtrue );
	CHECK( policy.optionalHardwareHdrOutput == qtrue );
	CHECK( policy.persistentUploads == qfalse );
	CHECK( policy.indirectSubmission == qfalse );
	CHECK( policy.directStateAccess == qfalse );
	CHECK( policy.debugOutputRequired == qfalse );
	CHECK( policy.bufferStorageRequired == qfalse );
	CHECK( policy.directStateAccessRequired == qfalse );
	CHECK( policy.multiDrawIndirectRequired == qfalse );
	CHECK( policy.screenshots == qtrue );
	CHECK( policy.demos == qtrue );
	CHECK( std::strstr( policy.unavailable, "GL4.3" ) != nullptr );
	CHECK( std::strstr( policy.unavailable, "GL4.4" ) != nullptr );
	CHECK( std::strstr( policy.unavailable, "GL4.5" ) != nullptr );

	glx::UploadPlan staticUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::StaticWorld, static_cast<int>( glx::StreamStrategy::MapBufferRange ),
		8192, 6144, 2048 );
	staticUpload.sync = glx::UploadSyncPolicy::FrameFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL41, staticUpload ) == qtrue );

	glx::UploadPlan streamUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::TransientStream, static_cast<int>( glx::StreamStrategy::MapBufferRange ),
		1024, 512, 256 );
	streamUpload.texcoordBytes = 128;
	streamUpload.sync = glx::UploadSyncPolicy::FrameFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL41, streamUpload ) == qtrue );

	glx::UploadPlan persistentUpload = streamUpload;
	persistentUpload.strategy = static_cast<int>( glx::StreamStrategy::PersistentMapped );
	persistentUpload.sync = glx::UploadSyncPolicy::PersistentFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL41, persistentUpload ) == qfalse );
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL46, persistentUpload ) == qtrue );

	glx::MaterialIR material = glx::GLX_RenderIR_MakeMaterial(
		0, GLX_STAGE_LIGHTMAP | GLX_STAGE_MULTITEXTURE | GLX_STAGE_TEXMOD |
			GLX_STAGE_DEPTH_FRAGMENT | GLX_STAGE_ENVIRONMENT,
		GLX_MATERIAL_STATE_DEPTHMASK_TRUE | GLX_MATERIAL_STATE_ATEST_GE_80, 3 );
	material.rgbGen = GLX_MATERIAL_RGBGEN_VERTEX;
	material.alphaGen = GLX_MATERIAL_ALPHAGEN_VERTEX;
	material.tcGen0 = GLX_MATERIAL_TCGEN_TEXTURE;
	material.tcGen1 = GLX_MATERIAL_TCGEN_LIGHTMAP;
	CHECK( glx::GLX_RenderIR_TierSupportsMaterial( glx::RenderProductTier::GL41, material ) == qtrue );

	glx::WorldPacket packet {};
	packet.pass = glx::FramePassKind::SkyAndOpaqueWorld;
	packet.surfaces = 8;
	packet.vertexes = 256;
	packet.indexes = 384;
	packet.itemCount = 8;
	packet.material = material;
	packet.upload = staticUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsWorldPacket( glx::RenderProductTier::GL41, packet ) == qtrue );
	packet.upload = persistentUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsWorldPacket( glx::RenderProductTier::GL41, packet ) == qfalse );

	glx::DynamicDraw draw {};
	draw.kind = glx::DynamicDrawKind::Indexed;
	draw.pass = glx::FramePassKind::DynamicScene;
	draw.primitive = 0x0004;
	draw.count = 192;
	draw.indexType = 0x1403;
	draw.indices = reinterpret_cast<const void *>( static_cast<uintptr_t>( 0x100 ) );
	draw.legacyReason = GLX_LEGACY_DELEGATION_NONE;
	draw.profilerPath = GLX_DRAW_STREAM_GENERIC;
	draw.material = material;
	draw.upload = streamUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL41, draw ) == qtrue );
	draw.upload = persistentUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL41, draw ) == qfalse );

	glx::OutputTransform output = glx::GLX_RenderIR_DefaultOutputTransform();
	output.transfer = glx::OutputTransfer::MacEdr;
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL41, output ) == qtrue );
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL2X, output ) == qfalse );

	glx::PostNode post {};
	post.kind = glx::PostNodeKind::ToneMap;
	post.pass = glx::FramePassKind::PostProcess;
	post.sequence = 3;
	post.output = output;
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL41, post ) == qtrue );
	post.kind = glx::PostNodeKind::Grade;
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL41, post ) == qtrue );

	return true;
}

bool GL46ExecutorPolicyIsHighEndAndRequiresModernDriverFeatures()
{
	const glx::TierExecutionPolicy policy =
		glx::GLX_RenderIR_TierExecutionPolicy( glx::RenderProductTier::GL46 );

	CHECK( std::strcmp( policy.executorName, "high-end" ) == 0 );
	CHECK( policy.fixedFunction == qfalse );
	CHECK( policy.streamUploads == qtrue );
	CHECK( policy.materialCompiler == qtrue );
	CHECK( policy.commonMaterials == qtrue );
	CHECK( policy.dynamicEntities == qtrue );
	CHECK( policy.modernPostChain == qtrue );
	CHECK( policy.sceneLinearOutput == qtrue );
	CHECK( policy.fboPostProcess == qtrue );
	CHECK( policy.uboFrameObjectConstants == qtrue );
	CHECK( policy.timerQueries == qtrue );
	CHECK( policy.syncAwareUploads == qtrue );
	CHECK( policy.staticBufferOwnership == qtrue );
	CHECK( policy.dynamicBufferOwnership == qtrue );
	CHECK( policy.persistentUploads == qtrue );
	CHECK( policy.indirectSubmission == qtrue );
	CHECK( policy.directStateAccess == qtrue );
	CHECK( policy.debugOutputRequired == qtrue );
	CHECK( policy.bufferStorageRequired == qtrue );
	CHECK( policy.directStateAccessRequired == qtrue );
	CHECK( policy.multiDrawIndirectRequired == qtrue );
	CHECK( policy.bufferStorageUploads == qtrue );
	CHECK( policy.syncHeavyStreaming == qtrue );
	CHECK( policy.multiDrawIndirectSubmission == qtrue );
	CHECK( policy.aggressiveStaticWorldSubmission == qtrue );
	CHECK( policy.detailedGpuCounters == qtrue );
	CHECK( policy.optionalHardwareHdrOutput == qtrue );
	CHECK( std::strcmp( policy.unavailable, "none" ) == 0 );

	glx::UploadPlan persistentUpload = glx::GLX_RenderIR_MakeUploadPlan(
		glx::UploadPlanKind::TransientStream, static_cast<int>( glx::StreamStrategy::PersistentMapped ),
		2048, 1024, 512 );
	persistentUpload.texcoordBytes = 256;
	persistentUpload.sync = glx::UploadSyncPolicy::PersistentFence;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL46, persistentUpload ) == qtrue );
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL41, persistentUpload ) == qfalse );

	glx::UploadPlan staticPersistentUpload = persistentUpload;
	staticPersistentUpload.kind = glx::UploadPlanKind::StaticWorld;
	staticPersistentUpload.bytes = 16384;
	staticPersistentUpload.vertexBytes = 12288;
	staticPersistentUpload.indexBytes = 4096;
	staticPersistentUpload.texcoordBytes = 0;
	CHECK( glx::GLX_RenderIR_TierSupportsUploadPlan( glx::RenderProductTier::GL46, staticPersistentUpload ) == qtrue );

	glx::MaterialIR material = glx::GLX_RenderIR_MakeMaterial(
		0, GLX_STAGE_LIGHTMAP | GLX_STAGE_MULTITEXTURE | GLX_STAGE_TEXMOD |
			GLX_STAGE_DEPTH_FRAGMENT | GLX_STAGE_ENVIRONMENT | GLX_STAGE_SCREEN_MAP |
			GLX_STAGE_DLIGHT_MAP,
		GLX_MATERIAL_STATE_DEPTHMASK_TRUE | GLX_MATERIAL_STATE_ATEST_GE_80, 4 );
	material.rgbGen = GLX_MATERIAL_RGBGEN_VERTEX;
	material.alphaGen = GLX_MATERIAL_ALPHAGEN_VERTEX;
	material.tcGen0 = GLX_MATERIAL_TCGEN_TEXTURE;
	material.tcGen1 = GLX_MATERIAL_TCGEN_LIGHTMAP;
	material.texMods0 = 2;
	material.texMods1 = 1;
	CHECK( glx::GLX_RenderIR_TierSupportsMaterial( glx::RenderProductTier::GL46, material ) == qtrue );

	glx::WorldPacket packet {};
	packet.pass = glx::FramePassKind::SkyAndOpaqueWorld;
	packet.surfaces = 16;
	packet.vertexes = 512;
	packet.indexes = 768;
	packet.itemCount = 16;
	packet.material = material;
	packet.upload = staticPersistentUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsWorldPacket( glx::RenderProductTier::GL46, packet ) == qtrue );

	glx::DynamicDraw draw {};
	draw.kind = glx::DynamicDrawKind::Indexed;
	draw.pass = glx::FramePassKind::DynamicScene;
	draw.primitive = 0x0004;
	draw.count = 384;
	draw.indexType = 0x1403;
	draw.indices = reinterpret_cast<const void *>( static_cast<uintptr_t>( 0x200 ) );
	draw.legacyReason = GLX_LEGACY_DELEGATION_NONE;
	draw.profilerPath = GLX_DRAW_STREAM_GENERIC;
	draw.material = material;
	draw.upload = persistentUpload;
	CHECK( glx::GLX_RenderIR_TierSupportsDynamicDraw( glx::RenderProductTier::GL46, draw ) == qtrue );

	glx::OutputTransform output = glx::GLX_RenderIR_DefaultOutputTransform();
	output.transfer = glx::OutputTransfer::Hdr10Pq;
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL46, output ) == qtrue );
	CHECK( glx::GLX_RenderIR_TierSupportsOutputTransform( glx::RenderProductTier::GL2X, output ) == qfalse );

	glx::PostNode post {};
	post.kind = glx::PostNodeKind::Grade;
	post.pass = glx::FramePassKind::PostProcess;
	post.sequence = 4;
	post.output = output;
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL46, post ) == qtrue );
	post.kind = glx::PostNodeKind::ToneMap;
	CHECK( glx::GLX_RenderIR_TierSupportsPostNode( glx::RenderProductTier::GL46, post ) == qtrue );

	return true;
}

} // namespace

int main()
{
	struct Test {
		const char *name;
		bool ( *fn )();
	};

	const Test tests[] = {
		{ "MaterialKeysClassifyRcShapes", MaterialKeysClassifyRcShapes },
		{ "MaterialKeysRejectUnsupportedCombines", MaterialKeysRejectUnsupportedCombines },
		{ "MaterialKeysTreatSpecialSceneFlagsAsGates", MaterialKeysTreatSpecialSceneFlagsAsGates },
		{ "MaterialStageKeysCoverPreparedIdTech3StageLanguage", MaterialStageKeysCoverPreparedIdTech3StageLanguage },
		{ "MaterialIRCompilesToProgramStatePlans", MaterialIRCompilesToProgramStatePlans },
		{ "MaterialParameterBlocksMirrorNativeRenderInputs", MaterialParameterBlocksMirrorNativeRenderInputs },
		{ "StreamGatesMatchRcAllowlist", StreamGatesMatchRcAllowlist },
		{ "StreamBroadKeyModeRemainsDeveloperEscapeHatch", StreamBroadKeyModeRemainsDeveloperEscapeHatch },
		{ "StreamSpecialSceneGatesAreExplicit", StreamSpecialSceneGatesAreExplicit },
		{ "StreamShadowGateIsExplicit", StreamShadowGateIsExplicit },
		{ "StreamBeamGateIsExplicit", StreamBeamGateIsExplicit },
		{ "StreamPostProcessGateIsExplicit", StreamPostProcessGateIsExplicit },
		{ "StreamDynamicCategoriesNormalizeToSceneProducts", StreamDynamicCategoriesNormalizeToSceneProducts },
		{ "CapabilityLogicClassifiesTiersAndExtensions", CapabilityLogicClassifiesTiersAndExtensions },
		{ "StreamStrategySelectionFollowsFallbackLadder", StreamStrategySelectionFollowsFallbackLadder },
		{ "StaticWorldPacketLogicClassifiesRunsAndPolicies", StaticWorldPacketLogicClassifiesRunsAndPolicies },
		{ "RenderIRDefaultPassScheduleIsDeterministic", RenderIRDefaultPassScheduleIsDeterministic },
		{ "RenderIRProductsValidate", RenderIRProductsValidate },
		{ "RenderIRTierMappingKeepsSingleProductContract", RenderIRTierMappingKeepsSingleProductContract },
		{ "GL12ExecutorPolicyIsFixedFunctionAndSdrOnly", GL12ExecutorPolicyIsFixedFunctionAndSdrOnly },
		{ "GL2XExecutorPolicyIsProgrammableAndAvoidsLaterRequirements", GL2XExecutorPolicyIsProgrammableAndAvoidsLaterRequirements },
		{ "GL3XExecutorPolicyIsPerformanceAndAvoidsGL4OnlyRequirements", GL3XExecutorPolicyIsPerformanceAndAvoidsGL4OnlyRequirements },
		{ "PostOutputPlansRequireModernOwnedContract", PostOutputPlansRequireModernOwnedContract },
		{ "GL41ExecutorPolicyIsMacModernAndAvoidsUnavailableAppleFeatures", GL41ExecutorPolicyIsMacModernAndAvoidsUnavailableAppleFeatures },
		{ "GL46ExecutorPolicyIsHighEndAndRequiresModernDriverFeatures", GL46ExecutorPolicyIsHighEndAndRequiresModernDriverFeatures },
	};

	for ( const Test &test : tests ) {
		if ( !test.fn() ) {
			std::fprintf( stderr, "FAILED: %s\n", test.name );
			return 1;
		}
		std::printf( "passed: %s\n", test.name );
	}

	return 0;
}
