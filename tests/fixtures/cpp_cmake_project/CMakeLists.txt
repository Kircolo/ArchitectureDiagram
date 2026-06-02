add_library(core STATIC
    src/core/engine.cpp
    include/core/engine.hpp
)

add_executable(app
    src/main.cpp
    src/app.cpp
    include/app.hpp
)
