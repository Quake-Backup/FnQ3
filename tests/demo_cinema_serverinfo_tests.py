import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class DemoCinemaServerinfoSourceTests(unittest.TestCase):
    """Source contract for the read-only sv_playingDemo indicator.

    sv.demoPlayback (server-side demo cinema state) is otherwise invisible to
    the local console and to remote clients/server browsers. sv_playingDemo
    mirrors it as a CVAR_SERVERINFO | CVAR_ROM cvar, following the same
    pattern as the existing read-only `mapname` cvar.
    """

    def test_sv_playingDemo_registered_serverinfo_rom(self):
        source = read_text("code/server/sv_init.cpp")
        self.assertIn(
            'Cvar_Get( "sv_playingDemo", "0", CVAR_SERVERINFO | CVAR_ROM )',
            source,
        )

    def test_sv_playingDemo_set_entering_cinema(self):
        source = read_text("code/server/sv_demo_play.cpp")
        spawn_start = source.index("void SV_SpawnDemoServer(")
        spawn_body = source[spawn_start:spawn_start + 6000]
        demo_playback_true = spawn_body.index("sv.demoPlayback         = qtrue;")
        cvar_set = spawn_body.index('Cvar_Set( "sv_playingDemo", "1" );', demo_playback_true)
        self.assertGreater(
            cvar_set, demo_playback_true,
            "sv_playingDemo must be set to 1 after sv.demoPlayback is marked active",
        )

    def test_sv_playingDemo_reset_on_normal_spawn(self):
        source = read_text("code/server/sv_init.cpp")
        spawn_start = source.index("void SV_SpawnServer(")
        reset_call = source.index('Cvar_Set( "sv_playingDemo", "0" );', spawn_start)
        game_state = source.index("sv.state = SS_GAME;", spawn_start)
        self.assertLess(
            reset_call, game_state,
            "a normal map spawn must clear sv_playingDemo before entering SS_GAME",
        )

    def test_sv_playingDemo_reset_on_shutdown(self):
        source = read_text("code/server/sv_init.cpp")
        shutdown_start = source.index("void SV_Shutdown(")
        shutdown_body = source[shutdown_start:shutdown_start + 3000]
        running_reset = shutdown_body.index('Cvar_Set( "sv_running", "0" );')
        demo_reset = shutdown_body.index('Cvar_Set( "sv_playingDemo", "0" );', running_reset)
        self.assertGreater(demo_reset, running_reset)

    def test_getinfo_reports_playingDemo(self):
        source = read_text("code/server/sv_main.cpp")
        gametype_key = source.index('Info_SetValueForKey( infostring.data(), "gametype",')
        playing_demo_key = source.index(
            'Info_SetValueForKey( infostring.data(), "playingDemo", va( "%i", sv.demoPlayback ) );',
            gametype_key,
        )
        self.assertGreater(playing_demo_key, gametype_key)


class DemoCinemaMissingMapSourceTests(unittest.TestCase):
    """Source contract: sv_playdemo must refuse to start cinema for a demo whose
    map is not present on this server, instead of letting every connecting
    client discover the missing BSP on its own and disconnect.
    """

    def test_map_existence_checked_before_demo_playback_flag(self):
        source = read_text("code/server/sv_demo_play.cpp")
        spawn_start = source.index("void SV_SpawnDemoServer(")
        spawn_body = source[spawn_start:spawn_start + 6000]

        probe = spawn_body.index('FS_FOpenFileRead( va( "maps/%s.bsp", mapname )')
        demo_playback_true = spawn_body.index("sv.demoPlayback         = qtrue;")
        self.assertLess(
            probe, demo_playback_true,
            "the map existence probe must run before sv.demoPlayback is committed",
        )

    def test_missing_map_aborts_cleanly(self):
        source = read_text("code/server/sv_demo_play.cpp")
        spawn_start = source.index("void SV_SpawnDemoServer(")
        spawn_body = source[spawn_start:spawn_start + 6000]

        probe = spawn_body.index('FS_FOpenFileRead( va( "maps/%s.bsp", mapname )')
        # the failure branch immediately following the probe must abort via
        # SV_Shutdown + return, matching the sibling validation failures already
        # established in this function (corrupt/truncated demo, bad gamestate, ...)
        failure_branch = spawn_body[probe:probe + 500]
        self.assertIn('SV_Shutdown( "demo cinema init failed" )', failure_branch)
        self.assertIn("return;", failure_branch)

    def test_successful_probe_closes_the_handle(self):
        source = read_text("code/server/sv_demo_play.cpp")
        spawn_start = source.index("void SV_SpawnDemoServer(")
        spawn_body = source[spawn_start:spawn_start + 6000]

        probe = spawn_body.index('FS_FOpenFileRead( va( "maps/%s.bsp", mapname )')
        demo_playback_true = spawn_body.index("sv.demoPlayback         = qtrue;")
        between = spawn_body[probe:demo_playback_true]
        self.assertIn("FS_FCloseFile( mapFile );", between)


if __name__ == "__main__":
    unittest.main()
