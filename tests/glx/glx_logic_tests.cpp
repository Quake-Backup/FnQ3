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
#include "glx_static_world_logic.h"
#include "glx_stream_logic.h"

#include <cstdio>

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

	CHECK( glx::GLX_Material_StageKeyForInputsFull(
		GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT | GLX_STAGE_DEPTH_FRAGMENT,
		0x1234, 0,
		GLX_MATERIAL_RGBGEN_WAVEFORM, GLX_MATERIAL_ALPHAGEN_PORTAL,
		GLX_MATERIAL_TCGEN_VECTOR, GLX_MATERIAL_TCGEN_LIGHTMAP,
		glx::GLX_MATERIAL_MAX_TEXMODS_PER_BUNDLE,
		glx::GLX_MATERIAL_MAX_TEXMODS_PER_BUNDLE,
		fiveTexModMask, fiveTexModMask, fiveTexModSequence, fiveTexModSequence,
		qfalse, &key ) == qtrue );
	CHECK( key.flags == ( GLX_STAGE_TEXMOD | GLX_STAGE_ENVIRONMENT | GLX_STAGE_DEPTH_FRAGMENT ) );
	CHECK( key.stateBits == 0x1234u );
	CHECK( key.texModTypes0 == fiveTexModMask );
	CHECK( key.texModTypes1 == fiveTexModMask );
	CHECK( key.texModSequence0 == fiveTexModSequence );
	CHECK( key.texModSequence1 == fiveTexModSequence );
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
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		2, 0, scrollScaleMask, 0, scrollScaleSequence, 0, qfalse,
		&scrollScaleKey ) == qtrue );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		2, 0, scrollScaleMask, 0, scaleScrollSequence, 0, qfalse,
		&scaleScrollKey ) == qtrue );
	CHECK( glx::GLX_Material_KeyEquals( scrollScaleKey.program, scaleScrollKey.program ) == qtrue );
	CHECK( scrollScaleKey.texModTypes0 == scaleScrollKey.texModTypes0 );
	CHECK( glx::GLX_Material_StageKeyEquals( scrollScaleKey, scaleScrollKey ) == qfalse );
	CHECK( glx::GLX_Material_StageKeyForInputsFull( GLX_STAGE_TEXMOD, 0, 0,
		GLX_MATERIAL_RGBGEN_IDENTITY, GLX_MATERIAL_ALPHAGEN_SKIP,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_BAD,
		2, 0, scrollScaleMask, 0, scrollScaleSequence | ( 1u << 12 ), 0,
		qfalse, &scrollScaleKey ) == qfalse );

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
			GLX_STAGE_DLIGHT_MAP | GLX_STAGE_ST0 | GLX_STAGE_ST1,
		0xabcd, GLX_MATERIAL_COMBINE_MODULATE,
		GLX_MATERIAL_RGBGEN_LIGHTING_DIFFUSE, GLX_MATERIAL_ALPHAGEN_LIGHTING_SPECULAR,
		GLX_MATERIAL_TCGEN_TEXTURE, GLX_MATERIAL_TCGEN_LIGHTMAP,
		0, 0, 0, 0, qfalse, &key ) == qtrue );
	CHECK( key.program.mode == glx::MaterialProgramMode::MultiModulate );
	CHECK( key.program.features == glx::GLX_MATERIAL_FEATURE_DEPTH_FRAGMENT );
	CHECK( ( key.flags & GLX_STAGE_DLIGHT_MAP ) != 0 );
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

	glx::FeatureSet compat = glx::GLX_Caps_FeaturesForVersionAndExtensions( 2, 1, "" );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 2, 1, compat ) == glx::CapabilityTier::Compat );

	glx::FeatureSet core = glx::GLX_Caps_FeaturesForVersionAndExtensions( 3, 3, "" );
	CHECK( core.mapBufferRange == qtrue );
	CHECK( core.timerQuery == qtrue );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 3, 3, core ) == glx::CapabilityTier::Core );

	glx::FeatureSet extensionCore = glx::GLX_Caps_FeaturesForVersionAndExtensions( 2, 1,
		"GL_ARB_map_buffer_range GL_ARB_uniform_buffer_object GL_ARB_instanced_arrays" );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 2, 1, extensionCore ) == glx::CapabilityTier::Core );

	glx::FeatureSet advanced = glx::GLX_Caps_FeaturesForVersionAndExtensions( 2, 1,
		"GL_ARB_buffer_storage GL_ARB_sync GL_ARB_multi_draw_indirect" );
	CHECK( advanced.drawIndirect == qtrue );
	CHECK( advanced.multiDrawIndirect == qtrue );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 2, 1, advanced ) == glx::CapabilityTier::Advanced );
	CHECK( glx::GLX_Caps_TierForVersionAndFeatures( 2, 0, advanced ) == glx::CapabilityTier::BelowFloor );

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
		{ "StreamGatesMatchRcAllowlist", StreamGatesMatchRcAllowlist },
		{ "StreamBroadKeyModeRemainsDeveloperEscapeHatch", StreamBroadKeyModeRemainsDeveloperEscapeHatch },
		{ "StreamSpecialSceneGatesAreExplicit", StreamSpecialSceneGatesAreExplicit },
		{ "StreamShadowGateIsExplicit", StreamShadowGateIsExplicit },
		{ "StreamBeamGateIsExplicit", StreamBeamGateIsExplicit },
		{ "StreamPostProcessGateIsExplicit", StreamPostProcessGateIsExplicit },
		{ "CapabilityLogicClassifiesTiersAndExtensions", CapabilityLogicClassifiesTiersAndExtensions },
		{ "StreamStrategySelectionFollowsFallbackLadder", StreamStrategySelectionFollowsFallbackLadder },
		{ "StaticWorldPacketLogicClassifiesRunsAndPolicies", StaticWorldPacketLogicClassifiesRunsAndPolicies },
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
