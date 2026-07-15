local output_dir = os.getenv("MGBA_MAP_QA_OUTPUT") or "."
local release_version = os.getenv("EMERALD_RELEASE_VERSION") or "1.3.1"
local symbols_path = assert(os.getenv("MGBA_MAP_QA_SYMBOLS"), "MGBA_MAP_QA_SYMBOLS is required")
local report_path = output_dir .. "/mgba_map_qa_raw.json"
local maximum_frames = 8000
local samples = {}
local captured = {}
local finished = false
local frame_callback = nil

local case_names = {
    [1] = "littleroot",
    [2] = "oldale",
    [3] = "route101",
    [4] = "petalburg_woods",
}

local required_symbols = {
    "gMapQaState",
    "gMapQaCase",
    "gMapQaReady",
    "gMapQaAdvance",
    "gMapQaError",
    "gMapQaMapGroup",
    "gMapQaMapNum",
    "gMapQaX",
    "gMapQaY",
    "gMapQaTimer",
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


local function memory_sample(first, size, stride)
    local count = 0
    local signature = 2166136261
    for address = first, first + size - 2, stride do
        local value = emu:read16(address)
        if value ~= 0 then
            count = count + 1
        end
        signature = ((signature ~ value) * 16777619) & 0x7FFFFFFF
    end
    return count, signature
end


local function capture_case(case_id)
    local name = case_names[case_id]
    local screenshot = "map_qa_" .. case_id .. "_" .. name .. ".png"
    emu:screenshot(output_dir .. "/" .. screenshot)
    local vram_nonzero, vram_signature = memory_sample(0x06000000, 0x18000, 16)
    local palette_nonzero, palette_signature = memory_sample(0x05000000, 0x400, 2)
    local oam_nonzero, oam_signature = memory_sample(0x07000000, 0x400, 2)
    table.insert(samples, {
        case_id = case_id,
        name = name,
        frame = emu:currentFrame(),
        map_group = emu:read8(symbols.gMapQaMapGroup),
        map_num = emu:read8(symbols.gMapQaMapNum),
        x = emu:read8(symbols.gMapQaX),
        y = emu:read8(symbols.gMapQaY),
        timer = emu:read16(symbols.gMapQaTimer),
        screenshot = screenshot,
        vram_nonzero = vram_nonzero,
        vram_signature = vram_signature,
        palette_nonzero = palette_nonzero,
        palette_signature = palette_signature,
        oam_nonzero = oam_nonzero,
        oam_signature = oam_signature,
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
    file:write(string.format('  "final_state": %d,\n', emu:read8(symbols.gMapQaState)))
    file:write(string.format('  "final_error": %d,\n', emu:read8(symbols.gMapQaError)))
    file:write('  "case_samples": [\n')
    for index, sample in ipairs(samples) do
        file:write(string.format(
            '    {"case": %d, "name": "%s", "frame": %d, '
                .. '"map_group": %d, "map_num": %d, "x": %d, "y": %d, "timer": %d, '
                .. '"screenshot": "%s", '
                .. '"vram_nonzero": %d, "vram_signature": %d, '
                .. '"palette_nonzero": %d, "palette_signature": %d, '
                .. '"oam_nonzero": %d, "oam_signature": %d, "pc": %d}%s\n',
            sample.case_id,
            json_escape(sample.name),
            sample.frame,
            sample.map_group,
            sample.map_num,
            sample.x,
            sample.y,
            sample.timer,
            json_escape(sample.screenshot),
            sample.vram_nonzero,
            sample.vram_signature,
            sample.palette_nonzero,
            sample.palette_signature,
            sample.oam_nonzero,
            sample.oam_signature,
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
    local state = emu:read8(symbols.gMapQaState)
    local case_id = emu:read8(symbols.gMapQaCase)
    local ready = emu:read8(symbols.gMapQaReady)

    if state == 1 and ready == 1 and case_names[case_id] and not captured[case_id] then
        capture_case(case_id)
        captured[case_id] = true
        emu:write8(symbols.gMapQaAdvance, 1)
    end

    if state == 2 then
        local header_ok = emu:getGameTitle() == "POKEMON EMER"
            and emu:getGameCode() == "BPEE"
            and emu:romSize() == 16777216
        finish(header_ok and #samples == 4 and "passed" or "incomplete", false)
    elseif state == 3 then
        finish("harness_error", false)
    elseif emu:currentFrame() >= maximum_frames then
        finish("timeout", false)
    end
end)
