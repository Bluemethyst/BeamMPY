# Initial file management proposal

Proposed 2026-11-13 after reviewing v0.2.3, then deferred by the owner in favour
of accounts and Windows/Linux deployment. This historical proposal is not an
implemented feature, an active task or a completed milestone.

## Recommended first slice

Add a **Files** server tab for the configured `ResourceFolder/Server` tree.
This supplies ordinary server-resource file management alongside the existing
Maps and Mods tabs without introducing a host-wide file browser.

- Browse one directory at a time with breadcrumbs, filename, type, byte size
  and modification time; refresh and filter the current listing.
- Upload one ordinary file per request, using the existing progress transport
  and configured upload limit. Existing names are never overwritten, including
  case-only collisions. Browser multi-selection can issue sequential requests.
- Download individual regular files as attachments after access validation.
- Create folders, rename individual files within their current folder, and
  delete individual files or empty folders after confirmation.
- Permit listing/downloads while running; serialize filesystem access with
  power/configuration/deletion operations. Every mutation requires a stopped,
  idle instance, enforced by the backend as well as disabled UI controls.

Use M3E tabs, lists, menus, fields, progress, dialogs and notifications; retain
native attachment downloads and the existing native file-picker pattern. Show
the managed location as server resources, with relative breadcrumbs. Missing
resource folders are an empty state; reads must not create them.

## Boundaries

The backend derives the root from the registered server and its TOML, never
from a browser-supplied host path. A custom ResourceFolder is supported only
when the resulting resource tree remains inside that instance. External or
shared resources remain unchanged and unavailable through this first Files tab;
explain the restriction without rewriting configuration or moving installations.

The initial tab does not expose the instance root, executable, logs,
ServerConfig.toml, panel data, Client or .beammpy-disabled. Configuration and
map selection retain their existing managers. Client ZIP uploads and state
changes retain mod inspection and the current-map guard. Files must not provide
an alternate route into those trees through path aliases or rename operations.

Validate both source and destination on every request. Reject traversal,
absolute/drive/UNC paths, alternate data streams, invalid or reserved names,
symbolic links, Windows junctions/reparse points, special files and hard-linked
files. Verify every ancestor and the final object, not only the final resolved
path. Reject overlap with another instance's directory/resource ownership and
panel control files or application code. Normal private instance directories
under the panel's instances/ directory remain supported. If another instance's
resource ownership cannot be determined safely, refuse access rather than guess.

Credential/configuration filenames and their aliases must be protected at any
depth. Downloads must never expose the managed BeamMP AuthKey, including when
copied into an otherwise permitted file; reject such a download without echoing
the value. Determine a bounded validation strategy before enabling downloads;
do not start sending bytes before that validation completes. This is not a
promise to discover arbitrary third-party plugin credentials. No file contents,
credentials or raw filesystem exceptions belong in API errors or logs.

Uploads use a temporary file on the destination filesystem, bounded streaming,
cleanup on failure, and complete-file publication without replacement. Recheck
the destination before publication. Keep staging files out of listings and
downloads. Bound directory enumeration (proposed maximum 2,000 entries, with an
explicit limit error), path depth and path length; avoid recursive scans.
Downloads use attachment disposition, nosniff and no-store headers, never an
inline HTML/script preview. Uploads are stored without execution by the panel;
server resources may be loaded by BeamMP on its next start.

Panel locks serialize panel operations; they do not exclude concurrent writes by
host processes. Define and test path/identity revalidation at actual filesystem
access. Do not claim protection against a hostile local account with equivalent
filesystem privileges. Transfer cleanup and lock release must survive disconnects.

## Architecture findings and implementation outline

- `beammpy/api.py` already authenticates its API blueprint; `auth.py` checks CSRF
  for mutations. Extend these paths, including authentication on downloads.
- `Registry.idle()` in `manager.py` provides stopped-only mutual exclusion and
  rejects deleted instances or panel shutdown. Reuse it for mutations and define
  an equivalent read guard that does not require a stopped process. Preserve the
  existing lock order when checking ownership against registration/deletion.
- `Content.resource_dirs()` in `content.py` deliberately resolves external
  ResourceFolder values for existing mod management. It is not a containment
  policy for arbitrary file access. Add a dedicated file-access service rather
  than weakening or silently changing existing map/mod behavior.
- `copy_limited()` supplies bounded upload copying. ZIP validation remains with
  mod/import workflows; general uploads are not automatically extracted.
- Add a routed Files view and ServerTabs entry, using the existing API helpers
  for JSON and upload progress plus authenticated attachment handling.
- No database migration, version bump or executable/startup changes are needed
  for this proposal. Specify API shapes when the scope is agreed and document
  delivered endpoints in API.md during implementation.

## Acceptance before calling this delivered

1. Disposable two-instance API tests cover every file operation, persistence,
   authentication/session expiry, CSRF, stopped-only writes, power/delete races,
   duplicate names, size limits, interrupted transfers and failed publication.
2. Adversarial tests cover traversal/encoding, Windows path aliases and reserved
   names, links/junctions/hard links, shared/nested resources, protected files,
   secret-bearing downloads and source/destination replacement during access.
   Verify denied operations leave original files unchanged and no staged debris.
3. Existing configuration bytes/comments/secrets, users/hashes and installations
   survive; map/mod guards and the IPv6 default/legacy bind repair still pass.
4. Browser scenarios cover breadcrumbs, upload/download, collision errors,
   confirmations/cancellation, stopped-only controls, instance isolation,
   keyboard/focus handling and 320/390px layouts with actual M3E controls.
5. Backend, TypeScript, production build and browser suites pass. Build the Python
   distributions and verify the clean wheel with Node absent. Record actual
   platform results; Linux and full authenticated player joins remain separate
   gates until executed.

## Deferred

Raw text editing/preview, replacement/overwrite, directory moves or recursive
deletion, bulk downloads/archive extraction, instance-root/log access, external
resource roots and a dedicated plugin lifecycle UI. Backups/restores, monitoring,
player tools, scheduling/updates, additional permissions and remote hosts remain
outside this feature. Broadening these boundaries requires a subsequent scope
decision, especially for credentials, concurrent edits and mod/map invariants.
