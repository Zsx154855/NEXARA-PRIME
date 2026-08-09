# NEXARA Control Plane V1 — UI Component Map

> Phase 13 Product Architecture | Version 1.0

## Design Philosophy

**Professional. Calm. Enterprise. Human-centered.**

This is a governance dashboard for sovereign AI operations — not a sci-fi interface. The visual language should convey trust, clarity, and control. Think Apple's Server app or Xcode's organizer — tools for professionals who need precise information, not decorative flair.

**Rejected aesthetics**:
- AI HUD / terminal-green-on-black
- Robot avatars / mascot characters
- Cyberpunk neon / glitch effects
- "Futuristic" sci-fi tropes
- Emoji-heavy interfaces

**Embraced aesthetics**:
- Generous whitespace
- Clear typographic hierarchy
- Subtle rounded corners (6-8px)
- Muted, professional color palette
- Precise data visualization
- Thoughtful empty states
- Fluid, restrained motion

---

## Design Tokens

### Color System

```
Professional Slate

Background:
  Base:        #FAFBFC  (card white)
  Surface:     #FFFFFF  (pure white)
  Elevated:    #F6F8FA  (subtle gray)

Text:
  Primary:     #1A1D23  (near-black)
  Secondary:   #5F6B7A  (slate)
  Tertiary:    #8B95A5  (muted)
  Inverse:     #FFFFFF

Border:
  Default:     #E4E8EE
  Strong:      #CED4DE
  Focus:       #2962FF

Status:
  Intent/Info:   #2962FF  (blue)
  Running:       #0EA5E9  (sky)
  Success:       #16A34A  (green)
  Warning:       #F59E0B  (amber)
  Failure/Error: #DC2626  (red)
  Neutral:       #6B7280  (gray)
  Paused:        #8B5CF6  (purple)

Risk Levels:
  R0 (None):     #6B7280
  R1 (Low):      #0EA5E9
  R2 (Medium):   #F59E0B
  R3 (High):     #F97316
  R4 (Critical): #DC2626
```

### Typography

```
Font: Inter (system font stack on macOS: -apple-system, SF Pro Display)

Scale:
  Display:  32px / 1.2  (page titles)
  Heading:  24px / 1.3  (section headers)
  Title:    18px / 1.4  (card titles)
  Subtitle: 15px / 1.5  (card subtitles)
  Body:     14px / 1.6  (default text)
  Caption:  12px / 1.5  (metadata, labels)
  Code:     13px / 1.5  (monospace: SF Mono)

Weights:
  Regular:  400
  Medium:   500
  Semibold: 600
```

### Spacing

```
Scale (4px base):
  xs:  4px
  sm:  8px
  md:  16px
  lg:  24px
  xl:  32px
  2xl: 48px
  3xl: 64px

Component spacing:
  Card padding:   20px 24px
  Card gap:       16px
  Section gap:    32px
  Page padding:   24px (desktop), 16px (mobile)
```

### Border Radius

```
  Button:    6px
  Card:      8px
  Input:     6px
  Modal:     12px
  Badge:     4px
  Avatar:    circle (for status dots)
```

### Shadows

```
  Card:      0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)
  Elevated:  0 4px 12px rgba(0,0,0,0.08)
  Modal:     0 8px 30px rgba(0,0,0,0.12)
  None:      flat backgrounds use no shadow
```

---

## Component Library

### Layout Components

| Component | Description | States |
|-----------|-------------|--------|
| `<AppShell>` | Root layout: sidebar + topbar + content area | Default |
| `<Sidebar>` | Left navigation with icons + labels | Expanded (default), Collapsed (tablet) |
| `<TopBar>` | Top bar: project name, status dot, last updated | Default |
| `<ContentArea>` | Main content with page padding | Default |
| `<PageHeader>` | Page title + description + optional actions | Default, With actions |
| `<Section>` | Content section with optional header | Default, Collapsible |
| `<Card>` | Elevated surface for content groups | Default, Interactive (hover), Selected |
| `<CardGrid>` | Responsive grid of cards (2-4 columns) | Default |

### Navigation Components

| Component | Description |
|-----------|-------------|
| `<SidebarNav>` | Navigation items with icons |
| `<SidebarNavItem>` | Individual nav link with active state |
| `<Breadcrumb>` | Page location breadcrumb (Mission > Detail) |
| `<TabBar>` | Horizontal tab navigation (Mission Detail tabs) |
| `<TabItem>` | Individual tab with count badge |

### Data Display Components

| Component | Description | States |
|-----------|-------------|--------|
| `<StatusBadge>` | Colored pill for state (Intent, Execution, Completed...) | All 33 MissionState values + ApprovalStatus |
| `<RiskBadge>` | Risk level indicator (R0-R4) | R0 through R4 |
| `<MissionRow>` | Table row: ID, objective, state, risk, date, actions | Default, Hover, Selected |
| `<Timeline>` | Vertical timeline of events | Default, With icons, Collapsed groups |
| `<TimelineEvent>` | Single event node: icon, time, description, actor | Default, Highlighted (latest) |
| `<EvidenceCard>` | Evidence item: type, actor, hash, timestamp | Default, Expanded (show content) |
| `<EvidenceContent>` | JSON viewer for evidence artifact | Collapsed, Expanded |
| `<HashDisplay>` | Truncated hash with copy button | Default, Copied feedback |
| `<KeyValueList>` | Label-value pairs (Mission DNA) | Default |
| `<StatCard>` | Single metric: label, value, trend indicator | Default, With sparkline |
| `<DataTable>` | Sortable, filterable data table | Default, Loading, Empty, Error |
| `<CodeBlock>` | Monospace code display (JSON, config) | Default, With line numbers |

### Form Components

| Component | Description | States |
|-----------|-------------|--------|
| `<TextInput>` | Single-line text input | Default, Focus, Error, Disabled |
| `<TextArea>` | Multi-line text input | Default, Focus, Error, Disabled |
| `<Select>` | Dropdown select | Default, Open, Error, Disabled |
| `<Button>` | Action button (primary/secondary/ghost/danger) | Default, Hover, Active, Loading, Disabled |
| `<IconButton>` | Icon-only button | Default, Hover, Active, Disabled |
| `<Toggle>` | On/off toggle (safe mode) | Off, On, Disabled |
| `<SearchInput>` | Search with icon + clear | Default, Focus, With results |

### Feedback Components

| Component | Description | States |
|-----------|-------------|--------|
| `<Toast>` | Temporary notification | Success, Error, Warning, Info |
| `<Banner>` | Persistent inline message | Info, Warning, Error |
| `<Modal>` | Overlay dialog for confirmations | Default, With form |
| `<ConfirmDialog>` | Yes/No confirmation | Default |
| `<Skeleton>` | Loading placeholder (card, row, text) | Default, Animated |
| `<EmptyState>` | Illustration + message + CTA | Default |
| `<ErrorState>` | Error message + retry action | Default |
| `<ProgressBar>` | Linear progress indicator | Determinate, Indeterminate |

### Mission-Specific Components

| Component | Description |
|-----------|-------------|
| `<MissionCreateForm>` | Objective + source dir + submit |
| `<ApprovalCard>` | Approval request with mission context + action buttons |
| `<ApprovalForm>` | Approve/reject with note field |
| `<PlanStepList>` | Ordered list of plan steps with status icons |
| `<PlanStepItem>` | Single plan step: number, description, agent, status |
| `<StateTransitionDiagram>` | Visual state machine: current state highlighted |
| `<ExecutionPoller>` | Background polling component (2s interval) |
| `<ReceiptChain>` | Receipt chain with verification status per link |
| `<MemoryPatchCard>` | Memory patch: kind, content, provenance |
| `<EvaluationScore>` | Pass/fail indicator with criteria breakdown |

### Health Components

| Component | Description |
|-----------|-------------|
| `<HealthOverview>` | System health aggregate: provider, workers, resources |
| `<ProviderCard>` | Provider name, status dot, mock mode indicator |
| `<AdapterGrid>` | Grid of adapter status tiles (browser, git, CI, ...) |
| `<ResourceGauge>` | Horizontal gauge: used / total (tokens, budget) |
| `<WorkerPoolCard>` | Active/completed/failed worker counts |
| `<RecoveryCard>` | Recovery state + check button |

---

## Empty States

```
┌─────────────────────────────────────┐
│                                     │
│           ○  (subtle icon)          │
│                                     │
│        No missions yet              │
│                                     │
│    Create your first mission        │
│    to begin governing AI            │
│    operations.                      │
│                                     │
│        [Create Mission]             │
│                                     │
└─────────────────────────────────────┘

Variants:
- "No evidence recorded"
- "No pending approvals"
- "No events in this timeline"
- "No memory patches"
```

Design: Centered layout, 40px icon in #CED4DE, 18px title, 14px description in #8B95A5, primary CTA button.

## Error States

```
┌─────────────────────────────────────┐
│                                     │
│           ⚠  (amber icon)          │
│                                     │
│        Connection lost              │
│                                     │
│    Unable to reach the NEXARA       │
│    Runtime. Check that the          │
│    server is running.               │
│                                     │
│        [Retry]                      │
│                                     │
└─────────────────────────────────────┘
```

## Loading States

### Page Load
```
┌─────────────────────────────────────┐
│  ┌──────────┐                       │
│  │ Skeleton │  ┌──────────┐        │
│  │ Card     │  │ Skeleton │        │
│  └──────────┘  │ Card     │        │
│                 └──────────┘        │
│  ┌──────────────────────────────┐   │
│  │ Skeleton Table               │   │
│  │ ████████████                 │   │
│  │ ████████████████             │   │
│  │ ██████                       │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

Skeleton cards use subtle pulse animation (#E4E8EE → #F6F8FA → #E4E8EE). No spinner for page loads — skeletons are calmer and convey structure.

### Action Loading
Buttons show a subtle spinner replacing the icon, with the label remaining visible. Example: `[◌ Approving...]` instead of `[Approve]`.

---

## Motion Design

**Principle: Restrained, purposeful, fluid.**

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Page transition | Fade in (opacity 0→1) | 200ms | ease-out |
| Card appear | Fade + slide up (8px) | 250ms | ease-out |
| Status badge change | Crossfade + scale bounce | 300ms | spring |
| Timeline event | Slide in from left (16px) | 200ms | ease-out |
| Modal open | Fade + scale (0.97→1) | 200ms | ease-out |
| Toast appear | Slide from right | 300ms | spring |
| Skeleton pulse | Opacity oscillation | 1.5s infinite | ease-in-out |
| Hover state | Background/border change | 150ms | ease-out |
| Tab switch | Fade content | 150ms | ease-out |

**No**: bouncy overscroll, parallax, particle effects, auto-playing animations, scroll-jacking.

---

## Responsive Strategy

| Breakpoint | Layout |
|------------|--------|
| ≥ 1280px | Full sidebar (240px) + 2-3 column content |
| 1024-1279px | Full sidebar + 2 column content |
| 768-1023px | Collapsed sidebar (icon only, 56px) + 1-2 column |
| < 768px | No sidebar, bottom tab bar, single column, simplified tables |

Desktop-first. Mobile is informational (monitoring and approvals), not for complex data entry.

---

## Tech Stack Mapping

| Concern | Technology |
|---------|-----------|
| Framework | Next.js 16 (App Router) |
| Language | TypeScript (strict, no `any`) |
| Styling | Tailwind CSS v4 |
| Components | shadcn/ui (Radix UI primitives) |
| Icons | Lucide React |
| Data Fetching | SWR (stale-while-revalidate) |
| State | React Context + useReducer |
| Tables | @tanstack/react-table (headless) |
| Charts | Recharts (for resource gauges, sparingly) |
| Forms | react-hook-form + zod validation |
| Toast | sonner |
