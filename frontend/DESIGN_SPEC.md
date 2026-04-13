# PersonaCR Frontend — Complete Cursor Build Prompt

## PASTE THIS ENTIRE DOCUMENT INTO CURSOR AS CONTEXT. Then build page by page.

---

## WHAT THIS IS

PersonaCR is a personalized multi-agent code review system. The backend is fully built and running at http://localhost:8000. This document describes the complete frontend — a React + TypeScript application with 4 pages: landing page, login page, chat page, and dashboard page.

The backend API endpoints:
- POST /api/analyze-repo — analyzes a GitHub repo, builds a coding fingerprint
- POST /api/review — reviews code against a fingerprint using 6 AI agents
- GET /health — health check

---

## DESIGN REFERENCES (study these aesthetics)

1. **mazehq.com** — Agentic AI vulnerability product. Scrolling ticker of real outputs in hero. Numbered flow steps (01→02→03→04) with flow diagram alongside. Scroll-triggered animated stat counters. Dark theme. Product-focused, not marketing fluff.

2. **ciridae.com** — Cinematic dark landing. Massive 60-80px hero text. Numbered sections with two-letter abbreviations (01-WD, 02-SC). Scrolling logo ticker. Dramatic whitespace. Confident typography.

3. **ssscript.app** — Dark SaaS tool. Terminal-style product demo cards. Sharp monospace typography for technical data. Video sections. Polished nav with backdrop-blur.

4. **nisa.peachworlds.com** — Organic gradient backgrounds. Ambient blurred glow orbs behind content. Bento grid feature cards with 1px gap lines. Soft emotional design.

5. **Claude Cowork (claude.ai)** — Dark product page. Clean serif + sans pairing. Tabbed feature demos. Strong CTA sections.

6. **Linear.app** — Precision developer tool. Monospace accents. Tight spatial design.

7. **Notion/Arc** — Editorial serif moments. Generous whitespace. Thoughtful hierarchy.

## DESIGN DIRECTION: "Research-Grade Instrument"

PersonaCR should feel like a tool built by someone who reads research papers and writes clean code — precise, thoughtful, confident. Not flashy startup, not bland template. It should feel like the designer and the engineer were the same person.

**Signature visual:** Abstract code fingerprint pattern — thin curved lines at slight angles, barely visible, representing the concept of a "coding fingerprint." This appears as an animated background on the landing page hero and as subtle decorative elements throughout.

**What makes it NOT look AI-generated:**
- Serif headings (Instrument Serif) — AI tools default to sans-serif
- Monospace data labels (JetBrains Mono) — adds technical credibility
- 1px gap-line grids instead of bordered cards — editorial, not Bootstrap
- Numbered sections with abbreviation codes (01-FP, 02-RV) — deliberate, systematic
- Ambient glow orbs — organic, not geometric
- Real data in every demo (score 80, comp 0.80, 8.5s) — not placeholder lorem ipsum
- The terminal demo card is always dark regardless of theme — like a real terminal

---

## TECH STACK

```
React 18+
TypeScript
Vite (build tool)
React Router v6 (routing + auth guards)
Tailwind CSS (utility styling + CSS variable integration)
Zustand (state management)
Recharts (dashboard charts)
Framer Motion (all animations)
Supabase JS (@supabase/supabase-js for GitHub OAuth)
Lucide React (icons)
```

Install command:
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install react-router-dom zustand recharts framer-motion @supabase/supabase-js lucide-react
npm install -D tailwindcss @tailwindcss/vite
```

---

## THEME SYSTEM

The app supports dark/light mode toggle AND accent color switching. The landing page is ALWAYS dark. The app pages (chat + dashboard) respect the user's theme choice.

### globals.css — paste this as the base stylesheet:

```css
@import "tailwindcss";
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,400;9..40,500&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  /* Typography */
  --font-display: 'Instrument Serif', Georgia, serif;
  --font-body: 'DM Sans', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  
  /* Accent — Purple (default) */
  --accent: #8B7CF6;
  --accent-dark: #6C5CE7;
  --accent-glow: rgba(139,124,246,0.15);
  --accent-surface: rgba(139,124,246,0.06);
  --accent-text: #B4A9FA;
  
  /* Semantic */
  --success: #4ADE80;
  --warning: #FBBF24;
  --error: #F87171;
  --style-accent: #E2A84B;
  --defect-accent: #E25555;
}

/* Blue accent option */
[data-accent="blue"] {
  --accent: #5B8DEF;
  --accent-dark: #3B6FD4;
  --accent-glow: rgba(91,141,239,0.15);
  --accent-surface: rgba(91,141,239,0.06);
  --accent-text: #8CB4F7;
}

/* Teal accent option */
[data-accent="teal"] {
  --accent: #4ECDC4;
  --accent-dark: #2EAD9E;
  --accent-glow: rgba(78,205,196,0.15);
  --accent-surface: rgba(78,205,196,0.06);
  --accent-text: #7EDDD6;
}

/* Coral accent option */
[data-accent="coral"] {
  --accent: #F07167;
  --accent-dark: #D45750;
  --accent-glow: rgba(240,113,103,0.15);
  --accent-surface: rgba(240,113,103,0.06);
  --accent-text: #F5968F;
}

/* Dark theme */
[data-theme="dark"] {
  --bg-primary: #0A0A0B;
  --bg-secondary: #111113;
  --bg-tertiary: #18181B;
  --bg-card: #141416;
  --bg-card-hover: #1C1C1F;
  --text-primary: #EDEDEC;
  --text-secondary: #A1A1A0;
  --text-tertiary: #5C5C5B;
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.14);
}

/* Light theme */
[data-theme="light"] {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F8F8F7;
  --bg-tertiary: #F0F0EE;
  --bg-card: #FFFFFF;
  --bg-card-hover: #F5F5F3;
  --text-primary: #1A1A1A;
  --text-secondary: #6B6B6A;
  --text-tertiary: #9C9C9B;
  --border: rgba(0,0,0,0.08);
  --border-hover: rgba(0,0,0,0.14);
}

/* Landing page always dark regardless of theme */
.landing-page {
  --bg-primary: #0A0A0B;
  --bg-secondary: #111113;
  --bg-tertiary: #18181B;
  --bg-card: #141416;
  --bg-card-hover: #1C1C1F;
  --text-primary: #EDEDEC;
  --text-secondary: #A1A1A0;
  --text-tertiary: #5C5C5B;
  --border: rgba(255,255,255,0.08);
  --border-hover: rgba(255,255,255,0.14);
}

body {
  font-family: var(--font-body);
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: background 0.3s ease, color 0.3s ease;
}

* { transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease; }
```

---

## FILE STRUCTURE

```
frontend/
├── src/
│   ├── pages/
│   │   ├── LandingPage.tsx
│   │   ├── LoginPage.tsx
│   │   ├── ChatPage.tsx
│   │   └── DashboardPage.tsx
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── AuthGuard.tsx
│   │   │   └── ThemeToggle.tsx
│   │   ├── landing/
│   │   │   ├── LandingNav.tsx
│   │   │   ├── Hero.tsx
│   │   │   ├── FingerprintBg.tsx
│   │   │   ├── GlowOrbs.tsx
│   │   │   ├── ScrollingTicker.tsx
│   │   │   ├── ProductShowcase.tsx
│   │   │   ├── HowItWorks.tsx
│   │   │   ├── BentoFeatures.tsx
│   │   │   ├── Stats.tsx
│   │   │   ├── BottomCTA.tsx
│   │   │   └── Footer.tsx
│   │   ├── chat/
│   │   │   ├── MessageList.tsx
│   │   │   ├── BotMessage.tsx
│   │   │   ├── UserMessage.tsx
│   │   │   ├── FingerprintCard.tsx
│   │   │   ├── ReviewResult.tsx
│   │   │   ├── IssueCard.tsx
│   │   │   ├── AgentTrace.tsx
│   │   │   └── ChatInput.tsx
│   │   ├── dashboard/
│   │   │   ├── SummaryCards.tsx
│   │   │   ├── QualityTrend.tsx
│   │   │   ├── IssueBreakdown.tsx
│   │   │   └── ReviewHistory.tsx
│   │   └── ui/
│   │       ├── Button.tsx
│   │       ├── Badge.tsx
│   │       ├── Card.tsx
│   │       └── AccentPicker.tsx
│   ├── hooks/
│   │   ├── useTheme.ts
│   │   └── useInView.ts
│   ├── store/
│   │   └── useStore.ts
│   ├── lib/
│   │   ├── supabase.ts
│   │   └── api.ts
│   ├── styles/
│   │   └── globals.css
│   ├── App.tsx
│   └── main.tsx
├── index.html
├── tailwind.config.ts
├── tsconfig.json
├── vite.config.ts
└── package.json
```

---

## PAGE 1: LANDING PAGE (route: /)

Always dark. This is a product marketing page like mazehq.com and ciridae.com.

### 1A. Scrolling ticker (Maze-inspired)
A horizontal ticker scrolling continuously across the top of the hero, showing real review findings:
```
STYLE: Missing docstring — 70% coverage → DEFECT: No null check — TypeError risk → STYLE: Naming deviates from snake_case → DEFECT: Mutable default argument → STYLE: Function too long (60 lines, avg 15)
```
- Each finding is a small card with a colored left border (amber for style, red for defect)
- Scrolls infinitely using CSS animation (translateX, 30s linear infinite)
- Slightly transparent (opacity 0.5) so it doesn't compete with the hero text
- Sits at the very top, before the nav

### 1B. Nav (sticky, backdrop-blur)
- Left: PersonaCR logo (layered diamond SVG icon + "PersonaCR" in serif)
- Right: "Research" | "GitHub" links (font-mono, 13px, --text-tertiary) + "Sign in" outline button + "Get started" filled accent button
- On scroll: nav gains a border-bottom (--border) and background becomes --bg-secondary with backdrop-blur-lg
- Padding: 16px 40px

### 1C. Hero section
- FingerprintBg component behind everything: 60+ thin lines at random angles, --accent color at 5% opacity, slow CSS animation (rotate + float)
- GlowOrbs: 2 large blurred circles (300px), one top-right using --accent-glow, one bottom-left. CSS animation float up/down 20px over 10s. Opacity 0.25.
- Small label: "PERSONALIZED CODE REVIEW" (font-mono, 11px, uppercase, letter-spacing 3px, --text-tertiary)
- Hero heading (font-display, 60px, letter-spacing -1.5px, line-height 1.05, --text-primary):
  ```
  Your code has a
  fingerprint.
  We review against it.
  ```
  The word "fingerprint." is in italic serif + --accent color
- Subtitle (font-body, 17px, --text-secondary, max-width 460px, line-height 1.7):
  "Every tool reviews against generic rules. PersonaCR learns how you write code, then holds new code to your own standard."
- Two CTA buttons:
  - "Get started" — bg: --accent, color: white, px-6 py-3, rounded-lg, font-medium
  - "Read the research" — border: --border, bg: transparent, color: --text-primary, px-6 py-3, rounded-lg
- All hero content has staggered fade-in animation (Framer Motion: opacity 0→1, y: 14→0, stagger 0.12s per element)
- Padding: 120px top, 80px bottom

### 1D. Product showcase (Ssscript terminal-style)
- Centered, max-width 560px
- Terminal card — ALWAYS dark (#0D0D0F) regardless of theme
  - Fake window chrome: 3 dots (6px circles, #333), title "review output" in font-mono 11px #555
  - Inside the terminal:
    - Score: "80" in font-display 40px --success color + "/100" in font-body 14px #555 + "passed" badge (mono, 10px, bg #162A20, color --success) + "8.5s" on the right (mono, 11px, #444)
    - 3 issue cards stacked:
      - Amber left border (2px, --style-accent): "STYLE" mono label + "Missing docstring. Your fingerprint shows 70% coverage."
      - Red left border (2px, --defect-accent): "DEFECT" mono label + "No null check on input. TypeError risk."
      - Amber left border: "STYLE" mono label + "Naming deviates from your snake_case patterns."
    - Quality pills row: "comp 0.80" | "conc 0.67" | "rel 0.73" in mono 9px, bg #1a1a1a, border #2a2a2a
  - Animation (triggers on scroll into view via Intersection Observer):
    - Score counts up from 0 to 80 (ease-out, 1.5s)
    - Issue cards slide in from left one by one (stagger 0.2s, translateX -20→0, opacity 0→1)
    - Pills fade in last (delay 1s)
- Below terminal: 3 small stat labels in a row, centered:
  "8.5s total" | "6 agents" | "9 papers" (mono, 12px, --text-tertiary, separated by dots)

### 1E. How it works (Ciridae numbered sections + Maze flow style)
- Section label: "HOW IT WORKS" (font-mono, 11px, uppercase, letter-spacing 2px, --text-tertiary, centered)
- 3 columns, each with:
  - Number + abbreviation: "01—FP" / "02—RV" / "03—EV" (mono, 12px, --text-tertiary)
  - Heading (font-display, 22px): "Fingerprint" / "Review" / "Improve"
  - Description (font-body, 13px, --text-secondary, line-height 1.6)
    - FP: "Paste a GitHub repo. We extract 30 features and build a quantified profile of how you write code."
    - RV: "Submit new code. Six specialized agents review it against your patterns in parallel — style, defects, quality."
    - EV: "Track quality over time. See where you deviate most and watch your consistency grow."
  - Subtle connecting line between columns (1px, dashed, --border)
- Animation: stagger fade-in as each column scrolls into view
- Padding: 100px top/bottom
- Max-width: 720px centered

### 1F. Bento feature grid (Nisa-style)
- Section label: "WHAT MAKES THIS DIFFERENT" (mono, 11px, uppercase, centered)
- 2x2 grid using 1px gap (background: --border creates the gap lines, cards fill with --bg-card)
- Border-radius on the outer grid container only (12px), overflow hidden
- Each card padding: 32px
- Card contents:
  1. "Personal, not universal" (serif heading 18px) + "Reviews compare against your coding fingerprint. Every developer gets feedback shaped by their own history." (sans 13px --text-secondary) + subtle fingerprint line decoration (3-4 thin lines at 3% opacity in corner)
  2. "Research-grounded" (serif 18px) + "Built on 9 papers from top venues." + Row of small venue badges: EMNLP, NAACL, ACL, MSR (mono, 9px, bg --accent-surface, color --accent-text, rounded, px-2 py-0.5)
  3. "Parallel agents" (serif 18px) + "Style Analyst and Defect Hunter run simultaneously. Two agentic loops self-correct before results." + Mini agent trace: 6 small colored dots in a horizontal line (purple, coral, coral, pink, teal, green — 8px circles representing each agent)
  4. "Editor-native" (serif 18px) + "MCP server connects to your coding tools." + Three text labels: "Claude Code" | "Cursor" | "VS Code" (mono, 11px, --text-tertiary)
- Card hover: bg shifts to --bg-card-hover, translateY(-1px), transition 0.15s
- Animation: grid fades in on scroll
- Max-width: 720px centered
- Padding: 100px top/bottom

### 1G. Stats section (Maze animated counters)
- 4 numbers in a row, spaced evenly, max-width 600px centered
- Each stat:
  - Number: font-display, 40px, --accent color
  - Label: font-body, 12px, --text-tertiary
- Stats:
  - "48%" — "faster via parallel execution"
  - "69ms" — "quality scoring latency"
  - "9" — "research papers"
  - "$0" — "infrastructure cost"
- Animation: numbers count up from 0 when scrolled into view (use Framer Motion useInView + animate)
  - Percentages: 0→48 with "%" suffix
  - Milliseconds: 0→69 with "ms" suffix
  - Plain numbers: 0→9
  - Dollar: always "$0" (no animation needed)
- Padding: 80px top/bottom
- Border-top: 0.5px solid --border

### 1H. Bottom CTA
- Serif heading 32px: "Start reviewing."
- Sans subtitle 14px --text-secondary: "Sign in with GitHub. First review in under a minute."
- Single button: "Sign in with GitHub" (bg --accent, text white, px-7 py-3)
- Padding: 120px top, 80px bottom
- Border-top: 0.5px solid --border
- Center aligned

### 1I. Footer (NOT ignored — full section)
- Background: --bg-secondary
- Border-top: 0.5px solid --border
- Padding: 48px 40px 32px
- Three columns:
  - Left: PersonaCR logo + "Personalized multi-agent code review" (sans 13px --text-secondary) + "Built by Vaishnavi Chaughule" (sans 12px --text-tertiary)
  - Middle: "Product" heading (mono 11px --text-tertiary uppercase) + links: Chat, Dashboard, API, MCP (sans 13px --text-secondary)
  - Right: "Connect" heading (mono 11px --text-tertiary uppercase) + links: GitHub, LinkedIn, Research (sans 13px --text-secondary)
- Bottom row (full width, border-top --border, padding-top 20px, margin-top 32px):
  - Left: serif italic 13px --text-tertiary: "Grounded in 9 papers from EMNLP, NAACL, ACL, and MSR"
  - Right: mono 12px --text-tertiary: "2026"

---

## PAGE 2: LOGIN PAGE (route: /login)

- Respects theme (dark/light based on user preference or system)
- FingerprintBg in background at 2% opacity (very subtle)
- Centered vertically and horizontally
- Card (max-width 380px, bg --bg-card, border --border, rounded-xl, p-8):
  - PersonaCR logo (icon + serif text) centered
  - Heading: "Sign in" (serif 24px, centered, mt-6)
  - Subtitle: "Continue with your GitHub account" (sans 14px --text-secondary, centered, mt-2)
  - Button (full width, mt-8): "Sign in with GitHub" with GitHub SVG icon
    - Dark mode: bg --text-primary, color --bg-primary
    - Light mode: bg #1a1a1a, color white
    - Rounded-lg, py-3, font-medium
  - Small text (sans 12px --text-tertiary, centered, mt-4): "We only access public repositories"
- Supabase auth:
  ```typescript
  const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  await supabase.auth.signInWithOAuth({ provider: 'github' })
  ```
- After login success: redirect to /chat
- If already logged in: auto-redirect to /chat

---

## PAGE 3: CHAT PAGE (route: /chat, requires auth)

Respects theme. Claude-style layout with collapsible sidebar.

### Sidebar (240px, left)
- Background: --bg-secondary
- Border-right: 0.5px solid --border
- Top section:
  - Logo row: PersonaCR icon + "PersonaCR" serif text
  - "New review" button (full width, border --border, rounded-lg, py-2, flex with + icon)
- Starred section:
  - Label: "Starred" (sans 11px --text-tertiary, px-4)
  - Starred chat items: yellow star icon + title (sans 12px)
- Recent section:
  - Label: "Recent" (sans 11px --text-tertiary, px-4)
  - Chat items: title truncated (sans 12px --text-secondary)
  - Active item: bg --bg-card, left border 2px --accent
- Bottom: user profile card
  - Initials circle (28px, bg --accent-surface, color --accent, rounded-full, font-mono 11px)
  - Name (sans 12px, font-medium) + org below (sans 11px --text-tertiary)
  - 3-dot menu icon on right
- Collapsible: hamburger icon in TopBar toggles sidebar. Sidebar slides with Framer Motion (x: -240→0, 0.2s)

### TopBar
- Left: hamburger toggle + chat title (sans 14px --text-secondary)
- Right: "Chat" | "Dashboard" tab pills (active has border --border + bg --bg-card) + ThemeToggle (sun/moon icon) + AccentPicker (4 small colored dots)

### Chat area (centered, max-width 680px)
- Bot messages (left):
  - Small avatar circle (26px, bg --accent-surface, PersonaCR icon in --accent color)
  - Content below/right of avatar
- User messages (right):
  - bg --bg-secondary bubble
  - border-radius: 14px 14px 4px 14px (sent-message feel)
  
### Bot response: Fingerprint (when user pastes a repo URL):
- Text: "Analyzed X functions across Y files. Fingerprint cached."
- 4-column stat grid:
  - Each card: bg --bg-secondary, rounded-lg, p-2.5
  - Label: mono 10px --text-tertiary
  - Value: sans 16px font-medium

### Bot response: Review (when user pastes code):
- Score row: font-display 28px (green if 70+, amber 50-69, red <50) + "/100" sans 13px --text-secondary + status badge + "8.5s" mono on right
- Issue cards stacked with gap-2:
  - Style: left border 3px --style-accent, bg --bg-secondary, rounded-r-lg
  - Defect: left border 3px --defect-accent, bg --bg-secondary, rounded-r-lg
  - Each: category badge (mono 10px, tiny pill) + severity label (mono 10px --text-tertiary) + description (sans 13px, line-height 1.5)
- Quality pills row: "Comp 0.80" | "Conc 0.67" | "Rel 0.73" | "5 issues" (mono 10px, bg --bg-secondary, rounded-full, px-2.5 py-0.5)
- Collapsible agent trace (HTML details/summary):
  - Summary: "Agent trace" (sans 11px --text-tertiary)
  - Expanded: list of agents, each row:
    - Colored dot (6px circle) + agent name (mono 11px, w-20) + summary (sans 10px --text-tertiary) + timing (mono 10px --text-tertiary, ml-auto)
    - Colors: Planner=#8B7CF6, Style=#D85A30, Defect=#D85A30, QA=#D4537E, Confidence=#1D9E75, STS=#BA7517, Gate=#639922

### Input bar (bottom, sticky):
- Full width within 680px container
- Input: border --border, rounded-xl, py-2.5 px-4, font-body 14px
- Placeholder: "Paste a repo URL, drop a file, or ask a question..."
- Paperclip button (upload, outline) + Send button (bg --accent, rounded-lg)

### Frontend logic:
```typescript
function handleSubmit(message: string) {
  if (message.match(/https?:\/\/github\.com\/[\w-]+\/[\w.-]+/)) {
    callAnalyzeRepo(message.trim())
  } else if (message.includes('\n') && /\b(def |function |class |import |const |let |var |public |private )\b/.test(message)) {
    callReview(message, lastAnalyzedRepo)
  } else {
    addBotMessage("Paste a GitHub repo URL to analyze, or paste code to review.")
  }
}
```

---

## PAGE 4: DASHBOARD PAGE (route: /dashboard, requires auth)

Same sidebar + topbar as chat. "Dashboard" tab active.

### Summary cards (4 columns, gap-3)
- Each: bg --bg-secondary, rounded-lg, p-4
- Label: sans 12px --text-tertiary
- Value: sans 24px font-medium (use --accent for score, --text-primary for others)
- Cards: "Avg score" (80.0) | "Total reviews" (12) | "Top issue" (Documentation) | "Avg latency" (8.5s)

### Quality trend chart (Recharts, 2/3 width)
- Container: border --border, rounded-xl, p-5
- Title: "Quality trend" (sans 14px font-medium)
- LineChart with:
  - Line color: --accent (use CSS variable value)
  - Grid: dashed, --border color
  - Dots on data points
  - X axis: dates, Y axis: 0-100
  - Responsive container

### Issue breakdown (1/3 width, next to chart)
- Container: border --border, rounded-xl, p-5
- Title: "Issue breakdown" (sans 14px font-medium)
- Horizontal progress bars:
  - Documentation (38%, #8B7CF6)
  - Error handling (28%, #D85A30)
  - Naming (20%, #1D9E75)
  - Complexity (14%, #BA7517)
- Each: label (sans 12px) + percentage (sans 12px font-medium) + bar (h-1.5, rounded-full, bg --bg-tertiary with colored fill)

### Review history table (full width)
- Container: border --border, rounded-xl
- Headers: sans 12px font-medium --text-secondary, border-bottom --border
- Columns: Date | Repository | Score | Issues | Status
- Rows: border-bottom --border, py-3 px-5
- Score: font-medium, colored (green 70+, amber 50-69, red <50)
- Status: badge pill (mono 11px):
  - "passed" — bg green/10%, color --success
  - "re-reviewed" — bg amber/10%, color --warning
  - "failed" — bg red/10%, color --error
- Row hover: bg --bg-card-hover
- Click row: navigate to /chat with that session loaded

---

## ROUTING + AUTH

```typescript
// App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/chat" element={<AuthGuard><ChatPage /></AuthGuard>} />
        <Route path="/dashboard" element={<AuthGuard><DashboardPage /></AuthGuard>} />
      </Routes>
    </BrowserRouter>
  )
}

// AuthGuard.tsx
function AuthGuard({ children }: { children: React.ReactNode }) {
  const session = useStore(s => s.session)
  if (!session) return <Navigate to="/login" replace />
  return <>{children}</>
}
```

---

## ZUSTAND STORE

```typescript
interface AppState {
  // Auth
  user: any | null
  session: any | null
  setSession: (session: any) => void
  
  // Chat
  chats: { id: string; title: string; messages: any[]; starred: boolean }[]
  activeChatId: string | null
  
  // Review data
  lastAnalyzedRepo: string | null
  lastFingerprint: any | null
  reviews: any[]
  
  // UI
  sidebarOpen: boolean
  toggleSidebar: () => void
  theme: 'dark' | 'light'
  toggleTheme: () => void
  accent: 'purple' | 'blue' | 'teal' | 'coral'
  setAccent: (a: string) => void
}
```

---

## API INTEGRATION

```typescript
// lib/api.ts
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function analyzeRepo(repoUrl: string) {
  const res = await fetch(`${API}/api/analyze-repo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl }),
  })
  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`)
  return res.json()
}

export async function reviewCode(repoUrl: string, code: string, language = 'python') {
  const res = await fetch(`${API}/api/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, code, language }),
  })
  if (!res.ok) throw new Error(`Review failed: ${res.status}`)
  return res.json()
}
```

---

## ANIMATIONS (Framer Motion)

```
Landing hero: stagger fade-in (opacity 0→1, y 14→0, delay 0.12s each element)
Terminal demo: intersection observer trigger, score counts 0→80 (1.5s), issues stagger slide-in (0.2s each)
Stats: count-up from 0 on scroll into view
Bento grid: fade-in on scroll
Page transitions: fade + translateY(8→0), 0.3s ease
Sidebar toggle: translateX(-240→0), 0.2s
Chat messages: fade + translateY(6→0), stagger 0.05s
Issue cards: stagger slide-in from left, 0.15s delay
Card hover: translateY(-1px), border color shift, 0.15s
Nav scroll: border-bottom opacity 0→1, 0.2s
Theme toggle: all CSS vars transition 0.3s ease (already in globals.css)
```

---

## BUILD ORDER

1. Scaffold: Vite + React + TS + Tailwind + Router. Set up globals.css with theme system.
2. Landing: Nav + Hero + FingerprintBg + GlowOrbs
3. Landing: ProductShowcase terminal + ScrollingTicker
4. Landing: HowItWorks + BentoFeatures + Stats (with scroll animations)
5. Landing: BottomCTA + Footer
6. Login: Supabase GitHub OAuth page
7. Chat: Sidebar + TopBar + ThemeToggle + AccentPicker
8. Chat: MessageList + BotMessage + UserMessage + ChatInput
9. Chat: FingerprintCard + ReviewResult + IssueCard + AgentTrace
10. Dashboard: SummaryCards + QualityTrend + IssueBreakdown + ReviewHistory
11. Connect to backend API
12. Deploy to Vercel
