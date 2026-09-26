local mod = get_mod("BurningTertium")
local reforge = mod:io_dofile("BurningTertium/scripts/mods/BurningTertium/reforge")

if not reforge then
    mod:error("BurningTertium could not load Reforge; the hologram will remain stock.")
    return nil
end

-- Four hologram material streams (city, sides, base, grid), each pinned by
-- the stock SHA-256. Edit reforge.json and run `reforge build` to change them.
local manifest = "BurningTertium/scripts/mods/BurningTertium/reforge_manifest"
local handles = reforge.register_manifest(mod, manifest)

return {
    commit = function()
        reforge.commit()
        for i = 1, #handles do
            local handle = handles[i]
            local state = reforge.state(handle)
            mod:info("hologram material %s: %s %s", handle.stock, state, reforge.reason(handle) or "")
            if state == "restart_required" then
                mod:echo("BurningTertium: restart Darktide to apply the red hologram.")
            elseif not reforge.served(state) then
                mod:echo("BurningTertium: hologram material %s is %s; see the log.", handle.stock, state)
            end
        end
    end,
    clear = function()
        reforge.clear(mod)
    end,
}
