# First-release API

All endpoints return JSON. Obtain a session with `GET /api/auth/session`, which
returns `{user, setup_required, csrf_token}`. Send the token in `X-CSRF-Token`
on every non-GET API call and retain the session cookie. Login rotates the token.
Errors return `{error: "message"}` with the appropriate HTTP status; in particular,
401 means authentication is required, 403 means invalid CSRF, and 409 means a
conflicting operation or configuration. JSON bodies are limited to 64 KiB;
multipart ZIP uploads default to 2 GiB per file (BEAMMPY_UPLOAD_LIMIT).

Authenticated `user` contains `id`, `username`, `is_admin`, `can_create_servers`,
`must_change_password` and `permissions` (server ID to an array of permission
names). A member can view only assigned servers, including assignments with an
empty array. Member snapshots omit host directory paths. Unassigned server access
returns 404; an assigned server with insufficient action permission returns 403.
Temporary-password accounts must change their password before any server access.
The sole administrator has all permissions. Action names are:

| Permission | Allows |
| --- | --- |
| power | Start, stop and restart |
| maps | Select an available map |
| mods_toggle | Enable or disable existing mods |
| mods_upload | Upload map/vehicle ZIPs (uploads are enabled) |
| configure | Read masked configuration and edit typed settings |
| console_view | Subscribe to history, status and console output |
| console_command | Send BeamMP stdin commands, including commands that stop it |

Map changes through the config API also require maps permission. Commands require
console_view; commands and power are independent grants. Server creation uses the global can_create_servers
flag; creators receive all member permissions on the newly created server only.
Imports, deletion, executable reinstallation and user administration are admin-only.
Read-only map/mod catalogs and operation polling require assignment to that server.
Member mod mutations additionally require a private instance-local resource root;
shared, overlapping or external resource folders require administrator access.
If another instance's resource ownership cannot be read, member mod writes fail
closed until the administrator corrects the configuration. Existing administrator
map/mod behavior is preserved.

## Authentication

- `POST /api/auth/setup`: `{username, password}` creates the administrator and
  signs in. Only available while no accounts exist; new passwords need 8–1024
  characters. Setup is serialized in a database transaction.
- `POST /api/auth/login`: `{username, password}` signs in with an existing account.
- `POST /api/auth/logout`: revokes this session and disconnects its live consoles.
- `POST /api/auth/password`: `{current_password, new_password}` changes your
  password (8–1024 characters), clears a temporary-password requirement and
  signs out all sessions, including this one. Returns the signed-out session.
- `POST /api/auth/logout-all`: signs out every session for the current user and
  disconnects consoles. Returns the signed-out session.
- Responses use the session shape above; existing password hashes are preserved.

## Account administration

All `/api/users` endpoints require administrator authentication and mutations
require CSRF. There is no member registration or unauthenticated password reset.

- `GET /api/users`: `{users, permissions}`. Accounts have the session user fields
  plus enabled; password hashes and credentials are never included.
- `POST /api/users`: `{username, password, temporary?: true, enabled?: true,
  can_create_servers?: false, permissions?: {server_id: [permission, ...]}}`.
  Creates a member; returns HTTP 201 with `{user}`. A temporary password requires
  changing it at the next sign-in. Set temporary=false to use the supplied
  password directly without a forced change. The flag must be a boolean.
- `PUT /api/users/:id`: `{username, enabled?: true, can_create_servers?: false,
  permissions?: {...}}` replaces the member's access, revokes all its sessions
  and returns `{user}`. This is replacement, not a partial update; omitted
  grants are removed. Unknown fields, servers or permissions are rejected.
- `POST /api/users/:id/password`: `{password, temporary?: true}` sets the password
  and replaces its temporary status, revokes all sessions; `{reset: true}`.
  temporary=false clears an existing forced-change requirement.
- `DELETE /api/users/:id`: `{confirmation}` permanently deletes a member when
  confirmation equals its current username; returns `{deleted: true}`. Its
  grants and sessions are removed and consoles disconnected. Its servers and
  files are retained. Stale confirmation returns 409; missing accounts return 404.

The administrator cannot be disabled, deleted, demoted or reset through member endpoints;
use My account or offline CLI recovery. Members can be disabled or deleted after
confirmation. New/reset passwords must contain 8–1024 characters without
null characters. Server/account assignment changes invalidate existing cookies
and disconnect Socket.IO sessions before further broadcasts.

## Instances and operations

- `GET /api/servers`: `{servers: [...]}`.
- `POST /api/servers`: `{name, port, auth_key}` creates an isolated instance and starts
  installation; returns HTTP 202 with `{server, operation}`.
  The AuthKey is required, stored in the instance config, and never returned.
- `POST /api/servers/import`: `{name, directory}` imports an absolute local
  folder or ZIP containing a compatible executable; returns HTTP 201 with `{server}`.
  Alternatively send multipart form fields `name` and `archive` (server ZIP) to
  upload from the browser. ZIPs are extracted into a new instance; folders stay in
  place and the source archive is not changed. Imports do not start processes.
- `GET /api/servers/:id`: `{server}`.
- `DELETE /api/servers/:id`: `{confirmation, delete_files?: false}` removes a
  stopped idle instance. confirmation must equal its current display name.
  Optional delete_files=true permanently removes its verified instance directory;
  panel data, other instances and their resource directories are protected.
- `POST /api/servers/:id/install|start|stop|restart`: HTTP 202 with `{operation}`.
- `GET /api/operations/:id`: `{operation}`; poll until succeeded or failed.

A server has `id`, `name`, `directory`, `version`, `state`, `running`,
`executable_exists`, `port`, `error`, and an optional active `operation`. States:
installing, stopped, starting, running, stopping, error. Running means the owned
process is alive; it is not a public reachability or player-connection guarantee.

An operation has `id`, `server_id`, `action`, `state` (running/succeeded/failed),
`progress` (0–100) and `message`. Operation history is in memory and bounded;
instance state and process identity are persisted. Active operations appear in
server responses so progress remains visible after a browser reload.

## Configuration

`GET /api/servers/:id/config` returns `{config}` with recognised fields and
`has_auth_key`; it never returns the AuthKey itself.

`PUT /api/servers/:id/config` accepts partial typed settings: `Name`, `Description`,
`Map`, `Port`, `MaxPlayers`, `MaxCars`, `Private`, `AllowGuests`, `LogChat`, `Debug`,
`InformationPacket`, `IP`, `Tags`, and optional `AuthKey`. Omitting AuthKey retains
it; submitting an empty AuthKey clears it. Save requires a stopped, idle instance.
Unknown TOML content and comments remain on disk. There is no raw file editor.

## Maps and client mods

- `GET /api/servers/:id/maps`: `{current, maps}`. Each choice has `path`, `name`,
  `kind` (stock/custom), `enabled`, and optional `mod` filename. The catalog includes
  documented stock maps and levels discovered in enabled/disabled mod ZIPs.
- `PUT /api/servers/:id/maps`: `{path}` chooses an available map on a stopped idle
  instance; returns the updated catalog. The current providing mod cannot be disabled.
- `GET /api/servers/:id/mods`: `{mods}`. Each mod has filename, enabled, size (bytes),
  discovered maps, and optional inspection error.
- `POST /api/servers/:id/mods/upload`: multipart `file` containing one mod ZIP;
  returns HTTP 201 with `{mods}`. Existing filenames are never replaced.
- `POST /api/servers/:id/mods/state`: `{filename, enabled}` moves a ZIP between
  ResourceFolder/Client and ResourceFolder/.beammpy-disabled; returns `{mods}`.

Mutations require a stopped idle instance and CSRF. ZIPs are bounded to 20,000
entries and 8 GiB of expanded data; path traversal, links, encryption, duplicate
paths and corrupt content are rejected. Server configuration/panel data in ZIPs
is rejected by the mod-upload endpoint to avoid distributing a server backup as
a client mod. Custom maps use levels/<id>/info.json inside the ZIP, with an
optional title/name from its JSON metadata. Selecting a
map and changing mods take effect on the next server start. There is no Lua
plugin manager or general file editor in this version.

## Console

Socket.IO uses same-origin HTTP polling on `/socket.io/`. Connect with the session
cookie and `auth: {csrf_token}`. Emit `subscribe` with `{server_id}` to join the
instance room. `terminal_history` replays `{server_id, lines}`; `terminal_output`
contains `{server_id, sequence, text, time}`. Timestamps are Unix seconds. History
is bounded to 1,000 lines, and sequence numbers restart with the panel process.

`server_status` carries the server snapshot and `server_id`. Emit `unsubscribe`
with `{server_id}` on navigation. Emit `command` with `{server_id, text}`; the
acknowledgement is `{ok: true}` or `{ok: false, error}`. Commands are a single line,
at most 4,096 characters, written to BeamMP stdin without a shell. Every command
and subscription revalidates the session. Logout revokes all its connections.
`server_removed` with `{server_id}` notifies subscribers when an instance is deleted.
