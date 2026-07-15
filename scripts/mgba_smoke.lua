local output_dir = os.getenv("MGBA_SMOKE_OUTPUT") or "."
local report_path = output_dir .. "/mgba_smoke_raw.json"
local targets = {120, 600, 900}
local samples = {}
local screenshots = {}
local captured = {}
local finished = false
local frame_callback = nil


local function json_escape(value)
    return tostring(value)
        :gsub("\\", "\\\\")
        :gsub('"', '\\"')
        :gsub("\n", "\\n")
        :gsub("\r", "\\r")
end


local function vram_nonzero_samples()
    local count = 0
    for address = 0x06000000, 0x06017FFE, 0x100 do
        if emu:read16(address) ~= 0 then
            count = count + 1
        end
    end
    return count
end


local function write_report(status, crashed)
    local file = assert(io.open(report_path, "w"))
    file:write("{\n")
    file:write(string.format('  "version": "1.3.1",\n'))
    file:write(string.format('  "status": "%s",\n', json_escape(status)))
    file:write(string.format('  "crashed": %s,\n', crashed and "true" or "false"))
    file:write(string.format('  "game_title": "%s",\n', json_escape(emu:getGameTitle())))
    file:write(string.format('  "game_code": "%s",\n', json_escape(emu:getGameCode())))
    file:write(string.format('  "rom_size": %d,\n', emu:romSize()))
    file:write(string.format('  "platform": %d,\n', emu:platform()))
    file:write(string.format('  "frames_reached": %d,\n', emu:currentFrame()))
    file:write('  "frame_samples": [\n')
    for index, sample in ipairs(samples) do
        file:write(string.format(
            '    {"frame": %d, "vram_nonzero_samples": %d, "pc": %d}%s\n',
            sample.frame,
            sample.vram_nonzero_samples,
            sample.pc,
            index < #samples and "," or ""
        ))
    end
    file:write('  ],\n')
    file:write('  "screenshots": [')
    for index, screenshot in ipairs(screenshots) do
        file:write(string.format('"%s"%s', json_escape(screenshot), index < #screenshots and ", " or ""))
    end
    file:write(']\n')
    file:write("}\n")
    file:close()
end


local function request_clean_exit()
    local exit_stub = 0x03007E00
    local cpsr = emu:readRegister("cpsr")
    if (cpsr & 0x20) ~= 0 then
        emu:write16(exit_stub, 0xDF03)
    else
        emu:write32(exit_stub, 0xEF000003)
    end
    emu:writeRegister("pc", exit_stub)
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
    request_clean_exit()
end


callbacks:add("crashed", function()
    finish("crashed", true)
end)


frame_callback = callbacks:add("frame", function()
    local frame = emu:currentFrame()
    for _, target in ipairs(targets) do
        if frame >= target and not captured[target] then
            local filename = string.format("mgba-frame-%04d.png", target)
            emu:screenshot(output_dir .. "/" .. filename)
            table.insert(screenshots, filename)
            table.insert(samples, {
                frame = frame,
                vram_nonzero_samples = vram_nonzero_samples(),
                pc = emu:readRegister("pc"),
            })
            captured[target] = true
        end
    end

    if frame >= targets[#targets] then
        local header_ok = emu:getGameTitle() == "POKEMON EMER"
            and emu:getGameCode() == "BPEE"
            and emu:romSize() == 16777216
        finish(header_ok and "passed" or "invalid_header", false)
    end
end)
