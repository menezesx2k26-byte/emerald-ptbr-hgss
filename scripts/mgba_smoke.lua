local output_dir = os.getenv("MGBA_SMOKE_OUTPUT") or "."
local release_version = os.getenv("EMERALD_RELEASE_VERSION") or "1.3.1"
local report_path = output_dir .. "/mgba_smoke_raw.json"
-- Sample once during the direct-menu fade, then twice after it settles. The
-- old 120/600/900 schedule correctly looked static after the cinematic was
-- removed, because the main menu has no ambient animation.
local targets = {5, 120, 900}
local samples = {}
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


local function memory_sample(first, last, step)
    local count = 0
    local signature = 2166136261
    for address = first, last, step do
        local value = emu:read16(address)
        if value ~= 0 then
            count = count + 1
        end
        signature = ((signature ~ value) * 16777619) & 0x7FFFFFFF
    end
    return count, signature
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
    file:write(string.format('  "platform": %d,\n', emu:platform()))
    file:write(string.format('  "frames_reached": %d,\n', emu:currentFrame()))
    file:write('  "frame_samples": [\n')
    for index, sample in ipairs(samples) do
        file:write(string.format(
            '    {"frame": %d, "vram_nonzero_samples": %d, "vram_signature": %d, '
                .. '"palette_nonzero_samples": %d, "palette_signature": %d, '
                .. '"oam_nonzero_samples": %d, "oam_signature": %d, "pc": %d}%s\n',
            sample.frame,
            sample.vram_nonzero_samples,
            sample.vram_signature,
            sample.palette_nonzero_samples,
            sample.palette_signature,
            sample.oam_nonzero_samples,
            sample.oam_signature,
            sample.pc,
            index < #samples and "," or ""
        ))
    end
    file:write('  ]\n')
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
    local frame = emu:currentFrame()
    for _, target in ipairs(targets) do
        if frame >= target and not captured[target] then
            local vram_nonzero, vram_signature = memory_sample(0x06000000, 0x06017FFE, 0x80)
            local palette_nonzero, palette_signature = memory_sample(0x05000000, 0x050003FE, 2)
            local oam_nonzero, oam_signature = memory_sample(0x07000000, 0x070003FE, 2)
            table.insert(samples, {
                frame = frame,
                vram_nonzero_samples = vram_nonzero,
                vram_signature = vram_signature,
                palette_nonzero_samples = palette_nonzero,
                palette_signature = palette_signature,
                oam_nonzero_samples = oam_nonzero,
                oam_signature = oam_signature,
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
