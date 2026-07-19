import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class WindowManagementSourceTests(unittest.TestCase):
    def test_sdl_is_resizable_and_tracks_drawable_pixels(self) -> None:
        glimp = read_text("code/sdl/sdl_glimp.cpp")
        inputs = read_text("code/sdl/sdl_input.cpp")
        header = read_text("code/sdl/sdl_glw.h")
        self.assertIn("SDL_SetWindowResizable( SDL_window, true )", glimp)
        self.assertIn("SDL_SetWindowMinimumSize( SDL_window, 320, 240 )", glimp)
        self.assertIn("SDL_GetWindowBordersSize", glimp)
        self.assertIn("SDL_GetDisplayUsableBounds", glimp)
        self.assertIn("int pixel_width;", header)
        self.assertIn("SDL_EVENT_DISPLAY_USABLE_BOUNDS_CHANGED", inputs)
        self.assertIn("CL_NotifyWindowResize( glw_state.window_width", inputs)

    def test_client_refreshes_canvas_after_resize(self) -> None:
        client = read_text("code/client/cl_main.cpp")
        scheduler = read_text("code/client/window_resize.hpp")
        self.assertIn("kDebounceMilliseconds = 100", scheduler)
        self.assertIn("now - deadline < 0x80000000u", scheduler)
        self.assertIn('Cvar_SetIntegerValue( "r_customWidth", request.width );', client)
        self.assertIn("request.preserveWindow ? REF_KEEP_WINDOW : REF_DESTROY_WINDOW", client)
        canvas_update = client.index("fnq3::client::CalculateCanvasGeometry")
        console_reflow = client.index("Con_CheckResize();", canvas_update)
        self.assertLess(canvas_update, console_reflow)

    def test_windows_snap_dpi_and_resize_events(self) -> None:
        local = read_text("code/win32/win_local.h")
        glimp = read_text("code/win32/win_glimp.cpp")
        wndproc = read_text("code/win32/win_wndproc.cpp")
        self.assertIn("WS_MAXIMIZEBOX|WS_THICKFRAME", local)
        self.assertIn("AdjustWindowRectExForDpi", glimp)
        self.assertIn("case WM_DPICHANGED:", wndproc)
        self.assertIn("case WM_DISPLAYCHANGE:", wndproc)
        self.assertIn("case WM_EXITSIZEMOVE:", wndproc)
        self.assertIn("case WM_GETMINMAXINFO:", wndproc)
        self.assertIn("WIN_ApplyMinimumTrackSize", wndproc)
        self.assertIn("GetClientRect( hWnd, &clientRect )", wndproc)
        self.assertIn("CL_CompleteWindowResize();", wndproc)

    def test_x11_is_resizable_and_decoration_aware(self) -> None:
        source = read_text("code/unix/linux_glimp.cpp")
        hints_start = source.index("memset( &sizehints")
        hints = source[hints_start : hints_start + 350]
        self.assertIn("sizehints.flags = PMinSize;", hints)
        self.assertNotIn("PMaxSize", hints)
        self.assertIn('"_NET_FRAME_EXTENTS"', source)
        self.assertIn('"_NET_WORKAREA"', source)
        self.assertIn("CL_NotifyWindowResize( event.xconfigure.width", source)

    def test_all_renderers_requery_retained_window_geometry(self) -> None:
        for path in (
            "code/renderer/tr_init.c",
            "code/renderervk/tr_init.c",
            "code/rendererrtx/tr_init.c",
        ):
            with self.subTest(path=path):
                source = read_text(path)
                keep = source.index("code != REF_KEEP_WINDOW")
                self.assertIn(
                    "Com_Memset( &glConfig, 0, sizeof( glConfig ) );",
                    source[keep : keep + 800],
                )


if __name__ == "__main__":
    unittest.main()
