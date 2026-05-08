#ifndef GLX_LOCAL_H
#define GLX_LOCAL_H

#include "../qcommon/q_shared.h"
#include "../qcommon/qcommon.h"
#include "../renderercommon/tr_public.h"
#include "../renderer/qgl.h"

#include "glx_module.h"

namespace glx {

enum class CapabilityTier {
	BelowFloor,
	Compat,
	Core,
	Advanced
};

enum class StreamStrategy {
	OrphanSubData,
	MapBufferRange,
	PersistentMapped
};

struct FeatureSet {
	qboolean mapBufferRange;
	qboolean uniformBufferObject;
	qboolean instancedArrays;
	qboolean bufferStorage;
	qboolean syncObjects;
	qboolean drawIndirect;
	qboolean multiDrawIndirect;
	qboolean directStateAccess;
	qboolean debugContext;
	qboolean debugOutput;
	qboolean khrDebug;
	qboolean timerQuery;
};

struct Capabilities {
	const glconfig_t *config;
	const char *extensions;
	int major;
	int minor;
	CapabilityTier tier;
	FeatureSet features;
};

extern refimport_t *g_imports;

refimport_t &RI();
qboolean ImportsReady();
const char *BoolName( qboolean value );
qboolean ToQBool( bool value );

} // namespace glx

#endif // GLX_LOCAL_H
