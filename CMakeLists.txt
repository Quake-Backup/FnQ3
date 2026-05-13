CMAKE_MINIMUM_REQUIRED(VERSION 3.12)

file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/version/fnq3_version.h" FNQ3_VERSION_STRING_LINE REGEX "^#define FNQ3_VERSION_STRING \"[^\"]+\"$")
string(REGEX REPLACE "^#define FNQ3_VERSION_STRING \"([^\"]+)\"$" "\\1" FNQ3_VERSION_STRING "${FNQ3_VERSION_STRING_LINE}")

PROJECT(FnQuake3 VERSION ${FNQ3_VERSION_STRING} LANGUAGES C CXX)

SET(CMAKE_CXX_STANDARD 17)
SET(CMAKE_CXX_STANDARD_REQUIRED ON)
SET(CMAKE_CXX_EXTENSIONS OFF)

SET(CNAME "fnquake3")
SET(DNAME "fnquake3.ded")

SET(RENDERER_PREFIX ${CNAME})
SET(RENDERER_DEFAULT opengl CACHE STRING "Default renderer: opengl, glx, vulkan, or opengl2")
set_property(CACHE RENDERER_DEFAULT PROPERTY STRINGS opengl glx vulkan opengl2)

OPTION(USE_SDL "" ON)
OPTION(USE_CURL "" ON)
OPTION(USE_VULKAN "" ON)
OPTION(USE_GLX "Build the GLx OpenGL-lineage renderer module" ON)
OPTION(USE_SYSTEM_JPEG "" OFF)
OPTION(USE_RENDERER_DLOPEN "" ON)
OPTION(FNQ3_AUDIO_LOOPBACK_TESTS "Build deterministic audio runtime and OpenAL loopback tests" ON)
OPTION(FNQ3_GLX_LOGIC_TESTS "Build deterministic GLx renderer logic tests" ON)

IF(RENDERER_DEFAULT STREQUAL "glx")
	SET(USE_GLX ON CACHE BOOL "Build the GLx OpenGL-lineage renderer module" FORCE)
ENDIF()

IF(WIN32 AND CMAKE_CXX_COMPILER_ID MATCHES "Clang")
	# win_resource.rc already embeds q3.manifest; CMake's Windows-Clang rule
	# can add a generated manifest that lld-link rejects as a duplicate resource.
	FOREACH(lang C CXX)
		STRING(REPLACE " -Xlinker /MANIFEST:EMBED" "" CMAKE_${lang}_LINK_EXECUTABLE "${CMAKE_${lang}_LINK_EXECUTABLE}")
		STRING(REPLACE " /MANIFEST:NO" "" CMAKE_${lang}_LINK_EXECUTABLE "${CMAKE_${lang}_LINK_EXECUTABLE}")
	ENDFOREACH()
	IF(CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
		SET(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} /MANIFEST:NO")
	ENDIF()
ENDIF()

IF(NOT USE_RENDERER_DLOPEN AND RENDERER_DEFAULT STREQUAL "glx")
	SET(USE_VULKAN OFF)
ENDIF()

AUX_SOURCE_DIRECTORY(code/qcommon QCOMMON_SRCS)
# exclude platform-dependent QVM bytecode compilers
list(FILTER QCOMMON_SRCS EXCLUDE REGEX ".*vm_(aarch64|armv7l|powerpc|x86)\\.c$")
# add platform-dependent QVM bytecode compilers
IF(CMAKE_SYSTEM_PROCESSOR MATCHES AMD64|x86|i*86)
	IF(CMAKE_SYSTEM_PROCESSOR MATCHES AMD64)
		IF(WIN32)
			SET(BINEXT .x64)
		ELSE()
			SET(BINEXT .x86_64)
		ENDIF()
		SET(RENDEXT _x86_64)
	ELSE()
		#SET(BINEXT .x86)
		SET(RENDEXT _x86)
	ENDIF()
	list(APPEND QCOMMON_SRCS code/qcommon/vm_x86.c)
ELSEIF(CMAKE_SYSTEM_PROCESSOR MATCHES aarch64|arm64)
	SET(BINEXT .aarch64)
	SET(RENDEXT _aarch64)
	list(APPEND QCOMMON_SRCS code/qcommon/vm_aarch64.c)
ELSEIF(CMAKE_SYSTEM_PROCESSOR MATCHES arm*)
	SET(BINEXT .arm)
	SET(RENDEXT _arm)
	list(APPEND QCOMMON_SRCS code/qcommon/vm_armv7l.c)
ELSEIF(CMAKE_SYSTEM_PROCESSOR MATCHES "ppc64le|ppc64")
	IF(CMAKE_SYSTEM_PROCESSOR MATCHES "ppc64le")
		SET(BINEXT .ppc64le)
		SET(RENDEXT _ppc64le)
		list(APPEND QCOMMON_SRCS code/qcommon/vm_powerpc.c)
	ELSE()
		SET(BINEXT .ppc64)
		SET(RENDEXT _ppc64)
		list(APPEND QCOMMON_SRCS code/qcommon/vm_powerpc.c)
	ENDIF()
ELSE()
	SET(NO_VM_COMPILED ON)
ENDIF()

SET(PLATFORM_ASM_SRCS)
IF(MSVC AND NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND CMAKE_SIZEOF_VOID_P EQUAL 8)
	enable_language(ASM_MASM)
	list(APPEND PLATFORM_ASM_SRCS code/asm/common_x64.asm)
ENDIF()

# botlib
AUX_SOURCE_DIRECTORY(code/botlib BOTLIB_SRCS)
ADD_LIBRARY(botlib OBJECT ${BOTLIB_SRCS})
TARGET_COMPILE_DEFINITIONS(botlib PRIVATE BOTLIB)

SET(SERVER_SRCS
	code/server/sv_bot.cpp
	code/server/sv_ccmds.cpp
	code/server/sv_client.cpp
	code/server/sv_filter.cpp
	code/server/sv_game.cpp
	code/server/sv_init.cpp
	code/server/sv_main.cpp
	code/server/sv_net_chan.cpp
	code/server/sv_snapshot.cpp
	code/server/sv_world.cpp
)

# universal binary
ADD_LIBRARY(qcommon OBJECT ${QCOMMON_SRCS} ${SERVER_SRCS} ${PLATFORM_ASM_SRCS})

# dedicated server
ADD_LIBRARY(qcommon_ded OBJECT ${QCOMMON_SRCS} ${SERVER_SRCS} ${PLATFORM_ASM_SRCS})
TARGET_COMPILE_DEFINITIONS(qcommon_ded PUBLIC DEDICATED)

IF(NO_VM_COMPILED)
	TARGET_COMPILE_DEFINITIONS(qcommon PRIVATE NO_VM_COMPILED)
	TARGET_COMPILE_DEFINITIONS(qcommon_ded PRIVATE NO_VM_COMPILED)
ENDIF()

# client + cURL
AUX_SOURCE_DIRECTORY(code/client CLIENT_SRCS)
list(APPEND CLIENT_SRCS
	code/client/audio/snd_main.cpp
	code/client/audio/legacy/snd_adpcm.cpp
	code/client/audio/legacy/snd_dma.cpp
	code/client/audio/legacy/snd_mem.cpp
	code/client/audio/legacy/snd_mix.cpp
	code/client/audio/legacy/snd_wavelet.cpp
	code/client/audio/codecs/snd_codec.cpp
	code/client/audio/codecs/snd_codec_ogg.cpp
	code/client/audio/codecs/snd_codec_wav.cpp
	code/client/audio/openal/AudioSystem.cpp)
IF(NOT USE_CURL)
	list(REMOVE_ITEM CLIENT_SRCS code/client/cl_curl.cpp)
ENDIF()

#ADD_LIBRARY(client OBJECT ${CLIENT_SRCS})

# jpeg
IF(USE_SYSTEM_JPEG)
	ADD_LIBRARY(client OBJECT ${CLIENT_SRCS})
	find_package(JPEG REQUIRED)
	TARGET_COMPILE_DEFINITIONS(client PRIVATE -DUSE_SYSTEM_JPEG)
	TARGET_LINK_LIBRARIES(client ${JPEG_LIBRARIES})
ELSE()
	AUX_SOURCE_DIRECTORY(code/libjpeg JPEG_SRCS)
	#ADD_LIBRARY(jpeg ${JPEG_SRCS})
	#TARGET_LINK_LIBRARIES(client jpeg)
	ADD_LIBRARY(client OBJECT ${CLIENT_SRCS} ${JPEG_SRCS})
ENDIF()

target_compile_features(client PRIVATE cxx_std_17)

set(FNQ3_OPENAL_INCLUDE_DIRS)
set(FNQ3_OPENAL_INCLUDE_CANDIDATES
	"${CMAKE_CURRENT_SOURCE_DIR}/code/openal/include")
file(GLOB FNQ3_OPENAL_SOFT_INCLUDE_CANDIDATES CONFIGURE_DEPENDS
	"${CMAKE_CURRENT_SOURCE_DIR}/subprojects/openal-soft-*/include")
list(APPEND FNQ3_OPENAL_INCLUDE_CANDIDATES ${FNQ3_OPENAL_SOFT_INCLUDE_CANDIDATES})
foreach(FNQ3_OPENAL_INCLUDE_CANDIDATE IN LISTS FNQ3_OPENAL_INCLUDE_CANDIDATES)
	if(EXISTS "${FNQ3_OPENAL_INCLUDE_CANDIDATE}/AL/al.h")
		list(APPEND FNQ3_OPENAL_INCLUDE_DIRS "${FNQ3_OPENAL_INCLUDE_CANDIDATE}")
	endif()
endforeach()
if(FNQ3_OPENAL_INCLUDE_DIRS)
	target_include_directories(client PRIVATE ${FNQ3_OPENAL_INCLUDE_DIRS})
endif()

ADD_EXECUTABLE(fnq3-audiozonesc code/tools/audiozones/audiozonesc.cpp)
target_compile_features(fnq3-audiozonesc PRIVATE cxx_std_17)
target_include_directories(fnq3-audiozonesc PRIVATE code/client/audio/shared)
IF(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 9)
	TARGET_LINK_LIBRARIES(fnq3-audiozonesc PRIVATE stdc++fs)
ENDIF()

IF(FNQ3_AUDIO_LOOPBACK_TESTS)
	enable_testing()
	ADD_EXECUTABLE(fnq3_audio_zone_tests tests/audio/audiozone_runtime_tests.cpp)
	target_compile_features(fnq3_audio_zone_tests PRIVATE cxx_std_17)
	target_include_directories(fnq3_audio_zone_tests PRIVATE code/client/audio/shared)
	add_test(NAME fnq3_audio_zones COMMAND fnq3_audio_zone_tests)
	add_test(NAME fnq3_audio_zone_authoring
		COMMAND $<TARGET_FILE:fnq3-audiozonesc> -o "${CMAKE_CURRENT_BINARY_DIR}/$<CONFIG>/audiozone_authoring_test.azb" "${CMAKE_CURRENT_SOURCE_DIR}/tests/audio/authoring_metadata.audiozones")
	add_test(NAME fnq3_audio_zone_authoring_audit
		COMMAND $<TARGET_FILE:fnq3-audiozonesc> --audit --strict --samples 512 "${CMAKE_CURRENT_BINARY_DIR}/$<CONFIG>/audiozone_authoring_test.azb")
	set_tests_properties(fnq3_audio_zone_authoring PROPERTIES FIXTURES_SETUP fnq3_audio_zone_authoring_fixture)
	set_tests_properties(fnq3_audio_zone_authoring_audit PROPERTIES
		DEPENDS fnq3_audio_zone_authoring
		FIXTURES_REQUIRED fnq3_audio_zone_authoring_fixture)

	ADD_EXECUTABLE(fnq3_audio_recovery_tests tests/audio/recovery_policy_tests.cpp)
	target_compile_features(fnq3_audio_recovery_tests PRIVATE cxx_std_17)
	target_include_directories(fnq3_audio_recovery_tests PRIVATE code/client/audio/shared)
	add_test(NAME fnq3_audio_recovery COMMAND fnq3_audio_recovery_tests)

	ADD_EXECUTABLE(fnq3_audio_occlusion_tests tests/audio/occlusion_policy_tests.cpp)
	target_compile_features(fnq3_audio_occlusion_tests PRIVATE cxx_std_17)
	target_include_directories(fnq3_audio_occlusion_tests PRIVATE code/client/audio/shared)
	add_test(NAME fnq3_audio_occlusion COMMAND fnq3_audio_occlusion_tests)

	ADD_EXECUTABLE(fnq3_audio_loopback_tests tests/audio/openal_loopback_tests.cpp)
	target_compile_features(fnq3_audio_loopback_tests PRIVATE cxx_std_17)
	if(FNQ3_OPENAL_INCLUDE_DIRS)
		target_include_directories(fnq3_audio_loopback_tests PRIVATE ${FNQ3_OPENAL_INCLUDE_DIRS})
	endif()
	IF(UNIX)
		TARGET_LINK_LIBRARIES(fnq3_audio_loopback_tests PRIVATE m ${CMAKE_DL_LIBS})
	ENDIF()
	add_test(NAME fnq3_audio_loopback COMMAND fnq3_audio_loopback_tests)
	set_tests_properties(fnq3_audio_loopback PROPERTIES SKIP_RETURN_CODE 77)

	find_package(Python3 COMPONENTS Interpreter)
	IF(Python3_Interpreter_FOUND)
		add_test(NAME fnq3_audio_zone_sweep_script
			COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/audio/audio_zone_sweep_tests.py")
		add_test(NAME fnq3_audio_zone_material_map
			COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/audio/audio_zone_material_map_tests.py" $<TARGET_FILE:fnq3-audiozonesc>)
	ENDIF()
ENDIF()

IF(FNQ3_GLX_LOGIC_TESTS)
	enable_testing()
	ADD_EXECUTABLE(fnq3_glx_logic_tests tests/glx/glx_logic_tests.cpp)
	target_compile_features(fnq3_glx_logic_tests PRIVATE cxx_std_17)
	target_include_directories(fnq3_glx_logic_tests PRIVATE
		code/rendererglx
		code/qcommon
		code/renderercommon)
	add_test(NAME fnq3_glx_logic COMMAND fnq3_glx_logic_tests)
	find_package(Python3 COMPONENTS Interpreter)
	IF(Python3_Interpreter_FOUND)
		add_test(NAME fnq3_glx_header_boundary
			COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/glx/glx_header_boundary_tests.py")
	ENDIF()
ENDIF()

# renderers
AUX_SOURCE_DIRECTORY(code/renderercommon RENDERER_COMMON_SRCS)
AUX_SOURCE_DIRECTORY(code/renderer RENDERER_GL_SRCS)
AUX_SOURCE_DIRECTORY(code/rendererglx RENDERER_GLX_SRCS)
AUX_SOURCE_DIRECTORY(code/renderervk RENDERER_VK_SRCS)

IF(USE_RENDERER_DLOPEN)
	SET(AUX_SRCS
		code/qcommon/q_shared.c
		code/qcommon/puff.c
		code/qcommon/q_math.c
		${PLATFORM_ASM_SRCS}
	)
	TARGET_COMPILE_DEFINITIONS(client PRIVATE USE_RENDERER_DLOPEN RENDERER_PREFIX="${RENDERER_PREFIX}" RENDERER_DEFAULT=${RENDERER_DEFAULT})

	ADD_LIBRARY(${RENDERER_PREFIX}_opengl${RENDEXT} SHARED ${RENDERER_GL_SRCS} ${RENDERER_COMMON_SRCS} ${AUX_SRCS})
	TARGET_COMPILE_DEFINITIONS(${RENDERER_PREFIX}_opengl${RENDEXT} PRIVATE USE_RENDERER_DLOPEN)
	SET_TARGET_PROPERTIES(${RENDERER_PREFIX}_opengl${RENDEXT} PROPERTIES PREFIX "")

	IF(USE_GLX)
		ADD_LIBRARY(${RENDERER_PREFIX}_glx${RENDEXT} SHARED ${RENDERER_GL_SRCS} ${RENDERER_GLX_SRCS} ${RENDERER_COMMON_SRCS} ${AUX_SRCS})
		TARGET_COMPILE_DEFINITIONS(${RENDERER_PREFIX}_glx${RENDEXT} PRIVATE USE_RENDERER_DLOPEN RENDERER_GLX)
		SET_TARGET_PROPERTIES(${RENDERER_PREFIX}_glx${RENDEXT} PROPERTIES PREFIX "")
	ENDIF()

	ADD_LIBRARY(${RENDERER_PREFIX}_vulkan${RENDEXT} SHARED ${RENDERER_VK_SRCS} ${RENDERER_COMMON_SRCS} ${AUX_SRCS})
	TARGET_COMPILE_DEFINITIONS(${RENDERER_PREFIX}_vulkan${RENDEXT} PRIVATE USE_RENDERER_DLOPEN)
	SET_TARGET_PROPERTIES(${RENDERER_PREFIX}_vulkan${RENDEXT} PROPERTIES PREFIX "")
ELSE()
	IF(RENDERER_DEFAULT STREQUAL "glx")
		ADD_LIBRARY(${RENDERER_PREFIX}_glx OBJECT ${RENDERER_GL_SRCS} ${RENDERER_GLX_SRCS} ${RENDERER_COMMON_SRCS})
		TARGET_COMPILE_DEFINITIONS(${RENDERER_PREFIX}_glx PRIVATE RENDERER_GLX)
	ELSEIF(USE_VULKAN)
		ADD_LIBRARY(${RENDERER_PREFIX}_vulkan OBJECT ${RENDERER_VK_SRCS} ${RENDERER_COMMON_SRCS})
	ELSE()
		ADD_LIBRARY(${RENDERER_PREFIX}_opengl OBJECT ${RENDERER_GL_SRCS} ${RENDERER_COMMON_SRCS})
	ENDIF()
ENDIF()

# common function, window system
IF(UNIX)
	SET (Q3_SRCS
		code/unix/unix_main.cpp
		code/unix/unix_shared.cpp
		code/unix/unix_syscon.cpp
		code/unix/linux_signals.cpp)

	IF(USE_SDL)
		SET(Q3_UI_SRCS
			code/sdl/sdl_gamma.cpp
			code/sdl/sdl_glimp.cpp
			code/sdl/sdl_input.cpp
			code/sdl/sdl_snd.cpp)
	ELSE()
		SET(Q3_UI_SRCS
			code/unix/linux_glimp.cpp
			code/unix/linux_qgl.cpp
			code/unix/linux_snd.cpp
			code/unix/x11_dga.cpp
			code/unix/x11_randr.cpp
			code/unix/x11_vidmode.cpp)
		IF(USE_VULKAN)
			list(APPEND Q3_UI_SRCS code/unix/linux_qvk.cpp)
		ENDIF()
	ENDIF()

	IF(APPLE)
		SET(EXE_TYPE MACOSX_BUNDLE)
		list(APPEND Q3_SRCS code/unix/fnquake3.icns)
		set_source_files_properties(code/unix/fnquake3.icns PROPERTIES
			MACOSX_PACKAGE_LOCATION Resources)
		SET(MACOSX_BUNDLE_ICON_FILE fnquake3.icns)
	ENDIF()
ELSEIF(WIN32)
	SET(EXE_TYPE WIN32)
	IF(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
		ADD_COMPILE_DEFINITIONS(_CRT_SECURE_NO_WARNINGS) # v3.12+
	ELSEIF(MSVC)
		SET(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} /MANIFEST:NO")
		ADD_COMPILE_DEFINITIONS(_CRT_SECURE_NO_WARNINGS) # v3.12+
	ENDIF()

	SET(Q3_SRCS
		code/win32/win_main.cpp
		code/win32/win_shared.cpp
		code/win32/win_syscon.cpp
		code/win32/win_resource.rc)

	SET(Q3_UI_SRCS
		code/win32/win_gamma.cpp
		code/win32/win_glimp.cpp
		code/win32/win_input.cpp
		code/win32/win_minimize.cpp
		code/win32/win_qgl.cpp
		code/win32/win_snd.cpp
		code/win32/win_wndproc.cpp)
	IF(USE_VULKAN)
		list(APPEND Q3_UI_SRCS code/win32/win_qvk.cpp)
	ENDIF()
ENDIF(UNIX)

ADD_LIBRARY(q3ui OBJECT ${Q3_UI_SRCS})

IF(UNIX AND USE_SDL)
	find_package(SDL3 3.2.0 CONFIG QUIET COMPONENTS SDL3)
	IF(TARGET SDL3::SDL3)
		SET(Q3_SDL_TARGET SDL3::SDL3)
	ELSE()
		find_package(PkgConfig REQUIRED)
		pkg_check_modules(SDL3 REQUIRED IMPORTED_TARGET sdl3>=3.2.0)
		SET(Q3_SDL_TARGET PkgConfig::SDL3)
	ENDIF()

	TARGET_COMPILE_DEFINITIONS(q3ui PRIVATE SDL_FUNCTION_POINTER_IS_VOID_POINTER=1)
	TARGET_LINK_LIBRARIES(q3ui PRIVATE ${Q3_SDL_TARGET})
ELSEIF(UNIX AND NOT MSVC)
	IF(NOT USE_SDL)
		find_package (X11 REQUIRED)
		TARGET_LINK_LIBRARIES(q3ui ${X11_LIBRARIES})
	ENDIF()
ENDIF()

IF(USE_VULKAN)
	TARGET_COMPILE_DEFINITIONS(q3ui PRIVATE USE_VULKAN_API)
	TARGET_COMPILE_DEFINITIONS(client PRIVATE USE_VULKAN_API)
ENDIF()

IF(USE_RENDERER_DLOPEN OR RENDERER_DEFAULT STREQUAL "opengl" OR RENDERER_DEFAULT STREQUAL "glx")
	TARGET_COMPILE_DEFINITIONS(q3ui PRIVATE USE_OPENGL_API)
	TARGET_COMPILE_DEFINITIONS(client PRIVATE USE_OPENGL_API)
ENDIF()

# client executable

ADD_EXECUTABLE(${CNAME}${BINEXT} ${EXE_TYPE} ${Q3_SRCS})
TARGET_LINK_LIBRARIES(${CNAME}${BINEXT} qcommon botlib client q3ui)
set_property(TARGET ${CNAME}${BINEXT} PROPERTY LINKER_LANGUAGE CXX)
#TARGET_LINK_OPTIONS(${CNAME} PRIVATE -fno-pie) # v3.13+

IF(NOT USE_RENDERER_DLOPEN)
	IF(RENDERER_DEFAULT STREQUAL "glx")
		TARGET_LINK_LIBRARIES(${CNAME}${BINEXT} ${RENDERER_PREFIX}_glx)
	ELSEIF(USE_VULKAN)
		TARGET_LINK_LIBRARIES(${CNAME}${BINEXT} ${RENDERER_PREFIX}_vulkan)
	ELSE()
		TARGET_LINK_LIBRARIES(${CNAME}${BINEXT} ${RENDERER_PREFIX}_opengl)
	ENDIF()
ENDIF()

# dedicated server executable

ADD_EXECUTABLE(${DNAME}${BINEXT} ${EXE_TYPE} ${Q3_SRCS})
TARGET_LINK_LIBRARIES(${DNAME}${BINEXT} qcommon_ded botlib)
set_property(TARGET ${DNAME}${BINEXT} PROPERTY LINKER_LANGUAGE CXX)
#TARGET_LINK_OPTIONS(${DNAME} PRIVATE -fno-pie) # v3.13+

IF(WIN32)
	TARGET_LINK_LIBRARIES(${CNAME}${BINEXT} winmm comctl32 ws2_32)
	TARGET_LINK_LIBRARIES(${DNAME}${BINEXT} winmm comctl32 ws2_32)

	if(CMAKE_GENERATOR_PLATFORM STREQUAL "Win32")
		SET(FNQ3_OPENAL_DLL "${CMAKE_CURRENT_SOURCE_DIR}/code/openal/windows/x86/OpenAL32.dll")
	elseif(CMAKE_GENERATOR_PLATFORM STREQUAL "x64")
		SET(FNQ3_OPENAL_DLL "${CMAKE_CURRENT_SOURCE_DIR}/code/openal/windows/x64/OpenAL32.dll")
	elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "ARM64|arm64|AARCH64|aarch64")
		unset(FNQ3_OPENAL_DLL)
	elseif(CMAKE_SIZEOF_VOID_P EQUAL 4)
		SET(FNQ3_OPENAL_DLL "${CMAKE_CURRENT_SOURCE_DIR}/code/openal/windows/x86/OpenAL32.dll")
	else()
		SET(FNQ3_OPENAL_DLL "${CMAKE_CURRENT_SOURCE_DIR}/code/openal/windows/x64/OpenAL32.dll")
	endif()

	if(DEFINED FNQ3_OPENAL_DLL AND EXISTS "${FNQ3_OPENAL_DLL}")
		add_custom_command(
			TARGET ${CNAME}${BINEXT} POST_BUILD
			COMMAND ${CMAKE_COMMAND} -E copy_if_different
				"${FNQ3_OPENAL_DLL}"
				"$<TARGET_FILE_DIR:${CNAME}${BINEXT}>"
		)
		if(FNQ3_AUDIO_LOOPBACK_TESTS AND TARGET fnq3_audio_loopback_tests)
			add_custom_command(
				TARGET fnq3_audio_loopback_tests POST_BUILD
				COMMAND ${CMAKE_COMMAND} -E copy_if_different
					"${FNQ3_OPENAL_DLL}"
					"$<TARGET_FILE_DIR:fnq3_audio_loopback_tests>"
			)
		endif()
	endif()
ELSE()
	TARGET_LINK_LIBRARIES(${CNAME}${BINEXT} m ${CMAKE_DL_LIBS})
	TARGET_LINK_LIBRARIES(${DNAME}${BINEXT} m ${CMAKE_DL_LIBS})
ENDIF()
