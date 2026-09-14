# TruGrade native core.
#
# Builds one shared library, libtrugrade_core.so, that backend/native loads
# through ctypes. Nothing in the Python application links against it at build
# time — if this never compiles, the backend still runs on its pure-Python
# fallback, which is why this is a standalone CMake project rather than part of
# the Python packaging.
cmake_minimum_required(VERSION 3.16)

project(trugrade_core
    VERSION 0.1.0
    DESCRIPTION "TruGrade tracking and kinematics core"
    LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

add_library(trugrade_core SHARED
    src/tg_abi.c
    src/capi.cpp
    src/tracking.cpp
    src/kinematics.cpp)

target_include_directories(trugrade_core PUBLIC include)

# The library is loaded by dlopen, never linked, so the .so must carry no
# undefined symbols it expects a host to supply.
if(NOT APPLE AND NOT WIN32)
    target_link_options(trugrade_core PRIVATE "LINKER:--no-undefined")
endif()

if(MSVC)
    target_compile_options(trugrade_core PRIVATE /W4)
else()
    target_compile_options(trugrade_core PRIVATE -Wall -Wextra -Wpedantic -Wconversion)
endif()

# -ffast-math is deliberately NOT enabled: the Python fallback and the native
# path are asserted equal to the last decimal place in
# backend/tests/test_native_parity.py, and reassociating this arithmetic would
# break that equality for no measurable gain on these loop sizes.

option(TRUGRADE_BUILD_TESTS "Build the native self-tests" ON)

if(TRUGRADE_BUILD_TESTS)
    enable_testing()
    add_executable(trugrade_core_tests tests/test_core.cpp)
    target_link_libraries(trugrade_core_tests PRIVATE trugrade_core)
    add_test(NAME trugrade_core_tests COMMAND trugrade_core_tests)
endif()
