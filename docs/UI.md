# UI conventions

Version 0.4 adds a per-server Statistics tab, visible only with statistics_view.
Version 0.4.1 defaults it to Last hour with ten-second points and five-second
refreshes. Display seconds in short-range interval labels and inspection times.
It uses M3E cards, a radio menu for time ranges and a checkbox for the optional
administrator-managed player plugin. Resource/player graphs are local SVG data
visualizations using public theme tokens, hover/keyboard interval inspection and
optional accessible data tables. CPU/memory refer only to the selected BeamMP
process. Keep unknown observations distinct from observed zeroes and guard poll
responses by request generation so obsolete ranges/unmounted views cannot update.

The owner requires M3E across the interface. Version 1.8.0 is pinned and bundled
locally with its CSS, custom elements, Google Sans Flex and Material Symbols.
Vue recognises `m3e-*` elements through Vite's compiler configuration. No runtime
CDN requests are necessary. Do not recreate these controls with custom styling.

| UI | M3E integration |
| --- | --- |
| Text, password, number, multiline and search fields | `m3e-text-field`, adapted by UiField/UiSearch |
| Checkboxes | `m3e-checkbox` via UiCheck |
| Switches and radios | Documented M3E CSS markup on native inputs |
| Buttons and icon buttons | M3E CSS variants with ripple behavior |
| Appearance, colours and palette styles | `m3e-menu`, nested menus and grouped radio menu items |
| Confirmations and create/import forms | `m3e-dialog`, alert and full-screen variants |
| Desktop/mobile navigation | `m3e-navigation-drawer` and `m3e-navigation-item` |
| Server tabs and content | `m3e-tabs`, `m3e-tab`, `m3e-tab-panel` |
| Cards, mod lists, badges and banners | M3E CSS component contracts and surfaces |
| Icons | `m3e-icon` and local Material Symbols |
| Loading and progress | `m3e-loading-indicator`, `m3e-linear-progress` |
| Notifications | `m3e-snackbar-host`, queued with native dismissal/timing |

The palette icon beside logout opens AppearanceMenu. Its M3E menus select
light/dark/system, preset colours and palette styles. A M3E dialog offers a hex
field and a button opening the browser's native colour picker. Invalid hex values
show an error; Cancel preserves the current palette. File upload buttons likewise
open the browser's native file picker. Navigation/content links retain native
link semantics. Map selection belongs exclusively in the Maps tab: configuration
neither renders a map dropdown nor resubmits a stale Map value when saving.

`scripts/theme.mjs` uses M3E's theme generator with the blue seed `#1c88ff`, the
vibrant palette and expressive motion. It writes `src/theme.css` at dev/build
time as the initial theme. `src/appearance.ts` uses the same M3E createTheme API
in the browser to generate complete light/dark palettes from preset or custom
seed colours, without a reload. Mode, seed and style persist locally, system
appearance reacts to OS changes, and invalid stored preferences fall back to
defaults. Reset appearance restores system mode and the default blue/vibrant
palette. Keep using the generator instead of a partial hand-maintained set of
colour roles. The Python-yellow P (#ffd43b) and Python-blue Y (#3776ab) in the
logo stay fixed across palettes. Component exceptions
(destructive red, status colours and responsive field width) use public tokens.
`src/layout.css` arranges screens and renders console logs; it must not replace
M3E button, field, dialog or navigation styling. ServerTabs uses M3E primary
scrollable tabs with leading icons. Its public scrollable-edge-padding token is
zero so the first tab starts at the content edge; retain keyboard activation and
guarded routing. Docs: https://m3e.kyralabs.dev/components/tabs/ and
https://m3e.kyralabs.dev/get-started/theming/.

UiField normalises Vue boolean/number properties for custom elements. M3E sets
`aria-required` but not native `required`, and does not forward `min`, `max` or
`minlength`; the adapter applies these to its native input. Keep these browser
validation checks intact when upgrading M3E. Hidden AuthKeys remain masked and
configuration fields retain stopped-only editing.

Browser checks exercise existing management workflows as well as required and
length/range validation, show-password checkboxes, switch persistence, disabled
controls, tab alignment, keyboard tabs/menus, modal focus trapping/restoration,
palette generation/persistence/custom validation, both themes and
320/390 px configuration layouts. Run `npm --prefix frontend run build` before
`npm --prefix frontend run test:e2e`; tests use the compiled production frontend.
Refresh the browser after a source build. Release users need no Node tooling.

My account uses the same M3E fields and buttons for password changes and signing
out all devices. Field layout uses one 16px gap without additive bottom margins;
buttons keep their intrinsic width. The administrator-only Users screen uses M3E
cards, full-screen dialogs and checkboxes for selected-server permissions and
temporary passwords. Creation and reset both expose the Temporary password
checkbox, checked by default. Member deletion uses the shared M3E confirmation
dialog and retains server files; no delete action appears for the administrator.
All new-password fields enforce an eight-character minimum. Console command
selection also grants console viewing;
removing viewing clears command access. The login recovery dialog explains local
maintenance without adding unauthenticated reset functionality. Member server
controls reflect grants, while the backend independently enforces every action.

Authentication updates can overlap background polling and console refreshes.
Requests retain their starting CSRF token: an old 401 cannot expire a later
logout/sign-in. Already-signed-out expiry is a no-op; genuine expiry re-runs the
session guard even at /login. Session generations discard obsolete refresh
results, and console callbacks cannot reconnect closed views. Revoked sessions
must still redirect to login after clearing the user unmounts a console. Keep the logout regression's
visible-login-form and fresh-token assertions; checking the URL alone misses a
Connecting screen stuck on /login.
