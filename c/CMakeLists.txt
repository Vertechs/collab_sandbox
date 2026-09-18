cmake_minimum_required(VERSION 3.16)
project(collab_c_lib VERSION 0.1.0 LANGUAGES C)

include(GNUInstallDirs)

add_library(collab_c_lib STATIC
    src/math_ops.c
)

target_include_directories(collab_c_lib
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

install(TARGETS collab_c_lib
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)
