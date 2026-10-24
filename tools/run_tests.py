"""Offline checks using a locally installed 64-bit lua51.dll; no game process access."""
import argparse
import ctypes
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def quote_lua(text):
    for size in range(1, 20):
        equals = "=" * size
        if "]" + equals + "]" not in text:
            return "[" + equals + "[" + text + "]" + equals + "]"
    raise ValueError("Cannot quote Lua source")


def execute(dll, program):
    lua = ctypes.CDLL(str(dll.resolve()))
    lua.luaL_newstate.restype = ctypes.c_void_p
    lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
    lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lua.luaL_loadstring.restype = ctypes.c_int
    lua.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lua.lua_pcall.restype = ctypes.c_int
    lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    lua.lua_tolstring.restype = ctypes.c_void_p
    lua.lua_close.argtypes = [ctypes.c_void_p]
    state = lua.luaL_newstate()
    if not state:
        raise RuntimeError("Cannot create offline Lua state")
    try:
        lua.luaL_openlibs(state)
        status = lua.luaL_loadstring(state, program.encode("utf-8"))
        if status == 0:
            status = lua.lua_pcall(state, 0, 1, 0)
        length = ctypes.c_size_t()
        address = lua.lua_tolstring(state, -1, ctypes.byref(length))
        result = ctypes.string_at(address, length.value).decode("utf-8", errors="replace") if address else ""
        if status:
            raise RuntimeError(result or f"Lua failed with status {status}")
        return result
    finally:
        lua.lua_close(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lua-dll", type=Path, default=os.environ.get("HD2_LUA51_DLL"),
                        help="Local Helldivers 2/bin/lua51.dll, or set HD2_LUA51_DLL")
    args = parser.parse_args()
    if not args.lua_dll or not args.lua_dll.is_file():
        parser.error("Pass --lua-dll PATH to your local 64-bit lua51.dll")
    template = (ROOT / "src/rainie_love.lua.in").read_text("utf-8")
    boundary = (ROOT / "src/mission_boundary.lua").read_text("utf-8")
    compiled = template.replace("__MISSION_BOUNDARY__", boundary).replace("__AUDIO_BASE64__", "")
    program = "assert(loadstring(" + quote_lua(compiled) + "))\nreturn 'PASS: release Lua syntax'"
    print(execute(args.lua_dll, program))
    tests = (ROOT / "tests/test_mission_boundary.lua").read_text("utf-8")
    # Load the module from source instead of relying on ANSI Windows file paths.
    tests = tests.replace("local M = assert(loadfile(arg[1]))()", "local M = (function()\n" + boundary + "\nend)()")
    print(execute(args.lua_dll, tests))
    # Exercise the actual release classifier against missing, ordinary and shuttle records.
    match = re.search(r"  local function extraction_seat\(entity\).*?(?=\n  -- Independent read-only detector)", template, re.S)
    if not match:
        raise RuntimeError("Cannot locate the release extraction classifier")
    fixture = (ROOT / "tests/vehicle_seat_fixture.lua").read_text("utf-8")
    print(execute(args.lua_dll, fixture.replace("__EXTRACTION_CLASSIFIER__", match.group())))


if __name__ == "__main__":
    main()
