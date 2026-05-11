project('FnQuake3', 'c', 'cpp',
  license: 'GPL-2.0-or-later',
  version: run_command(
    find_program('python3', 'python', required: true),
    '-c',
    'import re, pathlib; text = pathlib.Path("version/fnq3_version.h").read_text(); print(re.search(r"#define FNQ3_VERSION_STRING \\"([^\\"]+)\\"", text).group(1))',
    check: true,
  ).stdout().strip(),
  meson_version: '>= 0.60.0',
  default_options: [
    meson.version().version_compare('>=1.3.0') ? 'c_std=gnu11,c11' : 'c_std=gnu11',
    'cpp_std=c++17',
    'buildtype=debugoptimized',
    'b_vscrt=from_buildtype',
  ],
)

python = find_program('python3', 'python', required: true)
fs = import('fs')
cc = meson.get_compiler('c')
cpp = meson.get_compiler('cpp')

win32 = host_machine.system() == 'windows'
darwin = host_machine.system() == 'darwin'
cpu_family = host_machine.cpu_family()

renderer_prefix = 'fnquake3'
renderer_default = get_option('renderer-default')
renderer_dlopen = get_option('renderer-dlopen')
enabled_renderers = get_option('renderers')

if renderer_default == 'glx' and 'glx' not in enabled_renderers
  enabled_renderers += 'glx'
endif

if not renderer_dlopen
  enabled_renderers = [renderer_default]
endif

if cpu_family == 'x86'
  renderer_arch = 'x86'
  binary_suffix = ''
elif cpu_family == 'x86_64'
  renderer_arch = 'x86_64'
  binary_suffix = win32 ? '.x64' : '.x86_64'
elif cpu_family == 'aarch64'
  renderer_arch = win32 ? 'arm64' : 'aarch64'
  binary_suffix = win32 ? '.arm64' : '.aarch64'
elif cpu_family.startswith('arm')
  renderer_arch = 'arm'
  binary_suffix = '.arm'
elif cpu_family == 'ppc64le'
  renderer_arch = 'ppc64le'
  binary_suffix = '.ppc64le'
elif cpu_family == 'ppc64'
  renderer_arch = 'ppc64'
  binary_suffix = '.ppc64'
else
  renderer_arch = cpu_family
  binary_suffix = ''
endif

client_binary_name = 'fnquake3' + binary_suffix
server_binary_name = 'fnquake3.ded' + binary_suffix

common_c_args = []
common_cpp_args = []
link_args = []
dll_link_args = []

if cc.get_argument_syntax() == 'gcc'
  common_c_args += cc.get_supported_arguments([
    '-Wall',
    '-Wimplicit',
    '-Wstrict-prototypes',
    '-Wno-unused-result',
    '-fvisibility=hidden',
    '-fno-strict-aliasing',
    '-fsigned-char',
  ])
  common_cpp_args += cpp.get_supported_arguments([
    '-Wall',
    '-Wno-unused-result',
    '-fvisibility=hidden',
    '-fno-strict-aliasing',
    '-fsigned-char',
  ])
  if win32
    common_c_args += cc.get_supported_arguments(['-ffunction-sections'])
    common_cpp_args += cpp.get_supported_arguments(['-ffunction-sections'])
    if cc.get_linker_id() == 'link' or cc.get_linker_id() == 'lld-link'
      link_args += ['-Wl,/DYNAMICBASE', '-Wl,/NXCOMPAT']
    else
      link_args += ['-Wl,--dynamicbase', '-Wl,--nxcompat']
    endif
  else
    link_args += cc.get_supported_link_arguments(['-Wl,--gc-sections'])
  endif
elif cc.get_id() == 'msvc'
  common_c_args += ['/D_CRT_SECURE_NO_WARNINGS', '/D_CRT_NONSTDC_NO_WARNINGS', '/D_WINSOCK_DEPRECATED_NO_WARNINGS']
  common_cpp_args += ['/D_CRT_SECURE_NO_WARNINGS', '/D_CRT_NONSTDC_NO_WARNINGS', '/D_WINSOCK_DEPRECATED_NO_WARNINGS']
endif

if win32
  common_c_args += ['-DWIN32', '-D_WINDOWS', '-D_CRT_SECURE_NO_WARNINGS', '-D_CRT_NONSTDC_NO_WARNINGS', '-D_WINSOCK_DEPRECATED_NO_WARNINGS']
  common_cpp_args += ['-DWIN32', '-D_WINDOWS', '-D_CRT_SECURE_NO_WARNINGS', '-D_CRT_NONSTDC_NO_WARNINGS', '-D_WINSOCK_DEPRECATED_NO_WARNINGS']
elif darwin
  common_c_args += ['-DMACOS_X']
  common_cpp_args += ['-DMACOS_X']
endif

if get_option('local-headers')
  common_c_args += ['-DUSE_LOCAL_HEADERS=1']
  common_cpp_args += ['-DUSE_LOCAL_HEADERS=1']
endif

default_basedir = get_option('default-basedir')
if default_basedir != ''
  common_c_args += ['-DDEFAULT_BASEDIR="@0@"'.format(default_basedir)]
  common_cpp_args += ['-DDEFAULT_BASEDIR="@0@"'.format(default_basedir)]
endif

if not ['x86', 'x86_64', 'aarch64', 'arm', 'ppc64le', 'ppc64'].contains(cpu_family) and not cpu_family.startswith('arm')
  common_c_args += ['-DNO_VM_COMPILED']
  common_cpp_args += ['-DNO_VM_COMPILED']
endif

use_opengl_api = renderer_dlopen or renderer_default in ['opengl', 'glx', 'opengl2'] or 'opengl' in enabled_renderers or 'glx' in enabled_renderers or 'opengl2' in enabled_renderers
use_vulkan_api = 'vulkan' in enabled_renderers

if use_opengl_api
  common_c_args += ['-DUSE_OPENGL_API']
  common_cpp_args += ['-DUSE_OPENGL_API']
endif

if use_vulkan_api
  common_c_args += ['-DUSE_VULKAN_API']
  common_cpp_args += ['-DUSE_VULKAN_API']
endif

if renderer_dlopen
  common_c_args += [
    '-DUSE_RENDERER_DLOPEN',
    '-DRENDERER_PREFIX="@0@"'.format(renderer_prefix),
    '-DRENDERER_DEFAULT=@0@'.format(renderer_default),
  ]
  common_cpp_args += [
    '-DUSE_RENDERER_DLOPEN',
    '-DRENDERER_PREFIX="@0@"'.format(renderer_prefix),
    '-DRENDERER_DEFAULT=@0@'.format(renderer_default),
  ]
endif

include_dirs = include_directories(
  'code',
  'code/openal/include',
)

qcommon_src = [
  'code/qcommon/cm_load.c',
  'code/qcommon/cm_patch.c',
  'code/qcommon/cm_polylib.c',
  'code/qcommon/cm_test.c',
  'code/qcommon/cm_trace.c',
  'code/qcommon/cmd.c',
  'code/qcommon/common.c',
  'code/qcommon/cvar.c',
  'code/qcommon/files.c',
  'code/qcommon/history.c',
  'code/qcommon/huffman_static.c',
  'code/qcommon/huffman.c',
  'code/qcommon/keys.c',
  'code/qcommon/md4.c',
  'code/qcommon/md5.c',
  'code/qcommon/msg.c',
  'code/qcommon/net_chan.c',
  'code/qcommon/net_ip.c',
  'code/qcommon/puff.c',
  'code/qcommon/q_math.c',
  'code/qcommon/q_shared.c',
  'code/qcommon/unzip.c',
  'code/qcommon/vm_interpreted.c',
  'code/qcommon/vm.c',
]

if cpu_family in ['x86', 'x86_64']
  qcommon_src += 'code/qcommon/vm_x86.c'
elif cpu_family == 'aarch64'
  qcommon_src += 'code/qcommon/vm_aarch64.c'
elif cpu_family.startswith('arm')
  qcommon_src += 'code/qcommon/vm_armv7l.c'
elif cpu_family in ['ppc64le', 'ppc64']
  qcommon_src += 'code/qcommon/vm_powerpc.c'
endif

platform_asm_src = []
if win32 and cc.get_id() == 'msvc' and cpu_family == 'x86_64'
  if add_languages('masm', required: false)
    platform_asm_src += 'code/asm/common_x64.asm'
  else
    warning('MSVC x64 build did not find MASM; Q_setjmp_c/Q_longjmp_c will be unresolved')
  endif
endif

server_src = [
  'code/server/sv_bot.c',
  'code/server/sv_ccmds.c',
  'code/server/sv_client.c',
  'code/server/sv_filter.c',
  'code/server/sv_game.c',
  'code/server/sv_init.c',
  'code/server/sv_main.c',
  'code/server/sv_net_chan.c',
  'code/server/sv_snapshot.c',
  'code/server/sv_world.c',
]

client_src = [
  'code/client/cl_avi.c',
  'code/client/cl_cgame.c',
  'code/client/cl_cin.c',
  'code/client/cl_console.c',
  'code/client/cl_hud.c',
  'code/client/cl_input.c',
  'code/client/cl_jpeg.c',
  'code/client/cl_keys.c',
  'code/client/cl_main.c',
  'code/client/cl_net_chan.c',
  'code/client/cl_parse.c',
  'code/client/cl_scrn.c',
  'code/client/cl_ui.c',
  'code/client/snd_adpcm.c',
  'code/client/snd_codec_wav.c',
  'code/client/snd_codec.c',
  'code/client/snd_dma.c',
  'code/client/snd_main.c',
  'code/client/snd_mem.c',
  'code/client/snd_mix.c',
  'code/client/snd_wavelet.c',
  'code/audio/AudioSystem.cpp',
]

botlib_src = [
  'code/botlib/be_aas_bspq3.c',
  'code/botlib/be_aas_cluster.c',
  'code/botlib/be_aas_debug.c',
  'code/botlib/be_aas_entity.c',
  'code/botlib/be_aas_file.c',
  'code/botlib/be_aas_main.c',
  'code/botlib/be_aas_move.c',
  'code/botlib/be_aas_optimize.c',
  'code/botlib/be_aas_reach.c',
  'code/botlib/be_aas_route.c',
  'code/botlib/be_aas_routealt.c',
  'code/botlib/be_aas_sample.c',
  'code/botlib/be_ai_char.c',
  'code/botlib/be_ai_chat.c',
  'code/botlib/be_ai_gen.c',
  'code/botlib/be_ai_goal.c',
  'code/botlib/be_ai_move.c',
  'code/botlib/be_ai_weap.c',
  'code/botlib/be_ai_weight.c',
  'code/botlib/be_ea.c',
  'code/botlib/be_interface.c',
  'code/botlib/l_crc.c',
  'code/botlib/l_libvar.c',
  'code/botlib/l_log.c',
  'code/botlib/l_memory.c',
  'code/botlib/l_precomp.c',
  'code/botlib/l_script.c',
  'code/botlib/l_struct.c',
]

renderer_common_src = [
  'code/renderercommon/tr_font.c',
  'code/renderercommon/tr_image_bmp.c',
  'code/renderercommon/tr_image_jpg.c',
  'code/renderercommon/tr_image_pcx.c',
  'code/renderercommon/tr_image_png.c',
  'code/renderercommon/tr_image_tga.c',
  'code/renderercommon/tr_image_wal.c',
  'code/renderercommon/tr_noise.c',
]

renderer_gl_src = [
  'code/renderer/tr_animation.c',
  'code/renderer/tr_arb.c',
  'code/renderer/tr_backend.c',
  'code/renderer/tr_bsp.c',
  'code/renderer/tr_cmds.c',
  'code/renderer/tr_curve.c',
  'code/renderer/tr_flares.c',
  'code/renderer/tr_image.c',
  'code/renderer/tr_init.c',
  'code/renderer/tr_light.c',
  'code/renderer/tr_main.c',
  'code/renderer/tr_marks.c',
  'code/renderer/tr_mesh.c',
  'code/renderer/tr_model_iqm.c',
  'code/renderer/tr_model.c',
  'code/renderer/tr_scene.c',
  'code/renderer/tr_shade_calc.c',
  'code/renderer/tr_shade.c',
  'code/renderer/tr_shader.c',
  'code/renderer/tr_shadows.c',
  'code/renderer/tr_sky.c',
  'code/renderer/tr_surface.c',
  'code/renderer/tr_vbo.c',
  'code/renderer/tr_world.c',
]

renderer_glx_src = [
  'code/rendererglx/glx_caps.cpp',
  'code/rendererglx/glx_debug.cpp',
  'code/rendererglx/glx_draw.cpp',
  'code/rendererglx/glx_executor.cpp',
  'code/rendererglx/glx_material.cpp',
  'code/rendererglx/glx_module.cpp',
  'code/rendererglx/glx_post_shader.cpp',
  'code/rendererglx/glx_postprocess.cpp',
  'code/rendererglx/glx_profiler.cpp',
  'code/rendererglx/glx_static_world.cpp',
  'code/rendererglx/glx_stream.cpp',
]

renderer_vk_src = [
  'code/renderervk/tr_animation.c',
  'code/renderervk/tr_backend.c',
  'code/renderervk/tr_bsp.c',
  'code/renderervk/tr_cmds.c',
  'code/renderervk/tr_curve.c',
  'code/renderervk/tr_image.c',
  'code/renderervk/tr_init.c',
  'code/renderervk/tr_light.c',
  'code/renderervk/tr_main.c',
  'code/renderervk/tr_marks.c',
  'code/renderervk/tr_mesh.c',
  'code/renderervk/tr_model_iqm.c',
  'code/renderervk/tr_model.c',
  'code/renderervk/tr_scene.c',
  'code/renderervk/tr_shade_calc.c',
  'code/renderervk/tr_shade.c',
  'code/renderervk/tr_shader.c',
  'code/renderervk/tr_shadows.c',
  'code/renderervk/tr_sky.c',
  'code/renderervk/tr_surface.c',
  'code/renderervk/tr_world.c',
  'code/renderervk/vk_flares.c',
  'code/renderervk/vk_vbo.c',
  'code/renderervk/vk.c',
]

renderer2_src = [
  'code/renderer2/tr_animation.c',
  'code/renderer2/tr_backend.c',
  'code/renderer2/tr_bsp.c',
  'code/renderer2/tr_cmds.c',
  'code/renderer2/tr_curve.c',
  'code/renderer2/tr_dsa.c',
  'code/renderer2/tr_extensions.c',
  'code/renderer2/tr_extramath.c',
  'code/renderer2/tr_fbo.c',
  'code/renderer2/tr_flares.c',
  'code/renderer2/tr_glsl.c',
  'code/renderer2/tr_image_dds.c',
  'code/renderer2/tr_image.c',
  'code/renderer2/tr_init.c',
  'code/renderer2/tr_light.c',
  'code/renderer2/tr_main.c',
  'code/renderer2/tr_marks.c',
  'code/renderer2/tr_mesh.c',
  'code/renderer2/tr_model_iqm.c',
  'code/renderer2/tr_model.c',
  'code/renderer2/tr_postprocess.c',
  'code/renderer2/tr_scene.c',
  'code/renderer2/tr_shade_calc.c',
  'code/renderer2/tr_shade.c',
  'code/renderer2/tr_shader.c',
  'code/renderer2/tr_shadows.c',
  'code/renderer2/tr_sky.c',
  'code/renderer2/tr_surface.c',
  'code/renderer2/tr_vbo.c',
  'code/renderer2/tr_world.c',
]

renderer2_glsl_files = [
  'code/renderer2/glsl/bokeh_fp.glsl',
  'code/renderer2/glsl/bokeh_vp.glsl',
  'code/renderer2/glsl/calclevels4x_fp.glsl',
  'code/renderer2/glsl/calclevels4x_vp.glsl',
  'code/renderer2/glsl/depthblur_fp.glsl',
  'code/renderer2/glsl/depthblur_vp.glsl',
  'code/renderer2/glsl/dlight_fp.glsl',
  'code/renderer2/glsl/dlight_vp.glsl',
  'code/renderer2/glsl/down4x_fp.glsl',
  'code/renderer2/glsl/down4x_vp.glsl',
  'code/renderer2/glsl/fogpass_fp.glsl',
  'code/renderer2/glsl/fogpass_vp.glsl',
  'code/renderer2/glsl/gamma_fp.glsl',
  'code/renderer2/glsl/gamma_vp.glsl',
  'code/renderer2/glsl/generic_fp.glsl',
  'code/renderer2/glsl/generic_vp.glsl',
  'code/renderer2/glsl/lightall_fp.glsl',
  'code/renderer2/glsl/lightall_vp.glsl',
  'code/renderer2/glsl/pshadow_fp.glsl',
  'code/renderer2/glsl/pshadow_vp.glsl',
  'code/renderer2/glsl/shadowfill_fp.glsl',
  'code/renderer2/glsl/shadowfill_vp.glsl',
  'code/renderer2/glsl/shadowmask_fp.glsl',
  'code/renderer2/glsl/shadowmask_vp.glsl',
  'code/renderer2/glsl/ssao_fp.glsl',
  'code/renderer2/glsl/ssao_vp.glsl',
  'code/renderer2/glsl/texturecolor_fp.glsl',
  'code/renderer2/glsl/texturecolor_vp.glsl',
  'code/renderer2/glsl/tonemap_fp.glsl',
  'code/renderer2/glsl/tonemap_vp.glsl',
]

renderer2_glsl_src = []
foreach shader : renderer2_glsl_files
  shader_name = shader.split('/')[-1].replace('.glsl', '')
  renderer2_glsl_src += custom_target(
    'renderer2_' + shader_name,
    input: shader,
    output: shader_name + '.c',
    command: [python, files('scripts/stringify_shader.py'), '@INPUT@', '@OUTPUT@'],
  )
endforeach

jpeg_src = [
  'code/libjpeg/jaricom.c',
  'code/libjpeg/jcapimin.c',
  'code/libjpeg/jcapistd.c',
  'code/libjpeg/jcarith.c',
  'code/libjpeg/jccoefct.c',
  'code/libjpeg/jccolor.c',
  'code/libjpeg/jcdctmgr.c',
  'code/libjpeg/jchuff.c',
  'code/libjpeg/jcinit.c',
  'code/libjpeg/jcmainct.c',
  'code/libjpeg/jcmarker.c',
  'code/libjpeg/jcmaster.c',
  'code/libjpeg/jcomapi.c',
  'code/libjpeg/jcparam.c',
  'code/libjpeg/jcprepct.c',
  'code/libjpeg/jcsample.c',
  'code/libjpeg/jctrans.c',
  'code/libjpeg/jdapimin.c',
  'code/libjpeg/jdapistd.c',
  'code/libjpeg/jdarith.c',
  'code/libjpeg/jdatadst.c',
  'code/libjpeg/jdatasrc.c',
  'code/libjpeg/jdcoefct.c',
  'code/libjpeg/jdcolor.c',
  'code/libjpeg/jddctmgr.c',
  'code/libjpeg/jdhuff.c',
  'code/libjpeg/jdinput.c',
  'code/libjpeg/jdmainct.c',
  'code/libjpeg/jdmarker.c',
  'code/libjpeg/jdmaster.c',
  'code/libjpeg/jdmerge.c',
  'code/libjpeg/jdpostct.c',
  'code/libjpeg/jdsample.c',
  'code/libjpeg/jdtrans.c',
  'code/libjpeg/jerror.c',
  'code/libjpeg/jfdctflt.c',
  'code/libjpeg/jfdctfst.c',
  'code/libjpeg/jfdctint.c',
  'code/libjpeg/jidctflt.c',
  'code/libjpeg/jidctfst.c',
  'code/libjpeg/jidctint.c',
  'code/libjpeg/jmemmgr.c',
  'code/libjpeg/jmemnobs.c',
  'code/libjpeg/jquant1.c',
  'code/libjpeg/jquant2.c',
  'code/libjpeg/jutils.c',
]

ogg_src = [
  'code/libogg/src/bitwise.c',
  'code/libogg/src/framing.c',
]

vorbis_src = [
  'code/libvorbis/lib/analysis.c',
  'code/libvorbis/lib/bitrate.c',
  'code/libvorbis/lib/block.c',
  'code/libvorbis/lib/codebook.c',
  'code/libvorbis/lib/envelope.c',
  'code/libvorbis/lib/floor0.c',
  'code/libvorbis/lib/floor1.c',
  'code/libvorbis/lib/info.c',
  'code/libvorbis/lib/lookup.c',
  'code/libvorbis/lib/lpc.c',
  'code/libvorbis/lib/lsp.c',
  'code/libvorbis/lib/mapping0.c',
  'code/libvorbis/lib/mdct.c',
  'code/libvorbis/lib/psy.c',
  'code/libvorbis/lib/registry.c',
  'code/libvorbis/lib/res0.c',
  'code/libvorbis/lib/sharedbook.c',
  'code/libvorbis/lib/smallft.c',
  'code/libvorbis/lib/synthesis.c',
  'code/libvorbis/lib/vorbisfile.c',
  'code/libvorbis/lib/window.c',
]

client_deps = []
server_deps = []
renderer_deps = []
copy_runtime_files = []

libm = cc.find_library('m', required: false)
if libm.found()
  client_deps += libm
  server_deps += libm
  renderer_deps += libm
endif

if not win32
  libdl = cc.find_library('dl', required: false)
  if libdl.found()
    client_deps += libdl
    server_deps += libdl
    renderer_deps += libdl
  endif
endif

if win32
  foreach lib : ['winmm', 'comctl32', 'ws2_32', 'gdi32', 'ole32', 'psapi', 'shell32', 'user32', 'advapi32']
    found_lib = cc.find_library(lib, required: true)
    client_deps += found_lib
    server_deps += found_lib
  endforeach
endif

sdl_opt = get_option('sdl')
sdl_dep = dependency('sdl3', version: '>=3.2.0', required: false)
sdl_source = 'system'
if not sdl_dep.found() and win32
  sdl_libdir = (cpu_family == 'x86') ? 'code/libsdl/windows/mingw/lib32' : 'code/libsdl/windows/mingw/lib64'
  sdl_lib = cc.find_library('SDL3', dirs: meson.current_source_dir() / sdl_libdir, required: false)
  if sdl_lib.found()
    sdl_dep = declare_dependency(
      dependencies: sdl_lib,
      include_directories: include_directories('code/libsdl/include'),
    )
    sdl_source = 'bundled'
    copy_runtime_files += sdl_libdir / 'SDL3.dll'
  endif
endif

if sdl_opt.enabled() and not sdl_dep.found()
  error('SDL3 was enabled but no SDL3 dependency was found')
endif
use_sdl = not sdl_opt.disabled() and sdl_dep.found()

if use_sdl
  client_deps += sdl_dep
  common_c_args += ['-DSDL_FUNCTION_POINTER_IS_VOID_POINTER=1', '-DUSE_SDL_SYSCON=1']
  common_cpp_args += ['-DSDL_FUNCTION_POINTER_IS_VOID_POINTER=1', '-DUSE_SDL_SYSCON=1']
endif

curl_opt = get_option('curl')
use_curl = false
use_curl_dlopen = get_option('curl-dlopen')
curl_dep = dependency('', required: false)
curl_c_args = []

if not curl_opt.disabled()
  if win32 and fs.exists('code/libcurl/windows/include/curl/curl.h')
    use_curl = true
    curl_c_args += ['-I' + meson.current_source_dir() / 'code/libcurl/windows/include']
    if not use_curl_dlopen
      curl_libdir = (cpu_family == 'x86') ? 'code/libcurl/windows/mingw/lib32' : 'code/libcurl/windows/mingw/lib64'
      curl_dep = cc.find_library('curl', dirs: meson.current_source_dir() / curl_libdir, required: curl_opt.enabled())
      if curl_dep.found()
        client_deps += curl_dep
        client_deps += cc.find_library('crypt32', required: true)
        zlib_dep = dependency('zlib', required: false)
        if zlib_dep.found()
          client_deps += zlib_dep
        else
          client_deps += cc.find_library('z', required: false)
        endif
        common_c_args += ['-DCURL_STATICLIB']
        common_cpp_args += ['-DCURL_STATICLIB']
      else
        use_curl = false
      endif
    endif
  else
    has_curl_header = cc.has_header('curl/curl.h', required: curl_opt.enabled())
    if has_curl_header
      if use_curl_dlopen
        use_curl = true
      else
        curl_dep = dependency('libcurl', required: curl_opt.enabled())
        use_curl = curl_dep.found()
        if use_curl
          client_deps += curl_dep
        endif
      endif
    endif
  endif
endif

if use_curl
  client_src += 'code/client/cl_curl.c'
  common_c_args += ['-DUSE_CURL'] + curl_c_args
  common_cpp_args += ['-DUSE_CURL'] + curl_c_args
  if use_curl_dlopen
    common_c_args += ['-DUSE_CURL_DLOPEN']
    common_cpp_args += ['-DUSE_CURL_DLOPEN']
  endif
endif

if get_option('system-jpeg')
  jpeg_dep = dependency('libjpeg', required: false)
  if not jpeg_dep.found()
    jpeg_dep = dependency('jpeg', required: true)
  endif
  client_deps += jpeg_dep
  common_c_args += ['-DUSE_SYSTEM_JPEG']
  common_cpp_args += ['-DUSE_SYSTEM_JPEG']
else
  client_src += jpeg_src
endif

if get_option('ogg-vorbis')
  client_src += ['code/client/snd_codec_ogg.c'] + ogg_src + vorbis_src
  common_c_args += [
    '-DUSE_OGG_VORBIS',
    '-I' + meson.current_source_dir() / 'code/libogg/include',
    '-I' + meson.current_source_dir() / 'code/libvorbis/include',
    '-I' + meson.current_source_dir() / 'code/libvorbis/lib',
  ]
  common_cpp_args += [
    '-DUSE_OGG_VORBIS',
    '-I' + meson.current_source_dir() / 'code/libogg/include',
    '-I' + meson.current_source_dir() / 'code/libvorbis/include',
    '-I' + meson.current_source_dir() / 'code/libvorbis/lib',
  ]
endif

if win32
  win_resource = []
  rc_prog = find_program('rc', 'llvm-rc', 'windres', required: false)
  if rc_prog.found()
    if rc_prog.full_path().to_lower().contains('windres')
      win_resource = custom_target('win_resource',
        input: 'code/win32/win_resource.rc',
        output: 'win_resource.o',
        command: [rc_prog, '-i', '@INPUT@', '-o', '@OUTPUT@'],
      )
    else
      win_resource = custom_target('win_resource',
        input: 'code/win32/win_resource.rc',
        output: 'win_resource.res',
        command: [rc_prog, '/fo', '@OUTPUT@', '@INPUT@'],
      )
    endif
  else
    warning('No Windows resource compiler found; Meson targets will build without win_resource.rc')
  endif
  q3_platform_src = [
    'code/win32/win_main.c',
    'code/win32/win_shared.c',
    'code/win32/win_syscon.c',
  ] + win_resource
  if use_sdl
    q3_ui_src = [
      'code/sdl/sdl_gamma.c',
      'code/sdl/sdl_glimp.c',
      'code/sdl/sdl_input.c',
      'code/sdl/sdl_snd.c',
    ]
  else
    q3_ui_src = [
      'code/win32/win_gamma.c',
      'code/win32/win_glimp.c',
      'code/win32/win_input.c',
      'code/win32/win_minimize.c',
      'code/win32/win_snd.c',
      'code/win32/win_wndproc.c',
    ]
    if use_opengl_api
      q3_ui_src += 'code/win32/win_qgl.c'
    endif
    if use_vulkan_api
      q3_ui_src += 'code/win32/win_qvk.c'
    endif
  endif

  openal_dll = (cpu_family == 'x86') ? 'code/openal/windows/x86/OpenAL32.dll' : 'code/openal/windows/x64/OpenAL32.dll'
  if fs.exists(openal_dll)
    copy_runtime_files += openal_dll
  endif
else
  q3_platform_src = [
    'code/unix/unix_main.c',
    'code/unix/unix_shared.c',
    'code/unix/unix_syscon.c',
    'code/unix/linux_signals.c',
  ]
  if use_sdl
    q3_ui_src = [
      'code/sdl/sdl_gamma.c',
      'code/sdl/sdl_glimp.c',
      'code/sdl/sdl_input.c',
      'code/sdl/sdl_snd.c',
    ]
  else
    x11_dep = dependency('x11', required: true)
    client_deps += x11_dep
    q3_ui_src = [
      'code/unix/linux_glimp.c',
      'code/unix/linux_snd.c',
      'code/unix/x11_dga.c',
      'code/unix/x11_randr.c',
      'code/unix/x11_vidmode.c',
    ]
    if use_opengl_api
      q3_ui_src += 'code/unix/linux_qgl.c'
    endif
    if use_vulkan_api
      q3_ui_src += 'code/unix/linux_qvk.c'
    endif
  endif
endif

foreach runtime_file : copy_runtime_files
  configure_file(
    input: runtime_file,
    output: runtime_file.split('/')[-1],
    copy: true,
    install: true,
    install_dir: '.',
  )
endforeach

botlib = static_library('botlib', botlib_src,
  include_directories: include_dirs,
  c_args: common_c_args + ['-DBOTLIB'],
  install: false,
)
botlib_objects = [botlib.extract_all_objects(recursive: false)]

renderer_base_src = renderer_common_src + ['code/qcommon/q_shared.c', 'code/qcommon/puff.c', 'code/qcommon/q_math.c'] + platform_asm_src
renderer_targets = []

if renderer_dlopen
  renderer_c_args = common_c_args + ['-DUSE_RENDERER_DLOPEN']
  renderer_cpp_args = common_cpp_args + ['-DUSE_RENDERER_DLOPEN']

  if 'opengl' in enabled_renderers
    renderer_targets += shared_library(renderer_prefix + '_opengl_' + renderer_arch,
      renderer_gl_src + renderer_base_src,
      include_directories: include_dirs,
      dependencies: renderer_deps,
      c_args: renderer_c_args,
      cpp_args: renderer_cpp_args,
      link_args: dll_link_args,
      name_prefix: '',
      gnu_symbol_visibility: 'hidden',
      install: true,
      install_dir: '.',
    )
  endif

  if 'glx' in enabled_renderers
    renderer_targets += shared_library(renderer_prefix + '_glx_' + renderer_arch,
      renderer_gl_src + renderer_glx_src + renderer_base_src,
      include_directories: include_dirs,
      dependencies: renderer_deps,
      c_args: renderer_c_args + ['-DRENDERER_GLX'],
      cpp_args: renderer_cpp_args + ['-DRENDERER_GLX'],
      link_args: dll_link_args,
      name_prefix: '',
      gnu_symbol_visibility: 'hidden',
      install: true,
      install_dir: '.',
    )
  endif

  if 'vulkan' in enabled_renderers
    renderer_targets += shared_library(renderer_prefix + '_vulkan_' + renderer_arch,
      renderer_vk_src + renderer_base_src,
      include_directories: include_dirs,
      dependencies: renderer_deps,
      c_args: renderer_c_args,
      cpp_args: renderer_cpp_args,
      link_args: dll_link_args,
      name_prefix: '',
      gnu_symbol_visibility: 'hidden',
      install: true,
      install_dir: '.',
    )
  endif

  if 'opengl2' in enabled_renderers
    renderer_targets += shared_library(renderer_prefix + '_opengl2_' + renderer_arch,
      renderer2_src + renderer2_glsl_src + renderer_base_src,
      include_directories: include_dirs,
      dependencies: renderer_deps,
      c_args: renderer_c_args,
      cpp_args: renderer_cpp_args,
      link_args: dll_link_args,
      name_prefix: '',
      gnu_symbol_visibility: 'hidden',
      install: true,
      install_dir: '.',
    )
  endif
endif

static_renderer_objects = []
if not renderer_dlopen
  if renderer_default == 'glx'
    static_renderer = static_library('renderer_static_glx',
      renderer_gl_src + renderer_glx_src + renderer_common_src,
      include_directories: include_dirs,
      dependencies: renderer_deps,
      c_args: common_c_args + ['-DRENDERER_GLX'],
      cpp_args: common_cpp_args + ['-DRENDERER_GLX'],
      install: false,
    )
    static_renderer_objects = [static_renderer.extract_all_objects(recursive: false)]
  elif renderer_default == 'vulkan'
    static_renderer = static_library('renderer_static_vulkan',
      renderer_vk_src + renderer_common_src,
      include_directories: include_dirs,
      dependencies: renderer_deps,
      c_args: common_c_args,
      cpp_args: common_cpp_args,
      install: false,
    )
    static_renderer_objects = [static_renderer.extract_all_objects(recursive: false)]
  elif renderer_default == 'opengl2'
    static_renderer = static_library('renderer_static_opengl2',
      renderer2_src + renderer2_glsl_src + renderer_common_src,
      include_directories: include_dirs,
      dependencies: renderer_deps,
      c_args: common_c_args,
      cpp_args: common_cpp_args,
      install: false,
    )
    static_renderer_objects = [static_renderer.extract_all_objects(recursive: false)]
  else
    static_renderer = static_library('renderer_static_opengl',
      renderer_gl_src + renderer_common_src,
      include_directories: include_dirs,
      dependencies: renderer_deps,
      c_args: common_c_args,
      cpp_args: common_cpp_args,
      install: false,
    )
    static_renderer_objects = [static_renderer.extract_all_objects(recursive: false)]
  endif
endif

if get_option('build-client')
  executable(client_binary_name,
    q3_platform_src + q3_ui_src + qcommon_src + server_src + client_src + platform_asm_src,
    include_directories: include_dirs,
    dependencies: client_deps,
    objects: botlib_objects + static_renderer_objects,
    c_args: common_c_args,
    cpp_args: common_cpp_args,
    link_args: link_args,
    win_subsystem: win32 ? 'windows' : 'console',
    install: true,
    install_dir: '.',
  )
endif

if get_option('build-server')
  executable(server_binary_name,
    q3_platform_src + qcommon_src + server_src + platform_asm_src,
    include_directories: include_dirs,
    dependencies: server_deps,
    objects: botlib_objects,
    c_args: common_c_args + ['-DDEDICATED'],
    cpp_args: common_cpp_args + ['-DDEDICATED'],
    link_args: link_args,
    win_subsystem: win32 ? 'windows' : 'console',
    install: true,
    install_dir: '.',
  )
endif

audiozonesc = executable('fnq3-audiozonesc',
  'code/tools/audiozones/audiozonesc.cpp',
  include_directories: include_directories('code/audio'),
  cpp_args: common_cpp_args,
  install: true,
  install_dir: '.',
)

if get_option('audio-tests')
  audio_zone_tests = executable('fnq3_audio_zone_tests',
    'tests/audio/audiozone_runtime_tests.cpp',
    include_directories: include_directories('code/audio'),
    cpp_args: common_cpp_args,
  )
  test('fnq3_audio_zones', audio_zone_tests)

  audiozone_fixture = custom_target('audiozone_authoring_test',
    output: 'audiozone_authoring_test.azb',
    input: 'tests/audio/authoring_metadata.audiozones',
    command: [audiozonesc, '-o', '@OUTPUT@', '@INPUT@'],
  )
  test('fnq3_audio_zone_authoring_audit', audiozonesc,
    args: ['--audit', '--strict', '--samples', '512', audiozone_fixture],
    depends: audiozone_fixture,
  )

  audio_recovery_tests = executable('fnq3_audio_recovery_tests',
    'tests/audio/recovery_policy_tests.cpp',
    include_directories: include_directories('code/audio'),
    cpp_args: common_cpp_args,
  )
  test('fnq3_audio_recovery', audio_recovery_tests)

  audio_occlusion_tests = executable('fnq3_audio_occlusion_tests',
    'tests/audio/occlusion_policy_tests.cpp',
    include_directories: include_directories('code/audio'),
    cpp_args: common_cpp_args,
  )
  test('fnq3_audio_occlusion', audio_occlusion_tests)

  audio_loopback_tests = executable('fnq3_audio_loopback_tests',
    'tests/audio/openal_loopback_tests.cpp',
    include_directories: include_directories('code/openal/include'),
    dependencies: client_deps,
    cpp_args: common_cpp_args,
  )
  test('fnq3_audio_loopback', audio_loopback_tests, should_fail: false)

  test('fnq3_audio_zone_sweep_script', python,
    args: files('tests/audio/audio_zone_sweep_tests.py'),
  )
  test('fnq3_audio_zone_material_map', python,
    args: [files('tests/audio/audio_zone_material_map_tests.py'), audiozonesc],
  )
endif

if get_option('glx-tests')
  glx_logic_tests = executable('fnq3_glx_logic_tests',
    'tests/glx/glx_logic_tests.cpp',
    include_directories: include_directories('code/rendererglx', 'code/qcommon', 'code/renderercommon'),
    cpp_args: common_cpp_args,
  )
  test('fnq3_glx_logic', glx_logic_tests)
  test('fnq3_glx_header_boundary', python,
    args: files('tests/glx/glx_header_boundary_tests.py'),
  )
endif

curl_summary = 'disabled'
if use_curl
  curl_summary = use_curl_dlopen ? 'dlopen' : 'linked'
endif

summary({
  'client executable': get_option('build-client') ? client_binary_name : 'disabled',
  'dedicated server': get_option('build-server') ? server_binary_name : 'disabled',
  'renderer-dlopen': renderer_dlopen,
  'renderer modules': renderer_dlopen ? ', '.join(enabled_renderers) : 'disabled',
  'static renderer': renderer_dlopen ? 'disabled' : renderer_default,
  'renderer default': renderer_default,
  'renderer arch': renderer_arch,
  'SDL3': use_sdl ? sdl_source : 'disabled',
  'cURL': curl_summary,
  'JPEG': get_option('system-jpeg') ? 'system' : 'bundled',
  'Ogg Vorbis': get_option('ogg-vorbis') ? 'bundled' : 'disabled',
}, section: 'FnQuake3 build')
