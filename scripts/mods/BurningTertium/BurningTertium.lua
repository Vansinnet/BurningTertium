---@class BurningTertiumMod : DMFMod
local mod = get_mod("BurningTertium")

---@type number[][]
local roofs = mod:io_dofile("BurningTertium/scripts/mods/BurningTertium/roof_positions")
local hub_level = "content/levels/hub/hub_ship/mourningstar/world.level"
local package_reference = "BurningTertium"
local burning = "content/fx/particles/enemies/buff_burning"
-- buff_burning emits its flames from an enemy mesh (material_emission), so free-standing it only
-- gives smoke; the burning stacks gave embers. Liquid-area fire cells are spawned free-standing
-- with World.create_particles by the game itself (liquid_area_extension / liquid_area_drawer).
local smoke = { name = burning, package = true, scale = 1, step = 6, offset = 1 }
-- Liquid-area fire has a finite lifetime (~10 s observed), so each flame is re-lit before it ends.
local function fire(name, step)
    return { { name = name, package = true, scale = 1, step = step, renew = 7 }, smoke }
end
local modes = {
    fire = fire("content/fx/particles/weapons/grenades/fire_grenade/fire_grenade_player_lingering_fire", 3),
    fire2 = fire("content/fx/particles/liquid_area/fire_lingering", 3),
    fire3 = fire("content/fx/particles/liquid_area/promethium_fire_lingering", 3),
    smoke = {
        { name = burning, package = true, scale = 1, step = 2 },
    },
    candle = {
        { name = "content/fx/particles/burning_tertium/hologram_flame_red", scale = 5, step = 1 },
    },
}
local batch_size = 6
local batch_interval = 0.04
local enabled = true
local mode = "fire"
local first_step
local world
local package_ids = {}
local particle_ids = {}
local renewals = {}
local clock = 0
local layer = 1
local next_roof = 1
local batch_time = 0

local function cleanup()
    local current_world = Managers.world and Managers.world:world("level_world")
    if world and world == current_world then
        for i = 1, #particle_ids do
            local id = particle_ids[i]
            if World.are_particles_playing(world, id) then
                World.destroy_particles(world, id)
            end
        end
    end
    table.clear(particle_ids)
    table.clear(renewals)
    if Managers.package then
        for i = 1, #package_ids do
            Managers.package:release(package_ids[i])
        end
    end
    table.clear(package_ids)
    world = nil
    layer = 1
    next_roof = 1
    batch_time = 0
end

local function spawn(effect, p)
    local scale = Vector3(effect.scale, effect.scale, effect.scale)
    local id = World.create_particles(world, effect.name, Vector3(p[1], p[2], p[3] + 0.02),
        Quaternion.identity(), scale)
    if id then
        particle_ids[#particle_ids + 1] = id
    end
    return id
end

local function renew_flames()
    local renewed = false
    for i = 1, #renewals do
        local entry = renewals[i]
        if clock >= entry.due then
            spawn(entry.effect, entry.roof)
            entry.due = clock + entry.effect.renew
            renewed = true
        end
    end
    if not renewed then
        return
    end
    for i = #particle_ids, 1, -1 do
        if not World.are_particles_playing(world, particle_ids[i]) then
            table.remove(particle_ids, i)
        end
    end
end

local function packages_ready(layers)
    if #package_ids == 0 then
        for i = 1, #layers do
            if layers[i].package then
                package_ids[#package_ids + 1] = Managers.package:load(layers[i].name, package_reference)
            end
        end
    end
    for i = 1, #package_ids do
        if not Managers.package:has_loaded_id(package_ids[i]) then
            return false
        end
    end
    return true
end

mod.update = function(dt)
    if not enabled or DEDICATED_SERVER or not mod:is_enabled() then
        if world then
            cleanup()
        end
        return
    end
    local game_mode = Managers.state and Managers.state.game_mode
    if not game_mode or game_mode:game_mode_name() ~= "hub" then
        if world then
            cleanup()
        end
        return
    end
    local current_world = Managers.world and Managers.world:world("level_world")
    if not current_world then
        if world then
            cleanup()
        end
        return
    end
    local levels = World.get_data(current_world, "levels")
    if not levels or not levels[hub_level] then
        if world then
            cleanup()
        end
        return
    end
    if world ~= current_world then
        cleanup()
        world = current_world
        batch_time = batch_interval
    end
    clock = clock + dt
    local layers = modes[mode]
    if layer > #layers then
        if #renewals > 0 then
            renew_flames()
        end
        return
    end
    if not packages_ready(layers) then
        return
    end
    batch_time = batch_time + dt
    if batch_time < batch_interval then
        return
    end
    batch_time = 0
    local effect = layers[layer]
    if next_roof == 1 then
        next_roof = 1 + (effect.offset or 0)
    end
    local step = layer == 1 and first_step or effect.step
    local created = 0
    while next_roof <= #roofs and created < batch_size do
        local p = roofs[next_roof]
        next_roof = next_roof + step
        if spawn(effect, p) and effect.renew then
            -- Stagger the first renewal so re-lighting is spread out instead of pulsing together.
            renewals[#renewals + 1] = { effect = effect, roof = p,
                due = clock + effect.renew * (0.5 + 0.5 * math.random()) }
        end
        created = created + 1
    end
    if next_roof > #roofs then
        layer = layer + 1
        next_roof = 1
    end
end

mod.on_game_state_changed = function(status, state_name)
    if status == "exit" and state_name == "StateGameplay" then
        cleanup()
    end
end

mod.on_unload = cleanup

first_step = modes[mode][1].step

mod:command("bt_flames", "Roof flames: /bt_flames fire|fire2|fire3|smoke|candle [every Nth roof 1-20], off, status.",
    function(choice, every)
        local n = tonumber(choice)
        if n then
            choice, every = mode, n
        end
        if choice == "off" then
            enabled = false
            cleanup()
            mod:echo("Roof flames off.")
        elseif choice == "status" then
            mod:echo("Roof flames: %s, %d effects, every %d of %d roofs, enabled=%s",
                mode, #particle_ids, first_step, #roofs, tostring(enabled))
        elseif choice == nil or choice == "roofs" or modes[choice] then
            if modes[choice] then
                mode = choice
            end
            local step = tonumber(every)
            first_step = step and math.clamp(math.floor(step), 1, 20) or modes[mode][1].step
            cleanup()
            enabled = true
            mod:echo("Roof flames: %s on every %d of %d roofs.", mode, first_step, #roofs)
        else
            mod:echo("Use /bt_flames fire|fire2|fire3|smoke|candle [1-20], off, or status")
        end
    end)
