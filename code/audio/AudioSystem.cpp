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

#if defined( _WIN32 ) && !defined( NOMINMAX )
#define NOMINMAX
#endif

extern "C" {
#include "../client/snd_local.h"
#include "../client/client.h"
#include "../client/snd_codec.h"
#include "../qcommon/cm_public.h"
}

#include "../openal/include/AL/al.h"
#include "../openal/include/AL/alc.h"
#include "../openal/include/AL/alext.h"
#include "AudioDeviceRecovery.h"
#include "AudioOcclusion.h"
#include "AudioZoneFormat.h"
#include "AudioZoneRuntime.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <limits>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

#include "AudioSystemShared.inl"
#include "AudioSystemOpenAL.inl"
#include "AudioSystemWorld.inl"
#include "AudioSystemStreams.inl"
#include "AudioSystemBackend.inl"

} // namespace

extern "C" qboolean S_OpenAL_Init( soundInterface_t *si ) {
	return AudioSystem::Get().Init( si ) ? qtrue : qfalse;
}

extern "C" void S_OpenAL_ListDevices( void ) {
	AudioSystem::Get().ListDevices();
}

extern "C" void S_OpenAL_ListHrtfs( void ) {
	AudioSystem::Get().ListHrtfs();
}

extern "C" void S_OpenAL_ConfigHints( void ) {
	AudioSystem::Get().PrintOpenALSoftConfigHints();
}

extern "C" qboolean S_OpenAL_RecoverDevice( qboolean force ) {
	return AudioSystem::Get().RecoverDevice( force != qfalse ) ? qtrue : qfalse;
}
