---
name: thedandano profile page
description: A quiet, self-updating GitHub profile page for recruiters and hiring managers.
---

# Design System: thedandano profile page

## 1. Overview

**Creative North Star: "The One-Page Resume"**

The page reads like the top of a well-set resume that happens to live on GitHub. It is plain text, set by GitHub's own stylesheet.

GitHub's profile page already shows the name, location, links, pinned repos, and the contribution calendar. The README repeats none of them. It holds only what the profile cannot say by itself: one sentence on what Dan builds, one contact link, and open work in other people's projects.

This system rejects badge walls, star counts, "top languages" charts, third-party stat widgets, emoji headings, and animated typing banners.

**Key Characteristics:**
- Text only. No images.
- Nothing GitHub already shows next to it.
- Reading order: summary, contact link, open-source work, footer.

## 2. Colors

None of our own. Text and links keep GitHub's colors in both light and dark themes.

## 3. Typography

**Body Font:** GitHub's README stack (not ours to set).

### Hierarchy
- **Headline** (README `h2`): one section name, "Open-source work".
- **Body**: the summary sentence and one line per item.

## 4. Elevation

Flat. No shadows, borders, or cards.

## 5. Components

### Open-source item
- **Style:** linked title, project name, kind, and real status ("open" or "merged").

## 6. Do's and Don'ts

### Do:
- **Do** label every outside pull request and issue with its real status.
- **Do** change featured repos by pinning them on GitHub, not by editing this repo.

### Don't:
- **Don't** repeat anything the profile page already shows: name, location, links, pinned repos, the contribution calendar.
- **Don't** add badge walls or rows of shield icons.
- **Don't** show star counts, "top languages" charts, or third-party stat widgets.
- **Don't** use emoji headings, waving hands, or animated typing banners.
- **Don't** show closed, unmerged pull requests, or star counts of projects where nothing has merged.
- **Don't** name a private repo anywhere, including in logs.
