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

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE, GL_MODULATE, 0, 0,
		qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::MultiModulate );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_NONE );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE | GLX_STAGE_TEXMOD,
		GL_ADD, 0, 1, qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::MultiAdd );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_TEXMOD );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE, GL_REPLACE, 0, 0,
		qfalse, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::MultiReplace );

	CHECK( glx::GLX_Material_KeyForInputs( GLX_STAGE_MULTITEXTURE, GL_DECAL, 0, 0,
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
		GL_ADD, 4, 4, qtrue, &key ) == qtrue );
	CHECK( key.mode == glx::MaterialProgramMode::Fog );
	CHECK( key.features == glx::GLX_MATERIAL_FEATURE_NONE );

	return true;
}

bool StreamGatesMatchRcAllowlist()
{
	glx::StreamMaterialGateConfig rc {};
	glx::StreamMaterialGateResult result;

	rc.keyMode = 0;
	rc.multitexture = qtrue;
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

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_ENVIRONMENT, 0, 0, rc );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasEnvironment == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_MULTITEXTURE | GLX_STAGE_ST1,
		0, 0, rc );
	CHECK( result.allowed == qtrue );
	CHECK( result.hasSecondTexcoord == qtrue );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_ST1, 0, 0, rc );
	CHECK( result.allowed == qfalse );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_DLIGHT_MAP, 0, 0, rc );
	CHECK( result.allowed == qfalse );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_SCREEN_MAP, 0, 0, rc );
	CHECK( result.allowed == qfalse );

	result = glx::GLX_Stream_EvaluateMaterialGate( GLX_STAGE_VIDEO_MAP, 0, 0, rc );
	CHECK( result.allowed == qfalse );

	return true;
}

bool StreamBroadKeyModeRemainsDeveloperEscapeHatch()
{
	glx::StreamMaterialGateConfig config {};
	glx::StreamMaterialGateResult result;

	config.keyMode = 2;

	result = glx::GLX_Stream_EvaluateMaterialGate(
		GLX_STAGE_DLIGHT_MAP | GLX_STAGE_SCREEN_MAP | GLX_STAGE_VIDEO_MAP | GLX_STAGE_ST1,
		2, 3, config );

	CHECK( result.allowed == qtrue );
	CHECK( result.hasDynamicLight == qtrue );
	CHECK( result.hasScreenMap == qtrue );
	CHECK( result.hasVideoMap == qtrue );
	CHECK( result.hasSecondTexcoord == qtrue );

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
	CHECK( result.match == glx::StaticWorldPacketMatch::None );

	result = glx::GLX_StaticWorld_ClassifyRunAgainstPacketView( packet, 3,
		200, 24, 100, 4, "textures/base_floor/test", 8 );
	CHECK( result.match == glx::StaticWorldPacketMatch::None );

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
		glx::StaticWorldPacketMatch::None ) == qtrue );

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
		{ "StreamGatesMatchRcAllowlist", StreamGatesMatchRcAllowlist },
		{ "StreamBroadKeyModeRemainsDeveloperEscapeHatch", StreamBroadKeyModeRemainsDeveloperEscapeHatch },
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
