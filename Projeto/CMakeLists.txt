cmake_minimum_required(VERSION 3.10)
project(AgroDT_UAV)

set(CMAKE_CXX_STANDARD 17)

# Forma robusta de achar o ZeroMQ
find_package(PkgConfig REQUIRED)
pkg_check_modules(ZMQ REQUIRED libzmq)

# Inclui a pasta onde baixamos o json.hpp
include_directories(include)

# Executável do Drone
add_executable(drone_sim drone_sim.cpp)
target_include_directories(drone_sim PUBLIC ${ZMQ_INCLUDE_DIRS})
target_link_libraries(drone_sim ${ZMQ_LIBRARIES})

# Executável do Listener
add_executable(listener listener.cpp)
target_include_directories(listener PUBLIC ${ZMQ_INCLUDE_DIRS})
target_link_libraries(listener ${ZMQ_LIBRARIES})

