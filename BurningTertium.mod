return {
    run = function()
        fassert(rawget(_G, "new_mod"), "`BurningTertium` failed loading DMF.")
        new_mod("BurningTertium", {
            mod_script = "BurningTertium/scripts/mods/BurningTertium/BurningTertium",
            mod_data = "BurningTertium/scripts/mods/BurningTertium/BurningTertium_data",
            mod_localization = "BurningTertium/scripts/mods/BurningTertium/BurningTertium_localization",
        })
    end,
    packages = {},
}
