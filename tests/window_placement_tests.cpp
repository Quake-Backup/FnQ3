#include "../code/platform/window_placement.hpp"
#include "../code/client/canvas_geometry.hpp"
#include "../code/client/window_resize.hpp"

#include <cstdio>

namespace {

int failures;

void Check( bool condition, const char *message ) {
	if ( !condition ) {
		std::fprintf( stderr, "FAIL: %s\n", message );
		++failures;
	}
}

bool Near( float actual, float expected ) {
	const float difference = actual - expected;
	return difference > -0.001f && difference < 0.001f;
}

void TestPlacement() {
	using namespace fnq3::window;
	constexpr Bounds workArea{ 0, 0, 1920, 1040 };
	constexpr Insets frame{ 8, 31, 8, 8 };
	constexpr Position topLeft = ConstrainClientOrigin(
		{ -200, -100 }, 1280, 720, workArea, frame );
	constexpr Position bottomRight = ConstrainClientOrigin(
		{ 1800, 900 }, 1280, 720, workArea, frame );
	Check( topLeft.x == 8 && topLeft.y == 31,
		"client origin accounts for the title bar" );
	Check( bottomRight.x == 632 && bottomRight.y == 312,
		"complete decorated window remains in the work area" );

	constexpr Position negative = ConstrainClientOrigin(
		{ -4000, -500 }, 1600, 900, { -2560, -200, 2560, 1440 },
		{ 6, 28, 6, 6 } );
	Check( negative.x == -2554 && negative.y == -172,
		"negative multi-monitor coordinates remain valid" );

	constexpr Position oversized = ConstrainClientOrigin(
		{ 500, 500 }, 1200, 900, { 100, 50, 800, 600 },
		{ 5, 30, 5, 5 } );
	Check( oversized.x == 105 && oversized.y == 80,
		"oversized window keeps its title bar reachable" );
}

void TestResizeScheduler() {
	using fnq3::client::WindowResizeRequest;
	using fnq3::client::WindowResizeScheduler;
	WindowResizeScheduler scheduler;
	WindowResizeRequest request;

	Check( scheduler.Notify( 1000, 800, 600, true ), "valid resize is queued" );
	scheduler.Notify( 1100, 1280, 720, true );
	constexpr std::uint32_t finalDeadline =
		1100 + WindowResizeScheduler::kDebounceMilliseconds;
	Check( !scheduler.ConsumeIfReady( finalDeadline - 1, &request ), "burst remains debounced" );
	Check( scheduler.ConsumeIfReady( finalDeadline, &request ), "final resize is consumed" );
	Check( request.width == 1280 && request.height == 720 && request.preserveWindow,
		"final size uses the fast retained-window path" );

	scheduler.Notify( 20, 1024, 768, true );
	scheduler.Notify( 30, 1024, 768, false );
	Check( scheduler.ConsumeIfReady(
		30 + WindowResizeScheduler::kDebounceMilliseconds, &request ) &&
		!request.preserveWindow,
		"least-retainable event selects the safe backend path" );

	constexpr std::uint32_t wrapStart = 0xfffffff0u;
	constexpr std::uint32_t wrapDeadline =
		wrapStart + WindowResizeScheduler::kDebounceMilliseconds;
	scheduler.Notify( wrapStart, 1600, 900, true );
	Check( !scheduler.ConsumeIfReady( wrapDeadline - 1, &request ),
		"clock wrap remains before the deadline" );
	Check( scheduler.ConsumeIfReady( wrapDeadline, &request ),
		"clock wrap reaches the deadline" );

	scheduler.Notify( 500, 1366, 768, true );
	scheduler.Complete( 510 );
	Check( scheduler.ConsumeIfReady( 510, &request ),
		"interactive resize completion refreshes immediately" );
}

void TestCanvasGeometry() {
	using fnq3::client::CalculateCanvasGeometry;
	const auto native = CalculateCanvasGeometry( 640, 480 );
	const auto wide = CalculateCanvasGeometry( 1920, 1080 );
	const auto tall = CalculateCanvasGeometry( 800, 1000 );
	Check( Near( native.scale, 1.0f ) && Near( native.biasX, 0.0f ) && Near( native.biasY, 0.0f ),
		"native canvas is unbiased" );
	Check( Near( wide.scale, 2.25f ) && Near( wide.biasX, 240.0f ) && Near( wide.biasY, 0.0f ),
		"wide canvas is centred horizontally" );
	Check( Near( tall.scale, 1.25f ) && Near( tall.biasX, 0.0f ) && Near( tall.biasY, 200.0f ),
		"tall canvas is centred vertically" );
}

} // namespace

int main() {
	TestPlacement();
	TestResizeScheduler();
	TestCanvasGeometry();
	return failures == 0 ? 0 : 1;
}
