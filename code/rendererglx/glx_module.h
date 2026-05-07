#ifndef GLX_MODULE_H
#define GLX_MODULE_H

#ifdef __cplusplus
extern "C" {
#endif

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

void GLX_Renderer_RegisterCommands( void );
void GLX_Renderer_RemoveCommands( void );
void GLX_Renderer_SetImports( refimport_t *imports );
void GLX_Renderer_OnOpenGLReady( const glconfig_t *config, const char *extensions );
void GLX_Renderer_Shutdown( refShutdownCode_t code );
void GLX_Renderer_BeginBackendTimer( void );
void GLX_Renderer_EndBackendTimer( void );
void GLX_Renderer_FrameComplete( void );
void GLX_Renderer_PrintCaps_f( void );
void GLX_Renderer_PrintInfo_f( void );
void GLX_Renderer_Material_f( void );
void GLX_Renderer_PostProcess_f( void );
void GLX_Renderer_StaticWorld_f( void );
void GLX_Renderer_StreamTest_f( void );
void GLX_Renderer_PrintFrameCounters( void );
void GLX_Renderer_RecordDraw( int indexes, int path );
void GLX_Renderer_RecordShaderBatch( const char *shaderName, int sort, int numPasses,
	int numVertexes, int numIndexes, int flags );
void GLX_Renderer_RecordMaterialStage( int path, int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	int numVertexes, int numIndexes );
qboolean GLX_Renderer_MaterialRendererActive( void );
qboolean GLX_Renderer_BindMaterialStage( int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int tcGen1, int texMods0, int texMods1,
	int multitextureEnv, qboolean fogPass );
qboolean GLX_Renderer_BindFogMaterial( void );
void GLX_Renderer_UnbindMaterial( void );
qboolean GLX_Renderer_StreamDrawEnabled( void );
qboolean GLX_Renderer_StreamDrawMultitextureEnabled( void );
qboolean GLX_Renderer_StreamDrawFogEnabled( void );
qboolean GLX_Renderer_StreamDrawDepthFragmentEnabled( void );
qboolean GLX_Renderer_StreamDrawAllowsMaterial( int flags, unsigned int stateBits,
	int rgbGen, int alphaGen, int tcGen0, int texMods0 );
qboolean GLX_Renderer_StreamReserve( int bytes, int alignment, glxStreamReservation_t *reservation );
qboolean GLX_Renderer_StreamUploadAt( glxStreamReservation_t *reservation, int relativeOffset,
	const void *data, int bytes );
void GLX_Renderer_StreamCommit( glxStreamReservation_t *reservation );
void GLX_Renderer_RecordStreamDrawResult( int numVertexes, int numIndexes,
	int totalBytes, int indexBytes, int texcoord1Bytes, qboolean multitexture, qboolean fog,
	qboolean depthFragment, qboolean success );
void GLX_Renderer_RecordStreamDrawSkip( int reason );
void GLX_Renderer_RecordFboInit( qboolean requested, qboolean ready,
	qboolean programReady, qboolean framebufferFnsReady, int vidWidth, int vidHeight,
	int captureWidth, int captureHeight, int windowWidth, int windowHeight,
	int internalFormat, int textureFormat, int textureType, qboolean multiSampled,
	qboolean superSampled, qboolean windowAdjusted, int blitFilter, int hdrMode,
	int renderScaleMode, int bloomMode );
void GLX_Renderer_RecordFboShutdown( void );
void GLX_Renderer_RecordPostProcessFrame( qboolean minimized, qboolean bloomAvailable,
	qboolean programReady, int screenshotMask, qboolean windowAdjusted, int fboReadIndex,
	int hdrMode, int renderScaleMode, float greyscale );
void GLX_Renderer_RecordPostProcessResult( int result );
void GLX_Renderer_RecordBloomCreate( int result, int requestedPasses,
	int effectivePasses, int textureUnits );
void GLX_Renderer_RecordBloom( int result, qboolean finalStage, int bloomMode,
	int requestedPasses, int effectivePasses, int blendBase, int filterSize,
	int textureUnits, int thresholdMode, int modulate, float threshold, float intensity,
	float reflection );
void GLX_Renderer_RecordFboCopyScreen( int viewportWidth, int viewportHeight );
void GLX_Renderer_RecordFboBlit( int kind, qboolean depthOnly,
	int srcWidth, int srcHeight, int dstWidth, int dstHeight );
void GLX_Renderer_PushShaderDebugGroup( const char *shaderName, int numVertexes, int numIndexes, int numPasses );
void GLX_Renderer_PopDebugGroup( void );
void GLX_Renderer_ShadowUploadTess( int numVertexes, int numIndexes,
	const void *xyz, int xyzBytes, const void *indexes, int indexBytes );
void GLX_Renderer_RecordStaticWorldCache( int surfaces, int vertexes, int indexes, int vertexBytes, int indexBytes );
void GLX_Renderer_RecordStaticWorldBatches( int batches, int largestBatchSurfaces,
	int faceSurfaces, int gridSurfaces, int triangleSurfaces, int shaderStagePasses, int maxShaderStages );
void GLX_Renderer_RecordStaticWorldPacket( const char *shaderName, int sort,
	int surfaces, int vertexes, int indexes, int firstItem, int itemCount, int vertexOffset, int vertexBytes,
	int indexOffset, int indexBytes, int shaderStagePasses, int flags );
void GLX_Renderer_UploadStaticWorldArena( const void *vertexData, int vertexBytes,
	const void *indexData, int indexBytes );
unsigned int GLX_Renderer_StaticWorldArenaVertexBuffer( void );
unsigned int GLX_Renderer_StaticWorldArenaIndexBuffer( void );
qboolean GLX_Renderer_StaticWorldDrawDeviceRun( int indexes, int offsetBytes,
	int firstItem, int itemCount, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound );
qboolean GLX_Renderer_StaticWorldDrawDeviceRuns( int runCount, const int *counts,
	const void *const *offsets, const int *firstItems, const int *itemCounts,
	unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound );
qboolean GLX_Renderer_StaticWorldDrawSoftIndexes( int indexes, const void *indexData,
	unsigned int indexType, int indexBytes, const char *shaderName, int sort, qboolean arenaBound );
int GLX_Renderer_StaticWorldDrawDeviceRunsFiltered( int runCount, const int *counts,
	const void *const *offsets, const int *firstItems, const int *itemCounts,
	int *drawnRuns, unsigned int indexType, int indexBytes,
	const char *shaderName, int sort, qboolean arenaBound );
void GLX_Renderer_RecordStaticWorldQueue( int queuedItems, int queuedVertexes, int queuedIndexes,
	int deviceRuns, int deviceIndexes, int softIndexes, int largestDeviceRunIndexes );
void GLX_Renderer_RecordStaticWorldDeviceRuns( int runCount, const int *counts,
	const void *const *offsets, const int *firstItems, const int *itemCounts,
	int indexBytes, const char *shaderName, int sort );

#ifdef __cplusplus
}
#endif

#endif // GLX_MODULE_H
