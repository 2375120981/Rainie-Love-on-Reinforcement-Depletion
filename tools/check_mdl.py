"""Offline Lua 5.1 checks for the MDL implementation; never attaches to the game."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', type=Path, default=ROOT / '.work/lua-runtime')
    parser.add_argument('--hot-entry', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.runtime_dir))
    from lupa.lua51 import LuaRuntime

    runtime = LuaRuntime(unpack_returned_tuples=True)
    runtime.globals().print = lambda *items: print(*items) if items and str(items[0]).startswith('PASS:') else None
    runtime.execute('os.getenv = function() return nil end')
    modules = runtime.table()
    for name in ('policy', 'data', 'audio'):
        source = (ROOT / f'src/mdl_{name}.lua').read_text(encoding='utf-8')
        modules[name] = runtime.execute(source)
    runtime.globals().MODULES = modules
    runtime.execute((ROOT / 'tests/test_mdl.lua').read_text(encoding='utf-8'))
    source = (args.hot_entry or ROOT / 'src/rainie_love_mdl.lua.in').read_text(encoding='utf-8')
    for name in ('policy', 'data', 'audio'):
        source = source.replace(f'__MDL_{name.upper()}__', (ROOT / f'src/mdl_{name}.lua').read_text(encoding='utf-8'))
    source = source.replace('__AUDIO_FORMAT__', '').replace('__AUDIO_CONTENT__', '')
    definition = runtime.execute(source)
    context = runtime.table(settings=runtime.table(volume=50, preview=True), log=lambda message: None)
    definition.on_enable(context)
    assert not context.settings.preview
    definition.on_setting(context, 'preview', True)
    assert context.settings.preview
    for _ in range(64):
        definition.on_update(context, 0.25)
    assert context.settings.preview, 'preview must wait for the upload instead of expiring after 15 seconds'
    for _ in range(1160):
        definition.on_update(context, 0.25)
    assert context.settings.preview, 'preview must remain enabled without an arbitrary wait timeout'
    definition.on_disable()
    runtime.execute('''
        TEST_PLAYS, TEST_STOPS, TEST_FREE = 0, 0, 1
        AUTO_READY, AUTO_COOLDOWN = true, 0
        MDL3 = {audio = {api = 2,
            define_format = function() return true end,
            pool = function() return true end,
            upload = function() return true end,
            ready = function() return true end,
            status = function() return {pool = 1, free = {music = TEST_FREE}, pending = {music = 0}} end,
            play = function() TEST_PLAYS = TEST_PLAYS + 1; TEST_FREE = 0; return TEST_PLAYS end,
            resume = function() TEST_FREE = 0; return true end,
            halt = function() TEST_STOPS = TEST_STOPS + 1; TEST_FREE = 1; return true end,
            pause = function() TEST_STOPS = TEST_STOPS + 1; TEST_FREE = 1; return true end,
            set = function() return true end,
            info = function() return {state = TEST_FREE == 0 and 'playing' or 'paused', position = TEST_FREE == 0 and 1 or 0} end,
            stop = function() TEST_STOPS = TEST_STOPS + 1; TEST_FREE = 1; return true end,
            release = function() return true end
        }}
        HD2Data = {
            ready = function() return true end,
            mission = function() return {in_mission = true, epoch = AUTO_EPOCH or 20} end,
            on = function(name, callback, opts)
                assert(name == 'mission_ended' and opts.owner == 'rainie_love_mdl')
                TEST_MISSION_END = callback
                return {unsubscribe = function() TEST_UNSUBSCRIBED = (TEST_UNSUBSCRIBED or 0) + 1 end}
            end,
            players = function() return {{slot = 0, alive = true}} end,
            stratagems = function() return {{slot = 0, stratagems = {{type = 127, unlimited = true,
                ready = AUTO_READY, cooldown_left = AUTO_COOLDOWN, cooldown_base = 6, last_cooldown = 5.7}}}} end
        }
    ''')
    definition.on_enable(context)
    for _ in range(50):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_PLAYS == 1, 'prepared voice stays paused until trigger'
    runtime.globals().AUTO_READY = False
    runtime.globals().AUTO_COOLDOWN = 30
    for _ in range(8):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_PLAYS == 1, 'Hub readiness transition must drive the actual audio entry'
    runtime.globals().AUTO_COOLDOWN = 2
    for _ in range(8):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_FREE == 0
    runtime.globals().AUTO_READY = True
    runtime.globals().AUTO_COOLDOWN = 0
    for _ in range(4):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_FREE == 1 and runtime.globals().TEST_STOPS >= 1
    runtime.globals().AUTO_READY = False
    runtime.globals().AUTO_COOLDOWN = 90
    for _ in range(8):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_FREE == 0
    runtime.globals().TEST_MISSION_END(runtime.table(mission=20))
    for _ in range(8):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_FREE == 1, 'end event stops despite a stale Mission snapshot'
    runtime.globals().AUTO_EPOCH = 21
    runtime.globals().AUTO_READY = True
    runtime.globals().AUTO_COOLDOWN = 0
    definition.on_update(context, 0.25)
    runtime.globals().AUTO_READY = False
    runtime.globals().AUTO_COOLDOWN = 90
    for _ in range(8):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_FREE == 0, 'new task must rearm'
    definition.on_setting(context, 'automatic', False)
    for _ in range(4):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_FREE == 1, 'automatic off fades out'
    definition.on_setting(context, 'automatic', True)
    for _ in range(8):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_FREE == 0, 'automatic on restarts confirmed condition'
    definition.on_disable()
    assert runtime.globals().TEST_UNSUBSCRIBED >= 1, 'end subscription must be removed on disable'
    definition.on_enable(context)
    definition.on_disable()
    runtime.execute('''
        TEST_READY, TEST_PLAYS, TEST_STOPS, TEST_FREE = false, 0, 0, 1
        HD2Data = {ready = function() return true end,
            mission = function() return {in_mission = false, epoch = 1} end}
        MDL3 = {audio = {api = 2,
            define_format = function() return true end,
            pool = function() return true end,
            upload = function() return true end,
            ready = function() return TEST_READY end,
            status = function() return {pool = 1, free = {music = TEST_FREE}, pending = {music = 0}} end,
            play = function() TEST_PLAYS = TEST_PLAYS + 1; TEST_FREE = 0; return TEST_PLAYS end,
            resume = function() TEST_FREE = 0; return true end,
            halt = function() TEST_STOPS = TEST_STOPS + 1; TEST_FREE = 1; return true end,
            pause = function() TEST_STOPS = TEST_STOPS + 1; TEST_FREE = 1; return true end,
            set = function() return true end,
            info = function() return {state = TEST_FREE == 0 and 'playing' or 'paused', position = TEST_FREE == 0 and 1 or 0} end,
            stop = function() TEST_STOPS = TEST_STOPS + 1; TEST_FREE = 1; return true end,
            release = function() return true end
        }}
    ''')
    definition.on_enable(context)
    definition.on_setting(context, 'preview', True)
    for _ in range(200):
        definition.on_update(context, 0.25)
    assert context.settings.preview and runtime.globals().TEST_PLAYS == 0
    runtime.globals().TEST_READY = True
    for _ in range(4):
        definition.on_update(context, 0.25)
    assert runtime.globals().TEST_PLAYS == 1 and context.settings.preview
    for _ in range(1000):
        definition.on_update(context, 0.25)
    assert context.settings.preview and runtime.globals().TEST_PLAYS == 1, 'preview must loop beyond a full track without timing out'
    definition.on_setting(context, 'preview', False)
    for _ in range(4):
        definition.on_update(context, 0.25)
    assert not context.settings.preview and runtime.globals().TEST_STOPS >= 1
    definition.on_disable()
    runtime.execute('''
        SLIDER_SPECS, SLIDER_VALUES = {}, {}
        ModOptionsMenu = {
            register_option = function(id, specification)
                assert(specification.type == 'slider')
                SLIDER_SPECS[id] = specification
                if SLIDER_VALUES[id] == nil then SLIDER_VALUES[id] = specification.default end
                return true
            end,
            get = function(id) return SLIDER_VALUES[id] end,
            set = function(id, value) SLIDER_VALUES[id] = value; return true end
        }
    ''')
    context.settings.volume = 60
    context.id = 'rainie_love_mdl'
    definition.on_enable(context)
    values = runtime.globals().SLIDER_VALUES
    specifications = runtime.globals().SLIDER_SPECS
    assert values['rainie_love_mdl.volume'] == 60
    assert specifications['rainie_love_mdl.fade_out_seconds'].min == 1
    assert specifications['rainie_love_mdl.fade_out_seconds'].max == 30
    assert specifications['rainie_love_mdl.volume'].step == 5
    assert specifications['rainie_love_mdl.volume'].mod_id == 'rainie_love_mdl'
    values['rainie_love_mdl.volume'] = 80
    definition.on_update(context, 0.25)
    assert context.settings.volume == 80
    definition.on_disable()
    definition.on_enable(context)
    assert values['rainie_love_mdl.volume'] == 80
    definition.on_disable()
    assert set(specifications.keys()) == {'rainie_love_mdl.volume', 'rainie_love_mdl.fade_out_seconds'}
    assert {option.key for option in definition.options.values()} == {'preview', 'automatic'}
    assert len(list(specifications.keys())) + len(list(definition.options.values())) == 4, 'release must expose exactly four settings'
    for option in definition.options.values():
        assert option.type != 'number', 'numeric settings must not remain as number inputs'
    assert runtime.globals().update is None and runtime.globals().shutdown is None
    print('PASS: Lua 5.1 entry, delayed-ready preview, ship preview, unlimited looping preview and manual stop, reload cleanup')
    print('PASS: all numeric settings are sliders, value migration, saved values, live polling')
    print('PASS: full entry automatic switch, mission end event, stale snapshot lock, new task reset, subscription cleanup')
    print('PASS: complete entry uses Hub availability, variable cooldown, playback and recovery stop')


if __name__ == '__main__':
    main()
