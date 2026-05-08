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

#ifndef GLX_TYPES_H
#define GLX_TYPES_H

#include "../qcommon/q_shared.h"

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

} // namespace glx

#endif // GLX_TYPES_H
