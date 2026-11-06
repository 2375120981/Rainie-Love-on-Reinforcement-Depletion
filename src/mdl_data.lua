local Data = {}

local function call(function_value, ...)
    if type(function_value) ~= 'function' then return nil end
    local ok, value = pcall(function_value, ...)
    if ok then return value end
end

function Data.sample(hub)
    if type(hub) ~= 'table' or call(hub.ready) ~= true then
        return nil, nil, 'HUB_NOT_READY'
    end
    local mission = call(hub.mission)
    if type(mission) ~= 'table' or type(mission.in_mission) ~= 'boolean' then
        return nil, nil, 'WAIT_MISSION'
    end
    if not mission.in_mission then return mission, nil, 'OUTSIDE_MISSION' end
    local players = call(hub.players)
    local stratagems = call(hub.stratagems)
    if type(players) ~= 'table' or #players < 1 or #players > 4 then
        return mission, nil, 'WAIT_PLAYERS'
    end
    local alive, slots = 0, {}
    for _, player in ipairs(players) do
        if type(player) ~= 'table' or type(player.slot) ~= 'number' or
           player.slot < 0 or player.slot > 3 or player.slot ~= math.floor(player.slot) or
           slots[player.slot] or type(player.alive) ~= 'boolean' then
            return mission, nil, 'INCOMPLETE_PLAYERS'
        end
        slots[player.slot] = true
        if player.alive then alive = alive + 1 end
    end
    local sample = {seats = #players, alive_players = alive}
    if type(stratagems) ~= 'table' then return mission, sample, 'WAIT_STRATAGEMS' end
    local uses
    local cooldown, ready, normal_cooldown
    local source
    local observed = false
    for _, player in ipairs(stratagems) do
        if type(player) == 'table' and slots[player.slot] and type(player.stratagems) == 'table' then
            for _, stratagem in ipairs(player.stratagems) do
                if type(stratagem) == 'table' and stratagem.type == 127 then
                    observed = true
                    if stratagem.unlimited == false and type(stratagem.uses) == 'number' and
                       stratagem.uses >= 0 and stratagem.uses < math.huge and stratagem.uses == math.floor(stratagem.uses) then
                        if source and source ~= 'hub_uses' then return mission, sample, 'REINFORCEMENT_SOURCE_CONFLICT' end
                        if uses ~= nil and uses ~= stratagem.uses then return mission, sample, 'REINFORCEMENT_COUNT_CONFLICT' end
                        uses, source = stratagem.uses, 'hub_uses'
                    elseif stratagem.unlimited == true and type(stratagem.ready) == 'boolean' and
                           type(stratagem.cooldown_left) == 'number' and stratagem.cooldown_left >= 0 and
                           stratagem.cooldown_left < math.huge and type(stratagem.cooldown_base) == 'number' and
                           stratagem.cooldown_base >= 0 and stratagem.cooldown_base < math.huge then
                        if source and source ~= 'hub_global_cooldown' then return mission, sample, 'REINFORCEMENT_SOURCE_CONFLICT' end
                        if stratagem.ready ~= (stratagem.cooldown_left == 0) then return mission, sample, 'REINFORCEMENT_STATUS_CONFLICT' end
                        if ready ~= nil and (ready ~= stratagem.ready or math.abs(cooldown - stratagem.cooldown_left) > 0.5) then
                            return mission, sample, 'REINFORCEMENT_STATUS_CONFLICT'
                        end
                        local baseline = stratagem.cooldown_base
                        if type(stratagem.last_cooldown) == 'number' and stratagem.last_cooldown >= 0 and stratagem.last_cooldown < math.huge then
                            baseline = math.max(baseline, stratagem.last_cooldown)
                        end
                        cooldown, ready, normal_cooldown = stratagem.cooldown_left, stratagem.ready, math.max(normal_cooldown or 0, baseline)
                        source = 'hub_global_cooldown'
                    else
                        return mission, sample, 'REINFORCEMENT_COUNT_UNAVAILABLE'
                    end
                end
            end
        end
    end
    if not observed then return mission, sample, 'WAIT_REINFORCEMENT_ENTRY' end
    local current = call(hub.mission)
    if type(current) ~= 'table' or current.in_mission ~= true or current.epoch ~= mission.epoch then
        return nil, nil, 'MISSION_CHANGED_DURING_SAMPLE'
    end
    sample.reinforcements = uses
    sample.reinforcement_source = source
    if source == 'hub_global_cooldown' then
        sample.reinforcement_ready = ready
        sample.reinforcement_cooldown = cooldown
        sample.reinforcement_long_cooldown = not ready and cooldown > normal_cooldown + 1
        return mission, sample, 'READY_STATUS'
    end
    return mission, sample, 'READY'
end

return Data
