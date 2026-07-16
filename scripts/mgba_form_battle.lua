local output_dir = os.getenv("MGBA_FORM_BATTLE_OUTPUT") or "."
local release_version = os.getenv("EMERALD_RELEASE_VERSION") or "1.3.1"
local symbols_path = assert(os.getenv("MGBA_FORM_BATTLE_SYMBOLS"), "MGBA_FORM_BATTLE_SYMBOLS is required")
local report_path = output_dir .. "/mgba_form_battle_raw.json"
local maximum_frames = 5000
local samples = {}
local captured = {}
local finished = false
local frame_callback = nil

local required_symbols = {
    "gFormBattleTestState",
    "gFormBattleTestCase",
    "gFormBattleTestMode",
    "gFormBattleTestExpectedValue",
    "gFormBattleTestPlayerValue",
    "gFormBattleTestOpponentValue",
    "gFormBattleTestPlayerResult",
    "gFormBattleTestOpponentResult",
    "gFormBattleTestError",
    "gFormBattleTestBackPaletteNum",
    "gFormBattleTestFrontPaletteNum",
    "gFormBattleTestReadyMask",
    "gFormBattleTestBackTileNum",
    "gFormBattleTestFrontTileNum",
    "gFormBattleTestBackSpecies",
    "gFormBattleTestFrontSpecies",
    "gFormBattleTestBackPersonality",
    "gFormBattleTestFrontPersonality",
    "gBattleWeather",
    "gBattleMonForms",
}


local function json_escape(value)
    return tostring(value)
        :gsub("\\", "\\\\")
        :gsub('"', '\\"')
        :gsub("\n", "\\n")
        :gsub("\r", "\\r")
end


local function load_symbols(path)
    local symbols = {}
    local file = assert(io.open(path, "r"))
    for line in file:lines() do
        local address, name = line:match("^([0-9a-fA-F]+)%s+[%a]%s+([^%s]+)$")
        if address and name then
            symbols[name] = tonumber(address, 16)
        end
    end
    file:close()

    for _, name in ipairs(required_symbols) do
        assert(symbols[name], "Missing diagnostic symbol: " .. name)
    end
    return symbols
end


local symbols = load_symbols(symbols_path)


local function read32(address)
    return emu:read16(address) | (emu:read16(address + 2) << 16)
end


local function memory_sample(first, size)
    local count = 0
    local signature = 2166136261
    for address = first, first + size - 2, 2 do
        local value = emu:read16(address)
        if value ~= 0 then
            count = count + 1
        end
        signature = ((signature ~ value) * 16777619) & 0x7FFFFFFF
    end
    return count, signature
end


local function capture_case(case_id)
    local back_tile_num = emu:read16(symbols.gFormBattleTestBackTileNum)
    local front_tile_num = emu:read16(symbols.gFormBattleTestFrontTileNum)
    local back_palette_num = emu:read8(symbols.gFormBattleTestBackPaletteNum)
    local front_palette_num = emu:read8(symbols.gFormBattleTestFrontPaletteNum)
    local back_tiles_nonzero, back_tiles_signature = memory_sample(0x06010000 + back_tile_num * 32, 2048)
    local front_tiles_nonzero, front_tiles_signature = memory_sample(0x06010000 + front_tile_num * 32, 2048)
    local back_palette_nonzero, back_palette_signature = memory_sample(0x05000200 + back_palette_num * 32, 32)
    local front_palette_nonzero, front_palette_signature = memory_sample(0x05000200 + front_palette_num * 32, 32)

    table.insert(samples, {
        case_id = case_id,
        frame = emu:currentFrame(),
        state = emu:read8(symbols.gFormBattleTestState),
        mode = emu:read8(symbols.gFormBattleTestMode),
        expected_value = emu:read8(symbols.gFormBattleTestExpectedValue),
        player_value = emu:read8(symbols.gFormBattleTestPlayerValue),
        opponent_value = emu:read8(symbols.gFormBattleTestOpponentValue),
        player_result = emu:read8(symbols.gFormBattleTestPlayerResult),
        opponent_result = emu:read8(symbols.gFormBattleTestOpponentResult),
        error = emu:read8(symbols.gFormBattleTestError),
        weather = emu:read16(symbols.gBattleWeather),
        player_form = emu:read8(symbols.gBattleMonForms),
        opponent_form = emu:read8(symbols.gBattleMonForms + 1),
        back_species = emu:read16(symbols.gFormBattleTestBackSpecies),
        front_species = emu:read16(symbols.gFormBattleTestFrontSpecies),
        back_personality = read32(symbols.gFormBattleTestBackPersonality),
        front_personality = read32(symbols.gFormBattleTestFrontPersonality),
        back_tile_num = back_tile_num,
        front_tile_num = front_tile_num,
        back_palette_num = back_palette_num,
        front_palette_num = front_palette_num,
        back_tiles_nonzero = back_tiles_nonzero,
        back_tiles_signature = back_tiles_signature,
        front_tiles_nonzero = front_tiles_nonzero,
        front_tiles_signature = front_tiles_signature,
        back_palette_nonzero = back_palette_nonzero,
        back_palette_signature = back_palette_signature,
        front_palette_nonzero = front_palette_nonzero,
        front_palette_signature = front_palette_signature,
        pc = emu:readRegister("pc"),
    })
end


local function write_report(status, crashed)
    local file = assert(io.open(report_path, "w"))
    file:write("{\n")
    file:write(string.format('  "version": "%s",\n', json_escape(release_version)))
    file:write(string.format('  "status": "%s",\n', json_escape(status)))
    file:write(string.format('  "crashed": %s,\n', crashed and "true" or "false"))
    file:write(string.format('  "game_title": "%s",\n', json_escape(emu:getGameTitle())))
    file:write(string.format('  "game_code": "%s",\n', json_escape(emu:getGameCode())))
    file:write(string.format('  "rom_size": %d,\n', emu:romSize()))
    file:write(string.format('  "frames_reached": %d,\n', emu:currentFrame()))
    file:write(string.format('  "final_state": %d,\n', emu:read8(symbols.gFormBattleTestState)))
    file:write(string.format('  "final_error": %d,\n', emu:read8(symbols.gFormBattleTestError)))
    file:write(string.format('  "final_ready_mask": %d,\n', emu:read16(symbols.gFormBattleTestReadyMask)))
    file:write('  "case_samples": [\n')
    for index, sample in ipairs(samples) do
        file:write(string.format(
            '    {"case": %d, "frame": %d, "state": %d, "mode": %d, '
                .. '"expected_value": %d, "player_value": %d, "opponent_value": %d, '
                .. '"player_result": %d, "opponent_result": %d, "error": %d, '
                .. '"weather": %d, "player_form": %d, "opponent_form": %d, '
                .. '"back_species": %d, "front_species": %d, '
                .. '"back_personality": %u, "front_personality": %u, '
                .. '"back_tile_num": %d, "front_tile_num": %d, '
                .. '"back_palette_num": %d, "front_palette_num": %d, '
                .. '"back_tiles_nonzero": %d, "back_tiles_signature": %d, '
                .. '"front_tiles_nonzero": %d, "front_tiles_signature": %d, '
                .. '"back_palette_nonzero": %d, "back_palette_signature": %d, '
                .. '"front_palette_nonzero": %d, "front_palette_signature": %d, '
                .. '"pc": %d}%s\n',
            sample.case_id,
            sample.frame,
            sample.state,
            sample.mode,
            sample.expected_value,
            sample.player_value,
            sample.opponent_value,
            sample.player_result,
            sample.opponent_result,
            sample.error,
            sample.weather,
            sample.player_form,
            sample.opponent_form,
            sample.back_species,
            sample.front_species,
            sample.back_personality,
            sample.front_personality,
            sample.back_tile_num,
            sample.front_tile_num,
            sample.back_palette_num,
            sample.front_palette_num,
            sample.back_tiles_nonzero,
            sample.back_tiles_signature,
            sample.front_tiles_nonzero,
            sample.front_tiles_signature,
            sample.back_palette_nonzero,
            sample.back_palette_signature,
            sample.front_palette_nonzero,
            sample.front_palette_signature,
            sample.pc,
            index < #samples and "," or ""
        ))
    end
    file:write("  ]\n")
    file:write("}\n")
    file:close()
end


local function finish(status, crashed)
    if finished then
        return
    end
    finished = true
    write_report(status, crashed)
    if frame_callback then
        callbacks:remove(frame_callback)
    end
end


callbacks:add("crashed", function()
    finish("crashed", true)
end)


frame_callback = callbacks:add("frame", function()
    local state = emu:read8(symbols.gFormBattleTestState)
    local case_id = emu:read8(symbols.gFormBattleTestCase)

    if state >= 1 and case_id >= 1 and case_id <= 9 and not captured[case_id] then
        capture_case(case_id)
        captured[case_id] = true
    end

    if state == 2 then
        local header_ok = emu:getGameTitle() == "POKEMON EMER"
            and emu:getGameCode() == "BPEE"
            and emu:romSize() == 16777216
        finish(header_ok and #samples == 9 and "passed" or "incomplete", false)
    elseif emu:currentFrame() >= maximum_frames then
        finish("timeout", false)
    end
end)
