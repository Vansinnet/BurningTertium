local mod = get_mod("BurningTertium")
local redirect = mod:io_dofile("BurningTertium/scripts/mods/BurningTertium/asset_redirect")

if not redirect then
    mod:error("BurningTertium could not load Asset Redirect; the hologram will remain stock.")
    return nil
end

local materials = {
    { stock = "data/ba/bacd9b3be2a4c57f", file = "bacd9b3be2a4c57f.btmat",
        sha256 = "e0d63444385473b9b4e299318cd3fdc85e2188f9df9da06ab2224a41654cb616" },
    { stock = "data/97/97b5490a85966a77", file = "97b5490a85966a77.btmat",
        sha256 = "28a94fa9b2a988d8dd93925c40e4687091b6e766f57d1c283eab9fddbaa03a03" },
    { stock = "data/51/51f7e0e66641669b", file = "51f7e0e66641669b.btmat",
        sha256 = "078ed294f4bab50fa984a035d9c94da4e5521da858c148cc52316f5fcfe448e8" },
    { stock = "data/59/59c4260bff372016", file = "59c4260bff372016.btmat",
        sha256 = "c49cba30643a8c863c2818df51bbf5f761f7dc0cd32c4912b3d51d037e655db4" },
}

local handles = {}
for i = 1, #materials do
    local material = materials[i]
    handles[i] = redirect.register(mod, {
        stock = material.stock,
        file = "payload/redirect/" .. material.file,
        sha256 = material.sha256,
    })
end

return {
    commit = function()
        redirect.commit()
        for i = 1, #materials do
            local state = redirect.state(handles[i])
            mod:info("hologram material %s: %s", materials[i].stock, state)
            if state == "restart_required" then
                mod:echo("BurningTertium: restart Darktide to apply the red hologram.")
            elseif state ~= "active" and state ~= "shared" then
                mod:echo("BurningTertium: hologram material %s is %s; see the log.", materials[i].stock, state)
            end
        end
    end,
    clear = function()
        redirect.clear(mod)
    end,
}
