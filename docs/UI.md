# UI conventions

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
