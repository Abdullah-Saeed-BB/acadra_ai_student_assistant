---
name: Acadra
description: From scattered updates to a clear next step.
colors:
  ink: "#142e36"
  paper: "#f2f6f5"
  white: "#ffffff"
  muted: "#43585e"
  line: "#b3c4c0"
  action-teal: "#0a665e"
  mint: "#4fa894"
  signal-amber: "#9e6c11"
  priority-coral: "#96352c"
typography:
  display-accent:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: "clamp(40px, 4vw, 48px)"
    fontWeight: 600
  heading:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "clamp(26px, 3vw, 32px)"
    fontWeight: 700
  body:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 600
---

# Design System: Acadra

## Overview

**Creative north star: An annotated study sheet.** Acadra brings course updates together, explains what changed, and turns deadlines into a realistic next step. The interface should feel calm, capable, and evidence-led. Its visual structure pairs a source note with the action it justifies, then shows how that action fits into the student's day and week.

This is the **target brand system** from `Brand Guidelines.canvas`, its `Brand Assets/` SVGs, and the illustrated `Acadra UI Example.svg` in the Acadra project vault. The current `app/web/app/globals.css` is a brand-neutral, blue-toned implementation; it has not yet adopted this system. Treat this guide as design direction for future frontend work, not as a claim that the current UI already matches it.

**Key characteristics:** warm Paper, dark Ink, restrained teal, fine rules, generous space, clear provenance, and a small waypoint that marks the current step. The identity is Acadra's own; platform connections and Alexa+ do not become part of its logo.

## Colors

The frontmatter is the canonical palette. Use color to identify actions and genuine changes in meaning, not to decorate courses.

| Token | Role |
| --- | --- |
| `ink` | Main text, headings, rules, and the primary logo on light surfaces. |
| `paper` | App background and the base of branded scenes. |
| `white` | Content surfaces that need separation from Paper. |
| `muted` | Secondary text, supporting metadata, and quiet labels. |
| `line` | Fine dividers between records and timetable segments. |
| `action-teal` | Buttons, links, confirmed progress, and the current waypoint. |
| `mint` | Accent within the mark and on dark Ink surfaces. |
| `signal-amber` | Upcoming attention or approaching load, with Ink text. |
| `priority-coral` | Actual urgency, conflicts, or contradictory information; use sparingly. |

**The signal rule.** Pair every status color with a word or icon. Do not use amber as small text on Paper or give each course its own color. Reserve coral for a real conflict or urgency.

**Readability.** Ink on Paper is about 11.9:1; teal on Paper about 4.9:1; coral on Paper about 5.5:1. White on teal is about 5.4:1. Use Ink or White text according to the surface. Source references, due dates, uncertainty labels, and focus states must stay readable at a glance. `line` is a separator, not a text color.

## Typography

**Manrope** is the working typeface for app text, navigation, controls, academic facts, and voice captions: 400 for body, 600 for labels and controls, 700 for headings. **Fraunces** at 600 adds a human academic accent to a short campaign headline or trailer title. At most one Fraunces headline should appear in a view or scene; never use it for tables, dates, or long instructions. Fallbacks are Arial and Georgia, respectively.

The web scale is a 40–48 px hero, 26–32 px section heading, 16 px body with 1.5 line height, and labels no smaller than 14 px. Use sentence case and tabular numerals for dates and durations. Keep dense details in Manrope even when an accent headline is present. The trailer reference scale is 64–80 px titles and captions of at least 36 px; captions must remain visible long enough to read and cannot depend on voice alone.

## Layout

Use the study-sheet relationship shown in `Acadra UI Example.svg`: a narrow margin holds the course, original source, observed time, and changed field; the main column holds the next action, duration, and reason. Align each source note with the plan line it explains. Fine Ink and Line rules organize records; generous space gives each decision room to breathe.

Organize student work around three jobs: **Inbox** shows revisions in the margin, **Today** shows a short numbered agenda with a verb, duration, and reason for every step, and **Next 7–14 days** uses a compact timetable that makes collisions visible. These are layout principles for screens that contain those features, not a claim that those screens exist today.

At narrow widths, preserve the source-to-action relationship in reading order: present the source and its changed detail immediately before the corresponding action. Let the timetable adapt to the available width without hiding due dates or conflicts. Do not turn the entire workspace into a stack of interchangeable rounded cards.

## Elevation & Depth

The reference uses flat Paper and White surfaces, contrast, fine rules, and spacing to establish hierarchy. Avoid decorative shadows and floating cards. A temporary overlay may need depth for legibility, but it should not become the default container treatment.

## Shapes

Protect the waypoint A: retain its proportions and rounded stroke ends. The icon has a rounded-square field; the UI around it should stay quieter, with restrained corners and clear alignment. Do not infer a universal corner radius from the logo artwork.

The primary lockup is the mark plus lowercase `acadra` wordmark in Manrope 700. Use the mark alone for a favicon, app icon, or small avatar. Keep clear space of at least one quarter of the mark width on every side. Minimum digital sizes are 24 px for the mark and 120 px for the lockup. Use Ink on light surfaces, or the supplied Paper/Mint mark on Ink. Before a final vector handoff, outline the wordmark. The source vectors are `Brand Assets/Acadra Logo.svg` and `Brand Assets/Acadra Mark.svg` beside the canvas; they are not yet copied into `app/web/public/`.

## Components

**Primary action.** Use action teal with readable White text for the action that advances the student's task. Keep a visible keyboard focus treatment and express disabled or pending states in words as well as appearance. Secondary links can use teal text on Paper or White.

**Source note.** Show the source name, observed time, and changed field beside the recommendation it supports. Link to the original source when available. Label estimates and uncertain dates plainly; do not present an inferred date as confirmed.

**Agenda step.** Use a short numbered line with an action verb, duration, and “why now” explanation. Mark the current step with a small teal waypoint. Keep the source note aligned with its step so the recommendation remains traceable.

**Week timetable.** Use compact, legible time segments and fine rules. Signal approaching load in amber and genuine collisions in coral, with text labels for both. Do not rely on hue alone to show a conflict.

**Forms and status.** Keep labels explicit, helper text readable, and error messages specific to the field or operation. The present source-entry and Gmail screens should use these same color, type, and evidence rules when they are brought onto the brand system.

## Do's and Don'ts

- **Do** make the next step clear, with its source and reason visible nearby.
- **Do** use teal for action and confirmed progress; use amber and coral only for their stated signals.
- **Do** caption Alexa+ exchanges and respect reduced-motion preferences. In a trailer, motion should show cause and effect: source note to margin, study step to agenda, then a rebalanced timetable.
- **Don't** add gradients, shadows, books, graduation caps, or AI sparkles to the mark or workspace.
- **Don't** combine the Acadra logo with Alexa+ or Amazon marks.
- **Don't** hide the original source during a transition or let color alone carry meaning.
