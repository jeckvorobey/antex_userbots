---
version: "superdesign-alpha"
name: "Paper-white component workbench"
description: "A near-white, edge-to-edge marketing system built for demonstrating UI primitives: rounded-sm surfaces, oversized rounded-geometric display type, and a semantic swatch palette rationed into isolated bento tiles."
colors:
  background: "#FFFFFF"
  surface: "#F8F8F8"
  text-primary: "#18181B"
  text-secondary: "#71717B"
  border: "#E8E8E8"
  accent-primary: "#422AD5"
  accent-pink: "#F43098"
  accent-rose: "#FF6596"
  accent-teal: "#44EBD3"
  semantic-red: "#FB2C36"
  semantic-orange: "#FF8904"
  semantic-yellow: "#F0B100"
  semantic-green: "#00A63E"
  semantic-emerald: "#00BC7D"
  semantic-teal: "#00BBA7"
  ink-black: "#000000"
  ink-gold: "#DCA54D"
typography:
  display-lg:
    fontFamily: "Outfit"
    fontSize: "64px"
    fontWeight: 400
    lineHeight: "1.1"
  headline-md:
    fontFamily: "Outfit"
    fontSize: "72px"
    fontWeight: 700
    lineHeight: "1"
  body-md:
    fontFamily: "Outfit"
    fontSize: "24px"
    fontWeight: 300
    lineHeight: "1.33"
  label-md:
    fontFamily: "ui-sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "1.5"
  body-base:
    fontFamily: "ui-sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "1.5"
  accent-mono:
    fontFamily: "ui-monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "1.4"
spacing:
  base: "4px"
  gap: "24px"
  section-padding: "32px"
rounded:
  control: "8px"
  card: "16px"
  chip: "9999px"
  square: "4px"
  pill: "9999px"
components:
  navbar-cta:
    background: "#09090B"
    text-color: "#E4E4E7"
    radius: "4px"
    height: "36px"
  button-hero-primary:
    background: "#000000 (observed near-black solid)"
    text-color: "#FFFFFF"
    radius: "8px (observed, ~6-10px)"
    height: "48px"
  button-hero-secondary:
    background: "#F5F5F5 (observed light-gray solid)"
    text-color: "#18181B"
    radius: "8px (observed, ~6-10px)"
    height: "48px"
  button-indigo:
    background: "#422AD5"
    text-color: "#E0E7FF"
    radius: "4px"
    height: "40px"
    border: "1px solid oklab(0.4275 0.0278771 -0.226289)"
    hover-background: "#3B25C1"
  button-pink-pill:
    background: "#F43098"
    text-color: "#FFFFFF"
    radius: "32px"
    height: "40px"
    border: "1px solid oklab(0.65 0.239812 -0.0239026)"
  button-rose-square:
    background: "#FF6596"
    text-color: "#180408"
    radius: "0px"
    height: "40px"
    border: "1px solid oklab(0.7422 0.207718 0.0231157)"
  button-teal-outline-pill:
    background: "#44EBD3"
    text-color: "#005D58"
    radius: "32px"
    height: "40px"
    border: "2px solid oklab(0.8075 -0.131077 -0.00245042)"
  card-panel-list:
    background: "#FFFFFF"
    radius: "0px"
    padding: "0px"
  card-media-heading:
    background: "transparent"
    radius: "0px"
    padding: "0px"
  card-icon-body:
    background: "transparent"
    radius: "8px"
    padding: "0px"
---
# Paper-white component workbench
Source: https://daisyui.com/

## Overview
This is a flat, minimalist, white-canvas marketing page for a UI toolkit — the design system's own visual language is deliberately understated so that embedded product illustrations (device-style panels showing toggles, checkboxes, and semantic swatches) become the color event. Typography is the true brand carrier: a rounded-geometric sans (Outfit) at very large sizes drives every section opener, paired with a workaday ui-sans-serif for body copy. The palette is otherwise near-monochrome (black ink on white), with saturated brand hues (indigo, magenta, rose, teal) appearing only inside demonstration widgets and buttons, never as page-level washes. This is Swiss-adjacent minimalism crossed with a component-catalog aesthetic: generous whitespace, left-aligned text blocks, and zero decorative chrome outside the isolated demo tiles.

## Composition
The first screen is a two-column hero: left-aligned stacked text (eyebrow chip, two-line display headline, a light body paragraph, then a button pair) against a right-side tilted, isometric composition of layered UI-mockup cards showing toggles, checkbox scales, and a semantic-color swatch grid — this cluster is the only saturated color on the entire first screen. Below the fold, the page moves through a rhythm of full-bleed white sections separated only by vertical whitespace (no dividers, no background shifts): a bold declarative headline paired with a code-diff comparison card, a stat-forward section with an oversized colored numeral, a large centered CTA headline with two buttons, a three-column testimonial wall of flat cards, and finally a four-column footer on a pale gray band. The deliberate choice is restraint — nearly the entire scroll is white-on-white typographic composition with color rationed into small enclosed rectangles (mockup panels, buttons, highlighted phrase spans), rejecting the more common SaaS approach of full-width gradient hero bands or dark section alternation. This keeps the color swatches and code snippets legible as literal product demonstrations rather than atmosphere.

## Colors
`#FFFFFF` dominates at ~83% of rendered pixels — this is a true white-canvas system, not off-white. A near-black ink (`#18181B` for body text, `#000000` for display headlines) carries all typographic hierarchy. `#F0F0F0`/`#F8F8F8` (~7%) forms the footer band and card-hover surfaces — the system's only "surface" elevation step above pure white. The remaining ~3% black is concentrated in solid dark buttons and the mockup device frame. Saturated hues appear exclusively as demonstration content: indigo `#422AD5`, magenta `#F43098`, rose `#FF6596`, and teal `#44EBD3` each surface once as a mid-page button variant; a fuller semantic set (`#FB2C36` red, `#FF8904` orange, `#F0B100` yellow, `#00A63E` green, `#00BC7D` emerald, `#00BBA7`/`#009689` teal) lives inside the hero's swatch-grid illustration only. An `#DCA54D` gold accent appears as isolated inline ink (star/rating glyph). Borders are hairline `#E8E8E8` or near-black `#191919` — used sparingly, mostly around code blocks and comparison cards.

## Typography
Outfit is the display voice at two registers: a 64px/400/1.1 weight for hero-style headlines and a heavier 72px/700/1 weight for declarative section headlines — both set tight and left-aligned, sized to dominate their section alone. A lighter Outfit 24px/300/1.33 serves as oversized lead-paragraph body text under major headlines, giving a soft, airy secondary voice distinct from the workhorse UI body copy. Standard interface text runs on ui-sans-serif: 16px/400 for paragraph copy in `#18181B`, and a 14px/400/1.5 label size for chips, nav items, and captions. A monospace face renders inline in the code-diff comparison card (the signature accent face, used only for literal class-name/code content). Numerals inside stat sections are rendered at extreme scale in a saturated hue directly inline with body-weight text, creating the page's most emphatic visual beat.

## Layout
Content is edge-to-edge (no visible max-width clamp below ~1600px) with generous section padding (~96px vertical rhythm) and no persistent grid lines — sections are typographic blocks, not card grids, for most of the page. Two card grids depart from this: the hero's mockup cluster reads as a 3-tile overlapping composition (rows of [100 | 100 | 100] stacked full-width panels with media-top + heading + two embedded tiles each), and the testimonial wall is a 3-column masonry of variable-height flat cards (row heights uneven: 91% / 97% / 74% of container) — a true masonry/waterfall pattern, not uniform card grid. The footer runs a 4-column link grid (AI / Frameworks / Compare Libraries / Related Projects) atop a pale `#F8F8F8` band, with a full-width email-capture bar beneath it. Spacing scale is tight and consistent: 4px, 8px, 16px, 24px, 32px increments; corner radii range from sharp 0px (most content panels) to 4px (buttons/CTAs) to a rounded 8-32px band (pill buttons, illustration frames) to full 9999px pills for chips.

## Components
- **Navbar**: edge-to-edge square bar, 64px tall, spans full 1920px viewport width with 0px inset on both sides, all four corners 0px radius (true full-bleed rectangle, not inset/capsule), sticky, transparent background. Contains logo lockup + version chip at far left, ~90 total interactive items (nav links, docs/components/templates/MCP dropdown, search field with ⌘K hint, theme/language switchers, a GitHub-star counter). Its CTA button: `#09090B` fill, text `#E4E4E7`, radius 4px, compact height.
- **Hero primary button**: an observed near-black solid pill/rectangle beneath the headline, approximate radius ~8px, ~48px height, white label — this is the single most emphasized control on the first screen, paired with an arrow glyph.
- **Hero secondary button**: an observed light-gray/near-white solid button beside the primary, same approximate radius and height, dark text, carrying an icon glyph — a lower-emphasis companion, not a glass or outline style.
- **Prominent utility buttons (mid-page, ×4 variants)**: demonstration/showcase buttons, not navigation — indigo `#422AD5` radius 4px (sharp), magenta `#F43098` radius 32px (rounded pill-adjacent), rose `#FF6596` radius 0px (fully square), teal `#44EBD3` outline radius 32px with 2px border. All 40px tall, `0px 16px` padding, each with a soft multi-layer inset+drop shadow combination (verbatim: `oklch(1 0 0 / 0.06) 0px 0.5px 0px 0.5px inset, oklab(...) 0px 3px 2px -2px, oklab(...) 0px 4px 3px -2px`); indigo variant darkens to `#3B25C1` on hover.
- **Code-diff comparison card**: a bordered panel mid-page showing a form-markup snippet in monospace next to its rendered live equivalent (email input, two toggle switches, one dark save button), flanking a horizontal bar-chart comparison (class-name count and HTML byte size, two bars per metric — one long muted bar, one short green bar with a checkmark stat line beneath).
- **Stat/numeral band**: a left-aligned block pairing dense body paragraphs with one oversized numeral rendered in a saturated coral/pink hue inline with surrounding regular-weight text — the numeral is roughly 3-4× the surrounding type size and appears once per stat callout.
- **CTA callout band**: full-width centered section — bold declarative headline, a lighter three-line supporting paragraph, and a two-button row directly beneath (light-gray outline button + solid black button), no card container, floating on plain white.
- **Testimonial wall**: masonry/waterfall of flat white-to-pale cards in 3 columns, uneven card heights (rows measuring 91%/97%/74% of column width as height proxy), each card holding a quote line (occasionally with a yellow inline text-highlight span), a circular avatar, a name, and a role/title caption — no border, no shadow, cards separated by gap alone.
- **Footer**: pale `#F8F8F8` band, logo lockup + tagline + social icon row on the left, 4 plain-text link columns (each with a small-caps/label-style column heading) to the right, a bottom strip with a founder avatar/credit and a right-aligned email-capture input + dark "Subscribe"-style button, 1 primary footer link total measured plus the column lists.

## Graphics & Effects
The hero's mockup cluster is the only illustrated color surface: a layered stack of white device-style panels (toggle-switch demo, checkbox-scale demo, and a semantic-swatch grid) tilted in a shallow isometric perspective — these panels carry the radial gradient washes (`radial-gradient(at 40% 40%, oklch(0.45 0.24 277.023) -200%, rgba(0,0,0,0) 30%)` indigo-violet and `radial-gradient(at 60% 60%, oklch(0.65 0.241 354.308) -200%, rgba(0,0,0,0) 30%)` magenta-pink) as small internal glows behind the toggle knobs — each covers roughly 6% of total page area and stays confined to a single small card region, never the hero backdrop itself. A second pair of cyan/teal radial glows (`circle at 30-70% 50-60%`, ~3% each) sits behind other small icon tiles further down the page. Card shadows elsewhere are near-invisible utility elevation: `rgba(0,0,0,0.1) 0px 1px 3px 0px, rgba(0,0,0,0.1) 0px 1px 2px -1px` on hoverable surfaces, and a hairline `inset 0px 1px 0px` on flat panels. No blur/glass layers appear except an 8px backdrop-filter reserved for an overlay/dropdown surface, and no noise, grain, or photographic texture is present — the whole system stays crisp and flat.

## Motion
Interactive color/shadow/transform changes use `color, background-color, box-shadow 0.2s cubic-bezier(0, 0, 0.2, 1)` and a combined `color, background-color, border-color, box-shadow, transform 0.2s cubic-bezier(0, 0, 0.2, 1)` for buttons and links — fast, standard-ease micro-transitions with no overshoot. Section entrances use scroll-driven reveal keyframes (`reveal`, `reveal-slow`, `reveal-slower`, `reveal-top`, `reveal-top-slow`) built on a slower `opacity, scale, filter` triple set to `1s ease-out` each — content fades/scales/de-blurs in as it enters viewport, staggered by the "slow/slower" variants for sequential elements in the same band. Focus rings animate via `outline 0.2s ease-in-out`. Motion is otherwise restrained: no parallax, no looping animation, no video — everything ties to scroll-entry or direct interaction.

## Guardrails
- Never wash the hero or any full section in the indigo/magenta/teal gradients — they belong only inside small mockup-panel or icon-tile regions (~3–6% of page each).
- Keep the page canvas true white (`#FFFFFF`); do not tint it gray or introduce a dark section — the only gray band is the footer at `#F8F8F8`.
- Do not merge the four mid-page button variants into one style — each keeps its own radius (4px / 32px / 0px / 32px-outline) and fill; never substitute one variant's shadow or color into another.
- Preserve the navbar as a true edge-to-edge, square-cornered, transparent bar — do not inset it or round its corners into a floating capsule.
- Keep saturated semantic colors (red/orange/yellow/green/emerald/teal) confined to the hero swatch-grid illustration; they are demonstration content, not a page-wide palette.
- Do not add card borders/shadows to the testimonial wall or footer link columns — both stay flat and separated by whitespace only.