cmake_minimum_required(VERSION 3.16)
project(ror_isobus_game_demo VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)

if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../AgIsoStack-plus-plus/CMakeLists.txt")
    message(FATAL_ERROR "AgIsoStack-plus-plus nao encontrado ao lado desta pasta. Esperado: ../AgIsoStack-plus-plus")
endif()

add_subdirectory(
    "../AgIsoStack-plus-plus"
    "${CMAKE_BINARY_DIR}/AgIsoStack-build"
)

add_executable(ror_to_isobus ror_to_isobus.cpp)
target_link_libraries(ror_to_isobus PRIVATE
    isobus::Isobus
    isobus::HardwareIntegration
    isobus::Utility
    Threads::Threads
)

add_executable(sprayer_sim sprayer_sim.cpp)
target_link_libraries(sprayer_sim PRIVATE
    isobus::Isobus
    isobus::HardwareIntegration
    isobus::Utility
    Threads::Threads
)
