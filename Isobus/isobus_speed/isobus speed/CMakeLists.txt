cmake_minimum_required(VERSION 3.16)

project(isobus_speed_demo VERSION 2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)

set(AGISOSTACK_DIR "" CACHE PATH "Caminho para o repositorio AgIsoStack-plus-plus")

if(NOT AGISOSTACK_DIR AND DEFINED ENV{AGISOSTACK_DIR})
    set(AGISOSTACK_DIR "$ENV{AGISOSTACK_DIR}")
endif()

if(NOT AGISOSTACK_DIR)
    foreach(candidate
        "${CMAKE_CURRENT_SOURCE_DIR}/../AgIsoStack-plus-plus"
        "${CMAKE_CURRENT_SOURCE_DIR}/AgIsoStack-plus-plus"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../AgIsoStack-plus-plus")
        if(EXISTS "${candidate}/CMakeLists.txt")
            set(AGISOSTACK_DIR "${candidate}")
            break()
        endif()
    endforeach()
endif()

if(NOT AGISOSTACK_DIR OR NOT EXISTS "${AGISOSTACK_DIR}/CMakeLists.txt")
    message(FATAL_ERROR
        "AgIsoStack-plus-plus nao encontrada. Coloque este projeto ao lado da pasta "
        "AgIsoStack-plus-plus ou configure -DAGISOSTACK_DIR=/caminho/AgIsoStack-plus-plus")
endif()

get_filename_component(AGISOSTACK_DIR "${AGISOSTACK_DIR}" ABSOLUTE)
message(STATUS "Usando AgIsoStack++ em: ${AGISOSTACK_DIR}")

add_subdirectory(
    "${AGISOSTACK_DIR}"
    "${CMAKE_BINARY_DIR}/AgIsoStack-build"
)

function(configure_demo_target target_name)
    target_link_libraries(${target_name} PRIVATE
        isobus::Isobus
        isobus::HardwareIntegration
        isobus::Utility
        Threads::Threads
    )

    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(${target_name} PRIVATE -Wall -Wextra -Wpedantic)
    endif()
endfunction()

add_executable(tractor_sim tractor_sim.cpp)
configure_demo_target(tractor_sim)

add_executable(sprayer_sim sprayer_sim.cpp)
configure_demo_target(sprayer_sim)
