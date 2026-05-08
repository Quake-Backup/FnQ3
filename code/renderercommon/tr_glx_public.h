/*
===========================================================================
Copyright (C) 2026

This file is part of FnQuake3.

FnQuake3 is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option)
any later version.
===========================================================================
*/

#ifndef TR_GLX_PUBLIC_H
#define TR_GLX_PUBLIC_H

/*
 * Shared GLx compatibility vocabulary.
 *
 * Keep renderer-facing ids here instead of in the GLx module bridge so pure
 * classification logic and the legacy compatibility substrate do not need to
 * include the full GLx C ABI just to agree on counters, flags, and payload
 * shapes.
 */

#define GLX_DRAW_GENERIC 0
#define GLX_DRAW_VBO_DEVICE 1
#define GLX_DRAW_VBO_SOFT 2
#define GLX_DRAW_DEBUG 3
#define GLX_DRAW_STREAM_GENERIC 4

#define GLX_BATCH_VBO 0x0001
#define GLX_BATCH_FOG 0x0002
#define GLX_BATCH_MULTITEXTURE 0x0004
#define GLX_BATCH_POLYGON_OFFSET 0x0008

#define GLX_STAGE_PATH_GENERIC 0
#define GLX_STAGE_PATH_VBO 1

#define GLX_STAGE_MULTITEXTURE 0x0001
#define GLX_STAGE_DEPTH_FRAGMENT 0x0002
#define GLX_STAGE_BLEND 0x0004
#define GLX_STAGE_ALPHA_TEST 0x0008
#define GLX_STAGE_DEPTH_WRITE 0x0010
#define GLX_STAGE_LIGHTMAP 0x0020
#define GLX_STAGE_ANIMATED_IMAGE 0x0040
#define GLX_STAGE_VIDEO_MAP 0x0080
#define GLX_STAGE_SCREEN_MAP 0x0100
#define GLX_STAGE_DLIGHT_MAP 0x0200
#define GLX_STAGE_TEXMOD 0x0400
#define GLX_STAGE_ENVIRONMENT 0x0800
#define GLX_STAGE_ST0 0x1000
#define GLX_STAGE_ST1 0x2000
#define GLX_STAGE_SHADOW_PASS 0x4000
#define GLX_STAGE_BEAM_PASS 0x8000
#define GLX_STAGE_POSTPROCESS_PASS 0x10000

#define GLX_MATERIAL_COMBINE_INVALID 0
#define GLX_MATERIAL_COMBINE_MODULATE 1
#define GLX_MATERIAL_COMBINE_ADD 2
#define GLX_MATERIAL_COMBINE_REPLACE 3
#define GLX_MATERIAL_COMBINE_DECAL 4

#define GLX_STREAM_SKIP_NO_BIND_BUFFER 0
#define GLX_STREAM_SKIP_BAD_INPUT 1
#define GLX_STREAM_SKIP_MULTITEXTURE 2
#define GLX_STREAM_SKIP_DEPTH_FRAGMENT 3
#define GLX_STREAM_SKIP_NO_TEXCOORDS 4
#define GLX_STREAM_SKIP_EMPTY_BATCH 5
#define GLX_STREAM_SKIP_MATERIAL_KEY 6
#define GLX_STREAM_SKIP_FOG 7
#define GLX_STREAM_SKIP_MATERIAL_PROGRAM 8

#define GLX_POSTPROCESS_RESULT_NONE 0
#define GLX_POSTPROCESS_RESULT_BLOOM_FINAL 1
#define GLX_POSTPROCESS_RESULT_GAMMA_DIRECT 2
#define GLX_POSTPROCESS_RESULT_GAMMA_BLIT 3
#define GLX_POSTPROCESS_RESULT_MINIMIZED 4

#define GLX_BLOOM_CREATE_NONE 0
#define GLX_BLOOM_CREATE_SUCCESS 1
#define GLX_BLOOM_CREATE_TEXTURE_UNITS 2
#define GLX_BLOOM_CREATE_FBO 3

#define GLX_BLOOM_RESULT_NONE 0
#define GLX_BLOOM_RESULT_SKIPPED 1
#define GLX_BLOOM_RESULT_INTERMEDIATE 2
#define GLX_BLOOM_RESULT_FINAL 3
#define GLX_BLOOM_RESULT_CREATE_FAILED 4

#define GLX_FBO_BLIT_MS 1
#define GLX_FBO_BLIT_SS 2

typedef struct glxStreamReservation_s {
	unsigned int buffer;
	unsigned int offset;
	unsigned int bytes;
	void *ptr;
	int strategy;
	int mapped;
	int committed;
} glxStreamReservation_t;

#endif // TR_GLX_PUBLIC_H
