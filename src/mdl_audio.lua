local Audio = {}
local namespace = 'rainie_love_mdl_music'

local function invoke(api, name, ...)
    if type(api) ~= 'table' or type(api[name]) ~= 'function' then return nil, 'missing audio.' .. name end
    local ok, value, reason = pcall(api[name], ...)
    if not ok then return nil, tostring(value) end
    return value, reason
end

function Audio.new(format, content, report)
    local state = {api = nil, registered = false, handle = nil, running = false,
        gain = 0, target = 0, from = 0, elapsed = 0, duration = 1, clock = 0, retry = 0, resume_at = nil, last_wanted = false, started = false, restart = false}
    local backend = {}
    local function clear_handle()
        state.handle, state.running, state.gain, state.target = nil, false, 0, 0
        state.from, state.elapsed, state.resume_at = 0, 0, nil
        state.started, state.restart = false, false
    end
    local function release()
        if state.api then invoke(state.api, 'release', namespace) end
        state.api, state.registered = nil, false
        clear_handle()
    end
    function backend.update(seconds, wanted, volume, fade_out)
        state.clock = state.clock + seconds
        if wanted and not state.last_wanted and state.started then state.restart = true end
        state.last_wanted = wanted
        local mdl = rawget(_G, 'MDL3')
        local api = type(mdl) == 'table' and mdl.audio or nil
        if state.api ~= api then release(); state.api, state.retry = api, 0 end
        if not api then return 'AUDIO_API_MISSING' end
        if type(api.api) ~= 'number' or api.api < 2 then return 'AUDIO_FAILED api_2_required' end
        if not state.registered then
            if state.clock < state.retry then return 'AUDIO_RETRY' end
            state.retry = state.clock + 10
            local ok, reason = invoke(api, 'define_format', namespace, format)
            if ok == true then ok, reason = invoke(api, 'pool', namespace, {music = 1}) end
            if ok == true then ok, reason = invoke(api, 'upload', namespace, 'song', content) end
            if ok ~= true then
                invoke(api, 'release', namespace)
                report('AUDIO_REGISTER_FAILED ' .. tostring(reason))
                return 'AUDIO_REGISTER_FAILED'
            end
            state.registered, state.retry = true, state.clock
            report('AUDIO_UPLOAD_QUEUED api=2')
        end
        local status = invoke(api, 'status', namespace)
        if type(status) == 'table' and status.failed ~= nil and status.failed ~= false and
           status.failed ~= 0 and status.failed ~= '' then
            if state.handle then invoke(api, 'halt', state.handle); clear_handle() end
            return 'AUDIO_FAILED ' .. tostring(status.failed)
        end
        local ready, reason = invoke(api, 'ready', namespace, 'song')
        if ready ~= true then
            if type(reason) == 'string' and reason:find('upload this asset again', 1, true) and state.clock >= state.retry then
                clear_handle()
                local uploaded = invoke(api, 'upload', namespace, 'song', content)
                state.retry = state.clock + 10
                if uploaded then report('AUDIO_REUPLOAD_QUEUED') end
            end
            return 'AUDIO_LOADING'
        end
        if type(status) ~= 'table' or (tonumber(status.pool) or 0) < 1 then return 'AUDIO_VOICE_WAIT' end
        if state.restart and state.handle then
            if not invoke(api, 'halt', state.handle) then return 'AUDIO_CONTROL_PENDING' end
            report('AUDIO_RESTART_FROM_BEGINNING old_handle=' .. tostring(state.handle))
            clear_handle()
            state.retry = state.clock + 0.05
            return 'AUDIO_RESTARTING'
        end
        local info, info_reason
        if state.handle then
            info, info_reason = invoke(api, 'info', state.handle)
            if type(info) == 'table' and info.state == 'ended' then
                report('AUDIO_HANDLE_ENDED ' .. tostring(info.why))
                clear_handle()
                state.retry = state.clock + 1
            end
        end
        if not state.handle then
            if state.clock < state.retry then return 'AUDIO_START_PENDING' end
            local handle, why = invoke(api, 'play', namespace, 'song',
                {role = 'music', volume = 0, paused = true, loop = true})
            state.retry = state.clock + 0.1
            if type(handle) ~= 'number' or handle <= 0 or handle ~= math.floor(handle) then
                if why then report('AUDIO_PLAY_REFUSED ' .. tostring(why)) end
                return 'AUDIO_START_PENDING'
            end
            state.handle = handle
            report('AUDIO_PREPARED handle=' .. tostring(handle))
            return 'AUDIO_PREPARING'
        end
        local target = wanted and volume > 0 and volume or 0
        if target > 0 and not state.running then
            -- play() and controls are asynchronous; wait for native preparation acknowledgement.
            if type(info) ~= 'table' or (info.state ~= 'paused' and info.state ~= 'playing') then
                return 'AUDIO_PREPARING'
            end
            local resumed = invoke(api, 'resume', state.handle)
            if not resumed then return 'AUDIO_START_PENDING' end
            state.running, state.resume_at, state.started = true, state.clock, true
            report('AUDIO_RESUME handle=' .. tostring(state.handle))
        end
        if target ~= state.target then
            state.from, state.target, state.elapsed = state.gain, target, 0
            state.duration = target == 0 and math.max(1, math.min(30, fade_out or 1)) or 1
            report('AUDIO_FADE target=' .. tostring(target) .. ' seconds=' .. tostring(state.duration))
        end
        if state.gain ~= state.target then
            local elapsed = math.min(state.elapsed + seconds, state.duration)
            local gain = state.from + (state.target - state.from) * elapsed / state.duration
            local changed = invoke(api, 'set', state.handle, {volume = gain})
            if not changed then return 'AUDIO_CONTROL_PENDING' end
            state.elapsed, state.gain = elapsed, gain
        end
        if state.target == 0 and state.gain == 0 and state.running then
            if not invoke(api, 'pause', state.handle) then return 'AUDIO_CONTROL_PENDING' end
            state.running = false
            report('AUDIO_PAUSE handle=' .. tostring(state.handle))
        end
        if target > 0 then
            if type(info) == 'table' and info.state == 'playing' and
               type(info.position) == 'number' and info.position > 0 then return 'AUDIO_PLAYING' end
            if state.resume_at and state.clock - state.resume_at > 5 then return 'AUDIO_NATIVE_WAIT' end
            return 'AUDIO_START_PENDING'
        end
        return state.running and 'AUDIO_FADING_OUT' or 'AUDIO_READY'
    end
    function backend.close() release() end
    return backend
end

return Audio
