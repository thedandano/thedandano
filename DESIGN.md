---
name: thedandano profile page
description: A quiet, self-updating GitHub profile page for recruiters and hiring managers.
---

# Design System: thedandano profile page

## 1. Overview

**Creative North Star: "The One-Page Resume"**

The page reads like the top of a well-set resume that happens to live on GitHub. It is plain text, set by GitHub's own stylesheet.

GitHub's profile page already shows the name, location, links, pinned repos, and the contribution calendar. The README repeats none of them. It holds only what the profile cannot say by itself: who Dan is, in one bold headline and three claims. Each claim links to merged work that backs it.

This system rejects badge walls, star counts, "top languages" charts, third-party stat widgets, emoji headings, and animated typing banners.

**Key Characteristics:**
- Text only. No images.
- Nothing GitHub already shows next to it.
- Reading order: headline, three claims, contact link, footer.
- Bold in what it says, quiet in how it looks.

## 2. Colors

None of our own. Text and links keep GitHub's colors in both light and dark themes.

## 3. Typography

**Body Font:** GitHub's README stack (not ours to set).

### Hierarchy
- **Display** (README `h1`): the headline claim. Used once.
- **Body**: one short paragraph per claim, opening with the trait in bold.

## 4. Elevation

Flat. No shadows, borders, or cards.

## 5. Components

### Claim
- **Style:** the trait in bold, then one or two sentences of evidence with links. Numbers come live from GitHub.

### Merged outside work
- **Style:** linked title and project name. The section appears only when a pull request in someone else's public repo has merged.

## 6. Do's and Don'ts

### Do:
- **Do** back every claim with a link to merged work.
- **Do** change featured repos by pinning them on GitHub, not by editing this repo.

### Don't:
- **Don't** repeat anything the profile page already shows: name, location, links, pinned repos, the contribution calendar.
- **Don't** add badge walls or rows of shield icons.
- **Don't** show star counts, "top languages" charts, or third-party stat widgets.
- **Don't** use emoji headings, waving hands, or animated typing banners.
- **Don't** use open or closed-unmerged pull requests as evidence, or star counts of projects where nothing has merged.
- **Don't** name a private repo anywhere, including in logs.
