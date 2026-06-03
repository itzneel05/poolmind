# 🎨 POOLMIND — MASTER UI/UX DESIGN SYSTEM v1.0

You are designing/building UI for **poolmind** — a cybersecurity resource pool 
tool for power users. Every page, component, and screen you generate MUST follow 
this design system exactly. No deviation. No "improvements." Consistency over creativity.

═══════════════════════════════════════════════════════════════════
🎯 DESIGN PHILOSOPHY — THE FIVE LAWS
═══════════════════════════════════════════════════════════════════

1. CLEAN — Negative space is a feature. White space breathes. Crowded = broken.
2. MINIMAL — Show only what the user needs RIGHT NOW. Hide the rest behind clicks.
3. DENSE WHEN NEEDED — Data tables, dashboards, lists: information density wins.
4. UNIQUE BUT NOT WEIRD — Subtle personality. Not Bootstrap. Not Material. Ours.
5. TERMINAL-INSPIRED — User is a hacker. Monospace accents. Tactical feel. No fluff.

═══════════════════════════════════════════════════════════════════
🎨 VISUAL IDENTITY — LOCKED VALUES
═══════════════════════════════════════════════════════════════════

## COLOR PALETTE (deep navy + electric accent)

CSS Custom Properties — paste at root:

:root {
  /* Backgrounds — layered depth */
  --bg-base:       #0a0e1a;   /* deepest — body */
  --bg-surface:    #111726;   /* cards, panels */
  --bg-elevated:   #1a2138;   /* modals, dropdowns */
  --bg-hover:      #1f2942;   /* hover states */
  --bg-active:     #252f4a;   /* active/selected */

  /* Borders — subtle separation */
  --border-faint:  #1f2942;
  --border-soft:   #2a3553;
  --border-strong: #3d4a6e;

  /* Text — high contrast hierarchy */
  --text-primary:   #e8ecf4;   /* headings, important */
  --text-secondary: #a8b2cf;   /* body, regular */
  --text-tertiary:  #6b7795;   /* meta, captions */
  --text-faint:     #4a5470;   /* disabled, hints */

  /* Accent — single signature color (electric cyan-blue) */
  --accent:         #4d9fff;
  --accent-hover:   #6cb0ff;
  --accent-muted:   #2a5a99;
  --accent-glow:    rgba(77, 159, 255, 0.15);

  /* Semantic — sparingly used */
  --success:        #4ade80;
  --warning:        #fbbf24;
  --danger:         #f87171;
  --info:           #60a5fa;

  /* Data viz / category colors (subtle, not loud) */
  --cat-1: #4d9fff;  /* blue   — primary */
  --cat-2: #a78bfa;  /* purple — secondary */
  --cat-3: #4ade80;  /* green  — positive */
  --cat-4: #fbbf24;  /* amber  — attention */
  --cat-5: #f87171;  /* red    — critical */
  --cat-6: #2dd4bf;  /* teal   — info */
}

## TYPOGRAPHY (two fonts only — strict)

/* Primary — clean sans for everything */
--font-sans: 'Inter', -apple-system, system-ui, sans-serif;

/* Mono — for IDs, URLs, code, numbers, tags */
--font-mono: 'JetBrains Mono', 'Fira Code', Menlo, monospace;

## TYPE SCALE (use these exact values — no other sizes)

--text-xs:   0.75rem;    /* 12px — meta, labels */
--text-sm:   0.875rem;   /* 14px — body, table cells */
--text-base: 1rem;       /* 16px — default */
--text-md:   1.125rem;   /* 18px — emphasized body */
--text-lg:   1.375rem;   /* 22px — section headings */
--text-xl:   1.75rem;    /* 28px — page headings */
--text-2xl:  2.25rem;    /* 36px — dashboard stats */
--text-3xl:  3rem;       /* 48px — hero stats only */

## FONT WEIGHTS

--weight-regular: 400;
--weight-medium:  500;
--weight-semibold: 600;
--weight-bold:    700;

NEVER use weight 800 or 900. Never italic except for hints.

## SPACING SCALE (4px base — strict)

--space-1:  0.25rem;   /*  4px */
--space-2:  0.5rem;    /*  8px */
--space-3:  0.75rem;   /* 12px */
--space-4:  1rem;      /* 16px */
--space-5:  1.5rem;    /* 24px */
--space-6:  2rem;      /* 32px */
--space-7:  3rem;      /* 48px */
--space-8:  4rem;      /* 64px */

NEVER use arbitrary spacing. Pick from the scale.

## BORDER RADIUS

--radius-sm: 4px;    /* tags, small buttons */
--radius-md: 6px;    /* buttons, inputs */
--radius-lg: 8px;    /* cards, panels */
--radius-xl: 12px;   /* modals */

NEVER use radius > 12px. NEVER use circular/pill except for tag chips.

## SHADOWS (very subtle — barely there)

--shadow-sm:  0 1px 2px rgba(0,0,0,0.2);
--shadow-md:  0 4px 12px rgba(0,0,0,0.25);
--shadow-lg:  0 8px 24px rgba(0,0,0,0.3);
--shadow-glow: 0 0 20px var(--accent-glow);  /* only on focused/special */

═══════════════════════════════════════════════════════════════════
✨ THE UNIQUE TOUCH — SUBTLE SIGNATURE ELEMENTS
═══════════════════════════════════════════════════════════════════

These are what makes poolmind feel different from generic admin dashboards:

1. CORNER BRACKETS on important panels (tactical/HUD aesthetic):
   ┌─                      ─┐
                            
   └─                      ─┘
   Implement as ::before/::after with 12px L-shaped borders in --accent.
   Only on: dashboard hero stats, AI panels, audit cards. Not everywhere.

2. MONOSPACE EVERYTHING TECHNICAL:
   - Resource IDs: `abc12345` (always in mono, --text-tertiary)
   - URLs: `github.com/...` (mono)
   - Numbers in stats: mono
   - Percentages: mono
   - Status codes: mono
   - Tags: mono with # prefix

3. SINGLE-PIXEL ACCENT BAR on hover/active rows:
   On list rows, on hover: 2px left border in --accent appears.
   No background change. Just the bar slides in.

4. GLOWING ACCENT (sparingly):
   - Active nav item: --accent text + 1px bottom border
   - Focused input: 1px --accent border + subtle --shadow-glow
   - Primary CTA button: --accent bg with --shadow-glow on hover
   NEVER glow more than ONE thing at a time on screen.

5. TERMINAL-STYLE STATUS INDICATORS:
   Instead of colored dots, use bracketed labels:
   [OK] [WARN] [DEAD] [SYNC] [LOW]
   In mono font, bracketed, color-coded.

6. SECTION DIVIDERS = single hairline + tiny label
   ────────────  RESOURCES  ────────────────────────
   Hairline in --border-faint, label in --text-tertiary mono uppercase.

═══════════════════════════════════════════════════════════════════
🧱 COMPONENT LIBRARY — STRICT SPECS
═══════════════════════════════════════════════════════════════════

## BUTTONS

Three variants only. No more.

PRIMARY (one per view max):
  bg: --accent
  text: white
  padding: 10px 18px
  radius: --radius-md
  font: sans, weight-medium, text-sm
  hover: --accent-hover + --shadow-glow
  transition: 150ms ease

SECONDARY (most buttons):
  bg: transparent
  border: 1px solid --border-strong
  text: --text-primary
  padding: 10px 18px (same as primary)
  hover: bg --bg-hover, border --accent

GHOST (table actions, inline):
  bg: transparent
  no border
  text: --text-secondary
  padding: 6px 12px
  hover: text --accent, bg --bg-hover

NEVER:
- Gradient buttons
- 3D effects
- More than 3 button styles
- Capitalized button text (use sentence case)

## INPUTS / FORMS

bg: --bg-base (recessed — INSIDE a panel)
border: 1px solid --border-soft
padding: 10px 14px
radius: --radius-md
font: sans, text-sm
text: --text-primary
placeholder: --text-faint

Focus state:
  border: 1px solid --accent
  outline: none
  box-shadow: --shadow-glow

Label:
  font: sans, text-xs, weight-medium
  color: --text-tertiary
  text-transform: uppercase
  letter-spacing: 0.05em
  margin-bottom: 6px

## CARDS / PANELS

Default:
  bg: --bg-surface
  border: 1px solid --border-faint
  radius: --radius-lg
  padding: --space-5
  no shadow (clean)

Hover (when clickable):
  border: 1px solid --border-soft
  transform: translateY(-1px)
  transition: 150ms ease

Special (HUD panels — dashboard hero, AI panel):
  Add corner brackets (::before, ::after)
  Slightly thicker border (--border-soft)

## TABLES

Header row:
  bg: --bg-base
  border-bottom: 1px solid --border-soft
  text: --text-tertiary
  font: sans, text-xs, weight-semibold, uppercase
  letter-spacing: 0.05em
  padding: 12px 16px

Body row:
  border-bottom: 1px solid --border-faint
  text: --text-secondary
  padding: 14px 16px
  font: sans, text-sm

Hover:
  bg: --bg-hover
  left-border accent bar (see signature element #3)

IDs in tables: mono, --text-tertiary, smaller (text-xs)

## NAVIGATION (top bar)

height: 56px
bg: --bg-base
border-bottom: 1px solid --border-faint
padding: 0 24px

Logo: mono font, --accent, lowercase "poolmind"

Nav items:
  font: sans, text-sm, weight-medium
  color: --text-secondary
  padding: 8px 14px
  hover: color --text-primary
  active: color --accent + 2px bottom border in --accent

## TAGS / CHIPS

font: mono, text-xs
padding: 3px 8px
radius: --radius-sm (4px — slightly rounded square)
bg: --bg-elevated
text: --text-secondary
border: 1px solid --border-faint

Hover: bg --bg-hover, text --accent

Category-colored tags use --cat-N as text color, bg stays neutral.

## MODALS

Backdrop: rgba(0,0,0,0.6) + backdrop-filter: blur(4px)
Panel: 
  bg: --bg-elevated
  border: 1px solid --border-strong
  radius: --radius-xl
  padding: --space-6
  max-width: 560px
  shadow: --shadow-lg

Header: text-lg, weight-semibold, --text-primary
Close button: top-right, ghost variant, × character

## STATUS BADGES (the bracketed style)

Format: [LABEL] in mono uppercase

  [OK]    → --success
  [WARN]  → --warning
  [DEAD]  → --danger
  [SYNC]  → --info
  [LOW]   → --text-tertiary
  [AI]    → --accent

font: mono, text-xs, weight-semibold
no background — just colored bracketed text
letter-spacing: 0.05em

═══════════════════════════════════════════════════════════════════
📐 LAYOUT GRID — APPLIED TO EVERY PAGE
═══════════════════════════════════════════════════════════════════

## PAGE STRUCTURE (mandatory)

┌─────────────────────────────────────────────────┐
│  TOP NAV (56px fixed, full-width)               │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─ Page header (60-80px) ─────────────────┐    │
│  │  Page title + primary actions (right)   │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ┌─ Main content area ─────────────────────┐    │
│  │  Max-width 1280px, centered             │    │
│  │  Padding: 32px horizontal, 24px top     │    │
│  │                                         │    │
│  │  [Content goes here]                    │    │
│  │                                         │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
└─────────────────────────────────────────────────┘

## GRID SYSTEM

Use CSS Grid for dashboards:
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);

For 2-column detail pages:
  grid-template-columns: 1fr 320px;  /* main + sidebar */
  gap: var(--space-6);

## RESPONSIVE BREAKPOINTS

--bp-sm: 640px   (mobile → tablet)
--bp-md: 1024px  (tablet → desktop)
--bp-lg: 1280px  (desktop → large)

Below 1024px: collapse sidebars, stack columns
Below 640px: hamburger nav, single column

═══════════════════════════════════════════════════════════════════
🎬 ANIMATION RULES
═══════════════════════════════════════════════════════════════════

ALL transitions: 150ms ease-out. No more, no less.

Allowed animations:
- Color transitions on hover
- Opacity fades
- Small Y-translate (1-2px) on hover
- Width animation on progress bars

FORBIDDEN:
- Spinning loaders (use thin pulsing line instead)
- Bouncing elements
- Parallax
- Confetti
- Any animation > 300ms
- Slide-in modals (use fade only)

LOADING STATE = single 2px horizontal line under nav with
  background: linear-gradient(90deg, transparent, --accent, transparent)
  animation: shimmer 1.5s infinite
  No spinner. Ever.

═══════════════════════════════════════════════════════════════════
📋 ICONOGRAPHY
═══════════════════════════════════════════════════════════════════

Use Lucide icons ONLY (lucide.dev). One icon library, period.
  Size: 16px (inline), 18px (buttons), 20px (nav)
  Stroke-width: 1.5px (slightly thinner than default for refinement)
  Color: inherits from parent text color

Emoji is allowed ONLY for:
  - Resource type indicators (📦 repo, 🎬 video, etc.) — already defined
  - Section emoji in headers (sparingly: 🧠 AI, 🔍 Search, ⚙ Settings)

NEVER mix emoji and Lucide in the same context.

═══════════════════════════════════════════════════════════════════
🗣 COPY / MICRO-COPY VOICE
═══════════════════════════════════════════════════════════════════

Voice: Direct, technical, no fluff. Like a senior engineer wrote it.

YES:
  "Add resource"        not  "✨ Add a Magical Resource ✨"
  "15 resources"        not  "You have 15 amazing resources!"
  "Sync failed"         not  "Oops! Something went wrong 😢"
  "Run audit"           not  "Let's check things out"

Empty states: Brief, helpful, no apology.
  "No resources yet. [+ Add your first]"
  "No duplicates found."
  "Pool is healthy."

Errors: State what failed, suggest next action.
  "Extraction failed. URL returned 403. [Retry] [Add manually]"

Button labels: verb + noun. Sentence case.
  "Add resource"  "Generate path"  "Run evolution"

═══════════════════════════════════════════════════════════════════
📑 PAGE LAYOUT TEMPLATE (use for every page)
═══════════════════════════════════════════════════════════════════

<body>
  <nav class="top-nav">[logo] [items] [search]</nav>
  
  <main class="page">
    <header class="page-header">
      <h1 class="page-title">{title}</h1>
      <div class="page-actions">{primary action}</div>
    </header>

    <!-- Optional: page-level meta strip -->
    <div class="page-meta">{breadcrumb / context}</div>

    <section class="page-content">
      {content}
    </section>
  </main>

  <div class="toast-container" aria-live="polite"></div>
</body>

═══════════════════════════════════════════════════════════════════
🚫 ANTI-PATTERNS — NEVER DO THESE
═══════════════════════════════════════════════════════════════════

✗ Gradients (except the loading shimmer)
✗ Glassmorphism / heavy blur
✗ Neumorphism
✗ Multiple accent colors on one page
✗ Drop shadows on text
✗ Rounded corners > 12px
✗ Capitalize labels
✗ Animations longer than 300ms
✗ Loading spinners (use shimmer bar)
✗ Emoji in body text (only icons/sections)
✗ Bootstrap-style alert boxes
✗ Material Design ripples
✗ Glowing borders on everything (max 1 glow on screen)
✗ More than 3 button variants
✗ Sidebar nav (we use top nav only)
✗ Breadcrumbs > 3 levels
✗ Hover effects that move > 2px
✗ Multiple H1 per page
✗ Centered body text (left-align always, except stats)
✗ Italic except for hints / placeholders

═══════════════════════════════════════════════════════════════════
✅ APPROVAL CHECKLIST (run mentally before submitting any UI)
═══════════════════════════════════════════════════════════════════

[ ] All colors come from CSS custom properties — no hardcoded hex
[ ] All spacing comes from --space-N scale
[ ] All text sizes come from --text-N scale
[ ] Mono font used for: IDs, URLs, numbers, tags, status badges
[ ] Sans font used for: everything else
[ ] One primary button max per view
[ ] One glowing element max per view
[ ] One H1 per page
[ ] Loading state uses shimmer bar, not spinner
[ ] Empty state is brief and actionable
[ ] All transitions are 150ms
[ ] No emoji in body text (only sections/types)
[ ] No gradient except loading shimmer
[ ] Status uses [BRACKETED] mono labels
[ ] Page has top nav + page-header + page-content structure
[ ] Lucide icons only (16/18/20px, stroke 1.5)

═══════════════════════════════════════════════════════════════════
🧠 WHEN GENERATING A PAGE, ALWAYS:
═══════════════════════════════════════════════════════════════════

1. State which page you're building (e.g. "Building /add page")
2. Show the page header (title + primary CTA)
3. Show the main content area
4. Reference these CSS variables — do not invent new ones
5. Use the corner-bracket signature on the page's hero/key panel
6. Use mono font for the page's "technical" elements
7. Keep negative space generous — 32px padding minimum on panels
8. End with the [BRACKETED] status indicators where applicable
9. If asked for HTML, use semantic tags (<header>, <main>, <section>, <article>)
10. If asked for templates, use Jinja2 syntax matching existing Flask app

═══════════════════════════════════════════════════════════════════
END OF MASTER DESIGN PROMPT v1.0
═══════════════════════════════════════════════════════════════════

This prompt is the source of truth.
If a design decision is not covered here → DEFAULT TO MINIMAL.
If in doubt → REMOVE, don't add.
Less surface area = more clarity = better tool.
