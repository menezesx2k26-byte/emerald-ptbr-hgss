local output_dir = os.getenv("MGBA_QUICK_START_OUTPUT") or "."
local release_version = os.getenv("EMERALD_RELEASE_VERSION") or "1.3.1"
local symbols_path = assert(os.getenv("MGBA_QUICK_START_SYMBOLS"), "MGBA_QUICK_START_SYMBOLS is required")
local report_path = output_dir .. "/mgba_quick_start_raw.json"
local maximum_frames = 4000
local samples = {}
local finished = false
local frame_callback = nil
local state = "main_menu"
local state_frame = 0
local held_key = nil
local release_frame = 0

local required_symbols = {
    "gMain",
    "gTasks",
    "CB2_MainMenu",
    "Task_NewGameBirchSpeech_ChooseGender",
    "Task_NewGameBirchSpeech_WaitPressBeforeNameChoice",
    "CB2_NamingScreen",
    "CB2_Overworld",
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
        assert(symbols[name], "Missing production symbol: " .. name)
    end
    return symbols
end


local symbols = load_symbols(symbols_path)


local function same_pointer(left, right)
    return (left & 0xFFFFFFFE) == (right & 0xFFFFFFFE)
end


local function callback2()
    return emu:read32(symbols.gMain + 4)
end


local function has_task(function_address)
    for task_id = 0, 15 do
        local task = symbols.gTasks + task_id * 40
        if emu:read8(task + 4) ~= 0 and same_pointer(emu:read32(task), function_address) then
            return true
        end
    end
    return false
end


local function press_key(key)
    emu:addKey(key)
    held_key = key
    release_frame = emu:currentFrame() + 2
end


local function capture(label)
    local screenshot = "quick_start_" .. tostring(#samples + 1) .. "_" .. label .. ".png"
    emu:screenshot(output_dir .. "/" .. screenshot)
    table.insert(samples, {
        label = label,
        frame = emu:currentFrame(),
        screenshot = screenshot,
        callback2 = callback2(),
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
    file:write('  "samples": [\n')
    for index, sample in ipairs(samples) do
        file:write(string.format(
            '    {"label": "%s", "frame": %d, "screenshot": "%s", "callback2": %d, "pc": %d}%s\n',
            json_escape(sample.label),
            sample.frame,
            json_escape(sample.screenshot),
            sample.callback2,
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
    if held_key then
        emu:clearKey(held_key)
        held_key = nil
    end
    write_report(status, crashed)
    if frame_callback then
        callbacks:remove(frame_callback)
    end
end


callbacks:add("crashed", function()
    finish("crashed", true)
end)


frame_callback = callbacks:add("frame", function()
    local frame = emu:currentFrame()
    if held_key and frame >= release_frame then
        emu:clearKey(held_key)
        held_key = nil
    end

    if state == "main_menu"
        and frame >= 120
        and same_pointer(callback2(), symbols.CB2_MainMenu)
    then
        capture("main_menu")
        press_key(0) -- GBA_KEY_A
        state = "gender"
    elseif state == "gender"
        and not held_key
        and has_task(symbols.Task_NewGameBirchSpeech_ChooseGender)
    then
        capture("gender")
        press_key(0)
        state = "name_prompt"
    elseif state == "name_prompt"
        and not held_key
        and has_task(symbols.Task_NewGameBirchSpeech_WaitPressBeforeNameChoice)
    then
        capture("name_prompt")
        press_key(0)
        state = "naming_screen"
    elseif state == "naming_screen"
        and same_pointer(callback2(), symbols.CB2_NamingScreen)
    then
        if state_frame == 0 then
            state_frame = frame
        elseif frame - state_frame >= 60 and not held_key then
            capture("naming_screen")
            press_key(3) -- GBA_KEY_START moves the cursor to OK.
            state = "naming_confirm"
            state_frame = frame
        end
    elseif state == "naming_confirm"
        and frame - state_frame >= 45
        and not held_key
    then
        press_key(0)
        state = "littleroot_start"
        state_frame = 0
    elseif state == "littleroot_start"
        and same_pointer(callback2(), symbols.CB2_Overworld)
    then
        if state_frame == 0 then
            state_frame = frame
        elseif frame - state_frame >= 600 then
            capture("littleroot_start")
            local header_ok = emu:getGameTitle() == "POKEMON EMER"
                and emu:getGameCode() == "BPEE"
                and emu:romSize() == 16777216
            finish(header_ok and #samples == 5 and "passed" or "incomplete", false)
        end
    end

    if frame >= maximum_frames then
        finish("timeout_" .. state, false)
    end
end)
