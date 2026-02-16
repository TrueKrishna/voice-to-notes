# Voice-to-Notes Frontend Specification V2

> **Status**: Active Implementation  
> **Last Updated**: February 16, 2026  
> **Scope**: Ingest + Projects UX Redesign

---

## Philosophy

This is a **filesystem-native tool**, not a SaaS dashboard.

**Core Principles:**
- **Deterministic** — UI always reflects filesystem state
- **Instant** — No page refreshes for simple actions
- **Dense** — Information-rich, minimal whitespace
- **Finder Energy** — macOS Finder + Obsidian plugin aesthetic
- **Zero Hiding** — All folders and files always visible

---

## 1. INGEST PAGE

**Purpose**: Primary workspace for monitoring and managing incoming audio files.

### A. Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ Ingest                                      🔄 ● Watcher Running │
│ Sorted by Recently Added                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  File  │  Status  │  Ingested ▼  │  Captured  │  Project  │ ⚡  │
│  ───────────────────────────────────────────────────────────────│
│  audio.m4a     🟢 Done      Feb 16  08:27   Feb 16  08:25   📁  │
│  2.1 MB · 3m              2026                2026                │
│  ───────────────────────────────────────────────────────────────│
│  voice.m4a     🔵 Proc...   Feb 16  08:26   Unknown       + Ass │
│  1.8 MB · 2m              2026                                    │
└─────────────────────────────────────────────────────────────────┘
```

### B. Default Sorting

- **Always default**: `ingested_at DESC` (newest first)
- **Visual indicator**: "Ingested ▼" column header
- **User override**: Click header to reverse (optional)

### C. Table Columns

| Column | Width | Content | Behavior |
|--------|-------|---------|----------|
| **File** | 30% | Filename + metadata | Clickable → open audio |
| **Status** | 10% | Colored pill + icon | Visual only |
| **Ingested** | 15% | Two-line timestamp | Sortable (default DESC) |
| **Captured** | 15% | Parsed from filename | Display only |
| **Project** | 20% | Dropdown assignment | Inline editable |
| **Actions** | 10% | Icon row | Hover to reveal |

### D. Column Details

#### 1. File Column
```
audio_recording.m4a
2.1 MB · 3m 15s
```
- **Primary**: Filename (truncate if needed)
- **Secondary**: File size + duration
- **Click behavior**: Open raw audio via OS
- **Hover**: Subtle highlight

#### 2. Status Column

| Status | Icon | Color | Description |
|--------|------|-------|-------------|
| Pending | 🟡 | `var(--warning)` | Queued for processing |
| Processing | 🔵 | `var(--accent)` | Currently processing |
| Done | 🟢 | `var(--success)` | Completed successfully |
| Failed | 🔴 | `var(--error)` | Processing failed |

**Failed rows**:
- Red left border
- Hover shows error tooltip
- Retry + Skip actions visible

#### 3. Ingested Column

```
Feb 16, 2026
08:27
```
- **Format**: Two-line display
- **Parsing**: ISO 8601 → human readable
- **Sort**: Tied to this column (default DESC)

#### 4. Captured Column

```
Feb 16, 2026
08:25
```
or
```
Unknown
```

- **Source**: Parsed from filename (YYYY_MM_DD_HH_MM format)
- **Unknown state**: Muted gray text
- **Purpose**: Distinguish recording time from ingestion time

#### 5. Project Column

**Unassigned state**:
```
+ Assign
```

**Assigned state**:
```
📁 alum  ▼
```

**Behavior**:
- Click → Open dropdown
- Dropdown shows:
  - All projects (alphabetical)
  - Separator line
  - "➕ Create New Project"
- Selecting → Instant update (no reload)
- Before processing → Disabled with tooltip "Process first"

**Dropdown Design**:
```
┌────────────────────┐
│ 🔍 Search...       │
├────────────────────┤
│ 📁 alum            │
│ 📁 personal        │
│ 📁 work            │
├────────────────────┤
│ ➕ Create New...   │
└────────────────────┘
```

#### 6. Actions Column

Icon row (hover to reveal):
- **🎧** Open Audio (always available)
- **📝** Open Note (if processed)
- **🔄** Reprocess (if failed/completed)
- **🗑** Delete (confirmation required)

**States**:
- Available: Full opacity
- Disabled: 30% opacity, no cursor
- Hover: Slight scale + color shift

### E. Row Interaction Rules

- **Hover**: Subtle background change (`var(--bg-elevated)`)
- **Click row**: No action (prevents accidental navigation)
- **Click column**: Action specific to that column
- **All actions inline**: No forced navigation

---

## 2. PROJECTS PAGE

**Purpose**: Visual overview of user-created project folders.

### A. Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ Projects                                               + New     │
│ Sort by: Last Modified ▾                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 📁 alum  │  │ 📁 work  │  │ 📁 pers  │  │ 📁 docs  │       │
│  │          │  │          │  │          │  │          │       │
│  │ 12 notes │  │  8 notes │  │  5 notes │  │  0 notes │       │
│  │ Updated: │  │ Updated: │  │ Updated: │  │ Updated: │       │
│  │ Feb 16   │  │ Feb 15   │  │ Feb 14   │  │ Never    │       │
│  │ 08:25    │  │ 14:30    │  │ 09:15    │  │          │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### B. Grid Layout

- **Responsive**: 4-6 columns depending on viewport width
- **Tile size**: Fixed height (~180px)
- **Spacing**: Consistent gutters (16px)
- **Wrap**: Auto-wrap to new rows

### C. Project Tile Design

```
┌─────────────────────┐
│ 📁 alum             │
│                     │
│ 12 notes            │
│                     │
│ Last updated:       │
│ Feb 16, 2026 — 08:25│
│                     │
│                  ⋮  │  ← 3-dot menu (hover)
└─────────────────────┘
```

**States**:
- **Default**: Subtle border, no shadow
- **Hover**: Slight elevation, border highlight
- **Empty (0 notes)**: Muted text, still visible

### D. Tile Actions (3-dot Menu)

Click **⋮** reveals:
```
┌─────────────────────┐
│ 🗂 Open in Finder   │
│ ✏️ Rename            │
│ 🗑 Delete            │
└─────────────────────┘
```

**Rename Flow**:
1. Click "Rename"
2. Tile title becomes editable
3. Press Enter → Confirm
4. Press Escape → Cancel
5. Validation: No empty names, no duplicates

**Delete Flow**:
1. Click "Delete"
2. Confirmation modal:
   ```
   Delete "alum" project?
   
   Warning: This deletes the folder.
   Notes inside will NOT be deleted.
   
   [Cancel]  [Delete Folder]
   ```
3. Confirm → Folder removed, UI updates instantly

### E. Empty Project Display

Even if folder has 0 notes, **always show tile**:
```
┌─────────────────────┐
│ 📁 empty-project    │
│                     │
│ 0 notes             │  ← Muted color
│                     │
│ Never updated       │  ← Muted color
└─────────────────────┘
```

**Rationale**: Folders exist in filesystem → Must be visible.

### F. Sorting Controls

Dropdown above grid:
```
Sort by: [Last Modified ▾]
```

Options:
- **Last Modified** (default)
- **Name** (A-Z)
- **Note Count** (high to low)

### G. Create Project Flow

Click **+ New Project**:

1. New tile appears at top (inline)
2. Title field is focused and editable
3. Placeholder: "Project name"
4. Press Enter → Folder created, tile persists
5. Press Escape → Cancel, tile disappears

**No modal. No page transition. Pure inline editing.**

---

## 3. PROJECT ASSIGNMENT FEEDBACK LOOP

**Goal**: When a project is assigned to a note, the UI updates **everywhere instantly**.

### Flow:

1. User clicks "+ Assign" in Ingest table
2. Dropdown opens
3. User selects "alum"
4. **Instant updates**:
   - Ingest row: Shows "📁 alum ▼"
   - Projects page: "alum" tile count increments
   - Projects page: "alum" last modified updates
5. **Zero page refresh**

### Implementation:

- Use WebSocket or SSE for live updates
- Or: Optimistic UI update + background sync
- Fallback: Poll `/api/system-status` every 3s (current behavior)

---

## 4. REMOVE MODE FROM PROJECTS PAGE

**Critical architectural fix**:

Projects page **must NOT** group by:
- `mode` (system classification)
- Processing type

**Why**:
- **Mode** = System's understanding (personal_note, meeting, idea)
- **Projects** = User's organization (alum, work, personal)

**Keep them separate.**

Only show **user-created project folders**. Nothing else.

---

## 5. VISUAL LANGUAGE

### Tone
- **Dark minimal** — Single accent color, neutral grays
- **Finder energy** — Feels like a native macOS tool
- **Obsidian plugin vibe** — Dense, information-rich
- **Tool, not product** — No marketing fluff

### Typography
- **Headings**: 14-16px, medium weight
- **Body**: 12-13px, regular weight
- **Metadata**: 11px, muted color
- **Monospace**: For timestamps and paths

### Spacing
- **Dense, not cramped**: 8px base unit
- **Gutters**: 16px between major sections
- **Table rows**: 40-44px height
- **Cards**: 16px internal padding

### Colors (Dark Theme)

```css
--bg-base: #0a0a0b;
--bg-surface: #111113;
--bg-elevated: #18181b;
--border-subtle: #27272a;
--text-primary: #fafafa;
--text-secondary: #a1a1aa;
--text-muted: #71717a;
--accent: #3b82f6;
--success: #22c55e;
--warning: #f59e0b;
--error: #ef4444;
```

### Anti-Patterns (Forbidden)

❌ Card-based everything  
❌ Excessive whitespace  
❌ Toast notifications  
❌ Modal dialogs for simple actions  
❌ Hamburger menus  
❌ Hover-only critical information  
❌ Friendly empty states with illustrations  

---

## 6. BEHAVIORAL REQUIREMENTS

### Filesystem Fidelity

**Rule**: If it exists in the filesystem, it shows in the UI.

- Folder created → Tile appears
- File added → Row appears
- File deleted → Row disappears
- Note moved → Project count updates

**Zero hiding. Zero guessing.**

### Instant Updates

Actions that must update instantly:
- Project assignment
- Note creation
- Folder creation
- File processing completion

**No "refresh to see changes" allowed.**

### No Page Hopping

Simple actions stay inline:
- Assign project → Dropdown in table
- Rename project → Inline edit
- Delete file → Confirmation inline

**Modal dialogs only for destructive actions.**

---

## 7. SUCCESS CRITERIA

User drops file in watched folder:
1. ✅ File appears at top of Ingest table
2. ✅ Status shows "Pending"
3. ✅ Watcher picks it up
4. ✅ Status changes to "Processing"
5. ✅ Processing completes
6. ✅ Status changes to "Done"
7. ✅ User clicks "+ Assign" → Dropdown appears
8. ✅ User selects "alum"
9. ✅ Row shows "📁 alum ▼"
10. ✅ User navigates to Projects page
11. ✅ "alum" tile shows updated count
12. ✅ "alum" tile shows "Last updated: Just now"

**UI matches reality at every step.**

---

## 8. IMPLEMENTATION NOTES

### Technology Stack
- **Backend**: FastAPI (Python)
- **Frontend**: Alpine.js (no build step)
- **Styling**: Custom CSS with CSS variables
- **Icons**: Lucide icons
- **No dependencies**: Tailwind, React, Vue, etc.

### File Structure
```
app/
├── templates/v2/
│   ├── dashboard.html      # Ingest page (primary view)
│   ├── projects.html       # Projects grid
│   └── base.html           # Shared layout
├── static/
│   ├── css/v2/
│   │   ├── tokens.css      # Design system variables
│   │   └── base.css        # Core styles
│   └── js/v2/
│       └── app.js          # Alpine.js components
└── v2_routes.py            # FastAPI routes
```

### API Endpoints Required

```python
# Ingest
GET  /v2/api/ingest-files          # List files with all metadata
POST /v2/api/ingest-files/{id}/assign-project
POST /v2/api/ingest-files/{id}/reprocess
DELETE /v2/api/ingest-files/{id}

# Projects
GET  /v2/api/projects               # List user projects
POST /v2/api/projects               # Create new project
PUT  /v2/api/projects/{name}        # Rename project
DELETE /v2/api/projects/{name}      # Delete project folder

# System
GET /v2/api/system-status           # Current implementation (keep)
```

---

## 9. MIGRATION STRATEGY

### Phase 1: Backend API (Current)
- ✅ `ingested_at` column added
- ✅ Sorting by `ingested_at DESC` implemented
- ✅ Filename format changed to YYYY_MM_DD_HH_MM

### Phase 2: Ingest Table Redesign (Next)
- [ ] Update dashboard.html template
- [ ] Add project dropdown component
- [ ] Add captured_at parsing logic
- [ ] Add inline actions (reprocess, delete)
- [ ] Update CSS for dense layout

### Phase 3: Projects Page Redesign
- [ ] Remove mode grouping
- [ ] Implement grid layout
- [ ] Add tile actions (rename, delete)
- [ ] Add sorting controls
- [ ] Update CSS for compact tiles

### Phase 4: Live Updates
- [ ] Implement optimistic UI updates
- [ ] Add feedback loop for project assignment
- [ ] Ensure instant sync across views

---

## 10. OPEN QUESTIONS

1. **Captured timestamp parsing**: Should we parse from audio metadata or just filename?
2. **Project folder location**: Always `VoiceNotes/Projects/{name}/`?
3. **Delete behavior**: Confirm deletion moves to trash or permanently deletes?
4. **Search/filter**: Add search bar to Ingest table?
5. **Keyboard shortcuts**: ⌘K command palette for quick actions?

---

## Appendix: Visual Mockups

### Ingest Table (Dense Layout)
```
File                    Status  Ingested ▼      Captured        Project   Actions
────────────────────────────────────────────────────────────────────────────────
audio_note.m4a          🟢 Done  Feb 16, 2026   Feb 16, 2026   📁 alum    🎧📝🔄🗑
2.1 MB · 3m 15s                 08:27           08:25
────────────────────────────────────────────────────────────────────────────────
voice_memo.m4a          🔵 Proc  Feb 16, 2026   Unknown        + Assign   🎧
1.8 MB · 2m 40s                 08:26
────────────────────────────────────────────────────────────────────────────────
meeting_rec.m4a         🟡 Pend  Feb 16, 2026   Feb 16, 2026   + Assign   🎧
3.2 MB · 5m 10s                 08:25           08:23
────────────────────────────────────────────────────────────────────────────────
```

### Projects Grid
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ 📁 alum     │  │ 📁 work     │  │ 📁 personal │  │ 📁 research │
│             │  │             │  │             │  │             │
│ 12 notes    │  │ 8 notes     │  │ 5 notes     │  │ 0 notes     │
│             │  │             │  │             │  │             │
│ Updated:    │  │ Updated:    │  │ Updated:    │  │ Never       │
│ Feb 16      │  │ Feb 15      │  │ Feb 14      │  │ updated     │
│ 08:25       │  │ 14:30       │  │ 09:15       │  │             │
│          ⋮  │  │          ⋮  │  │          ⋮  │  │          ⋮  │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

---

*End of Specification*
