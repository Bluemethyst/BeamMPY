-- BeamMPY aggregate player telemetry. No names, identifiers or chat are collected.
local token = "__TOKEN__"
local epoch = tostring(os.time()) .. "-" .. tostring(math.random(1, 2147483647))
local sequence, joins = 0, 0

function BeamMPYStatisticsSnapshot()
    sequence = sequence + 1
    printRaw("BEAMMPY_STATS:" .. token .. ":" .. Util.JsonEncode({
        version = 1, epoch = epoch, sequence = sequence,
        online = MP.GetPlayerCount(), joins = joins
    }))
end

function BeamMPYStatisticsJoin()
    joins = joins + 1
    BeamMPYStatisticsSnapshot()
end

function BeamMPYStatisticsInit()
    MP.RegisterEvent("BeamMPYStatisticsTick", "BeamMPYStatisticsSnapshot")
    MP.CreateEventTimer("BeamMPYStatisticsTick", 5000)
    BeamMPYStatisticsSnapshot()
end

MP.RegisterEvent("onInit", "BeamMPYStatisticsInit")
MP.RegisterEvent("onPlayerJoin", "BeamMPYStatisticsJoin")
-- Periodic snapshots also reconcile the count after disconnect handlers finish.
MP.RegisterEvent("onPlayerDisconnect", "BeamMPYStatisticsSnapshot")
