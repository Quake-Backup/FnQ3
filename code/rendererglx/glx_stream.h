#ifndef GLX_STREAM_H
#define GLX_STREAM_H

#include "glx_caps.h"

namespace glx {

static constexpr int GLX_STREAM_SKIP_REASON_COUNT = 9;

struct StreamReservation {
	GLuint buffer;
	size_t offset;
	size_t bytes;
	void *ptr;
	StreamStrategy strategy;
	qboolean mapped;
	qboolean committed;
};

struct StreamState {
	cvar_t *r_glxStreamMode;
	cvar_t *r_glxStreamMegabytes;
	cvar_t *r_glxStreamTess;
	cvar_t *r_glxStreamDraw;
	cvar_t *r_glxStreamDrawKeyMode;
	cvar_t *r_glxStreamDrawMultitexture;
	cvar_t *r_glxStreamDrawFog;
	cvar_t *r_glxStreamDrawDepthFragment;
	cvar_t *r_glxStreamDrawTexMods;
	cvar_t *r_glxStreamDrawEnvironment;
	cvar_t *r_glxStreamDrawDynamicLights;
	cvar_t *r_glxStreamDrawScreenMaps;
	cvar_t *r_glxStreamDrawVideoMaps;
	cvar_t *r_glxStreamDrawShadows;
	cvar_t *r_glxStreamDrawBeams;
	cvar_t *r_glxStreamDrawPostProcess;
	StreamStrategy strategy;
	char reason[96];
	int ringMegabytes;
	size_t ringBytes;
	size_t writeOffset;
	void *mappedPtr;
	void *frameSync;
	GLuint buffer;
	qboolean ready;
	qboolean persistentMapped;
	qboolean syncReady;
	qboolean frameTouched;
	unsigned int fallbackCount;
	unsigned int allocationFailures;
	unsigned int mapFailures;
	unsigned int unmapFailures;
	unsigned int reserveFailures;
	unsigned int uploadFailures;
	unsigned int reservations;
	unsigned int commits;
	unsigned int uploadCalls;
	unsigned int wraps;
	unsigned int sameFrameWrapRejects;
	unsigned int orphans;
	unsigned int syncInsertions;
	unsigned int syncWaits;
	unsigned int syncTimeouts;
	unsigned int syncFailures;
	unsigned int syncFenceSkips;
	unsigned int selfTests;
	unsigned int shadowTessUploads;
	unsigned int shadowTessSkips;
	unsigned int shadowTessFailures;
	unsigned int streamedDrawAttempts;
	unsigned int streamedDraws;
	unsigned int streamedDrawFallbacks;
	unsigned int streamedDrawSkips;
	unsigned int streamedDrawSkipReasons[GLX_STREAM_SKIP_REASON_COUNT];
	unsigned int streamedDrawMaterialAccepted;
	unsigned int streamedDrawMaterialRejected;
	unsigned int streamedDrawMultitextureDraws;
	unsigned int streamedDrawFogDraws;
	unsigned int streamedDrawDepthFragmentDraws;
	unsigned int streamedDrawTexModDraws;
	unsigned int streamedDrawTexModAccepted;
	unsigned int streamedDrawTexModRejected;
	unsigned int streamedDrawEnvironmentDraws;
	unsigned int streamedDrawEnvironmentAccepted;
	unsigned int streamedDrawEnvironmentRejected;
	unsigned int streamedDrawDynamicLightDraws;
	unsigned int streamedDrawDynamicLightAccepted;
	unsigned int streamedDrawDynamicLightRejected;
	unsigned int streamedDrawScreenMapDraws;
	unsigned int streamedDrawScreenMapAccepted;
	unsigned int streamedDrawScreenMapRejected;
	unsigned int streamedDrawVideoMapDraws;
	unsigned int streamedDrawVideoMapAccepted;
	unsigned int streamedDrawVideoMapRejected;
	unsigned int streamedDrawShadowDraws;
	unsigned int streamedDrawBeamDraws;
	unsigned int streamedDrawPostProcessDraws;
	unsigned int streamedDrawVertexes;
	unsigned int streamedDrawIndexes;
	unsigned int largestReservationBytes;
	unsigned int lastReservationBytes;
	unsigned int lastReservationOffset;
	StreamStrategy lastReservationStrategy;
	unsigned long long uploadBytes;
	unsigned long long shadowTessBytes;
	unsigned long long streamedDrawBytes;
	unsigned long long streamedDrawIndexBytes;
	unsigned long long streamedDrawTexcoord1Bytes;
	unsigned int frames;
};

void GLX_Stream_RegisterCvars( StreamState *state );
void GLX_Stream_OnOpenGLReady( StreamState *state, const Capabilities &caps );
void GLX_Stream_Shutdown( StreamState *state );
void GLX_Stream_FrameComplete( StreamState *state );
qboolean GLX_Stream_Reserve( StreamState *state, size_t bytes, size_t alignment, StreamReservation *reservation );
qboolean GLX_Stream_Upload( StreamState *state, StreamReservation *reservation, const void *data, size_t bytes );
qboolean GLX_Stream_UploadAt( StreamState *state, StreamReservation *reservation, size_t relativeOffset,
	const void *data, size_t bytes );
void GLX_Stream_Commit( StreamState *state, StreamReservation *reservation );
qboolean GLX_Stream_DrawEnabled( const StreamState &state );
qboolean GLX_Stream_DrawMultitextureEnabled( const StreamState &state );
qboolean GLX_Stream_DrawFogEnabled( const StreamState &state );
qboolean GLX_Stream_DrawDepthFragmentEnabled( const StreamState &state );
qboolean GLX_Stream_DrawTexModsEnabled( const StreamState &state );
qboolean GLX_Stream_DrawEnvironmentEnabled( const StreamState &state );
qboolean GLX_Stream_DrawDynamicLightsEnabled( const StreamState &state );
qboolean GLX_Stream_DrawScreenMapsEnabled( const StreamState &state );
qboolean GLX_Stream_DrawVideoMapsEnabled( const StreamState &state );
qboolean GLX_Stream_DrawShadowsEnabled( const StreamState &state );
qboolean GLX_Stream_DrawBeamsEnabled( const StreamState &state );
qboolean GLX_Stream_DrawPostProcessEnabled( const StreamState &state );
qboolean GLX_Stream_DrawAllowsMaterial( StreamState *state, int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int texMods0, int texMods1 );
void GLX_Stream_RecordDrawResult( StreamState *state, int numVertexes, int numIndexes,
	int totalBytes, int indexBytes, int texcoord1Bytes, qboolean multitexture, qboolean fog,
	qboolean depthFragment, int materialFlags, qboolean success );
void GLX_Stream_RecordDrawSkip( StreamState *state, int reason );
void GLX_Stream_RunSelfTest( StreamState *state );
void GLX_Stream_ShadowUploadTess( StreamState *state, int numVertexes, int numIndexes,
	const void *xyz, size_t xyzBytes, const void *indexes, size_t indexBytes );
const char *GLX_Stream_StrategyName( StreamStrategy strategy );
void GLX_Stream_PrintInfo( const StreamState &state );

} // namespace glx

#endif // GLX_STREAM_H
