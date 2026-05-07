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

#pragma once

#include <cstdint>

namespace fnq3_audiozones {

constexpr std::uint8_t kMagic[4] = { 'F', 'Q', 'A', 'Z' };
constexpr std::uint32_t kVersion = 1;
constexpr std::uint32_t kMaxZones = 1024;
constexpr std::uint32_t kMaxNameBytes = 63;
constexpr std::uint32_t kMaxFileBytes = 1024u * 1024u;
constexpr std::uint32_t kDefaultTransitionMs = 650;

enum class Preset : std::uint32_t {
	SmallRoom = 0,
	Room = 1,
	StoneRoom = 2,
	Hallway = 3,
	Hall = 4,
	Outdoors = 5,
	Underwater = 6,
	Count
};

constexpr const char *kPresetNames[] = {
	"small-room",
	"room",
	"stone-room",
	"hallway",
	"hall",
	"outdoors",
	"underwater"
};

} // namespace fnq3_audiozones
