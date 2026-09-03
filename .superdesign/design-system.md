# Swarm Control — visual design system

## Product context

Swarm Control is a responsive web console for operating Telegram userbot agents. It follows Hermes Agent as an architectural reference for agent identity, runtime settings, provider configuration, schedules, logs, and operational status, while using its own product stack and visual identity.

Primary operator jobs:

- understand swarm health at a glance;
- enable or disable a bot without restarting the whole swarm;
- edit, compare, test, publish, and roll back bot personalities;
- choose Gemini or OpenRouter and configure a model per bot;
- manage groups, schedules, system prompts, and provider settings;
- inspect conversations, errors, and audit history;
- authenticate through a token-based login before accessing the console.

Target platform is desktop-first responsive web. The dense operational views must remain usable at 1280px and scale down to a compact tablet/mobile monitoring experience.

## Primary visual source

Use the extracted daisyUI visual language as inspiration, adapted from a component-library workbench into an operator console. Keep the system recognizably its own product: do not reuse the daisyUI flower logo, product name, marketing composition, or marketing copy.

Core character:

- true white primary canvas;
- near-black typography;
- restrained pale-gray surfaces;
- rounded but not soft or playful controls;
- color confined to status, model/provider identity, charts, and primary actions;
- generous whitespace around major page regions, with compact spacing inside operational tables and forms;
- crisp borders and almost invisible elevation;
- no glassmorphism, large gradients, neon backgrounds, photographic decoration, or ornamental 3D scenes.

## Layout system

- Application shell: persistent 240px left sidebar, 64px top bar, flexible content canvas.
- Content width: fluid, with 32px desktop page padding and 20px compact padding.
- Base grid: 4px.
- Standard gaps: 4, 8, 12, 16, 24, 32, and 48px.
- Dashboard cards: 12-column grid; common spans are 3, 4, 6, 8, and 12 columns.
- Forms: labels above controls; 640–760px comfortable reading width for personality and prompt editing.
- Tables: sticky header, 44px default row height, 52px comfortable row height, horizontal scroll only as a final responsive fallback.
- Detail pages: list/detail or main/inspector layouts are preferred over nested modal stacks.
- Mobile: sidebar becomes a drawer; primary status and actions remain visible; dense tables become compact cards.

## Color tokens

Light mode is the reference mode for initial design drafts.

- `base-100`: #FFFFFF — page and primary card surface.
- `base-200`: #F8F8F8 — sidebar, secondary regions, hover surfaces.
- `base-300`: #E8E8E8 — borders and dividers.
- `base-content`: #18181B — primary text.
- `content-muted`: #71717B — secondary text and metadata.
- `primary`: #422AD5 — primary actions, active navigation, selected provider/model.
- `primary-content`: #FFFFFF.
- `secondary`: #F43098 — rare AI/personality accent; never a page wash.
- `accent`: #00BBA7 — positive realtime activity and connected state.
- `info`: #2563EB.
- `success`: #00A63E.
- `warning`: #F0A000.
- `error`: #E5484D.

Status colors must always be paired with an icon and text. Never encode bot state by color alone.

Optional dark mode may be specified later as a token remap. Do not introduce it into the first visual comparison.

## Typography

- UI font: Inter, fallback `ui-sans-serif, system-ui, sans-serif`.
- Display/accent font: Outfit, used only for the product wordmark, empty-state headlines, and major page titles.
- Technical font: JetBrains Mono, fallback `ui-monospace, monospace`, used for model ids, timestamps, tokens, JSON previews, and logs.
- Page title: 28px / 36px / 650.
- Section title: 20px / 28px / 650.
- Card title: 16px / 24px / 600.
- Body: 14px / 21px / 400.
- Compact UI: 13px / 18px / 500.
- Caption and table metadata: 12px / 16px / 500.
- Large metric: 32px / 38px / 650, tabular numerals.

Do not use large marketing typography inside the console. Operational readability takes priority over visual spectacle.

## Shape and elevation

- Input and button radius: 8px.
- Card and panel radius: 12px.
- Dialog radius: 16px.
- Badge and status radius: 9999px.
- Default border: 1px solid #E8E8E8.
- Default shadow: 0 1px 2px rgba(0,0,0,.05).
- Raised overlay shadow: 0 12px 32px rgba(0,0,0,.12).

Avoid stacked shadows and decorative inner glows. Selected cards may use a 2px primary border instead of a larger shadow.

## Core component rules

Use daisyUI component anatomy and semantic class concepts as the implementation basis.

- Buttons: primary, secondary, ghost, outline, and error variants; 40px default height, 32px compact height.
- Inputs and selects: 40px default height, persistent label, inline validation, visible focus ring.
- Cards: flat white surfaces with border; headers separate title, status, and action slots.
- Stats: compact metric, delta, period, and optional sparkline; never large decorative stat blocks.
- Tables: explicit column labels, sortable headers, row selection only where batch actions exist.
- Badges: bot state, provider, model, group permission, and revision status.
- Tabs: page-local views only; primary navigation stays in the sidebar.
- Drawer: mobile navigation and optional right-side inspector.
- Modal: destructive confirmation and short focused flows only.
- Toast: transient success; persistent error details belong in an alert or error panel.
- Skeleton: preserve final layout dimensions.
- Empty state: explain why it is empty and provide exactly one primary recovery action.

Use TanStack Table behavior beneath daisyUI table styling for sorting, filtering, pagination, and column visibility.

## Application shell

Sidebar groups:

1. Overview
2. Agents
3. Personalities
4. Groups
5. Schedules
6. Conversations
7. Logs
8. Audit
9. Settings

The bottom sidebar area contains runtime version, connection status, and sign-out. The top bar contains breadcrumbs, global search, environment badge, realtime connection state, and contextual primary action.

## Key page patterns

### Login

Centered token form on a white canvas with one compact explanation, secure token input, primary sign-in button, and connection/help status. Never place token values in a URL or display them after submission.

### Overview

Runtime status strip, four compact metrics, active agent roster, current incidents, scheduled activity, provider health, and recent audit events. The page answers “is the swarm healthy?” before exposing configuration details.

### Agents

Filterable roster with avatar, name, Telegram account state, assigned personality, provider/model, target groups, last activity, and guarded enable/disable control. A right inspector or detail route exposes configuration without overloading the table.

### Personality editor

Three-region workspace: revision list, main structured editor, and test/preview inspector. Primary actions are Save draft, Test, Compare, and Publish. Publishing is visually distinct and requires revision metadata.

### Provider settings

Gemini and OpenRouter cards show connection state, masked credential availability, default model, timeout, and latest health check. Raw keys are never readable from the UI.

### Logs and audit

Dense searchable table, severity filters, monospace event details, correlation identifiers, and a side inspector. Prompts, tokens, and Telegram session material must be redacted.

## Interaction and motion

- Micro-transitions: 160–200ms standard ease for hover, focus, expansion, and state changes.
- No looping decorative animation.
- Realtime updates use subtle row highlight fading within 800ms.
- Enabling/disabling a bot shows immediate pending state and resolves to success or a persistent error.
- Destructive or runtime-impacting actions require confirmation with clear scope.
- Respect `prefers-reduced-motion`.

## Accessibility

- Minimum WCAG AA contrast for text and controls.
- Complete keyboard navigation for sidebar, tables, forms, tabs, dialogs, and editor actions.
- Visible 2px focus ring with 2px offset.
- Minimum 40px primary pointer target; 32px compact controls require surrounding spacing.
- Every icon-only action has an accessible label and tooltip.
- Status always combines text, icon, and color.

## Draft constraints

- Use Russian interface copy in all screens.
- Use realistic but fictional bot names and redacted identifiers.
- Never render Telegram session strings, provider keys, full access tokens, or unredacted private prompts.
- Show both Gemini and OpenRouter in provider/model controls.
- Use only the fonts, colors, spacing, and component styles defined here.
- Do not introduce new fonts, page-wide gradients, glass effects, or decorative brand marks.
