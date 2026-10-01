#include "../../code/renderervk/tr_local.h"

#include <stdio.h>
#include <string.h>

Vk_Instance vk;
trGlobals_t tr;

static vk_tess_t frame;
static image_t white_image;
static int failures;
static unsigned int bind_calls;
static uint32_t first_set, set_count, offset_count, dynamic_offset;
static VkDescriptorSet bound_sets[VK_DESC_COUNT];

static void Check( int condition, const char *message )
{
	if ( !condition ) {
		fprintf( stderr, "FAIL: %s\n", message );
		failures++;
	}
}

static VKAPI_ATTR void VKAPI_CALL CaptureBind( VkCommandBuffer command_buffer,
	VkPipelineBindPoint bind_point, VkPipelineLayout layout, uint32_t first,
	uint32_t count, const VkDescriptorSet *sets, uint32_t offsets,
	const uint32_t *offsets_data )
{
	uint32_t i;
	(void)command_buffer;
	Check( bind_point == VK_PIPELINE_BIND_POINT_GRAPHICS,
		"main descriptors use the graphics bind point" );
	Check( layout == vk.pipeline_layout, "main descriptors use the main layout" );
	Check( first + count <= vk.maxBoundDescriptorSets,
		"bind stays within the device's pipeline layout" );
	Check( count <= VK_DESC_COUNT, "bind fits the descriptor array" );
	Check( count > 0, "bind contains at least one descriptor" );
	Check( offsets == ( first == VK_DESC_UNIFORM ? 1U : 0U ),
		"only a bind containing the uniform set carries a dynamic offset" );
	bind_calls++;
	first_set = first;
	set_count = count;
	offset_count = offsets;
	dynamic_offset = offsets ? offsets_data[0] : ~0U;
	for ( i = 0; i < count && i < VK_DESC_COUNT; i++ ) {
		bound_sets[i] = sets[i];
		Check( sets[i] != VK_NULL_HANDLE, "every submitted descriptor is valid" );
	}
}

static PFN_vkCmdBindDescriptorSets qvkCmdBindDescriptorSets = CaptureBind;

#include "vk_descriptor_bindings.inc"

static VkDescriptorSet Handle( uintptr_t value )
{
	return (VkDescriptorSet)value;
}

static void Reset( uint32_t start, uint32_t end, uint32_t device_sets )
{
	memset( &vk, 0, sizeof( vk ) );
	memset( &frame, 0, sizeof( frame ) );
	memset( bound_sets, 0, sizeof( bound_sets ) );
	vk.cmd = &frame;
	vk.maxBoundDescriptorSets = device_sets;
	frame.uniform_descriptor = Handle( 101 );
	frame.descriptor_set.start = start;
	frame.descriptor_set.end = end;
	white_image.descriptor = Handle( 11 );
	tr.whiteImage = &white_image;
	bind_calls = 0;
	first_set = set_count = offset_count = dynamic_offset = ~0U;
}

static void TestFirstMenuDraw( void )
{
	Reset( 0, 1, 5 );
	frame.descriptor_set.current[0] = frame.uniform_descriptor;
	frame.descriptor_set.current[1] = Handle( 202 );
	frame.descriptor_set.offset[0] = 96;
	vk_bind_descriptor_sets();
	Check( bind_calls == 1 && first_set == 0 && set_count == 3,
		"first single-texture draw also binds the shader's depth sampler" );
	Check( bound_sets[0] == frame.uniform_descriptor && bound_sets[1] == Handle( 202 ),
		"first draw preserves its authored uniform and diffuse texture" );
	Check( bound_sets[2] == white_image.descriptor,
		"inactive depth fade uses a valid fallback sampler" );
	Check( offset_count == 1 && dynamic_offset == 96,
		"first draw preserves its dynamic uniform offset" );
	vk_bind_descriptor_sets();
	Check( bind_calls == 1, "unchanged descriptors do not trigger another bind" );
}

static void TestTextureOnlyUpdate( void )
{
	Reset( 1, 1, 5 );
	frame.descriptor_set.current[1] = Handle( 303 );
	frame.descriptor_set.current[2] = Handle( 404 );
	vk_bind_descriptor_sets();
	Check( first_set == 1 && set_count == 2 && offset_count == 0,
		"texture-only updates cover the depth sampler without rebinding uniforms" );
	Check( bound_sets[0] == Handle( 303 ) && bound_sets[1] == Handle( 404 ),
		"existing diffuse and depth samplers are preserved" );
}

static void TestSamplerGaps( void )
{
	uint32_t i;
	Reset( 1, 4, 5 );
	frame.descriptor_set.current[2] = Handle( 404 );
	vk_bind_descriptor_sets();
	for ( i = 0; i < 4; i++ ) {
		Check( bound_sets[i] == ( i == 1 ? Handle( 404 ) : white_image.descriptor ),
			"fallbacks fill leading, interior, and trailing sampler gaps" );
	}
}

static void TestFullRestore( uint32_t device_sets )
{
	uint32_t i;
	Reset( 0, 4, device_sets );
	frame.uniform_read_offset = 256;
	vk_bind_descriptor_sets();
	Check( bind_calls == 1 && first_set == 0 && set_count == device_sets,
		"post-process restore binds every supported main-layout set" );
	Check( bound_sets[0] == frame.uniform_descriptor,
		"missing uniform set uses the frame's uniform descriptor" );
	Check( dynamic_offset == 256, "restored uniforms use the current read offset" );
	for ( i = 1; i < device_sets; i++ ) {
		Check( bound_sets[i] == white_image.descriptor,
			"post-process restore supplies valid sampler fallbacks" );
	}
}

int main( void )
{
	Reset( ~0U, 0, 5 );
	vk_bind_descriptor_sets();
	Check( bind_calls == 0, "clean descriptor state emits no bind" );
	Reset( 4, 4, 4 );
	vk_bind_descriptor_sets();
	Check( bind_calls == 0 && frame.descriptor_set.start == ~0U,
		"unused optional sets outside the layout do not emit an empty bind" );
	TestFirstMenuDraw();
	TestTextureOnlyUpdate();
	TestSamplerGaps();
	TestFullRestore( 5 );
	TestFullRestore( 4 );
	return failures ? 1 : 0;
}
