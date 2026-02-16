# Voice Infrastructure Portal — Frontend Blueprint

> Version 1.0  
> Date: 14 February 2026  
> Classification: Internal Architecture Document

---

## Executive Summary

This document defines the complete frontend strategy for the Voice Infrastructure Portal V2. The portal is a private intelligence system — not a SaaS product. Every design decision should reinforce the sense that this is an engineered tool built for a single user who demands precision, speed, and depth.

The interface will be **dark-only**, **keyboard-first**, and **information-dense** — designed to feel like a professional audio workstation merged with a personal knowledge management system.

---

## 1. Design Philosophy & Visual Language

### 1.1 Core Identity

**Atmosphere:** Command center. Not a dashboard. Not an admin panel.  
**Tone:** Precise, restrained, engineered.  
**Emotional Target:** The interface should feel like opening a well-maintained IDE or professional audio software — tools that respect your time and intelligence.

### 1.2 Visual Principles

| Principle | Implementation |
|-----------|----------------|
| **Density over whitespace** | Information-rich layouts. Every pixel earns its place. |
| **Hierarchy through contrast** | Not through size inflation. Small type with careful weight/opacity variance. |
| **Motion with purpose** | No decorative animation. Transitions communicate state change. |
| **Monochromatic restraint** | Single accent color. No gradients. No color-coding everything. |
| **Edges matter** | Precise borders, deliberate corner radii, consistent gutters. |

### 1.3 Interaction Principles

- **Keyboard-first** — Every action reachable without mouse
- **Progressive disclosure** — Depth available, not demanded
- **Immediate feedback** — State changes visible within 16ms
- **Direct manipulation** — Click targets act like physical controls
- **Context preservation** — Never lose your place, state persists

### 1.4 Anti-Patterns (Explicitly Forbidden)

| Avoid | Rationale |
|-------|-----------|
| Card-based layouts | Generic, wastes space, obscures hierarchy |
| Rounded-everything | Loses precision feel |
| Colorful status badges | Creates visual noise |
| Toast notifications | Interrupts flow |
| Loading spinners | Use skeleton states or progress bars |
| Modal dialogs for forms | Use inline expansion or drawers |
| Hamburger menus | Information should be visible |
| Hover-only information | Critical data always visible |
| "Friendly" empty states | No illustrations, no jokes |

---

## 2. Design System Specification

### 2.1 Color System

Dark theme only. Single neutral scale with one accent.

```css
:root {
  /* Base Neutrals — Cool Gray */
  --bg-base: #0a0a0b;          /* App background */
  --bg-surface: #111113;       /* Primary surface */
  --bg-elevated: #18181b;      /* Elevated panels, hovers */
  --bg-overlay: #1f1f23;       /* Dropdowns, popovers */
  
  /* Borders */
  --border-subtle: #27272a;    /* Dividers, inactive borders */
  --border-default: #3f3f46;   /* Input borders, active dividers */
  --border-strong: #52525b;    /* Focus rings, emphasis */
  
  /* Text */
  --text-primary: #fafafa;     /* Headings, primary content */
  --text-secondary: #a1a1aa;   /* Body text, descriptions */
  --text-tertiary: #71717a;    /* Timestamps, metadata */
  --text-muted: #52525b;       /* Disabled, placeholders */
  
  /* Accent — Restrained Blue */
  --accent: #3b82f6;           /* Primary actions, focus */
  --accent-hover: #2563eb;     /* Hover state */
  --accent-muted: #1e40af;     /* Subtle indicators */
  --accent-subtle: rgba(59, 130, 246, 0.1);  /* Accent backgrounds */
  
  /* Semantic — Minimal */
  --success: #22c55e;          /* Completed states only */
  --error: #ef4444;            /* Errors only */
  --warning: #f59e0b;          /* Requires attention */
  
  /* Status Indicators */
  --status-active: #22c55e;
  --status-processing: #3b82f6;
  --status-pending: #71717a;
  --status-failed: #ef4444;
}
```

### 2.2 Typography

Single typeface. Hierarchy through weight and opacity.

```css
:root {
  /* Font Stack */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  
  /* Scale — Restrained */
  --text-xs: 0.6875rem;    /* 11px — Metadata, timestamps */
  --text-sm: 0.75rem;      /* 12px — Secondary content */
  --text-base: 0.8125rem;  /* 13px — Primary content */
  --text-md: 0.875rem;     /* 14px — Section headings */
  --text-lg: 1rem;         /* 16px — Page section titles */
  --text-xl: 1.125rem;     /* 18px — Page titles */
  
  /* Weights */
  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  
  /* Line Heights */
  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;
  
  /* Letter Spacing */
  --tracking-tight: -0.01em;
  --tracking-normal: 0;
  --tracking-wide: 0.025em;
  --tracking-caps: 0.05em;   /* For uppercase labels */
}
```

### 2.3 Spacing System

4px base unit. Consistent vertical rhythm.

```css
:root {
  --space-0: 0;
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;   /* 20px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */
}
```

### 2.4 Motion System

Purposeful, fast, non-decorative.

```css
:root {
  /* Durations */
  --duration-instant: 50ms;   /* Hover color changes */
  --duration-fast: 100ms;     /* Button feedback */
  --duration-normal: 150ms;   /* Panel transitions */
  --duration-slow: 250ms;     /* Page transitions, overlays */
  
  /* Easings */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);      /* Exits, reveals */
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);  /* State changes */
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1); /* Micro-interactions */
}
```

### 2.5 Elevation & Layering

```css
:root {
  /* Z-Index Scale */
  --z-base: 0;
  --z-elevated: 10;      /* Floating elements */
  --z-sticky: 20;        /* Sticky headers */
  --z-overlay: 30;       /* Drawers, panels */
  --z-modal: 40;         /* Modal dialogs */
  --z-command: 50;       /* Command palette */
  --z-toast: 60;         /* System messages */
  
  /* Shadows — Subtle */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);
  --shadow-overlay: 0 16px 32px rgba(0, 0, 0, 0.6);
}
```

### 2.6 Component States

| State | Visual Treatment |
|-------|------------------|
| **Default** | Base colors, no border emphasis |
| **Hover** | `--bg-elevated`, subtle brightness increase |
| **Focus** | 2px `--accent` ring, `opacity: 1` on text |
| **Active/Pressed** | `--bg-overlay`, slight scale(0.98) |
| **Selected** | `--accent-subtle` background, accent left border |
| **Disabled** | 40% opacity, cursor: not-allowed |
| **Loading** | Animated shimmer on skeleton, or deterministic progress |

### 2.7 Processing Indicators

No spinners. Progress is always deterministic or states are skeleton.

| Type | Implementation |
|------|----------------|
| **Determinate** | Thin horizontal progress bar with percentage |
| **Indeterminate** | Pulsing shimmer on skeleton UI |
| **Step-based** | Numbered steps with current highlighted |
| **Background** | Subtle badge or icon change in nav |

---

## 3. Information Architecture

### 3.1 Navigation Structure

```
┌────────────────────────────────────────────────────────────┐
│ Command Palette (⌘K)                                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────┐  ┌──────────────────────────────────────┐   │
│  │          │  │                                      │   │
│  │ Sidebar  │  │           Main Content               │   │
│  │          │  │                                      │   │
│  │ • Inbox  │  │  ┌─────────────────────────────────┐ │   │
│  │ • Tasks  │  │  │ Context Header                  │ │   │
│  │ • Daily  │  │  ├─────────────────────────────────┤ │   │
│  │ ──────── │  │  │                                 │ │   │
│  │ Projects │  │  │ Content Area                    │ │   │
│  │ ──────── │  │  │                                 │ │   │
│  │ System   │  │  │                                 │ │   │
│  │          │  │  └─────────────────────────────────┘ │   │
│  └──────────┘  └──────────────────────────────────────┘   │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ Status Bar                                                 │
└────────────────────────────────────────────────────────────┘
```

### 3.2 Sidebar Behavior

- **Width:** Fixed 220px, collapsible to 48px (icons only)
- **Collapse trigger:** Edge drag or `⌘\`
- **State persistence:** Stored in localStorage
- **Sections:** Grouped with subtle dividers, not headers
- **Active state:** Left border accent, subtle background

**Sidebar Items:**
```
📥 Inbox (12)           ← Unreviewed notes count
☑️ Tasks                 ← Today's task count badge
📅 Daily                 ← Current day highlighted
📆 Weekly                ← Current week highlighted
───────────────
📁 Projects              ← Expandable, shows active projects
   └─ AlumERP (3)
   └─ Personal
───────────────
⚙️ Settings
🔑 API Keys
📊 Activity
```

### 3.3 Command Palette

Global access via `⌘K`. Central nervous system of the interface.

**Capabilities:**
- Navigate to any page
- Search across all notes
- Quick actions (process file, add tag, copy link)
- Switch between recent items
- System commands (clear cache, reprocess)

**Behavior:**
- Fuzzy search
- Recent commands shown by default
- Category filtering with `/` prefix
- Preview pane for search results

### 3.4 Global State Indicators

| Indicator | Location | Implementation |
|-----------|----------|----------------|
| Watcher status | Status bar (bottom) | Dot color + text |
| Processing queue | Status bar | Count badge |
| API health | Status bar | Green/red dot |
| Sync status | Status bar | Subtle icon |
| Keyboard shortcuts | Status bar right | Show on hover |

### 3.5 Page Hierarchy

```
/v2/                    → Dashboard (Inbox focus)
/v2/inbox               → Full inbox list
/v2/inbox/{id}          → Note detail view
/v2/tasks               → Tasks aggregation
/v2/daily               → Daily notes list
/v2/daily/{date}        → Specific daily rollup
/v2/weekly              → Weekly notes list
/v2/weekly/{week}       → Specific weekly rollup
/v2/projects            → Project folders
/v2/projects/{slug}     → Project note list
/v2/settings            → Configuration
/v2/keys                → API key management
/v2/activity            → API usage log
```

---

## 4. Page-Level Specifications

### 4.1 Dashboard (`/v2/`)

**Purpose:** Mission control. Quick access to recent notes, today's tasks, and system status.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Dashboard                                           ⌘1  14 Feb  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ TODAY ──────────────────────┐  ┌─ RECENT NOTES  ──────────┐ │
│  │                              │  │                          │ │
│  │  3 voice notes captured      │  │  → Brief inquiry...  2m  │ │
│  │  2 tasks extracted           │  │  → Meeting notes...  1h  │ │
│  │  ▓▓▓▓▓▓░░░░░░░░░░░ 42%       │  │  → Project idea...   3h  │ │
│  │                              │  │  → Call summary...   5h  │ │
│  │  [ View Daily Rollup ]       │  │                          │ │
│  └──────────────────────────────┘  └──────────────────────────┘ │
│                                                                 │
│  ┌─ TASKS DUE TODAY  ────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  ☐  Follow up on cluster issue        from: Brief inquiry │  │
│  │  ☐  Review AlumERP deployment         from: Meeting notes │  │
│  │  ☐  Send invoice to client            from: Call summary  │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ QUICK UPLOAD  ───────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  [ Drop audio file or click to upload ]            ⌘U     │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- `TodaySummary` — Note count, task count, processing progress
- `RecentNotesList` — Last 5 notes, hover to preview
- `TasksList` — Today's tasks with source note links
- `QuickUpload` — Drag-drop zone, always visible

**Interactions:**
- Keyboard: `↑↓` navigate lists, `Enter` open, `Space` toggle task
- Click note → Navigate to detail
- Click task checkbox → Toggle inline (optimistic update)
- Drag file → Upload and process

**Shortcuts:**
| Key | Action |
|-----|--------|
| `⌘1` | Go to Dashboard |
| `⌘U` | Focus upload zone |
| `N` | New note (if implemented) |
| `T` | Jump to tasks section |

### 4.2 Inbox (`/v2/inbox`)

**Purpose:** Source of truth. All processed notes in review queue.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Inbox                                    12 notes    ⌘2  Filter │
├─────────────────────────────────────────────────────────────────┤
│ ┌─ FILTERS ─────────────────────────────────────────────────┐   │
│ │ All (12)  │  Unreviewed (8)  │  Has Tasks (3)  │  Tagged   │   │
│ └───────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ○ 14_02_26_brief-inquiry-regarding-clusters      2m ago │   │
│  │   Summary preview text appears here truncated at...      │   │
│  │   ☑ 1 task  │  No tags                          [+ Tag]  │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ ○ 14_02_26_meeting-notes-deployment-review      1h ago  │   │
│  │   Discussion about the AlumERP deployment timeline and...│   │
│  │   ☑ 2 tasks │  #AlumERP #Work                   [+ Tag]  │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │ ● 13_02_26_voice-memo-project-ideas             1d ago  │   │
│  │   Random thoughts about the new project direction and... │   │
│  │   No tasks  │  #Personal                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Showing 12 of 12 notes                          ← 1 of 1 →    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Legend: ○ = unreviewed, ● = reviewed
```

**Components:**
- `FilterBar` — Tab-style filters (not dropdowns)
- `NoteListItem` — Title, preview, metadata, inline tag button
- `Pagination` — Page numbers, not infinite scroll

**Interactions:**
- Click row → Open detail view
- Click tag → Filter by tag
- Click [+ Tag] → Inline tag picker dropdown
- Hover row → Show action icons (archive, delete, open transcript)
- Multi-select with `⌘+Click` or `Shift+Click`
- Bulk actions appear in floating bar when selected

**Inline Tag Picker:**
```
┌─────────────────┐
│ Add Tag         │
├─────────────────┤
│ 🔍 Search...    │
├─────────────────┤
│ ○ AlumERP      │
│ ○ Personal     │
│ ○ Work         │
├─────────────────┤
│ + Create new... │
└─────────────────┘
```

**Shortcuts:**
| Key | Action |
|-----|--------|
| `⌘2` | Go to Inbox |
| `J/K` | Navigate up/down |
| `Enter` | Open selected |
| `T` | Add tag to selected |
| `A` | Archive selected |
| `⌘A` | Select all |
| `Esc` | Clear selection |
| `/` | Focus search |

### 4.3 Note Detail View (`/v2/inbox/{id}`)

**Purpose:** Full note with transcript side-by-side. Editing and tagging.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ← Inbox    Brief Inquiry Regarding Clusters           Actions ▾ │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ META ────────────────────────────────────────────────────┐ │
│  │ 14 Feb 2026, 10:32 AM  │  Duration: 1m 23s  │  Personal    │ │
│  │ Tags: #inquiry  [+ Add]                                    │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─ STRUCTURED NOTE ─────────────┐  ┌─ TRANSCRIPT ──────────┐ │
│  │                               │  │                        │ │
│  │  ## Summary                   │  │  Full verbatim text    │ │
│  │  AI-generated summary text    │  │  of the recording      │ │
│  │                               │  │  appears here with     │ │
│  │  ## Key Points                │  │  proper formatting     │ │
│  │  • Point one extracted        │  │  preserved from the    │ │
│  │  • Point two extracted        │  │  original audio...     │ │
│  │                               │  │                        │ │
│  │  ## Action Items              │  │                        │ │
│  │  - [ ] Task from note         │  │                        │ │
│  │                               │  │                        │ │
│  │  ## Details                   │  │                        │ │
│  │  Extended content...          │  │                        │ │
│  │                               │  │                        │ │
│  └───────────────────────────────┘  └────────────────────────┘ │
│                                                                 │
│  ┌─ SOURCE AUDIO ────────────────────────────────────────────┐ │
│  │  ▶  ━━━━━━━━━━━━━━━━━━━━━━━━○━━━━━━━  0:42 / 1:23          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- `NoteBreadcrumb` — Back navigation with keyboard hint
- `NoteMetaBar` — Date, duration, mode, tags
- `NoteContent` — Rendered markdown with task checkboxes
- `TranscriptPanel` — Collapsible, scrollable raw text
- `AudioPlayer` — Minimal, waveform optional
- `ActionsMenu` — Dropdown: Copy link, Open in Obsidian, Reprocess, Delete

**Split View Modes:**
- Default: 60% note / 40% transcript
- `⌘\` toggles transcript panel
- Drag divider to resize (persisted)

**Interactions:**
- Click task checkbox → Toggle task, sync to daily file
- Double-click tag → Remove tag
- Hover action item → Show "Copy" icon
- Click "Open in Obsidian" → `obsidian://` protocol link

**Shortcuts:**
| Key | Action |
|-----|--------|
| `Esc` or `⌘[` | Back to Inbox |
| `J/K` | Prev/Next note |
| `T` | Add tag |
| `E` | Edit title (inline) |
| `⌘\` | Toggle transcript |
| `Space` | Play/pause audio |
| `⌘C` | Copy current URL |

### 4.4 Tasks View (`/v2/tasks`)

**Purpose:** Aggregated task list from all notes. Daily focus.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Tasks                                     8 open     ⌘3  Today  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ TODAY — 14 Feb 2026 ────────────────────────────────────┐  │
│  │                                                           │  │
│  │  ☐  Follow up on cluster issue                           │  │
│  │      └─ Brief Inquiry Regarding Clusters         10:32   │  │
│  │                                                           │  │
│  │  ☐  Review AlumERP deployment                            │  │
│  │      └─ Meeting Notes: Deployment Review         09:15   │  │
│  │                                                           │  │
│  │  ☑  Send invoice to client                    ✓ 11:42   │  │
│  │      └─ Call Summary with Design Agency          08:30   │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ YESTERDAY — 13 Feb 2026 ────────────────────────────────┐  │
│  │                                                           │  │
│  │  ☑  Update project timeline                   ✓ 16:20   │  │
│  │      └─ Planning Session Notes                   14:00   │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ OLDER ──────────────────────────────────────────────────┐  │
│  │  3 tasks from 5 notes                     [ Show older ]  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- `DateGroup` — Collapsible day sections
- `TaskItem` — Checkbox, task text, source note link, completion time
- `OlderTasksCollapsed` — Summary with expand trigger

**Interactions:**
- Click checkbox → Toggle (strikethrough completed)
- Click source note → Navigate to note detail
- Hover task → Show context menu icon
- Right-click → Context menu (edit, move to today, delete)

**Shortcuts:**
| Key | Action |
|-----|--------|
| `⌘3` | Go to Tasks |
| `J/K` | Navigate tasks |
| `Space` or `Enter` | Toggle selected task |
| `→` | Jump to source note |
| `H` | Hide completed |

### 4.5 Projects View (`/v2/projects`)

**Purpose:** Tag-routed note collections by project.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Projects                                           ⌘4  + New    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ ACTIVE PROJECTS ────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │ AlumERP                                     5 notes │ │  │
│  │  │ ERP system development project                      │ │  │
│  │  │ Last: 2 hours ago              Tags: #AlumERP #dev  │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │ Personal                                    12 notes│ │  │
│  │  │ Personal notes and ideas                           │ │  │
│  │  │ Last: 5 hours ago              Tags: #personal      │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ TAG ROUTING ────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  Tag         →  Folder                         Actions   │  │
│  │  ─────────────────────────────────────────────────────   │  │
│  │  #AlumERP    →  Projects/AlumERP                    ✎ ✕  │  │
│  │  #personal   →  Projects/Personal                   ✎ ✕  │  │
│  │                                                           │  │
│  │  [ + Add Route ]                                          │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- `ProjectCard` — Name, description, note count, last activity, associated tags
- `TagRouteTable` — Inline editable routing configuration
- `NewProjectModal` — Drawer for creating project + route

**Interactions:**
- Click project → View project notes
- Click edit route → Inline text edit
- Click delete route → Confirmation inline (not modal)

### 4.6 Settings (`/v2/settings`)

**Purpose:** System configuration. Dense, technical.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Settings                                               ⌘,       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ PROCESSING ─────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  Default Mode          [ Personal Note      ▾ ]          │  │
│  │  AI Model              [ gemini-2.0-flash   ▾ ]          │  │
│  │  Audio Bitrate         [ 48k                ▾ ]          │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ WATCHER ────────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  Watch Directory       /data/gdrive/VoiceMemos            │  │
│  │  Stability Delay       [ 10 ] seconds                     │  │
│  │  Scan Interval         [ 5  ] seconds                     │  │
│  │                                                           │  │
│  │  Status                ● Running                          │  │
│  │                        [ Restart Watcher ]                │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ OUTPUT ─────────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  Obsidian Vault        /data/gdrive/Obsidian/Workspace    │  │
│  │  Notes Subdirectory    [ VoiceNotes        ]              │  │
│  │                                                           │  │
│  │  Folder Structure:                                        │  │
│  │    Inbox/        Structured notes                         │  │
│  │    Transcripts/  Raw transcriptions                       │  │
│  │    Tasks/        Daily task aggregations                  │  │
│  │    Daily/        Daily rollups                            │  │
│  │    Weekly/       Weekly rollups                           │  │
│  │    Projects/     Tag-routed copies                        │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ DANGER ZONE ────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  [ Clear Processing Registry ]    [ Reprocess All ]       │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Form Patterns:**
- Inline edit with auto-save (debounced)
- Dropdowns for constrained choices
- Text inputs for paths (with validation)
- Danger zone visually separated

### 4.7 Command Palette Overlay

**Purpose:** Keyboard-first navigation and actions.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│        ┌────────────────────────────────────────────┐          │
│        │ 🔍 Search or enter command...              │          │
│        ├────────────────────────────────────────────┤          │
│        │                                            │          │
│        │  RECENT                                    │          │
│        │  ──────                                    │          │
│        │  → Brief Inquiry Regarding Clusters        │          │
│        │  → Meeting Notes: Deployment Review        │          │
│        │                                            │          │
│        │  NAVIGATION                                │          │
│        │  ──────────                                │          │
│        │  ⌘1  Dashboard                             │          │
│        │  ⌘2  Inbox                                 │          │
│        │  ⌘3  Tasks                                 │          │
│        │  ⌘4  Projects                              │          │
│        │                                            │          │
│        │  ACTIONS                                   │          │
│        │  ───────                                   │          │
│        │  ⌘U  Upload audio file                     │          │
│        │  ⌘,  Settings                              │          │
│        │                                            │          │
│        └────────────────────────────────────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

With search results:
┌────────────────────────────────────────────┐
│ 🔍 cluster                                 │
├────────────────────────────────────────────┤
│                                            │
│  NOTES (3)                                 │
│  ─────────                                 │
│  → Brief Inquiry Regarding Clusters   ●    │ ← Selected
│  → Database Cluster Architecture           │
│  → Cluster Deployment Notes                │
│                                            │
│  TAGS (1)                                  │
│  ────────                                  │
│  #cluster                                  │
│                                            │
└────────────────────────────────────────────┘
│              PREVIEW PANE                  │
│  ═══════════════════════════════════════   │
│  Brief Inquiry Regarding Clusters          │
│  14 Feb 2026                               │
│  ───────────────────────────────────────   │
│  Summary preview of the selected note      │
│  appears here for quick context without    │
│  navigating away...                        │
└────────────────────────────────────────────┘
```

**Behavior:**
- `⌘K` opens, `Esc` closes
- Fuzzy search across notes, tags, commands
- `↑↓` navigate, `Enter` execute
- `Tab` moves focus to preview
- `/notes`, `/tags`, `/commands` filter prefixes

---

## 5. Interaction Depth

### 5.1 Hover Behaviors

| Element | Hover Effect |
|---------|--------------|
| List rows | Subtle background shift, reveal action icons |
| Tags | Show remove "×" icon |
| Timestamps | Show relative → absolute time |
| Truncated text | Tooltip with full text |
| Buttons | Brightness increase, no movement |
| Links | Underline appears |

### 5.2 Context Menus

Right-click enabled on:
- Note list items → Copy link, Archive, Delete, Open transcript
- Tasks → Edit, Move to today, Delete
- Tags → Remove, Go to project
- Projects → Rename, Delete, View folder

Implementation: Custom context menu component, not browser native.

### 5.3 Inline Editing

| Element | Edit Trigger | Save Trigger |
|---------|--------------|--------------|
| Note title | Double-click or `E` key | Blur or Enter |
| Tag routes | Click edit icon | Blur or Enter |
| Project name | Double-click | Blur or Enter |

Pattern: Transform text to input, auto-focus, auto-select.

### 5.4 Keyboard-First Workflows

**Full keyboard navigation:**
```
Tab / Shift+Tab     → Move between sections
J / K               → Move within lists
Enter               → Select / Open
Space               → Toggle (tasks, checkboxes)
Esc                 → Back / Close / Deselect
/ or ⌘K             → Search
⌘1-4                → Jump to main sections
⌘\                  → Toggle sidebar
```

**Vim-style bindings (optional, can be toggled):**
```
gg                  → Go to top
G                   → Go to bottom
x                   → Delete selected
dd                  → Delete (same as x)
u                   → Undo last action
```

### 5.5 Multi-Select Model

- `Click` → Select single (deselect others)
- `⌘+Click` → Toggle item in selection
- `Shift+Click` → Range select
- `⌘A` → Select all visible
- `Esc` → Clear selection

**Selection feedback:**
- Selected items get accent left border + subtle background
- Floating action bar appears at bottom
- Action bar shows: `3 selected | Archive | Tag | Delete | × Clear`

### 5.6 Bulk Operations

| Operation | Trigger | Behavior |
|-----------|---------|----------|
| Archive multiple | Select + Click Archive | Moves to "reviewed" status |
| Tag multiple | Select + `T` | Opens tag picker, applies to all |
| Delete multiple | Select + Delete | Confirmation required |
| Export multiple | Select + `⌘⇧E` | Download as ZIP |

### 5.7 Progressive Disclosure

| Pattern | Example |
|---------|---------|
| Collapsed sections | "Older tasks" shows count, click to expand |
| Truncated previews | Note summary shows 2 lines, detail view shows all |
| Hidden metadata | Timestamps show relative, hover for absolute |
| Nested information | Project shows note count, click to see list |

### 5.8 Smart Empty States

No illustrations. Information-dense even when empty.

```
┌─────────────────────────────────────────┐
│ Inbox                                   │
├─────────────────────────────────────────┤
│                                         │
│  No notes yet                           │
│                                         │
│  Notes appear here when audio files     │
│  are processed from Google Drive.       │
│                                         │
│  Watching: /VoiceMemos                  │
│  Status: Idle                           │
│                                         │
│  [ Upload audio file ]  ⌘U              │
│                                         │
└─────────────────────────────────────────┘
```

---

## 6. Advanced UI Capabilities

### 6.1 Command Palette Capabilities

```
/navigate inbox           → Go to Inbox
/search cluster           → Search notes for "cluster"
/tag add:AlumERP          → Add AlumERP tag to selected
/process                  → Upload and process file
/reprocess                → Reprocess selected note
/settings model           → Jump to model setting
/clear registry           → Clear processing registry
/status                   → Show system status
```

### 6.2 Quick-Switch Navigation

`⌘P` opens note picker (distinct from command palette):
```
┌────────────────────────────────────────┐
│ 🔍 Jump to note...                     │
├────────────────────────────────────────┤
│ Brief Inquiry Regarding Clusters   2m  │
│ Meeting Notes: Deployment Review   1h  │
│ Project Ideas and Brainstorm       3h  │
│ Call Summary with Agency           5h  │
│ Weekly Rollup: Feb 10-14           1d  │
└────────────────────────────────────────┘
```

### 6.3 Live Filtering

Inbox filter bar updates results as you type:
- Instant (debounced 150ms)
- URL reflects filter state
- Keyboard navigable (`/` to focus)

### 6.4 Search with Preview

Search results show preview pane:
- Preview updates on selection change
- Shows first 200 chars of note content
- Links to open full note

### 6.5 Split View

Note detail view supports:
- Resizable split (drag divider)
- Hide/show transcript (`⌘\`)
- State persisted per-session

### 6.6 Status Indicators

**Watcher status (status bar):**
```
● Idle          — Green dot, watching
◐ Processing    — Blue animated dot
○ Disconnected  — Gray dot, error state
```

**API status:**
```
API: 3 keys active    — Normal
API: 1 key remaining  — Warning color
API: No keys          — Error color
```

---

## 7. Technical Frontend Architecture

### 7.1 Recommended Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | Vanilla JS + Alpine.js | Already in use, minimal overhead, sufficient reactivity |
| **Templating** | Jinja2 (server-rendered) | FastAPI integration, no build step |
| **Styling** | Tailwind CSS + CSS Variables | Design token system, dark mode support |
| **Icons** | Lucide (tree-shakeable) | Consistent, not FontAwesome bloat |
| **Build** | None (CDN) or Vite (if scaling) | Start simple, migrate if needed |

**Upgrade path if complexity grows:**
- Alpine.js → HTMX for more server-driven interactions
- Or Alpine.js → Vue 3 (petite-vue) for more reactive needs
- Tailwind CDN → PostCSS build for production optimization

### 7.2 Component Structure

```
app/
├── static/
│   ├── css/
│   │   ├── tokens.css          # Design tokens (CSS variables)
│   │   ├── base.css            # Reset, typography, utilities
│   │   └── components.css      # Component-specific styles
│   └── js/
│       ├── app.js              # Alpine.js initialization
│       ├── components/
│       │   ├── command-palette.js
│       │   ├── tag-picker.js
│       │   ├── audio-player.js
│       │   └── context-menu.js
│       └── utils/
│           ├── keyboard.js     # Global keyboard handling
│           ├── api.js          # Fetch wrappers
│           └── storage.js      # localStorage helpers
└── templates/
    └── v2/
        ├── base.html           # Layout with sidebar, status bar
        ├── dashboard.html
        ├── inbox.html
        ├── note-detail.html
        ├── tasks.html
        ├── projects.html
        ├── settings.html
        └── partials/
            ├── sidebar.html
            ├── status-bar.html
            ├── note-list-item.html
            └── task-item.html
```

### 7.3 State Management

| State Type | Storage | Example |
|------------|---------|---------|
| UI preferences | localStorage | Sidebar collapsed, split width |
| Filter state | URL params | Inbox filters |
| Selection state | Alpine.js $store | Multi-select items |
| Form state | Alpine.js local | Settings edits |
| Server state | Fetch on navigate | Note list, task list |

```javascript
// Alpine.js global store
Alpine.store('ui', {
  sidebarCollapsed: localStorage.getItem('sidebar') === 'collapsed',
  selectedNotes: [],
  commandPaletteOpen: false,
  
  toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
    localStorage.setItem('sidebar', this.sidebarCollapsed ? 'collapsed' : 'expanded');
  },
  
  selectNote(id) {
    if (!this.selectedNotes.includes(id)) {
      this.selectedNotes.push(id);
    }
  },
  
  clearSelection() {
    this.selectedNotes = [];
  }
});
```

### 7.4 Routing Model

Server-rendered pages with client-side enhancements:

```python
# FastAPI routes
@app.get("/v2/", response_class=HTMLResponse)
@app.get("/v2/inbox", response_class=HTMLResponse)
@app.get("/v2/inbox/{note_id}", response_class=HTMLResponse)
@app.get("/v2/tasks", response_class=HTMLResponse)
@app.get("/v2/projects", response_class=HTMLResponse)
@app.get("/v2/settings", response_class=HTMLResponse)

# API endpoints for AJAX operations
@app.post("/v2/api/notes/{id}/tags")
@app.post("/v2/api/tasks/{id}/toggle")
@app.get("/v2/api/search")
@app.get("/v2/api/status")
```

### 7.5 CSS Strategy

**Design token structure:**
```css
/* tokens.css */
:root {
  /* All tokens from Design System section */
}

/* Semantic aliases */
.text-primary { color: var(--text-primary); }
.bg-surface { background-color: var(--bg-surface); }
.border-subtle { border-color: var(--border-subtle); }
```

**Tailwind config (if using build):**
```javascript
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'surface': 'var(--bg-surface)',
        'elevated': 'var(--bg-elevated)',
        // Map all tokens
      },
      fontSize: {
        'xs': 'var(--text-xs)',
        'sm': 'var(--text-sm)',
        // Map all typography
      }
    }
  }
}
```

### 7.6 Animation Implementation

```css
/* Consistent transition classes */
.transition-colors {
  transition: color var(--duration-fast) var(--ease-out),
              background-color var(--duration-fast) var(--ease-out);
}

.transition-opacity {
  transition: opacity var(--duration-normal) var(--ease-out);
}

.transition-transform {
  transition: transform var(--duration-normal) var(--ease-spring);
}

/* Component animations */
.command-palette-enter {
  animation: fadeIn var(--duration-normal) var(--ease-out),
             slideUp var(--duration-normal) var(--ease-out);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(8px); }
  to { transform: translateY(0); }
}
```

### 7.7 Performance Constraints

| Metric | Target |
|--------|--------|
| First Contentful Paint | < 1s |
| Time to Interactive | < 2s |
| Largest Contentful Paint | < 1.5s |
| JS bundle size | < 50KB gzipped |
| CSS bundle size | < 20KB gzipped |

**Strategies:**
- Server-render critical content
- Lazy load below-fold content
- Defer non-critical JS
- Preload fonts
- Use `content-visibility: auto` for long lists

---

## 8. Execution Roadmap

### Phase 1: Foundation (Week 1)

**Goal:** Functional V2 layout with design system.

| Task | Priority | Deliverable |
|------|----------|-------------|
| Create design tokens CSS | P0 | `tokens.css` with all variables |
| Build base layout | P0 | `v2/base.html` with sidebar, status bar |
| Implement sidebar | P0 | Navigation working, collapse toggle |
| Dashboard page | P0 | Static layout, basic data display |
| Inbox list page | P0 | Note list with basic styling |

**Skip:** Animation polish, keyboard shortcuts, command palette.

### Phase 2: Core Functionality (Week 2)

**Goal:** Interactive inbox and note detail.

| Task | Priority | Deliverable |
|------|----------|-------------|
| Note detail view | P0 | Split view layout |
| Inline tagging | P0 | Tag picker component |
| Tasks view | P0 | Grouped task list |
| Filter bar | P1 | Inbox filtering |
| Audio player | P1 | Basic playback controls |

**Skip:** Multi-select, bulk actions, context menus.

### Phase 3: Interaction Depth (Week 3)

**Goal:** Keyboard-first, power user features.

| Task | Priority | Deliverable |
|------|----------|-------------|
| Command palette | P0 | `⌘K` navigation and search |
| Keyboard navigation | P0 | J/K, Enter, Esc everywhere |
| Multi-select | P1 | Selection model with floating bar |
| Bulk actions | P1 | Archive, tag, delete selected |
| Context menus | P2 | Right-click actions |

**Skip:** Vim bindings, advanced search filters.

### Phase 4: Polish (Week 4)

**Goal:** Premium feel, edge cases handled.

| Task | Priority | Deliverable |
|------|----------|-------------|
| Animation system | P1 | Transitions on all state changes |
| Empty states | P1 | Informative zero states |
| Error handling | P0 | Graceful failures, retry UI |
| Settings page | P1 | Full configuration UI |
| Projects view | P2 | Tag routing management |

### Phase 5: Refinement (Ongoing)

**Iterate based on usage:**
- Weekly/Daily rollup views
- Search result preview pane
- Split view persistence
- Performance optimization
- Accessibility audit

---

## 9. API Requirements (Backend)

The following API endpoints are required for V2 frontend:

### Navigation & Lists

```
GET  /v2/api/inbox                → List inbox notes (paginated)
GET  /v2/api/inbox/{id}           → Single note detail
GET  /v2/api/tasks                → Aggregated tasks (grouped by date)
GET  /v2/api/projects             → List projects with note counts
GET  /v2/api/daily/{date}         → Daily rollup content
GET  /v2/api/weekly/{week}        → Weekly rollup content
```

### Actions

```
POST /v2/api/notes/{id}/tags       → Add/remove tags { "add": [], "remove": [] }
POST /v2/api/notes/{id}/archive    → Archive note
POST /v2/api/notes/{id}/reprocess  → Reprocess from source audio
DEL  /v2/api/notes/{id}            → Delete note

POST /v2/api/tasks/{id}/toggle     → Toggle task completion
POST /v2/api/upload                → Upload audio for processing

POST /v2/api/routes                → Create tag route
PUT  /v2/api/routes/{tag}          → Update tag route
DEL  /v2/api/routes/{tag}          → Delete tag route
```

### System

```
GET  /v2/api/status                → Watcher status, queue, API health
GET  /v2/api/search?q=             → Full-text search
POST /v2/api/settings              → Update settings
```

---

## 10. Success Criteria

The V2 frontend is complete when:

1. **A note can be processed end-to-end** — Drop file → See in inbox → View detail → Tag → Route to project
2. **Tasks are actionable** — Toggle from tasks view, changes persist
3. **Navigation is fluid** — Never waiting for page load > 500ms
4. **Keyboard is primary** — Can complete all core tasks without mouse
5. **Dark mode is polished** — No harsh contrasts, consistent tokens
6. **Empty states inform** — New user understands system immediately
7. **Status is always visible** — Watcher state, API health, queue position

---

## Appendix: Quick Reference

### Keyboard Shortcuts (Global)

| Shortcut | Action |
|----------|--------|
| `⌘K` | Command palette |
| `⌘P` | Quick-switch notes |
| `⌘1` | Dashboard |
| `⌘2` | Inbox |
| `⌘3` | Tasks |
| `⌘4` | Projects |
| `⌘,` | Settings |
| `⌘\` | Toggle sidebar |
| `⌘U` | Upload file |
| `/` | Focus search |
| `Esc` | Close / Back / Clear |

### File Structure Reference

```
/v2/
├── Dashboard (⌘1)
├── Inbox (⌘2)
│   └── Note Detail
├── Tasks (⌘3)
├── Projects (⌘4)
│   └── Project Detail
├── Daily
│   └── Daily Rollup
├── Weekly
│   └── Weekly Rollup
├── Settings (⌘,)
├── API Keys
└── Activity
```

---

*This document is the source of truth for V2 frontend implementation. Update as decisions are made.*
