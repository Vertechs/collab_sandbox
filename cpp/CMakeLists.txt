cmake_minimum_required(VERSION 3.16)
project(collab_cpp_lib VERSION 0.1.0 LANGUAGES CXX)

include(GNUInstallDirs)

add_library(collab_cpp_lib STATIC
    src/math_ops.cpp
)

target_include_directories(collab_cpp_lib
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

install(TARGETS collab_cpp_lib
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)
