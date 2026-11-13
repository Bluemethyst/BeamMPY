# Server statistics (v0.4.1)

Approved 2026-11-14, with the explicit requirement that metrics describe each
individual server on its own Statistics tab. Implemented process CPU, resident
memory, uptime, historical graphs and optional aggregate player telemetry.
System-wide monitoring and overview resource summaries are outside this scope.

## Using the Statistics tab

Select a server, then Statistics. Resource collection is automatic while the
panel runs, independent of open browsers. It samples only the owned BeamMP process
every five seconds. CPU needs two observations; 100% means one logical CPU core,
so a multithreaded server can exceed 100%. Resident memory is reported in MiB.
Uptime resets when this server process restarts. No host-wide totals are used.

CPU and memory charts show averages and peaks. Player bars show peak simultaneous
server counts per interval. The default Last hour view shows ten-second points
and refreshes every five seconds. Choose Last 24 hours, Last 7 days or Last 30 days
for aggregated history. Hover over charts or use left/right arrow keys to inspect intervals;
Show data table provides the same observations as a table. M3E navigation, menus,
checkboxes and cards follow the selected palette in light/dark themes.

## Player collection

As administrator, stop the server and enable Collect player statistics. This
installs the bundled Lua plugin at ResourceFolder/Server/BeamMPYStatistics/main.lua.
Start the server to begin collection; no client mod or new listening port is
needed. CPU/memory graphs work independently of this option.

Only verified private instance-local resources support automatic plugin setup.
External/shared roots, directory links/junctions, overlapping resources and
unverifiable other-server configuration are rejected. Existing plugins are never
overwritten. If the managed plugin is changed or its ResourceFolder is moved,
restore the managed file/location before removing it through the panel. Disable
collection while stopped to remove the unchanged managed plugin and keep history.

The plugin uses BeamMP's documented `MP.GetPlayerCount()`, `onPlayerJoin` and
`onPlayerDisconnect` APIs. See the
[official server API](https://docs.beammp.com/scripting/server/latest-server-reference/).
It emits framed aggregate snapshots through the owned process reader, with
periodic count reconciliation and cumulative joins to avoid duplicate accounting.
The panel excludes these frames from the human console.

Online counts use BeamMP's own player count; they are not a guarantee that every
counted client has finished syncing. Successful joins use onPlayerJoin and include
repeat visits. No names, player identifiers, IPs or chat are stored. Plugin counts
and restart behavior were exercised against official Windows BeamMP v3.9.3 with
throwaway keys and loopback networking; authenticated game/player joins have not
been verified with a real client.

## History and permissions

SQLite schema 5 retains ten-second detail for 24 hours and minute summaries for
30 days, with automatic pruning on startup/hourly. The Last hour graph uses
ten-second detail; longer views use the minute summaries. Detail begins when the
updated panel starts collecting; older minute history remains in the longer views
and is never interpolated into invented ten-second points.
Account IDs/hashes, existing grants,
server directories and TOML content survive migration. Query results are bounded
to at most 721 intervals and older periods use larger display buckets. History
survives panel/server restarts; deleting a server registration deletes its history.
Back up the full data directory before upgrading; old panels cannot open schema 5.

Collection occurs only while BeamMPY runs. Stopped, unavailable and stale states
are explicit. Missing observations are chart gaps rather than invented zeroes;
zero is valid when the plugin observes an empty server. An inactive or missing
plugin shows unknown player data after its freshness window expires.

Administrators have statistics access. Existing members need the new View
statistics checkbox under their assigned server in Users; previous grants are
preserved. Member creators receive the grant on their new servers. Every
statistics request enforces the grant, independently of console permission.
The view polls authenticated HTTP; there is no statistics Socket.IO room.

## Verification

Tests use disposable data/processes and cover owned-process identity, restart
baselines, history/retention/rollups, migration preservation, permissions/revocation,
plugin file protection, malformed/duplicate/stale player frames and background
collector shutdown. Browser scenarios exercise collection without an open console,
charts/time ranges/tables, player fixtures, member access and mobile themes.
The distribution verifier installs the wheel without Node and checks the bundled
UI and Lua plugin. Exact session results and remaining gates are in HANDOFF.md.

The outstanding real Linux BeamMP release gate remains independent. Alerts,
moderation/player profiles,
playtime rankings, exports, disk/network monitoring and indefinite history are
later proposals, not implicit additions to this scope.
