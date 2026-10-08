---
name: thedandano profile page
description: A quiet, self-updating GitHub profile page for recruiters and hiring managers.
colors:
  amber-ink: "#8a5600"
  amber-ink-dark: "#f0b452"
  muted-ink: "#6b655a"
  muted-ink-dark: "#9c958a"
  heat-0: "#ebe8e2"
  heat-1: "#f1d9a8"
  heat-2: "#e3b25a"
  heat-3: "#c4831a"
  heat-4: "#8a5600"
  heat-0-dark: "#1c1f24"
  heat-1-dark: "#4a3410"
  heat-2-dark: "#80570f"
  heat-3-dark: "#b9801c"
  heat-4-dark: "#f0b452"
typography:
  label:
    fontFamily: "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
    fontSize: "10px"
    fontWeight: 400
rounded:
  cell: "2px"
spacing:
  cell: "10px"
  cell-gap: "3px"
---

# Design System: thedandano profile page

## 1. Overview

**Creative North Star: "The One-Page Resume"**

The page reads like a well-set one-page resume that happens to live on GitHub. It is mostly plain text, set by GitHub's own stylesheet. A single picture, the contribution calendar, carries the only color on the page.

GitHub strips all CSS and scripts from a profile README, so this system has two materials only: Markdown text and SVG images drawn by the daily build. Each image ships in a light and a dark version and follows the reader's GitHub theme. Neither theme is the default.

This system rejects badge walls, star counts, "top languages" charts, third-party stat widgets, emoji headings, and animated typing banners.

**Key Characteristics:**
- Text first. Numbers and links are real text, never baked into a picture.
- One accent hue (amber), used only in the calendar.
- Reading order: who, activity, featured work, open-source work, footer.
- No motion.

## 2. Colors

One warm amber on GitHub's own neutrals.

### Primary
- **Amber Ink** (`amber-ink`, `amber-ink-dark`): the strongest calendar cell. Amber separates the page from GitHub's default green without shouting.

### Neutral
- **Muted Ink** (`muted-ink`, `muted-ink-dark`): month labels in the calendar.
- **Heat ramp** (`heat-0` to `heat-4`, light and dark): five calendar steps, from an empty day to the busiest day.

### Named Rules
**The One Hue Rule.** Amber appears in the calendar and nowhere else. Body text and links keep GitHub's own colors.

**The Transparent Ground Rule.** Images have no background. They sit on whatever theme the reader uses.

## 3. Typography

**Body Font:** GitHub's README stack (not ours to set).
**Label Font:** system sans stack, inside SVG only.

**Character:** Plain and unstyled on purpose. The writing does the work.

### Hierarchy
- **Display** (README `h1`): the name. Used once.
- **Headline** (README `h2`): section names. Two at most.
- **Body**: one to two short sentences per item.
- **Label** (400, 10px): month names inside the calendar.

### Named Rules
**The No Baked Text Rule.** A fact a recruiter might copy or search for is never drawn into an image.

## 4. Elevation

Flat. No shadows, borders, or cards. Depth comes from spacing and reading order.

## 5. Components

### Contribution calendar
- **Shape:** 53 columns of 7 square cells (10px, 3px gap, 2px corner radius).
- **Color:** the heat ramp for the active theme.
- **Labels:** month names above the columns in Muted Ink.
- **Alt text:** states the total, so the picture is never the only source.

### Featured work row
- **Style:** bold linked repo name, language, last updated date, then the repo's own one-line description. Plain Markdown, no card.

### Open-source item
- **Style:** linked title, project name, kind, and real status ("open" or "merged").

## 6. Do's and Don'ts

### Do:
- **Do** label every outside pull request and issue with its real status.
- **Do** ship every image in a light and a dark version.
- **Do** give every image alt text that states the same fact as the picture.

### Don't:
- **Don't** add badge walls or rows of shield icons.
- **Don't** show star counts, "top languages" charts, or third-party stat widgets.
- **Don't** use emoji headings, waving hands, or animated typing banners.
- **Don't** show closed, unmerged pull requests, or star counts of projects where nothing has merged.
- **Don't** name a private repo anywhere, including in alt text and logs.
