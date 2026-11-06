local Policy = MODULES.policy
local Data = MODULES.data
local Audio = MODULES.audio
local function sample(tickets, seats, alive)
    return {reinforcements = tickets, seats = seats or 1, alive_players = alive or 1}
end
local mission = {in_mission = true, epoch = 1}
local function observe(state, value, boundary)
    return Policy.observe(state, boundary or mission, value, 0.25)
end
local function confirm(state, value)
    local wanted
    for index = 1, 4 do wanted = observe(state, value) end
    return wanted
end
local state = Policy.new()
assert(not confirm(state, sample(0)), 'solo zero-ticket start must remain disarmed')
assert(not observe(state, sample(5)))
assert(confirm(state, sample(0)), 'zero after a positive budget must trigger')
assert(not observe(state, sample(1)), 'restored reinforcement must stop')
assert(not observe(state, sample(0)), 'confirmation must restart after restoration')
assert(not observe(state, nil), 'unknown data must stop and reset confirmation')
assert(not observe(state, sample(0)))
assert(confirm(Policy.new(), sample(0, 4, 1)), 'joining a populated zero-ticket mission must arm')
assert(not confirm(Policy.new(), sample(0, 4, 2)), 'two living players must not trigger')
state = Policy.new()
observe(state, sample(5))
assert(confirm(state, sample(0)))
assert(not observe(state, sample(0), {in_mission = true, epoch = 2}), 'new epoch must reset solo budget')
observe(state, sample(5))
local extracted = sample(0)
extracted.extraction_seated = true
assert(not confirm(state, extracted))
assert(not confirm(state, sample(0)), 'extraction lock must persist')
state = Policy.new()
observe(state, sample(5))
Policy.observe(state, {in_mission = false, epoch = 1}, nil, 0.25)
Policy.observe(state, nil, nil, 0.25)
assert(state.active and state.ending == 0, 'unknown mission must not confirm an end')
Policy.observe(state, {in_mission = false, epoch = 1}, nil, 0.25)
Policy.observe(state, {in_mission = false, epoch = 1}, nil, 0.25)
assert(not state.active, 'two confirmed outside samples must end the mission')

-- A confirmed task end must survive a delayed/stale in-mission snapshot.
state = Policy.new()
observe(state, sample(5))
assert(confirm(state, sample(0)))
assert(not Policy.finish(state, 99), 'an older/different mission event must not stop this mission')
assert(Policy.finish(state, 1))
assert(not confirm(state, sample(0)), 'ended task cannot rearm from stale snapshots')
assert(select(2, observe(state, sample(0))) == 'MISSION_ENDED_LOCK')
assert(not observe(state, sample(2), {in_mission=true, epoch=2}))
local new_wanted
for i=1,4 do new_wanted=observe(state,sample(0),{in_mission=true,epoch=2}) end
assert(new_wanted, 'a new epoch resets the ended lock')
-- Explicit stop reasons distinguish recovery, team revival and squad wipe.
state = Policy.new()
observe(state, sample(2, 4, 1))
assert(confirm(state, sample(0, 4, 1)))
assert(select(2, observe(state, sample(0, 4, 2))) == 'MULTIPLE_SURVIVORS')
assert(select(2, observe(state, {reinforcements=0,seats=4,alive_players=0})) == 'NO_SURVIVORS')
assert(select(2, observe(state, sample(1, 4, 1))) == 'REINFORCEMENTS_AVAILABLE')
print('PASS: trigger confirmation, recovery, team revival, squad wipe, end lock, stale event rejection, next mission')

local roster = {{slot = 0, alive = true}, {slot = 1, alive = false}}
local reinforcement = {type = 127, unlimited = false, uses = 0}
local strata = {{slot = 0, stratagems = {reinforcement}}}
local hub = {
    ready = function() return true end,
    mission = function() return mission end,
    players = function() return roster end,
    stratagems = function() return strata end
}
local boundary, snapshot, reason = Data.sample(hub)
assert(reason == 'READY' and snapshot.reinforcements == 0 and snapshot.alive_players == 1)
reinforcement.unlimited, reinforcement.uses = true, nil
boundary, snapshot, reason = Data.sample(hub)
assert(reason == 'REINFORCEMENT_COUNT_UNAVAILABLE' and snapshot.reinforcements == nil,
       'actual Hub unlimited/nil observations must never become zero')
reinforcement.ready, reinforcement.cooldown_left, reinforcement.cooldown_base = true, 0, 6
boundary, snapshot, reason = Data.sample(hub)
assert(reason == 'READY_STATUS' and snapshot.reinforcements == nil and snapshot.reinforcement_ready == true,
       'Hub availability must remain status data rather than a fake positive ticket count')
local cooldown_policy = Policy.new()
assert(not observe(cooldown_policy, snapshot))
reinforcement.ready, reinforcement.cooldown_left, reinforcement.last_cooldown = false, 119.8, 5.7
boundary, snapshot, reason = Data.sample(hub)
assert(reason == 'READY_STATUS' and snapshot.reinforcement_long_cooldown and snapshot.reinforcements == nil)
assert(confirm(cooldown_policy, snapshot), 'observed ready-to-long-cooldown transition must trigger')
local solo_snapshot = {}
for key, value in pairs(snapshot) do solo_snapshot[key] = value end
solo_snapshot.seats = 1
assert(not confirm(Policy.new(), solo_snapshot), 'solo hot start already depleted must wait for observed availability')
reinforcement.cooldown_left = 3
boundary, snapshot = Data.sample(hub)
assert(not snapshot.reinforcement_long_cooldown)
assert(confirm(cooldown_policy, snapshot), 'confirmed depletion must persist through the countdown tail')
reinforcement.ready, reinforcement.cooldown_left = true, 0
boundary, snapshot = Data.sample(hub)
assert(not observe(cooldown_policy, snapshot), 'restored readiness must immediately stop')
reinforcement.ready, reinforcement.cooldown_left = false, 5.7
boundary, snapshot = Data.sample(hub)
assert(not confirm(cooldown_policy, snapshot), 'an ordinary short cooldown must not imply depletion')
reinforcement.cooldown_left = 0
boundary, snapshot, reason = Data.sample(hub)
assert(reason == 'REINFORCEMENT_STATUS_CONFLICT' and snapshot.reinforcements == nil)
reinforcement.ready, reinforcement.cooldown_left = true, 0
boundary, snapshot = Data.sample(hub)
observe(cooldown_policy, snapshot)
reinforcement.ready, reinforcement.cooldown_left = false, 120
boundary, snapshot = Data.sample(hub)
assert(confirm(cooldown_policy, snapshot))
assert(not observe(cooldown_policy, snapshot, {in_mission = true, epoch = 2}), 'mission changes must clear status-based arming')
for _, duration in ipairs({8, 30, 90, 180, 300}) do
    local variable_policy = Policy.new()
    observe(variable_policy, {seats = 1, alive_players = 1, reinforcement_source = 'hub_global_cooldown',
        reinforcement_ready = true, reinforcement_cooldown = 0})
    assert(confirm(variable_policy, {seats = 1, alive_players = 1, reinforcement_source = 'hub_global_cooldown',
        reinforcement_ready = false, reinforcement_cooldown = duration, reinforcement_long_cooldown = true}),
        'depletion must not assume a fixed 120-second duration')
end
reinforcement.cooldown_base, reinforcement.last_cooldown, reinforcement.cooldown_left = 1, 1, 4
boundary, snapshot = Data.sample(hub)
assert(snapshot.reinforcement_long_cooldown, 'normal cooldown baseline must come from the current Hub values')
reinforcement.unlimited, reinforcement.uses = false, 0
roster[2].alive = nil
boundary, snapshot, reason = Data.sample(hub)
assert(snapshot == nil and reason == 'INCOMPLETE_PLAYERS')
roster[2].alive = false
strata[2] = {slot = 1, stratagems = {{type = 127, unlimited = false, uses = 2}}}
boundary, snapshot, reason = Data.sample(hub)
assert(reason == 'REINFORCEMENT_COUNT_CONFLICT' and snapshot.reinforcements == nil)
strata[2] = nil
local mission_calls = 0
hub.mission = function()
    mission_calls = mission_calls + 1
    return {in_mission = true, epoch = mission_calls}
end
boundary, snapshot, reason = Data.sample(hub)
assert(boundary == nil and snapshot == nil and reason == 'MISSION_CHANGED_DURING_SAMPLE')
assert(select(3, Data.sample(nil)) == 'HUB_NOT_READY')

local plays, pauses, resumes, releases, uploads, halts = 0, 0, 0, 0, 0, 0
local ready, gain, voice_state = false, 0, 'paused'
local api = {
    api = 2,
    define_format = function() return true end,
    pool = function(namespace, roles) assert(roles.music == 1); return true end,
    upload = function() uploads = uploads + 1; return true end,
    ready = function() return ready end,
    status = function() return {pool = 1, free = {music = 0}} end,
    play = function(namespace, key, options)
        assert(options.role == 'music' and options.volume == 0 and options.loop and options.paused)
        plays = plays + 1; voice_state = 'paused'; return plays
    end,
    resume = function(h) assert(h == plays); resumes = resumes + 1; voice_state = 'playing'; return true end,
    pause = function(h) assert(h == plays); pauses = pauses + 1; voice_state = 'paused'; return true end,
    set = function(h, opts) assert(h == plays); gain = opts.volume; return true end,
    info = function() return {state = voice_state, position = voice_state == 'playing' and 1 or 0} end,
    halt = function() halts = halts + 1; voice_state = 'ended'; return true end,
    release = function() releases = releases + 1; return true end
}
MDL3 = {audio = api}
local audio = Audio.new('format', 'content', function() end)
for i = 1, 44 do audio.update(0.25, true, 50, 1) end
assert(uploads == 1 and plays == 0)
ready = true
assert(audio.update(0.25, false, 50, 1) == 'AUDIO_PREPARING')
assert(audio.update(0.25, false, 50, 1) == 'AUDIO_READY')
assert(plays == 1 and resumes == 0, 'prewarm must remain silent and paused')
assert(audio.update(0.25, true, 50, 1) == 'AUDIO_START_PENDING', 'queued resume is not confirmed playback')
for i = 1, 4 do assert(audio.update(0.25, true, 50, 1) == 'AUDIO_PLAYING') end
assert(gain == 50 and plays == 1 and resumes == 1, 'one second fade-in on the numeric handle')
for i = 1, 4 do audio.update(0.25, true, 80, 1) end
assert(gain == 80 and plays == 1 and resumes == 1, 'live volume must preserve the handle')
assert(audio.update(0.25, false, 80, 2) == 'AUDIO_FADING_OUT')
assert(gain == 70 and pauses == 0)
-- A new trigger during fade-out must halt the old handle and prepare a new one.
assert(audio.update(0.25, true, 80, 2) == 'AUDIO_RESTARTING')
assert(halts == 1 and plays == 1)
assert(audio.update(0.25, true, 80, 2) == 'AUDIO_PREPARING')
for i = 1, 6 do audio.update(0.25, true, 80, 2) end
assert(gain == 80 and pauses == 0 and plays == 2, 'retrigger starts a new handle at the beginning')
for i = 1, 8 do audio.update(0.25, false, 80, 2) end
assert(gain == 0 and pauses == 1 and voice_state == 'paused', 'fade-out completes before resting')
for i = 1, 8 do audio.update(0.25, true, 50, 1) end
assert(plays == 3 and resumes == 3 and gain == 50 and halts == 2, 'retrigger after pause replaces the old handle')
assert(uploads == 1, 'restarting must reuse the uploaded asset')
for i = 1, 4 do audio.update(0.25, true, 0, 1) end
assert(gain == 0 and pauses == 2, 'mute preserves playback position within the same trigger')
-- Failed volume submission must be retried rather than falsely completing a fade.
api.set = function() return false end
assert(audio.update(0.25, true, 50, 1) == 'AUDIO_CONTROL_PENDING')
api.set = function(h, opts) gain = opts.volume; return true end
for i = 1, 4 do audio.update(0.25, true, 50, 1) end
assert(gain == 50)
voice_state = 'ended'
audio.update(0.25, true, 50, 1)
for i = 1, 4 do audio.update(0.25, true, 50, 1) end
assert(plays == 4, 'unexpected voice end recreates after backoff')
-- An unacknowledged handle cannot be labelled as audible playback.
api.info = function() return nil, 'not acknowledged' end
assert(audio.update(0.25, true, 50, 1) == 'AUDIO_PREPARING')
MDL3 = nil
audio.update(0.25, true, 50, 1)
assert(releases == 1, 'API disappearance must release the old namespace')
MDL3 = {audio = api}
api.status = function() return {pool = 0, failed = 'audio setup retry limit'} end
assert(audio.update(0.25, true, 50, 1) == 'AUDIO_FAILED audio setup retry limit')
audio.close(); audio.close()
api.api = 1
MDL3 = {audio = api}
assert(audio.update(0.25, true, 50, 1) == 'AUDIO_FAILED api_2_required')
audio.close(); MDL3 = nil
print('PASS: API 2 numeric handles, silent preparation, loop, fades, retrigger from beginning, no reupload, live volume, mute, retry, cleanup')
print('PASS: MDL policy, unavailable reinforcement, data boundaries')
