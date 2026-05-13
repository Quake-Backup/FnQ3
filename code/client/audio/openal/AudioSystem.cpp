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
#include "../snd_local.h"
#include "../../client.h"
#include "../codecs/snd_codec.h"
#include "../../../qcommon/cm_public.h"
}

#include <AL/al.h>
#include <AL/alc.h>
#include <AL/alext.h>

// Older OpenAL headers can lack ALC_SOFT_output_mode even when a newer
// runtime provides it. The backend resolves support dynamically.
#ifndef ALC_SOFT_output_mode
#define ALC_SOFT_output_mode
#define ALC_OUTPUT_MODE_SOFT 0x19AC
#define ALC_ANY_SOFT 0x19AD
#define ALC_MONO_SOFT 0x1500
#define ALC_STEREO_SOFT 0x1501
#define ALC_STEREO_BASIC_SOFT 0x19AE
#define ALC_STEREO_UHJ_SOFT 0x19AF
#define ALC_STEREO_HRTF_SOFT 0x19B2
#define ALC_QUAD_SOFT 0x1503
#define ALC_SURROUND_5_1_SOFT 0x1504
#define ALC_SURROUND_6_1_SOFT 0x1505
#define ALC_SURROUND_7_1_SOFT 0x1506
#endif

// Older OpenAL headers can lack ALC_SOFT_system_events even when a newer
// runtime provides it. The backend resolves these entry points dynamically.
#ifndef ALC_SOFT_system_events
#define ALC_SOFT_system_events
#define ALC_PLAYBACK_DEVICE_SOFT 0x19D4
#define ALC_CAPTURE_DEVICE_SOFT 0x19D5
#define ALC_EVENT_TYPE_DEFAULT_DEVICE_CHANGED_SOFT 0x19D6
#define ALC_EVENT_TYPE_DEVICE_ADDED_SOFT 0x19D7
#define ALC_EVENT_TYPE_DEVICE_REMOVED_SOFT 0x19D8
#define ALC_EVENT_SUPPORTED_SOFT 0x19D9
#define ALC_EVENT_NOT_SUPPORTED_SOFT 0x19DA
typedef void ( ALC_APIENTRY *ALCEVENTPROCTYPESOFT )( ALCenum eventType, ALCenum deviceType, ALCdevice *device, ALCsizei length, const ALCchar *message, void *userParam );
typedef ALCenum ( ALC_APIENTRY *LPALCEVENTISSUPPORTEDSOFT )( ALCenum eventType, ALCenum deviceType );
typedef ALCboolean ( ALC_APIENTRY *LPALCEVENTCONTROLSOFT )( ALCsizei count, const ALCenum *events, ALCboolean enable );
typedef void ( ALC_APIENTRY *LPALCEVENTCALLBACKSOFT )( ALCEVENTPROCTYPESOFT callback, void *userParam );
#endif

#include "../shared/AudioDeviceRecovery.h"
#include "../shared/AudioOcclusion.h"
#include "../shared/AudioZoneFormat.h"
#include "../shared/AudioZoneRuntime.h"

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
