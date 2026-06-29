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
// sv_demo_play.cpp -- server-side demo cinema: replay a demo file to all
// connected clients simultaneously, locked to the recorded player's view.

#include "server.h"

#include <array>
#include <cstring>

// MAX_PARSE_ENTITIES is not available server-side; we only need a two-frame
// rolling buffer of entity states for delta decoding, which server_t already
// provides (demoEnts / demoPrevEnts).

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/*
SV_DemoResolveFile

Try to open <name> as a demo file.  Search order:
  1. demos/<name>.dm_<proto>        (client-recorded demos)
  2. demos/server/<name>.dm_<proto> (server auto-recorded demos)
  3. <name> verbatim                (absolute or already-extended path)

On failure prints each path that was tried and returns FS_INVALID_HANDLE.
On success fills outPath with the resolved path and returns the handle.
*/
static fileHandle_t SV_DemoResolveFile( const char *name, char *outPath, int outSize )
{
	fileHandle_t f;
	const int protocols[] = { NEW_PROTOCOL_VERSION, OLD_PROTOCOL_VERSION, 0 };
	std::array<char, MAX_OSPATH> tried{};
	bool anyTried = false;

	auto tryPath = [&]( const char *path ) -> fileHandle_t {
		FS_FOpenFileRead( path, &f, qtrue );
		if ( !anyTried ) {
			Com_Printf( "  trying: %s ... %s\n", path, f != FS_INVALID_HANDLE ? "found" : "not found" );
			anyTried = true;
		} else {
			Com_Printf( "  trying: %s ... %s\n", path, f != FS_INVALID_HANDLE ? "found" : "not found" );
		}
		if ( f != FS_INVALID_HANDLE ) {
			Q_strncpyz( outPath, path, outSize );
		}
		return f;
	};

	for ( int i = 0; protocols[i]; i++ ) {
		Com_sprintf( tried.data(), static_cast<int>( tried.size() ),
			"demos/%s." DEMOEXT "%d", name, protocols[i] );
		if ( tryPath( tried.data() ) != FS_INVALID_HANDLE ) return f;
	}

	for ( int i = 0; protocols[i]; i++ ) {
		Com_sprintf( tried.data(), static_cast<int>( tried.size() ),
			"demos/server/%s." DEMOEXT "%d", name, protocols[i] );
		if ( tryPath( tried.data() ) != FS_INVALID_HANDLE ) return f;
	}

	// Verbatim last — handles a fully-qualified path or already-extended name.
	Q_strncpyz( tried.data(), name, static_cast<int>( tried.size() ) );
	return tryPath( tried.data() );
}


/*
SV_DemoReadRawMessage

Read the next length-prefixed message from the demo file into msg.
Returns qtrue on success, qfalse on EOF or error.
The caller must provide a buffer of at least MAX_MSGLEN_BUF bytes.
*/
static qboolean SV_DemoReadRawMessage( msg_t *msg, byte *buf, int bufSize )
{
	int sequence, length;

	// sequence number (4 bytes)
	if ( FS_Read( &sequence, 4, sv.demoFile ) != 4 ) {
		return qfalse;
	}
	sequence = LittleLong( sequence );

	// length (4 bytes); -1 signals end of demo
	if ( FS_Read( &length, 4, sv.demoFile ) != 4 ) {
		return qfalse;
	}
	length = LittleLong( length );

	if ( length == -1 ) {
		return qfalse; // normal EOF terminator
	}

	if ( length < 0 || length > bufSize ) {
		Com_Printf( "SV_DemoReadRawMessage: bad length %d\n", length );
		return qfalse;
	}

	if ( FS_Read( buf, length, sv.demoFile ) != length ) {
		return qfalse;
	}

	sv.demoMessageSequence = sequence;
	MSG_Init( msg, buf, length );
	msg->cursize = length;
	return qtrue;
}


/*
SV_DemoParseGamestate

Consume the gamestate message that opens every demo file.  Populates
sv.configstrings[], sv.svEntities[].baseline / sv.baselineUsed[],
sv.demoClientNum, and sv.demoChecksumFeed.
*/
static qboolean SV_DemoParseGamestate( msg_t *msg )
{
	entityState_t	nullstate{};
	int				cmd;
	int				newnum;
	const char		*s;

	// The gamestate message starts with the server's reliableSequence.
	// We don't need it server-side but must read it to advance the cursor.
	MSG_ReadLong( msg ); // serverCommandSequence / reliableSequence

	while ( 1 ) {
		cmd = MSG_ReadByte( msg );

		if ( cmd == svc_EOF ) {
			break;
		}

		if ( cmd == svc_configstring ) {
			int index = MSG_ReadShort( msg );
			if ( index < 0 || index >= MAX_CONFIGSTRINGS ) {
				Com_Error( ERR_DROP, "SV_DemoParseGamestate: configstring index %d out of range", index );
			}
			s = MSG_ReadBigString( msg );
			SV_ZFree( sv.configstrings[index] );
			sv.configstrings[index] = CopyString( s );
		} else if ( cmd == svc_baseline ) {
			newnum = MSG_ReadEntitynum( msg );
			if ( newnum < 0 || newnum >= MAX_GENTITIES ) {
				Com_Error( ERR_DROP, "SV_DemoParseGamestate: baseline entity %d out of range", newnum );
			}
			MSG_ReadDeltaEntity( msg, &nullstate, &sv.svEntities[newnum].baseline, newnum );
			sv.baselineUsed[newnum] = 1;
		} else {
			Com_Error( ERR_DROP, "SV_DemoParseGamestate: bad command byte %d", cmd );
		}
	}

	// clientNum and checksumFeed follow the closing svc_EOF.
	sv.demoClientNum    = MSG_ReadLong( msg );
	sv.demoChecksumFeed = MSG_ReadLong( msg );
	sv.checksumFeed     = sv.demoChecksumFeed;

	return qtrue;
}


/*
SV_DemoHandleServerCommand

Called for each svc_serverCommand token found in a snapshot message.
Configstring commands (cs/bcs0/bcs1/bcs2) are applied to sv.configstrings
so late-joining clients see correct state.  All other commands are broadcast
to spectators so chat, centerprints, scores etc. reach the audience.
*/
static void SV_DemoHandleServerCommand( const char *cmd )
{
	int		index;
	char	key[MAX_STRING_CHARS];
	char	value[MAX_STRING_CHARS];

	if ( !strncmp( cmd, "cs ", 3 ) ) {
		// "cs <index> <value>"
		index = atoi( cmd + 3 );
		if ( index >= 0 && index < MAX_CONFIGSTRINGS ) {
			const char *sp = strchr( cmd + 3, ' ' );
			if ( sp ) {
				Q_strncpyz( value, sp + 1, sizeof( value ) );
				// strip surrounding quotes that SV_SendServerCommand adds
				if ( value[0] == '"' ) {
					int len = strlen( value );
					if ( len > 1 && value[len-1] == '"' ) {
						value[len-1] = '\0';
						SV_SetConfigstring( index, value + 1 );
					} else {
						SV_SetConfigstring( index, value );
					}
				} else {
					SV_SetConfigstring( index, value );
				}
			}
		}
	} else if ( !strncmp( cmd, "bcs0 ", 5 ) || !strncmp( cmd, "bcs1 ", 5 ) || !strncmp( cmd, "bcs2 ", 5 ) ) {
		// chunked configstring update — parse index and accumulate in scratch
		// bcs0 starts a new string, bcs1 appends, bcs2 appends and commits
		static int   bcsIndex = -1;
		static std::array<char, MAX_STRING_CHARS * 4> bcsAccum{};

		index = atoi( cmd + 5 );
		if ( index < 0 || index >= MAX_CONFIGSTRINGS ) return;

		const char *chunk = strchr( cmd + 5, ' ' );
		if ( !chunk ) return;
		chunk++; // skip space
		// strip outer quotes
		if ( chunk[0] == '"' ) {
			Q_strncpyz( key, chunk + 1, sizeof(key) );
			int kl = strlen( key );
			if ( kl > 0 && key[kl-1] == '"' ) key[kl-1] = '\0';
		} else {
			Q_strncpyz( key, chunk, sizeof(key) );
		}

		if ( cmd[3] == '0' ) {
			bcsIndex = index;
			Q_strncpyz( bcsAccum.data(), key, static_cast<int>(bcsAccum.size()) );
		} else {
			if ( bcsIndex == index ) {
				Q_strcat( bcsAccum.data(), static_cast<int>(bcsAccum.size()), key );
			}
		}
		if ( cmd[3] == '2' && bcsIndex == index ) {
			SV_SetConfigstring( index, bcsAccum.data() );
			bcsIndex = -1;
		}
	} else {
		// Non-configstring server command: broadcast to all spectators.
		SV_SendServerCommand( nullptr, "%s", cmd );
	}
}


/*
SV_DemoParseSnapshot

Decode one svc_snapshot message from the demo into sv.demoPS and sv.demoEnts[].
Also drains any leading svc_serverCommand tokens that precede the snapshot.
Returns qtrue on success.
*/
static qboolean SV_DemoParseSnapshot( msg_t *msg )
{
	int				cmd;
	int				serverTime;
	int				deltaNum;
	int				snapFlags;
	int				areabytes;
	byte			areamask[MAX_MAP_AREA_BYTES];
	int				newnum;
	entityState_t	*oldEnt;
	int				i;

	// Drain leading server commands.
	while ( 1 ) {
		cmd = MSG_ReadByte( msg );

		if ( cmd == svc_serverCommand ) {
			int seq = MSG_ReadLong( msg );
			(void)seq; // server-side we don't need the sequence for reliable tracking
			const char *s = MSG_ReadString( msg );
			SV_DemoHandleServerCommand( s );
			continue;
		}

		if ( cmd == svc_snapshot ) {
			break;
		}

		if ( cmd == svc_EOF ) {
			// Empty message (no snapshot this frame) — not a fatal error.
			return qfalse;
		}

		Com_Printf( "SV_DemoParseSnapshot: unexpected command byte %d before snapshot\n", cmd );
		return qfalse;
	}

	// svc_snapshot header
	serverTime = MSG_ReadLong( msg );
	deltaNum   = MSG_ReadByte( msg );
	snapFlags  = MSG_ReadByte( msg ); (void)snapFlags;

	areabytes = MSG_ReadByte( msg );
	if ( areabytes > static_cast<int>( sizeof(areamask) ) ) {
		Com_Printf( "SV_DemoParseSnapshot: invalid areabytes %d\n", areabytes );
		return qfalse;
	}
	MSG_ReadData( msg, areamask, areabytes );

	// Playerstate — delta from previous or null.
	if ( deltaNum == 0 ) {
		// Non-delta (first snapshot after gamestate, or forced non-delta)
		playerState_t nullPS{};
		MSG_ReadDeltaPlayerstate( msg, &nullPS, &sv.demoPS );
	} else {
		MSG_ReadDeltaPlayerstate( msg, &sv.demoPrevPS, &sv.demoPS );
	}
	sv.demoPrevPS = sv.demoPS;

	// Entities — same walk as CL_ParsePacketEntities, but into our flat arrays.
	// We decode against demoPrevEnts and write into demoEnts.
	entityState_t newEnts[MAX_GENTITIES];
	int           newCount = 0;

	// Build an index-sorted snapshot from demoPrevEnts for delta sources
	// (identical to how the client uses cl.parseEntities).
	int oldIndex = 0;

	while ( 1 ) {
		newnum = MSG_ReadEntitynum( msg );
		if ( newnum < 0 ) {
			Com_Printf( "SV_DemoParseSnapshot: end of message in entity list\n" );
			break;
		}
		if ( newnum == MAX_GENTITIES - 1 ) {
			break; // terminator
		}

		// Carry over unchanged old entities whose number < newnum
		while ( deltaNum != 0 && oldIndex < sv.demoNumEnts && sv.demoPrevEnts[oldIndex].number < newnum ) {
			newEnts[newCount++] = sv.demoPrevEnts[oldIndex++];
		}

		// Find the delta source for this entity
		oldEnt = nullptr;
		if ( deltaNum != 0 ) {
			// Check if old list has a matching entry
			for ( i = 0; i < sv.demoNumEnts; i++ ) {
				if ( sv.demoPrevEnts[i].number == newnum ) {
					oldEnt = &sv.demoPrevEnts[i];
					oldIndex = i + 1;
					break;
				}
			}
		}

		entityState_t decoded{};
		if ( oldEnt ) {
			MSG_ReadDeltaEntity( msg, oldEnt, &decoded, newnum );
		} else {
			// Delta from baseline
			MSG_ReadDeltaEntity( msg, &sv.svEntities[newnum].baseline, &decoded, newnum );
		}

		if ( decoded.number == MAX_GENTITIES - 1 ) {
			// Entity was removed (delta-to-null sentinel)
			continue;
		}

		if ( newCount < MAX_GENTITIES ) {
			newEnts[newCount++] = decoded;
		}
	}

	// Carry over any remaining old entities
	while ( deltaNum != 0 && oldIndex < sv.demoNumEnts ) {
		newEnts[newCount++] = sv.demoPrevEnts[oldIndex++];
	}

	// Commit new frame
	sv.demoNumEnts = newCount;
	for ( i = 0; i < newCount; i++ ) {
		sv.demoEnts[i]     = newEnts[i];
		sv.demoPrevEnts[i] = newEnts[i];
	}

	sv.time = serverTime;
	return qtrue;
}


// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/*
SV_BuildDemoSnapshot

Fill a per-client snapshot frame from the current decoded demo frame.
Called from SV_BuildClientSnapshot when sv.demoPlayback is set.
*/
void SV_BuildDemoSnapshot( clientSnapshot_t *frame )
{
	int i;

	frame->ps        = sv.demoPS;
	frame->areabytes = 0; // no area culling: send all entities

	// Stage demoEnts into svs.currFrame storage so SV_WriteSnapshotToClient
	// can reference them via the normal pointer array.
	if ( svs.currFrame == nullptr ) {
		// Allocate a fresh common frame (mirrors SV_BuildCommonSnapshot
		// but without reading from the game's linked entity list).
		snapshotFrame_t *sf = &svs.snapFrames[ svs.snapshotFrame % NUM_SNAPSHOT_FRAMES ];

		int count = sv.demoNumEnts;

		if ( svs.snapshotFrame - svs.lastValidFrame > ( NUM_SNAPSHOT_FRAMES - 1 ) ) {
			svs.lastValidFrame = svs.snapshotFrame - ( NUM_SNAPSHOT_FRAMES - 1 );
			svs.freeStorageEntities += sf->count;
			sf->count = 0;
		}

		while ( svs.freeStorageEntities < count && svs.lastValidFrame != svs.snapshotFrame ) {
			snapshotFrame_t *tmp = &svs.snapFrames[ svs.lastValidFrame % NUM_SNAPSHOT_FRAMES ];
			svs.lastValidFrame++;
			svs.freeStorageEntities += tmp->count;
			tmp->count = 0;
		}

		sf->count = count;
		svs.freeStorageEntities -= count;
		sf->start    = svs.currentStoragePosition;
		sf->frameNum = svs.snapshotFrame;
		svs.snapshotFrame++;

		int index = sf->start;
		for ( i = 0; i < count; i++ ) {
			svs.snapshotEntities[index] = sv.demoEnts[i];
			sf->ents[i] = &svs.snapshotEntities[index];
			index = ( index + 1 ) % svs.numSnapshotEntities;
		}

		svs.currFrame = sf;
	}

	frame->num_entities = sv.demoNumEnts;
	for ( i = 0; i < sv.demoNumEnts; i++ ) {
		frame->ents[i] = svs.currFrame->ents[i];
	}
}


/*
SV_DemoAdvance

Called once per server frame from SV_Frame when sv.demoPlayback is set.
Reads the next snapshot message from the demo file.  On EOF, sets
sv.demoEnded and sends a one-time "demo ended" centerprint.
*/
void SV_DemoAdvance( void )
{
	std::array<byte, MAX_MSGLEN_BUF> buf{};
	msg_t msg;

	if ( sv.demoEnded || sv.demoFile == FS_INVALID_HANDLE ) {
		return;
	}

	if ( !SV_DemoReadRawMessage( &msg, buf.data(), static_cast<int>( buf.size() ) ) ) {
		// EOF or read error — enter hold state.
		sv.demoEnded = qtrue;
		SV_SendServerCommand( nullptr, "cp \"Demo playback ended.\n\"" );
		Com_Printf( "SV_DemoAdvance: demo ended, holding on last frame.\n" );
		return;
	}

	SV_DemoParseSnapshot( &msg );
}


/*
SV_SpawnDemoServer

Switch the server into demo-cinema mode for the given demo file.
Replaces the usual SV_SpawnServer: skips the game VM, BSP load,
and entity simulation.  Connected clients are kept and will receive
a fresh gamestate derived from the demo.
*/
void SV_SpawnDemoServer( const char *demoName )
{
	std::array<char, MAX_OSPATH> resolvedPath{};
	std::array<byte, MAX_MSGLEN_BUF> buf{};
	msg_t msg;
	fileHandle_t demoFile;

	Com_Printf( "------ Demo Cinema Initialization ------\n" );
	Com_Printf( "Demo: %s\n", demoName );

	// Resolve and open the demo file BEFORE touching the running game.
	// If the file is not found we abort without disturbing the current server
	// state, which prevents gvm from being left null while sv_running is 1.
	demoFile = SV_DemoResolveFile( demoName, resolvedPath.data(), static_cast<int>( resolvedPath.size() ) );
	if ( demoFile == FS_INVALID_HANDLE ) {
		Com_Printf( S_COLOR_RED "sv_playdemo: could not find demo '%s'\n"
			S_COLOR_WHITE "  Place demos in <gamedir>/demos/ or <gamedir>/demos/server/\n"
			"  and omit the .dm_N extension.\n", demoName );
		return;
	}

	Com_Printf( "Opened demo: %s\n", resolvedPath.data() );

	// File is confirmed open — safe to tear down the existing game now.
	// Close any previously open cinema demo file first.
	SV_CloseFileHandle( sv.demoFile );
	sv.demoFile = demoFile; // take ownership before any further early returns

	// Shut down the existing game if it is running (frees gvm, etc.).
	SV_ShutdownGameProgs();

#ifndef DEDICATED
	CL_MapLoading();
	CL_ShutdownAll();
#endif

	// Do NOT clear the hunk — we have no BSP, so no new hunk allocation
	// is needed.  Just clear the per-level server_t and reset snapshot
	// storage.

	// Init/resize client slots if needed.
	if ( !Cvar_VariableIntegerValue( "sv_running" ) ) {
		SV_Startup();
	} else {
		if ( sv_maxclients->modified ) {
			SV_ChangeMaxClients();
		}
	}

	// Allocate snapshot entity storage.
	svs.snapshotEntities = SV_HunkAllocArray<entityState_t>( svs.numSnapshotEntities, h_high );
	SV_InitSnapshotStorage();

	svs.snapFlagServerBit ^= SNAPFLAG_SERVERCOUNT;

	// Save per-client timing before the clear.
	for ( client_t &client : SV_Clients() ) {
		if ( client.state >= CS_CONNECTED ) {
			client.oldServerTime = sv.time;
		} else {
			client.oldServerTime = 0;
		}
	}

	const int preservedMaxClients = sv.maxclients;

	// SV_ClearServer zeros sv including sv.demoFile, so grab the handle
	// from our local copy before the clear and restore it afterwards.
	SV_ClearServer();
	sv.maxclients = preservedMaxClients;
	sv.demoFile   = demoFile;

	// Reset all configstrings.
	for ( int index : SV_Indices( MAX_CONFIGSTRINGS ) ) {
		sv.configstrings[index] = CopyString( "" );
	}

	// Assign a fresh serverId.
	sv.serverId         = com_frameTime;
	sv.restartedServerId = sv.serverId;
	Cvar_SetIntegerValue( "sv_serverid", sv.serverId );

	// Demo cinema never runs sv_pure checks.
	sv_pure = Cvar_Get( "sv_pure", "0", CVAR_SYSTEMINFO | CVAR_LATCH );
	Cvar_Set( "sv_pure", "0" );
	sv.pure = 0;

	// Read and parse the gamestate from the demo header.
	if ( !SV_DemoReadRawMessage( &msg, buf.data(), static_cast<int>( buf.size() ) ) ) {
		Com_Printf( S_COLOR_RED "SV_SpawnDemoServer: failed to read demo gamestate — "
			"file may be empty or truncated\n" );
		SV_Shutdown( "demo cinema init failed" );
		return;
	}

	// First message byte should be svc_gamestate.
	{
		int header = MSG_ReadLong( &msg ); (void)header; // lastClientCommand ack
		int cmd    = MSG_ReadByte( &msg );
		if ( cmd != svc_gamestate ) {
			Com_Printf( S_COLOR_RED "SV_SpawnDemoServer: expected svc_gamestate (%d), got %d — "
				"corrupt or incompatible demo\n", svc_gamestate, cmd );
			SV_Shutdown( "demo cinema init failed" );
			return;
		}
	}
	// Re-init the message at the current cursor position and re-advance past
	// the ack long and svc_gamestate byte we already consumed above.
	MSG_Init( &msg, buf.data(), msg.cursize );
	MSG_ReadLong( &msg ); // lastClientCommand ack
	MSG_ReadByte( &msg ); // svc_gamestate

	if ( !SV_DemoParseGamestate( &msg ) ) {
		Com_Printf( S_COLOR_RED "SV_SpawnDemoServer: failed to parse demo gamestate\n" );
		SV_Shutdown( "demo cinema init failed" );
		return;
	}

	// Publish the mapname so clients see it in the serverinfo.
	const char *mapname = Info_ValueForKey( sv.configstrings[CS_SERVERINFO], "mapname" );
	if ( mapname && *mapname ) {
		Cvar_Set( "mapname", mapname );
	}
	sv_mapname = Cvar_Get( "mapname", "nomap", CVAR_SERVERINFO | CVAR_ROM );

	// Mark demo playback active.
	sv.demoPlayback = qtrue;
	sv.demoEnded    = qfalse;
	sv.demoNumEnts  = 0;
	sv.demoPS       = {};
	sv.demoPrevPS   = {};

	sv.state = SS_GAME;

	Cvar_Set( "sv_running", "1" );

	// Read the very first snapshot so sv.time is valid before any client connects.
	SV_DemoAdvance();

	// Force all already-connected clients back to CS_CONNECTED so the
	// normal per-client handshake loop re-sends a fresh gamestate.
	for ( client_t &client : SV_Clients() ) {
		if ( client.state >= CS_CONNECTED ) {
			client.gamestateAck = GSA_INIT;
			client.state        = CS_CONNECTED;
			client.gentity      = nullptr;
		}
	}

	Com_Printf( "Demo cinema ready.  Connect to watch.\n" );
}


/*
SV_PlayDemo_f

Console command handler: sv_playdemo <name>
*/
void SV_PlayDemo_f( void )
{
	if ( Cmd_Argc() < 2 ) {
		Com_Printf( "Usage: sv_playdemo <demoname>\n" );
		Com_Printf( "Example: sv_playdemo baseq3/demos/myfrag\n" );
		return;
	}

	SV_SpawnDemoServer( Cmd_Argv( 1 ) );
}
