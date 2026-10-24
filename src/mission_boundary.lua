-- Independent mission boundary policy. Unknown reads never end a mission.
local M = {}
function M.new()
  return { active = false, identity = nil, ending_samples = 0 }
end
function M.observe(state, sample)
  if not sample then state.ending_samples = 0; return nil end
  if sample.in_mission then
    state.ending_samples = 0
    local changed = state.active and state.identity and sample.identity and
                    state.identity ~= sample.identity
    if not state.active or changed then
      state.active, state.identity = true, sample.identity
      return "started"
    end
    if sample.identity then state.identity = sample.identity end
  elseif state.active then
    state.ending_samples = state.ending_samples + 1
    if state.ending_samples >= 2 then
      state.active, state.identity, state.ending_samples = false, nil, 0
      return "ended"
    end
  end
  return nil
end
return M
