---
name: thedandano profile page
description: A bold, self-updating GitHub profile page that says who Dan is and proves it.
colors:
  series-callback: "#2a78d6"
  series-callback-dark: "#3987e5"
  series-solar: "#eb6834"
  series-solar-dark: "#d95926"
  series-world-cup-bar: "#1baf7a"
  series-world-cup-bar-dark: "#199e70"
  series-other: "#8c959f"
  series-other-dark: "#6e7681"
  chart-ink: "#59636e"
  chart-ink-dark: "#9198a1"
  chart-grid: "#d1d9e0"
  chart-grid-dark: "#3d444d"
typography:
  label:
    fontFamily: "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
    fontSize: "10px"
    fontWeight: 400
rounded:
  bar: "1px"
---

# Design System: thedandano profile page

## 1. Overview

**Creative North Star: "The One-Page Resume"**

The page reads like a well-set resume that happens to live on GitHub. It is bold in what it claims and plain in how it looks. Almost all of it is text, set by GitHub's own stylesheet.

GitHub's profile page already shows the name, location, links, pinned repos, and the contribution calendar. The README repeats none of them. It says who Dan is, and every claim links to something a reader can check.

GitHub strips all CSS and scripts from a profile README, so the page has two materials only: Markdown text and one chart that the daily build draws as an SVG.

This system rejects badge walls, star counts, "top languages" charts, third-party stat widgets, emoji headings, and animated typing banners.

**Key Characteristics:**
- Reading order: headline, three taglines, what I build, where the work went, how I work, away from the keyboard, contact link, footer.
- The headline and taglines fit on the first screen. A 20-second reader gets the point without scrolling.
- One chart. It is the only color on the page.
- The wording lives in `template.md`. Live numbers are filled in by `build.py`.

## 2. Colors

Color appears only in the chart. Each project keeps one fixed color.

### Primary
- **callback blue** (`series-callback`), **solar orange** (`series-solar`), **World Cup Bar aqua** (`series-world-cup-bar`): one hue per project story, always in this order.

### Neutral
- **Other gray** (`series-other`): everything that is not one of the three stories.
- **Chart ink** (`chart-ink`) and **chart grid** (`chart-grid`): axis text, legend text, and faint grid lines.

### Named Rules
**The Validated Palette Rule.** Series colors must pass the dataviz palette validator on GitHub's light (`#ffffff`) and dark (`#0d1117`) backgrounds before they ship.

**The Ink For Text Rule.** Chart text is ink, never a series color. A colored swatch beside it carries the identity.

**The Transparent Ground Rule.** The chart has no background. It sits on whatever theme the reader uses.

## 3. Typography

**Body Font:** GitHub's README stack (not ours to set).
**Label Font:** system sans stack, inside the chart only.

### Hierarchy
- **Display** (README `h1`): the headline claim. Used once.
- **Headline** (README `h2`): four section names.
- **Body**: one short paragraph per claim, opening with its subject in bold.
- **Label** (400, 10px): axis, month, and legend text in the chart.

### Named Rules
**The No Baked Text Rule.** A fact a reader might copy or search for is never only in the picture. The chart's numbers are also written as a sentence under it.

## 4. Elevation

Flat. No shadows, borders, or cards.

## 5. Components

### Claim
- **Style:** the subject in bold, then one to three sentences with links to the evidence. Numbers come live from GitHub.

### Work chart
- **Shape:** one stacked bar per week, starting at the first week with merged work. Thin gap between projects, 1px corner radius.
- **Axis:** three faint grid lines with labels, month names below, legend at the bottom.
- **Themes:** a light and a dark file, swapped by the reader's GitHub theme.
- **Alt text and caption:** the same totals the chart shows.
- **Table view:** a collapsed table under the chart lists every week by project, so the breakdown never depends on color.

### Merged outside work
- **Style:** linked title and project name. The section appears only when a pull request in someone else's public GitHub repo has merged.

## 6. Do's and Don'ts

### Do:
- **Do** back every claim with a link to merged or landed work.
- **Do** keep personal lines in Dan's own words.
- **Do** change featured repos by pinning them on GitHub, not by editing this repo.

### Don't:
- **Don't** repeat anything the profile page already shows: name, location, links, pinned repos, the contribution calendar.
- **Don't** add badge walls or rows of shield icons.
- **Don't** show star counts, "top languages" charts, or third-party stat widgets.
- **Don't** use emoji headings, waving hands, or animated typing banners.
- **Don't** use open or closed-unmerged pull requests as evidence, or star counts of projects where nothing has merged.
- **Don't** name a private repo anywhere, including in logs.
