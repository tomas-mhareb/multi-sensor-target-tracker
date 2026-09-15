# Warning configuration, applied per target rather than globally so that fetched
# dependencies are not compiled under this project's stricter settings. Third-party
# code producing warnings we cannot fix would train us to ignore the output.

function(mstt_set_target_warnings target)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /permissive-)
    else()
        target_compile_options(${target} PRIVATE
            -Wall
            -Wextra
            -Wpedantic
            # A shadowed variable is almost always a rename that was left unfinished.
            -Wshadow
            # Implicit narrowing silently discards precision. In software whose whole
            # purpose is numerical estimation, that is a correctness issue rather than
            # a style one.
            -Wconversion
            -Wsign-conversion
            # Deleting through a base pointer without a virtual destructor leaks.
            -Wnon-virtual-dtor
            -Woverloaded-virtual
            # C-style casts hide exactly the conversions the flags above exist to find.
            -Wold-style-cast
            -Wnull-dereference
            # float promoted to double is usually an unintended mixed-precision
            # expression rather than a deliberate widening.
            -Wdouble-promotion
            -Wformat=2)
    endif()

    if(MSTT_WARNINGS_AS_ERRORS)
        if(MSVC)
            target_compile_options(${target} PRIVATE /WX)
        else()
            target_compile_options(${target} PRIVATE -Werror)
        endif()
    endif()
endfunction()

# AddressSanitizer detects out-of-bounds access, use-after-free, and leaks at runtime.
# UndefinedBehaviorSanitizer detects signed overflow, invalid casts, and misaligned
# access. Both instrument the binary and cost roughly a 2x slowdown, so they are opt-in
# and run as a separate CI job rather than on every build.
function(mstt_enable_sanitizers target)
    if(NOT MSTT_ENABLE_SANITIZERS)
        return()
    endif()
    if(MSVC)
        message(WARNING "Sanitizers are not configured for MSVC; ignoring.")
        return()
    endif()
    target_compile_options(${target} PRIVATE
        -fsanitize=address,undefined
        -fno-omit-frame-pointer
        -fno-sanitize-recover=all)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
endfunction()
