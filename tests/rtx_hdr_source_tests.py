from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def source_section(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


class RtxHdrSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.common = read_text("code/rendererrtx/tr_common.h")
        cls.local = read_text("code/rendererrtx/tr_local.h")
        cls.init = read_text("code/rendererrtx/tr_init.c")
        cls.image = read_text("code/rendererrtx/tr_image.c")
        cls.bsp = read_text("code/rendererrtx/tr_bsp.c")
        cls.vk = read_text("code/rendererrtx/vk.c")
        cls.gamma = read_text("code/rendererrtx/shaders/gamma.frag")
        cls.bloom = read_text("code/rendererrtx/shaders/bloom.frag")
        cls.raygen = read_text("code/rendererrtx/shaders/rt_main.rgen")
        cls.closest_hit = read_text("code/rendererrtx/shaders/rt_main.rchit")

    def test_hdr_controls_match_the_vulkan_default_contract(self) -> None:
        expected_defaults = {
            "r_hdr": "1",
            "r_hdrPrecision": "0",
            "r_srgbTextures": "1",
            "r_tonemap": "0",
            "r_tonemapExposure": "1.0",
            "r_bloom_soft_knee": "0.0",
        }
        for name, default in expected_defaults.items():
            with self.subTest(cvar=name):
                self.assertRegex(
                    self.init,
                    rf'ri\.Cvar_Get\(\s*"{re.escape(name)}",\s*"{re.escape(default)}"',
                )

        self.assertIn("display-referred SDR compatibility path", self.init)
        self.assertIn("scene-linear RGBA16F HDR pipeline with sRGB texture decode", self.init)
        self.assertIn("r_hdr 1 always requests RGBA16F", self.init)
        self.assertIn("r_tonemapExposure in the shared final pass", self.init)

        for declaration in (
            "extern cvar_t\t*r_hdrPrecision;",
            "extern cvar_t\t*r_srgbTextures;",
            "extern cvar_t\t*r_tonemap;",
            "extern cvar_t\t*r_tonemapExposure;",
            "extern cvar_t\t*r_bloom_soft_knee;",
        ):
            self.assertIn(declaration, self.local)

    def test_authored_color_textures_decode_to_linear_without_touching_data(self) -> None:
        for flag in (
            "IMGFLAG_COLORSPACE_SRGB",
            "IMGFLAG_COLORSPACE_LINEAR",
            "IMGFLAG_COLORSPACE_DATA",
        ):
            self.assertIn(flag, self.common)
        for color_space in (
            "IMAGE_COLORSPACE_SRGB",
            "IMAGE_COLORSPACE_LINEAR",
            "IMAGE_COLORSPACE_DATA",
        ):
            self.assertIn(color_space, self.common)

        classifier = source_section(
            self.image,
            "static imageColorSpace_t R_ImageColorSpaceForFlags",
            "static qboolean R_ImageWantsSrgbDecode",
        )
        self.assertIn("flags & IMGFLAG_LIGHTMAP", classifier)
        self.assertIn('"*dlight"', classifier)
        self.assertIn('"*identityLight"', classifier)
        self.assertIn('"*fog"', classifier)
        self.assertIn('"*white"', classifier)
        self.assertIn('"*black"', classifier)
        self.assertIn("return IMAGE_COLORSPACE_SRGB;", classifier)

        decode_gate = source_section(
            self.image,
            "static qboolean R_ImageWantsSrgbDecode",
            "typedef struct {\n\tbyte *buffer;",
        )
        self.assertIn("colorSpace == IMAGE_COLORSPACE_SRGB", decode_gate)
        self.assertIn("r_srgbTextures && r_srgbTextures->integer", decode_gate)
        self.assertIn("vk_scene_linear_enabled()", decode_gate)
        self.assertNotIn("#ifdef USE_FBO", decode_gate)
        self.assertIn("VK_FORMAT_R8G8B8A8_SRGB", self.image)
        self.assertIn('format = "sRGBA";', self.image)
        self.assertIn("image->colorSpace = R_ImageColorSpaceForFlags", self.image)
        self.assertIn("image->srgbDecode = R_ImageWantsSrgbDecode", self.image)
        self.assertIn("IMGFLAG_COLORSPACE_LINEAR", self.bsp)

    def test_scene_storage_precision_is_separate_from_hdr_semantics(self) -> None:
        hdr_format = source_section(
            self.vk,
            "static qboolean vk_hdr_scene_format_supported",
            "typedef struct {\n\tint bits;",
        )
        self.assertIn("VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT", hdr_format)
        self.assertIn("VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BLEND_BIT", hdr_format)
        self.assertIn("VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT", hdr_format)
        self.assertIn("VK_FORMAT_FEATURE_TRANSFER_SRC_BIT", hdr_format)
        self.assertIn("VK_FORMAT_FEATURE_TRANSFER_DST_BIT", hdr_format)
        self.assertIn("VK_FORMAT_FEATURE_BLIT_DST_BIT", hdr_format)
        self.assertNotIn("VK_FORMAT_FEATURE_BLIT_SRC_BIT", hdr_format)
        self.assertIn("VK_FORMAT_R16G16B16A16_SFLOAT", hdr_format)
        self.assertIn("precision = r_hdrPrecision ? r_hdrPrecision->integer : 0;", hdr_format)
        self.assertIn("case 8:", hdr_format)
        self.assertIn("case 16:", hdr_format)
        self.assertIn("if ( r_hdr && r_hdr->integer < 0 )", hdr_format)
        self.assertIn("if ( r_hdr && r_hdr->integer > 0 )", hdr_format)
        self.assertIn("VK_FORMAT_R16G16B16A16_UNORM", hdr_format)
        self.assertIn("qboolean vk_scene_linear_enabled( void )", hdr_format)
        self.assertIn(
            "vk.color_format == VK_FORMAT_R16G16B16A16_SFLOAT",
            hdr_format,
        )
        self.assertIn(
            "vk.bloom_format = vk_scene_linear_enabled() ?",
            self.vk,
        )
        self.assertIn("vk.blitEnabled = vk_blit_enabled(", self.vk)
        self.assertIn("vk.capture_format, vk.capture_format );", self.vk)
        self.assertIn(
            "vk.present_format.format, vk.capture_format",
            self.vk,
        )
        self.assertIn(
            "vk.capture_format = vk.present_format.format;",
            self.vk,
        )
        self.assertIn(
            "vk_scene_linear_enabled() ? \"scene-linear\"",
            self.init,
        )

    def test_capture_always_owns_the_final_output_transform(self) -> None:
        attachments = source_section(
            self.vk,
            "void vk_create_attachments( void )",
            "void vk_destroy_attachments( void )",
        )
        self.assertIn("Always retain an SDR capture target", attachments)
        self.assertIn(
            "create_color_attachment( gls.captureWidth, gls.captureHeight",
            attachments,
        )
        self.assertNotIn(
            "if ( r_ext_supersample->integer ) {\n\t\t\t// capture buffer",
            attachments,
        )

        end_frame = source_section(
            self.vk,
            "void vk_end_frame( void )",
            "void vk_read_pixels( byte *buffer",
        )
        self.assertIn(
            "( backEnd.screenshotMask || backEnd.levelshotPending ) && vk.capture.image",
            end_frame,
        )
        self.assertIn("vk.capture_pipeline", end_frame)
        self.assertIn("srcImage = vk.capture.image;", self.vk)
        self.assertIn("vk.capture_format = VK_FORMAT_R8G8B8A8_UNORM;", self.vk)

    def test_final_post_pass_owns_exposure_and_tone_mapping(self) -> None:
        for shader in (self.gamma, self.bloom):
            self.assertIn("layout(constant_id = 14) const int toneMapMode", shader)
            self.assertIn(
                "layout(constant_id = 15) const float toneMapExposure",
                shader,
            )

        self.assertIn("layout(constant_id = 17) const int sceneLinearMode", self.gamma)
        self.assertIn(
            "color = max(base * obScale * max(toneMapExposure, 0.0), vec3(0.0));",
            self.gamma,
        )
        self.assertIn("color = applyToneMap(color);", self.gamma)
        self.assertIn("vec3 linearToSrgb(vec3 color)", self.gamma)
        self.assertIn("color = linearToSrgb(color);", self.gamma)
        self.assertIn(
            "color = pow(max(color, vec3(0.0)), vec3(gamma));",
            self.gamma,
        )
        self.assertIn("toneMapReinhard", self.gamma)
        self.assertIn("toneMapAces", self.gamma)
        self.assertIn("pow(max(base, vec3(0.0)), vec3(gamma)) * obScale", self.gamma)

        post_pipeline = source_section(
            self.vk,
            "void vk_create_post_process_pipeline( int program_index, uint32_t width, uint32_t height )\n{",
            "void vk_create_blur_pipeline( uint32_t index, uint32_t width, uint32_t height, qboolean horizontal_pass )\n{",
        )
        self.assertIn("int tonemap_mode;", post_pipeline)
        self.assertIn("float tonemap_exposure;", post_pipeline)
        self.assertIn("float bloom_soft_knee;", post_pipeline)
        self.assertIn("int scene_linear_mode;", post_pipeline)
        self.assertIn("spec_entries[11].constantID = 14;", post_pipeline)
        self.assertIn("spec_entries[12].constantID = 15;", post_pipeline)
        self.assertIn("spec_entries[13].constantID = 16;", post_pipeline)
        self.assertIn("spec_entries[14].constantID = 17;", post_pipeline)

    def test_bloom_uses_scene_exposure_and_soft_knee(self) -> None:
        self.assertIn("layout(constant_id = 16) const float softKnee", self.bloom)
        self.assertIn(
            "metric * (toneMapMode == 0 ? 1.0 : max(toneMapExposure, 0.0))",
            self.bloom,
        )
        self.assertIn("smoothstep(threshold - knee, threshold + knee, exposedMetric)", self.bloom)
        self.assertIn("applyBaseModulation(base) * weight", self.bloom)

    def test_rt_reference_bridge_stays_in_the_scene_linear_domain(self) -> None:
        material_space = source_section(
            self.vk,
            "static rtxRtColorSpace_t vk_rt_material_albedo_color_space( const image_t *image )\n{",
            "static rtxRtColorSpace_t vk_rt_material_data_color_space",
        )
        self.assertIn("if ( image->srgbDecode )", material_space)
        self.assertIn("return RTX_RT_COLORSPACE_LINEAR;", material_space)
        self.assertIn("image->colorSpace == IMAGE_COLORSPACE_LINEAR", material_space)
        self.assertIn("image->colorSpace == IMAGE_COLORSPACE_DATA", material_space)
        self.assertIn("return RTX_RT_COLORSPACE_SRGB;", material_space)

        image_upload = source_section(
            self.image,
            "static void upload_vk_image",
            "#else // !USE_VULKAN",
        )
        self.assertIn("if ( image->srgbDecode )", image_upload)
        self.assertIn("image->internalFormat = VK_FORMAT_R8G8B8A8_SRGB;", image_upload)

        create_image = source_section(
            self.vk,
            "void vk_create_image( image_t *image, int width, int height, int mip_levels )",
            "void vk_upload_image_data",
        )
        self.assertIn("VkFormat format = image->internalFormat;", create_image)
        self.assertGreaterEqual(create_image.count("desc.format = format;"), 2)

        rt_descriptors = source_section(
            self.vk,
            "static qboolean vk_rt_update_descriptor_set( void )\n{",
            "static qboolean vk_rt_ensure_dynamic_blas",
        )
        self.assertIn("imageInfos[4 + i].imageView = sceneImage->view;", rt_descriptors)

        material_upload = source_section(
            self.vk,
            "static qboolean vk_rt_upload_material_buffer",
            "static qboolean vk_rt_parse_entity_vec3",
        )
        self.assertIn("dst->metadata[1] = src->albedoColorSpace;", material_upload)

        decode_helper = source_section(
            self.closest_hit,
            "vec3 decode_albedo_sample",
            "float trace_shadow_visibility",
        )
        self.assertIn("sampledColorSpace == RTX_RT_COLORSPACE_SRGB", decode_helper)
        self.assertIn("return pow(sampledColor, vec3(2.2));", decode_helper)
        self.assertIn(
            "albedoSample.rgb = decode_albedo_sample(albedoSample.rgb, material.metadata.y);",
            self.closest_hit,
        )

        albedo_lod = source_section(
            self.closest_hit,
            "float estimate_albedo_lod",
            "float trace_shadow_visibility",
        )
        for footprint_input in (
            "textureSize(",
            "textureQueryLevels(",
            "gl_HitTEXT",
            "pc.cameraForwardTanHalfFovY.w",
            "pc.cameraUpHeight.w",
            "viewCosine",
            "footprintTexels",
        ):
            with self.subTest(footprint_input=footprint_input):
                self.assertIn(footprint_input, albedo_lod)
        self.assertIn("return clamp(", albedo_lod)
        self.assertIn("maxLod", albedo_lod)
        self.assertIn("float albedoLod = estimate_albedo_lod(", self.closest_hit)
        self.assertIn("albedoSample = textureLod(", self.closest_hit)
        self.assertIn("albedoLod);", self.closest_hit)

        self.assertIn(
            "#define RTX_RT_MODE_FLAG_SCENE_LINEAR_OUTPUT ( 1u << 5 )",
            self.vk,
        )
        self.assertIn("if ( vk_scene_linear_enabled() )", self.vk)
        self.assertIn("flags |= RTX_RT_MODE_FLAG_SCENE_LINEAR_OUTPUT;", self.vk)
        self.assertIn(
            "const uint RTX_RT_MODE_FLAG_SCENE_LINEAR_OUTPUT = 1u << 5;",
            self.raygen,
        )
        self.assertIn("bool sceneLinearOutput =", self.raygen)
        self.assertIn(
            "(u_temporal.modes.w & RTX_RT_MODE_FLAG_SCENE_LINEAR_OUTPUT) != 0u;",
            self.raygen,
        )
        self.assertIn("accumulatedColor :", self.raygen)
        self.assertIn("tone_map(accumulatedColor, exposure, u_temporal.modes.z)", self.raygen)
        self.assertIn("vec3 linear_to_srgb(vec3 color)", self.raygen)
        self.assertIn(
            "linear_to_srgb(tone_map(accumulatedColor, exposure, u_temporal.modes.z))",
            self.raygen,
        )
        self.assertIn("rasterReference = texture(u_sceneColor, uv).rgb;", self.raygen)

        temporal_update = source_section(
            self.vk,
            "static qboolean vk_rt_update_temporal_state( void )",
            "static void vk_rt_fill_push_constants",
        )
        exposure_heuristic = source_section(
            temporal_update,
            "sceneLumaEstimate = 0.20f +",
            "sceneLumaEstimate = MAX",
        )
        self.assertIn("RTX_RT_LEGACY_SUN_UNIT_SCALE", exposure_heuristic)
        self.assertNotIn("vk.rt.light_count", exposure_heuristic)


if __name__ == "__main__":
    unittest.main()
