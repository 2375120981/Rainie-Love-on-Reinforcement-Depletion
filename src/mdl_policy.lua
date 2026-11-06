local Policy = {}

function Policy.new()
    return {active = false, epoch = nil, ending = 0, budget = false, armed = 0, locked = false, cooldown_depleted = false, ended_epoch = nil}
end

function Policy.finish(state, epoch)
    if epoch ~= nil and state.epoch ~= nil and epoch ~= state.epoch then return false end
    state.ended_epoch = epoch or state.epoch
    state.active, state.budget, state.locked, state.armed = false, false, true, 0
    state.cooldown_depleted = false
    return true
end

function Policy.observe(state, mission, sample, seconds)
    if type(mission) ~= 'table' or type(mission.in_mission) ~= 'boolean' then
        state.ending, state.armed = 0, 0
        return false, 'WAIT_MISSION'
    end
    if mission.in_mission == false then
        state.armed = 0
        state.ending = state.ending + 1
        if state.ending >= 2 then
            Policy.finish(state, state.epoch)
        end
        return false, 'OUTSIDE_MISSION'
    end
    state.ending = 0
    if state.ended_epoch ~= nil and mission.epoch == state.ended_epoch then
        state.armed = 0
        return false, 'MISSION_ENDED_LOCK'
    end
    if state.ended_epoch ~= nil and mission.epoch ~= nil and mission.epoch ~= state.ended_epoch then state.ended_epoch = nil end
    if not state.active or (state.epoch ~= nil and mission.epoch ~= nil and state.epoch ~= mission.epoch) then
        state.active, state.budget, state.armed, state.locked = true, false, 0, false
        state.cooldown_depleted = false
    end
    if mission.epoch ~= nil then state.epoch = mission.epoch end
    if type(sample) ~= 'table' then
        state.armed = 0
        return false, 'WAIT_DATA'
    end
    if sample.extraction_seated == true then state.locked = true end
    if state.locked then state.armed = 0; return false, 'EXTRACTION_LOCK' end
    if type(sample.seats) ~= 'number' or sample.seats < 1 or sample.seats > 4 or
       sample.seats ~= math.floor(sample.seats) or
       type(sample.alive_players) ~= 'number' or sample.alive_players < 0 or
       sample.alive_players ~= math.floor(sample.alive_players) or
       sample.alive_players > sample.seats then
        state.armed = 0
        return false, 'WAIT_DATA'
    end
    local depleted
    if type(sample.reinforcements) == 'number' and sample.reinforcements >= 0 and
       sample.reinforcements < math.huge and sample.reinforcements == math.floor(sample.reinforcements) then
        if sample.reinforcements > 0 then state.budget, state.cooldown_depleted = true, false end
        depleted = sample.reinforcements == 0
    elseif sample.reinforcement_source == 'hub_global_cooldown' and type(sample.reinforcement_ready) == 'boolean' and
           type(sample.reinforcement_cooldown) == 'number' and sample.reinforcement_cooldown >= 0 and sample.reinforcement_cooldown < math.huge then
        if sample.reinforcement_ready and sample.reinforcement_cooldown == 0 then
            state.budget, state.cooldown_depleted = true, false
            depleted = false
        elseif not sample.reinforcement_ready and sample.reinforcement_cooldown > 0 then
            if sample.reinforcement_long_cooldown == true then state.cooldown_depleted = true end
            if not state.cooldown_depleted then state.armed = 0; return false, 'SHORT_OR_UNCONFIRMED_COOLDOWN' end
            depleted = true
        else
            state.armed = 0; return false, 'WAIT_DATA'
        end
    else
        state.armed = 0; return false, 'WAIT_DATA'
    end
    if sample.seats > 1 then state.budget = true end
    if not state.budget then state.armed = 0; return false, 'WAIT_FIRST_REINFORCEMENT' end
    if not depleted then state.armed = 0; return false, 'REINFORCEMENTS_AVAILABLE' end
    if sample.alive_players == 0 then state.armed = 0; return false, 'NO_SURVIVORS' end
    if sample.alive_players > 1 then state.armed = 0; return false, 'MULTIPLE_SURVIVORS' end
    state.armed = state.armed + math.max(0, math.min(tonumber(seconds) or 0, 0.25))
    return state.armed >= 1, state.armed >= 1 and 'LAST_STAND' or 'CONFIRMING'
end

return Policy
