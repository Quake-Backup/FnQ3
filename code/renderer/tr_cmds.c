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
#include "tr_local.h"
#include "tr_glx_compat.h"

/*
=====================
R_PerformanceCounters
=====================
*/
static void R_PerformanceCounters( void ) {
	qboolean shadowDebug;
	qboolean csmDebug;
	qboolean spotShadowDebug;
	qboolean staticLightDebug;
	qboolean surfaceLightDebug;

	shadowDebug = ( r_dlightShadowDebug && r_dlightShadowDebug->integer ) ? qtrue : qfalse;
	csmDebug = ( r_csmDebug && r_csmDebug->integer ) ? qtrue : qfalse;
	spotShadowDebug = ( r_spotShadowDebug && r_spotShadowDebug->integer ) ? qtrue : qfalse;
	staticLightDebug = ( r_staticLightDebug && r_staticLightDebug->integer ) ? qtrue : qfalse;
	surfaceLightDebug = ( r_surfaceLightProxyDebug && r_surfaceLightProxyDebug->integer ) ? qtrue : qfalse;

	if ( !r_speeds->integer && !shadowDebug && !csmDebug && !spotShadowDebug && !staticLightDebug && !surfaceLightDebug ) {
		// clear the counters even if we aren't printing
		Com_Memset( &tr.pc, 0, sizeof( tr.pc ) );
		Com_Memset( &tr.shadowManager, 0, sizeof( tr.shadowManager ) );
		Com_Memset( &tr.csmDebugPlan, 0, sizeof( tr.csmDebugPlan ) );
		Com_Memset( &backEnd.pc, 0, sizeof( backEnd.pc ) );
		return;
	}

	if (r_speeds->integer == 1) {
		ri.Printf (PRINT_ALL, "%i/%i shaders/surfs %i leafs %i verts %i/%i tris %.2f mtex %.2f dc\n",
			backEnd.pc.c_shaders, backEnd.pc.c_surfaces, tr.pc.c_leafs, backEnd.pc.c_vertexes, 
			backEnd.pc.c_indexes/3, backEnd.pc.c_totalIndexes/3, 
			R_SumOfUsedImages()/(1000000.0f), backEnd.pc.c_overDraw / (float)(glConfig.vidWidth * glConfig.vidHeight) ); 
	} else if (r_speeds->integer == 2) {
		ri.Printf (PRINT_ALL, "(patch) %i sin %i sclip  %i sout %i bin %i bclip %i bout\n",
			tr.pc.c_sphere_cull_patch_in, tr.pc.c_sphere_cull_patch_clip, tr.pc.c_sphere_cull_patch_out, 
			tr.pc.c_box_cull_patch_in, tr.pc.c_box_cull_patch_clip, tr.pc.c_box_cull_patch_out );
		ri.Printf (PRINT_ALL, "(md3) %i sin %i sclip  %i sout %i bin %i bclip %i bout\n",
			tr.pc.c_sphere_cull_md3_in, tr.pc.c_sphere_cull_md3_clip, tr.pc.c_sphere_cull_md3_out, 
			tr.pc.c_box_cull_md3_in, tr.pc.c_box_cull_md3_clip, tr.pc.c_box_cull_md3_out );
	} else if (r_speeds->integer == 3) {
		ri.Printf (PRINT_ALL, "viewcluster: %i\n", tr.viewCluster );
	} else if (r_speeds->integer == 4) {
		if ( backEnd.pc.c_dlightVertexes ) {
			ri.Printf (PRINT_ALL, "dlight srf:%i  culled:%i  verts:%i  tris:%i\n", 
				tr.pc.c_dlightSurfaces, tr.pc.c_dlightSurfacesCulled,
				backEnd.pc.c_dlightVertexes, backEnd.pc.c_dlightIndexes / 3 );
		}
	} 
	else if (r_speeds->integer == 5 )
	{
		ri.Printf( PRINT_ALL, "zFar: %.0f\n", tr.viewParms.zFar );
	}
	else if (r_speeds->integer == 6 )
	{
		ri.Printf( PRINT_ALL, "flare adds:%i tests:%i renders:%i\n", 
			backEnd.pc.c_flareAdds, backEnd.pc.c_flareTests, backEnd.pc.c_flareRenders );
	}
	else if ( r_speeds->integer == 7 )
	{
		GLX_CompatPrintFrameCounters();
	}

	if ( ( r_speeds->integer == 4 || shadowDebug || csmDebug || spotShadowDebug ) && tr.shadowManager.planned ) {
		const shadowManager_t *manager = &tr.shadowManager;

		ri.Printf( PRINT_ALL,
			"shadow manager view:%i frame:%i noworld:%i sched:%i p:%i s:%i ca:%i cr:%i pub p:%i s:%i c:%i inputs dlight:%i point:%i/%i cand:%i records:%i/%i atlas:%ix%i/%i fill:%i%% gen:%u spot:%i/%i atlas:%ix%i/%i fill:%i%% gen:%u csm:%i atlas:%ix%i gen:%u\n",
			manager->viewCount, manager->frameCount, manager->noWorldModel,
			manager->scheduledPasses, manager->pointAtlasScheduled, manager->spotAtlasScheduled,
			manager->csmAtlasScheduled, manager->csmReceiverScheduled,
			manager->pointAtlasPublished, manager->spotAtlasPublished, manager->csmAtlasPublished,
			manager->inputDlights,
			manager->dlightPlannedCount, manager->dlightConsidered,
			manager->dlightCandidates,
			manager->pointPlanCount, manager->pointCandidateCount,
			manager->dlightAtlasWidth, manager->dlightAtlasHeight,
			manager->dlightAtlasFaceSize, manager->dlightAtlasFill,
			manager->pointAtlasGeneration,
			manager->spotPlanCount, manager->spotCandidateCount,
			manager->spotAtlasWidth, manager->spotAtlasHeight,
			manager->spotAtlasTileSize, manager->spotAtlasFill,
			manager->spotAtlasGeneration,
			manager->csmCascadeCount,
			manager->csmAtlasWidth, manager->csmAtlasHeight,
			manager->csmAtlasGeneration );
	}

	if ( ( r_speeds->integer == 4 || staticLightDebug ) &&
		( tr.staticMapLights.loaded || tr.staticMapLights.parseFailed ) ) {
		ri.Printf( PRINT_ALL,
			"static lights file:%s loaded:%i parsefail:%i count:%i point:%i spot:%i spatial:%i/%i promoted:%i shadow:%i skip disabled:%i pvs:%i budget:%i unsupported:%i invalid:%i overflow:%i\n",
			tr.staticMapLights.filename[0] ? tr.staticMapLights.filename : "<none>",
			tr.staticMapLights.loaded, tr.staticMapLights.parseFailed,
			tr.staticMapLights.count, tr.staticMapLights.pointCount,
			tr.staticMapLights.spotCount, tr.staticMapLights.spatialized,
			tr.staticMapLights.spatialFallback, tr.staticMapLights.promotedThisFrame,
			tr.staticMapLights.shadowEligibleThisFrame,
			tr.staticMapLights.skippedDisabledThisFrame,
			tr.staticMapLights.skippedPVSThisFrame,
			tr.staticMapLights.skippedBudgetThisFrame,
			tr.staticMapLights.skippedUnsupported,
			tr.staticMapLights.skippedInvalid,
			tr.staticMapLights.skippedOverflow );
	}

	if ( ( r_speeds->integer == 4 || surfaceLightDebug ) && tr.surfaceLightProxies.built ) {
		ri.Printf( PRINT_ALL,
			"surfacelight proxies sources:%i built:%i point:%i spot:%i subdiv:%i/%i spatial:%i/%i promoted:%i shadow:%i spotdefer:%i skip sky:%i invalid:%i disabled:%i pvs:%i budget:%i overflow:%i\n",
			tr.surfaceLightProxies.sourceSurfaces,
			tr.surfaceLightProxies.count,
			tr.surfaceLightProxies.pointProjectionCount,
			tr.surfaceLightProxies.spotProjectionCount,
			tr.surfaceLightProxies.subdividedSurfaces,
			tr.surfaceLightProxies.subdivisionProxies,
			tr.surfaceLightProxies.spatialized,
			tr.surfaceLightProxies.spatialFallback,
			tr.surfaceLightProxies.promotedThisFrame,
			tr.surfaceLightProxies.shadowEligibleThisFrame,
			tr.surfaceLightProxies.spotShadowDeferredThisFrame,
			tr.surfaceLightProxies.skippedSky,
			tr.surfaceLightProxies.skippedInvalid,
			tr.surfaceLightProxies.skippedDisabledThisFrame,
			tr.surfaceLightProxies.skippedPVSThisFrame,
			tr.surfaceLightProxies.skippedBudgetThisFrame,
			tr.surfaceLightProxies.skippedOverflow );
	}

#ifdef USE_PMLIGHT
	if ( ( r_speeds->integer == 4 || shadowDebug ) &&
		( tr.pc.c_dlightShadowConsidered || tr.pc.c_dlightShadowSkippedDisabled ) ) {
		ri.Printf( PRINT_ALL,
			"dlight shadows plan:%i/%i cand:%i atlas:%ix%i/%i fill:%i%% render lights:%i faces:%i batches:%i draws:%i surfs:%i cpu:%ims skip disabled:%i linear:%i nosurf:%i proj:%i budget:%i lowvalue:%i\n",
			tr.pc.c_dlightShadowPlanned, tr.pc.c_dlightShadowConsidered,
			tr.pc.c_dlightShadowCandidates,
			tr.pc.c_dlightShadowAtlasWidth, tr.pc.c_dlightShadowAtlasHeight,
			tr.pc.c_dlightShadowAtlasFaceSize,
			tr.pc.c_dlightShadowAtlasFill,
			backEnd.pc.c_dlightShadowAtlasLights,
			backEnd.pc.c_dlightShadowAtlasFaces,
			backEnd.pc.c_dlightShadowAtlasBatches,
			backEnd.pc.c_dlightShadowAtlasDraws,
			backEnd.pc.c_dlightShadowAtlasSurfaces,
			backEnd.pc.c_dlightShadowAtlasMsec,
			tr.pc.c_dlightShadowSkippedDisabled,
			tr.pc.c_dlightShadowSkippedLinear, tr.pc.c_dlightShadowSkippedNoSurfaces,
			tr.pc.c_dlightShadowSkippedProjection, tr.pc.c_dlightShadowSkippedBudget,
			tr.pc.c_dlightShadowSkippedLowValue );
	}
#endif

	if ( ( r_speeds->integer == 4 || csmDebug ) &&
		( tr.csmDebugPlan.enabled || ( csmDebug && r_csmShadows && r_csmShadows->integer ) ) ) {
		if ( tr.csmDebugPlan.enabled && tr.csmDebugPlan.cascadeCount > 0 ) {
			const csmPlan_t *csm = &tr.csmDebugPlan;
			float splitFar[CSM_MAX_CASCADES] = { 0.0f };
			float texelSize[CSM_MAX_CASCADES] = { 0.0f };
			const char *skyShaderName;
			int i;

			for ( i = 0; i < csm->cascadeCount && i < CSM_MAX_CASCADES; i++ ) {
				splitFar[i] = csm->cascades[i].splitFar;
				texelSize[i] = csm->cascades[i].texelSize;
			}
			skyShaderName = csm->skyShaderName[0] ? csm->skyShaderName : "<unknown>";

			ri.Printf( PRINT_ALL,
				"csm shadows sky:%s cascades:%i res:%i max:%i lambda:%.2f filter:%s strength:%.2f rbias:%.2f cbias:%.2f/%.2f/%.2f light-dir:%.2f %.2f %.2f to-sun:%.2f %.2f %.2f split far:%.0f %.0f %.0f %.0f texel:%.2f %.2f %.2f %.2f caster:%i cache h/m/u:%i/%i/%i cpu:%ims recv world:%i ent:%i\n",
				skyShaderName,
				tr.pc.c_csmCascades, tr.pc.c_csmResolution, tr.pc.c_csmMaxDistance,
				csm->splitLambda, R_ShadowFilterModeName( csm->filterMode ),
				csm->shadowStrength, csm->receiverBias, csm->casterDepthBias, csm->casterSlopeBias,
				csm->casterNormalBias,
				csm->lightDirection[0], csm->lightDirection[1], csm->lightDirection[2],
				csm->directionToSun[0], csm->directionToSun[1], csm->directionToSun[2],
				splitFar[0], splitFar[1], splitFar[2], splitFar[3],
				texelSize[0], texelSize[1], texelSize[2], texelSize[3],
				backEnd.pc.c_csmShadowAtlasSurfaces,
				backEnd.pc.c_csmShadowAtlasCacheHits,
				backEnd.pc.c_csmShadowAtlasCacheMisses,
				backEnd.pc.c_csmShadowAtlasCacheUncacheable,
				backEnd.pc.c_csmShadowAtlasMsec,
				backEnd.pc.c_csmShadowReceiverWorldSurfaces,
				backEnd.pc.c_csmShadowReceiverEntitySurfaces );
		} else if ( tr.pc.c_csmSkippedNoSun ) {
			ri.Printf( PRINT_ALL, "csm plan cascades:0 skip no-sky-sun\n" );
		} else if ( tr.pc.c_csmSkippedProjection ) {
			ri.Printf( PRINT_ALL, "csm plan cascades:0 skip projection\n" );
		} else if ( tr.pc.c_csmSkippedAtlas ) {
			ri.Printf( PRINT_ALL, "csm plan cascades:0 skip atlas\n" );
		} else if ( tr.pc.c_csmSkippedStrength ) {
			ri.Printf( PRINT_ALL, "csm plan cascades:0 skip strength\n" );
		} else if ( tr.pc.c_csmSkippedDisabled && !tr.pc.c_csmSkippedNoWorldRef ) {
			ri.Printf( PRINT_ALL, "csm plan cascades:0 skip disabled\n" );
		}
	}

	Com_Memset( &tr.pc, 0, sizeof( tr.pc ) );
	Com_Memset( &tr.shadowManager, 0, sizeof( tr.shadowManager ) );
	Com_Memset( &tr.csmDebugPlan, 0, sizeof( tr.csmDebugPlan ) );
	Com_Memset( &backEnd.pc, 0, sizeof( backEnd.pc ) );
}


/*
====================
R_IssueRenderCommands
====================
*/
static void R_IssueRenderCommands( void ) {
	renderCommandList_t	*cmdList;

	cmdList = &backEndData->commands;

	// add an end-of-list command
	*(int *)(cmdList->cmds + cmdList->used) = RC_END_OF_LIST;

	// clear it out, in case this is a sync and not a buffer flip
	cmdList->used = 0;

	if ( backEnd.screenshotMask == 0 && !backEnd.levelshotPending &&
		!backEnd.screenshotCubeActive && !backEnd.screenshotCubeFrontPending ) {
		if ( ri.CL_IsMinimized() )
			return; // skip backend when minimized
		if ( backEnd.throttle )
			return; // or throttled on demand
	}

	// actually start the commands going
	if ( !r_skipBackEnd->integer ) {
		// let it start on the new batch
		GLX_CompatBeginBackendTimer();
		RB_ExecuteRenderCommands( cmdList->cmds );
		GLX_CompatEndBackendTimer();
	}
}


/*
====================
R_IssuePendingRenderCommands

Issue any pending commands and wait for them to complete.
====================
*/
void R_IssuePendingRenderCommands( void ) {
	if ( !tr.registered ) {
		return;
	}
	R_IssueRenderCommands();
}


/*
============
R_GetCommandBufferReserved

make sure there is enough command space
============
*/
static void *R_GetCommandBufferReserved( int bytes, int reservedBytes ) {
	renderCommandList_t	*cmdList;

	cmdList = &backEndData->commands;
	bytes = PAD(bytes, sizeof(void *));

	// always leave room for the end of list command
	if ( cmdList->used + bytes + sizeof( int ) + reservedBytes > MAX_RENDER_COMMANDS ) {
		if ( bytes > MAX_RENDER_COMMANDS - sizeof( int ) ) {
			ri.Error( ERR_FATAL, "R_GetCommandBuffer: bad size %i", bytes );
		}
		// if we run out of room, just start dropping commands
		return NULL;
	}

	cmdList->used += bytes;

	return cmdList->cmds + cmdList->used - bytes;
}


/*
=============
R_GetCommandBuffer
returns NULL if there is not enough space for important commands
=============
*/
static void *R_GetCommandBuffer( int bytes ) {
	return R_GetCommandBufferReserved( bytes, PAD( sizeof( swapBuffersCommand_t ), sizeof(void *) ) );
}


/*
=============
R_AddDrawSurfCmd
=============
*/
void R_AddDrawSurfCmd( drawSurf_t *drawSurfs, int numDrawSurfs ) {
	drawSurfsCommand_t	*cmd;

	cmd = R_GetCommandBuffer( sizeof( *cmd ) );
	if ( !cmd ) {
		return;
	}
	cmd->commandId = RC_DRAW_SURFS;

	cmd->drawSurfs = drawSurfs;
	cmd->numDrawSurfs = numDrawSurfs;

	cmd->refdef = tr.refdef;
	cmd->viewParms = tr.viewParms;
	cmd->csm = tr.csm;
	cmd->shadowManager = tr.shadowManager;
}

void R_AddScreenshotCmd( int x, int y, int width, int height, int format, const char *fileName, qboolean silent, qboolean allowWatermark ) {
	screenshotCommand_t *cmd;

	cmd = R_GetCommandBuffer( sizeof( *cmd ) );
	if ( !cmd ) {
		return;
	}

	cmd->commandId = RC_SCREENSHOT;
	cmd->x = x;
	cmd->y = y;
	cmd->width = width;
	cmd->height = height;
	cmd->format = format;
	cmd->silent = silent;
	cmd->allowWatermark = allowWatermark;
	Q_strncpyz( cmd->fileName, fileName, sizeof( cmd->fileName ) );
}


/*
=============
RE_SetColor

Passing NULL will set the color to white
=============
*/
void RE_SetColor( const float *rgba ) {
	setColorCommand_t	*cmd;

	if ( !tr.registered ) {
		return;
	}
	cmd = R_GetCommandBuffer( sizeof( *cmd ) );
	if ( !cmd ) {
		return;
	}
	cmd->commandId = RC_SET_COLOR;
	if ( !rgba ) {
		rgba = colorWhite;
	}

	cmd->color[0] = rgba[0];
	cmd->color[1] = rgba[1];
	cmd->color[2] = rgba[2];
	cmd->color[3] = rgba[3];
}


/*
=============
RE_StretchPic
=============
*/
void RE_StretchPic( float x, float y, float w, float h,
					float s1, float t1, float s2, float t2, qhandle_t hShader ) {
	stretchPicCommand_t	*cmd;

	if ( !tr.registered ) {
		return;
	}
	cmd = R_GetCommandBuffer( sizeof( *cmd ) );
	if ( !cmd ) {
		return;
	}
	cmd->commandId = RC_STRETCH_PIC;
	cmd->shader = R_GetShaderByHandle( hShader );
	cmd->x = x;
	cmd->y = y;
	cmd->w = w;
	cmd->h = h;
	cmd->s1 = s1;
	cmd->t1 = t1;
	cmd->s2 = s2;
	cmd->t2 = t2;
}

#define MODE_RED_CYAN	1
#define MODE_RED_BLUE	2
#define MODE_RED_GREEN	3
#define MODE_GREEN_MAGENTA 4
#define MODE_MAX	MODE_GREEN_MAGENTA

static void R_SetColorMode(GLboolean *rgba, stereoFrame_t stereoFrame, int colormode)
{
	rgba[0] = rgba[1] = rgba[2] = rgba[3] = GL_TRUE;

	if(colormode > MODE_MAX)
	{
		if(stereoFrame == STEREO_LEFT)
			stereoFrame = STEREO_RIGHT;
		else if(stereoFrame == STEREO_RIGHT)
			stereoFrame = STEREO_LEFT;

		colormode -= MODE_MAX;
	}

	if(colormode == MODE_GREEN_MAGENTA)
	{
		if(stereoFrame == STEREO_LEFT)
			rgba[0] = rgba[2] = GL_FALSE;
		else if(stereoFrame == STEREO_RIGHT)
			rgba[1] = GL_FALSE;
	}
	else
	{
		if(stereoFrame == STEREO_LEFT)
			rgba[1] = rgba[2] = GL_FALSE;
		else if(stereoFrame == STEREO_RIGHT)
		{
			rgba[0] = GL_FALSE;

			if(colormode == MODE_RED_BLUE)
				rgba[1] = GL_FALSE;
			else if(colormode == MODE_RED_GREEN)
				rgba[2] = GL_FALSE;
		}
	}
}


/*
====================
RE_BeginFrame

If running in stereo, RE_BeginFrame will be called twice
for each RE_EndFrame
====================
*/
void RE_BeginFrame( stereoFrame_t stereoFrame ) {
	drawBufferCommand_t	*cmd = NULL;
	colorMaskCommand_t *colcmd = NULL;
	clearColorCommand_t *clrcmd = NULL;

	if ( !tr.registered ) {
		return;
	}

	glState.finishCalled = qfalse;

	tr.frameCount++;
	tr.frameSceneNum = 0;

	backEnd.doneBloom = qfalse;
	backEnd.framePostProcessed = qfalse;
	backEnd.bloomProtectHighlights = qfalse;

	backEnd.color2D.u32 = ~0U;

	// check for errors
	GL_CheckErrors();

	if ( ( cmd = R_GetCommandBuffer( sizeof( *cmd ) ) ) == NULL )
		return;
	cmd->commandId = RC_DRAW_BUFFER;

	if ( glConfig.stereoEnabled ) {
		if ( stereoFrame == STEREO_LEFT ) {
			cmd->buffer = (int)GL_BACK_LEFT;
		} else if ( stereoFrame == STEREO_RIGHT ) {
			cmd->buffer = (int)GL_BACK_RIGHT;
		} else {
			ri.Error( ERR_FATAL, "RE_BeginFrame: Stereo is enabled, but stereoFrame was %i", stereoFrame );
		}
	}
	else
	{
		if ( !Q_stricmp( r_drawBuffer->string, "GL_FRONT" ) )
			cmd->buffer = (int)GL_FRONT;
		else
			cmd->buffer = (int)GL_BACK;

		if ( r_anaglyphMode->integer )
		{
			if ( r_anaglyphMode->modified )
			{
				clrcmd = R_GetCommandBuffer( sizeof( *clrcmd ) );
				if ( clrcmd ) {
					Com_Memset( clrcmd, 0, sizeof( *clrcmd ) );
					clrcmd->commandId = RC_CLEARCOLOR;
				} else {
					return;
				}
				clrcmd->colorMask = qtrue;
#ifdef USE_FBO
				if ( !fboEnabled )
#endif
				{
					// clear both, front and backbuffer.
					clrcmd->frontAndBack = qtrue;
				}
			}

			if ( stereoFrame == STEREO_LEFT )
			{
				// first frame
			}
			else if ( stereoFrame == STEREO_RIGHT )
			{
				clearDepthCommand_t *cldcmd;
				
				if ( (cldcmd = R_GetCommandBuffer(sizeof(*cldcmd))) == NULL )
					return;

				cldcmd->commandId = RC_CLEARDEPTH;
			}
			else
				ri.Error( ERR_FATAL, "RE_BeginFrame: Stereo is enabled, but stereoFrame was %i", stereoFrame );

			if ( (colcmd = R_GetCommandBuffer(sizeof(*colcmd))) == NULL )
				return;

			R_SetColorMode( colcmd->rgba, stereoFrame, r_anaglyphMode->integer );
			colcmd->commandId = RC_COLORMASK;
		}
		else // !r_anaglyphMode->integer
		{
			if ( stereoFrame != STEREO_CENTER )
				ri.Error( ERR_FATAL, "RE_BeginFrame: Stereo is disabled, but stereoFrame was %i", stereoFrame );

			// reset color mask
			if ( r_anaglyphMode->modified )	{
				if ( ( colcmd = R_GetCommandBuffer( sizeof( *colcmd ) ) ) == NULL )
					return;

				R_SetColorMode( colcmd->rgba, stereoFrame, r_anaglyphMode->integer );
				colcmd->commandId = RC_COLORMASK;
			}
		}
	}

	if ( r_fastsky->integer ) {
		if ( stereoFrame != STEREO_RIGHT ) {
			if ( !clrcmd ) {
				clrcmd = R_GetCommandBuffer( sizeof( *clrcmd ) );
				if ( clrcmd ) {
					Com_Memset( clrcmd, 0, sizeof( *clrcmd ) );
					clrcmd->commandId = RC_CLEARCOLOR;
				} else {
					return;
				}
			}
			clrcmd->fullscreen = qtrue;
			if ( r_anaglyphMode->integer ) {
				clrcmd->colorMask = qtrue;
			}
		}
	}

	tr.refdef.stereoFrame = stereoFrame;
}


/*
=============
RE_EndFrame

Returns the number of msec spent in the back end
=============
*/
void RE_EndFrame( int *frontEndMsec, int *backEndMsec ) {

	swapBuffersCommand_t *cmd;

	if ( !tr.registered ) {
		return;
	}

	cmd = R_GetCommandBufferReserved( sizeof( *cmd ), 0 );
	if ( !cmd ) {
		return;
	}
	cmd->commandId = RC_SWAP_BUFFERS;

	R_IssueRenderCommands();

	GLX_CompatFrameComplete();
	R_PerformanceCounters();

	R_InitNextFrame();

	if ( frontEndMsec ) {
		*frontEndMsec = tr.frontEndMsec;
	}
	tr.frontEndMsec = 0;
	if ( backEndMsec ) {
		*backEndMsec = backEnd.pc.msec;
	}
	backEnd.pc.msec = 0;
	backEnd.throttle = qfalse;

	// recompile GPU shaders if needed
	if ( ri.Cvar_CheckGroup( CVG_RENDERER ) )
	{
		qboolean updateColorMappings = r_gamma->modified;

		ARB_UpdatePrograms();

#ifdef USE_FBO
		if ( r_ext_multisample->modified || r_hdrPrecision->modified ||
			r_hdrBloomFormat->modified ||
			r_fbo->modified || r_ext_supersample->modified || r_renderWidth->modified ||
			r_renderHeight->modified || r_renderScale->modified || r_flares->modified ||
			r_bloom_passes->modified || r_csmShadows->modified ||
			r_csmCascadeCount->modified || r_csmResolution->modified ) {
			QGL_InitFBO();
			updateColorMappings = qtrue;
		}
#endif

		if ( r_textureMode->modified )
			GL_TextureMode( r_textureMode->string );

		if ( updateColorMappings )
			R_SetColorMappings();

		ri.Cvar_ResetGroup( CVG_RENDERER, qtrue );
	}
}


/*
=============
RE_TakeVideoFrame
=============
*/
void RE_TakeVideoFrame( int width, int height,
		byte *captureBuffer, byte *encodeBuffer, qboolean motionJpeg )
{
	videoFrameCommand_t	*cmd;

	if( !tr.registered ) {
		return;
	}

	backEnd.screenshotMask |= SCREENSHOT_AVI;

	cmd = &backEnd.vcmd;

	//cmd->commandId = RC_VIDEOFRAME;

	cmd->width = width;
	cmd->height = height;
	cmd->captureBuffer = captureBuffer;
	cmd->encodeBuffer = encodeBuffer;
	cmd->motionJpeg = motionJpeg;
}


void RE_ThrottleBackend( void )
{
	backEnd.throttle = qtrue;
}


void RE_FinishBloom( void )
{
#ifdef USE_FBO
	finishBloomCommand_t *cmd;

	if ( !tr.registered ) {
		return;
	}

	cmd = R_GetCommandBuffer( sizeof( *cmd ) );
	if ( !cmd ) {
		return;
	}

	cmd->commandId = RC_FINISHBLOOM;
#endif // USE_FBO
}


void RE_DrawMenuDepthOfField( float amount )
{
#ifdef USE_FBO
	menuDepthOfFieldCommand_t *cmd;

	if ( !tr.registered || amount <= 0.0f ) {
		return;
	}

	cmd = R_GetCommandBuffer( sizeof( *cmd ) );
	if ( !cmd ) {
		return;
	}

	cmd->commandId = RC_MENU_DEPTH_OF_FIELD;
	cmd->amount = Com_Clamp( 0.0f, 1.0f, amount );
#else
	(void)amount;
#endif // USE_FBO
}


qboolean RE_CanMinimize( void )
{
#ifdef USE_FBO
	return fboEnabled;
#else
	return qfalse;
#endif
}


const glconfig_t *RE_GetConfig( void )
{
	return &glConfig;
}


void RE_VertexLighting( qboolean allowed )
{
	tr.vertexLightingAllowed = allowed;
}
