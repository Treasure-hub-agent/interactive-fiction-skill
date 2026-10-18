<p align="center">
  <img alt="Interactive Fiction Authoring Spec" src="assets/banner.svg#gh-light-mode-only" width="100%"/>
  <img alt="Interactive Fiction Authoring Spec (dark)" src="assets/banner-dark.svg#gh-dark-mode-only" width="100%"/>
</p>

# interactive-fiction

> **Complete interactive-fiction authoring spec v10.3.0** — turns any AI agent into a writer of tense, choice-driven, immersive stories.

> **Not "AI writes a novel for you" — it's "you choose, it writes."**
> You set the opening → the AI writes a segment and offers 5 choices → you pick → the story goes on.
> No deployment, no API keys, no code — drop it into your AI agent and play.

🌐 **[中文](README.md) | English**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-10.3.0-orange.svg)](VERSION)

---

## ✨ What It Does

**interactive-fiction** teaches AI agents how to write interactive fiction — stories with choices, branches, and consequences, like a text adventure. No more one-way narration: every scene ends with choices that move the story forward.

*New to interactive fiction?* It's a story format where you make choices for the protagonist at each step (A/B/C/D/E), and the story branches based on your decisions — think "Choose Your Own Adventure," written live by an AI.

**What you get:**

- 🎭 **Every scene ends with choices**: A/B/C/D/E options after each segment; you can also type anything you'd say or do, and the story follows your lead
- 📖 **Three tones, switch anytime**: Mainline (steady), Immersion (pure story), Power Fantasy (fast-paced, satisfying reversals)
- 🎴 **Characters with depth**: Distill character cards from novels/games or create your own; the AI stays in character
- 💾 **Auto-saving progress**: Plot, affection, and side quests are tracked; resume after interruptions or export as a complete novel
- 🔍 **Continuity that holds**: the AI checks established facts and pays off planted hooks — long arcs stay consistent

---

## What's New (v10.3.0 · Tavern Character Cards, Ready to Play)

**🃏 Bring a SillyTavern card straight into your story (headline)**

- **All three formats**: PNG, JSON and CHARX cards from SillyTavern / Tavo / Chub import with a single "import tavern card" — you get an intake card first (who they are, whether the worldbook is complete), then it is archived
- **Worldbook fires the tavern way**: always-on entries stay in play, keyword entries appear only when triggered, priority and ordering follow the original card — long stories keep their lore without blowing up the context
- **Only what is relevant**: the full worldbook stays local, and each turn injects just the entries that matter (default <=4 entries, <=300 characters each)
- **The source card is read-only**: verified byte-identical before and after, archived as-is with the original author's credit
- **Writing rules stay ours**: the card's global rule fields (system_prompt etc.) are archived but never injected, so the five-option engine keeps its authority

**🧪 Dev toolchain closed loop**

- Pre-commit gates + CI: every change runs the project gates, unit tests and static checks
- Property-based tests: thousands of generated inputs replace hand-written cases, turning past crash-class bugs into permanent defences
- A hard-contract eval harness for model output: five-options / word count / symbol discipline / status bar become machine-checkable assertions
## Install

### Option 1: npx skills

```bash
npx skills add Treasure-hub-agent/interactive-fiction-skill
```

> `npx skills` is a general agent-skill installer; if you don't have it, use Option 2.

### Option 2: Manual copy

Put the repo into your agent's skills directory:

| Client | Skills directory |
|--------|----------|
| Hermes | `~/.hermes/skills/creative/interactive-fiction/` |
| DeepSeek Harness (dsh) | `~/.dsh/skills/interactive-fiction/` |
| Generic convention (shared by agents) | `~/.agents/skills/interactive-fiction/` |
| Claude Code | `~/.claude/skills/interactive-fiction/` |
| Cursor | `~/.cursor/skills/interactive-fiction/` |
| Operit (Android) | `/sdcard/Download/Operit/skills/interactive-fiction/` |

> Any client that can read `SKILL.md` can use this skill — just drop the folder into its skills directory (file read/write access is required; see Platform Support below).

Reload / restart your client, then send the trigger phrase to start a story.

### Option 3: Hermes users · skills tap

```bash
hermes skills tap add Treasure-hub-agent/interactive-fiction-skill
```

Once added, the skill shows up in `hermes skills browse` / `hermes skills search`; `hermes skills check` reports updates.

### Option 4: Operit (Android) users

Operit manages skills itself — no command line needed:

1. Open `Packages → Skills` (or tap the store icon and search for this skill in the market)
2. Tap `+` → choose "Repository" and enter `https://github.com/Treasure-hub-agent/interactive-fiction-skill` (or use "ZIP" with a release package)
3. Make sure the toggle on the right of the entry is **on**, then send the trigger phrase to start a story

> Story data lives in `/sdcard/Download/Operit/novels/`, separate from the skill folder — upgrading or reinstalling the skill keeps your saves. The bookkeeping helper needs Python; without it the skill still works, falling back to the AI reading/writing runtime files directly.

### Upgrade path

- npx: `npx skills update Treasure-hub-agent/interactive-fiction-skill` (or re-add)
- Manual: overwrite from the latest [GitHub Releases](https://github.com/Treasure-hub-agent/interactive-fiction-skill/releases), or overlay changed files (keep your runtime data directory)
- Upgrades never touch existing runtime data (saves and character cards live in a separate storage root)

> Deployment, upgrade and verification details: `references/deployment.md`.

---

## Why It's Needed

Naive AI fiction has a familiar litany of failure:

- ❌ Scene ends with **no choices** — the story becomes a one-way broadcast
- ❌ POV drifts; "you" and "he/she" blur together — readers fall out of the story
- ❌ Length wildly inconsistent; a tense fight gets 300 words, a dull day gets 2,000
- ❌ Characters are interchangeable; dialogue is generic filler
- ❌ Multiple threads contradict each other; saves and switches collapse

**With interactive-fiction**, all of the above become hard rules enforced by a pre-output self-check. The prose carries choices, POV discipline, length targets, and continuity out of the box.

---

## Core Capabilities

| Capability | Description |
|:-----|:-----|
| 🔴 Iron Rule #0 — choices | A/B/C/D/E after every scene (reference + fallback); free-form input is an equally valid (priority) driver; a scene never ends the conversation |
| 🎭 POV consistency | Hard rules for "I/you" vs "he/she"; formatting constraints for multi-character switches |
| 📏 Length windows | 500–1200 words main; 250–400 for tense fights; 800–1200 for emotional/atmospheric |
| 💾 Saves | Lightweight / persistent / milestone tiers; resume, switch stories, export |
| 🎴 Character cards | Pop, edit, deep-create, one-shots; minor characters get cards silently |
| 📖 Three modes | Mainline / Immersion / Power Fantasy |
| 🧩 P0/P1/P2 layering | Constant rules lean; on-demand loading; zero standing context cost |
| 🧠 Memory offload assistant | Optional: four-tier brief + auto-decay; word counts and ledgers tallied automatically |
| 🤖 Sub-agent mode | Optional: delegate prose generation (auto-falls back to main agent if unsupported) |

---

## Quick Start

1. Load the skill in your agent client (Hermes `skill_view`, Claude Code skill mechanism, etc.)
2. Send the trigger phrase → pick an opening route
3. Choose route A (reincarnate as a character from the original work) / B (create your own) / C (worldbuilder mode) / 🎲 random opening → the story begins
4. After each scene, pick A/B/C/D/E to advance
5. Send the help command anytime for the full command reference

> Works out of the box with the main agent producing scenes directly — no extra setup. Sub-agent mode and online distillation are optional enhancements.

---

## Storage & Permissions

The skill creates a storage root (desktop default `~/novels/`; on Android/Operit `/sdcard/Download/Operit/novels/`; overridable via env var `NOVEL_STORAGE_ROOT`) for:

- Novel saves and runtime state (`{story}/meta/novel_runtime.json`)
- Assistant bookkeeping (`{story}/meta/novel_assist.json`)
- Character cards (`{story}/characters/` and `通用角色卡/`)
- Distillation intermediates (`output/characters/`, gitignored)

**File read/write permission is required.** In environments without write access, the skill degrades gracefully (story continues, saves don't persist).

---

## Architecture

```mermaid
%%{init: {"theme": "neutral", "themeVariables": {"fontFamily": "monospace"}}}%%
graph LR
  SKILL[SKILL.md<br/>P0 resident] --> Data[data/*.json]
  SKILL --> Extended[extended/]
  SKILL --> Modes[modes/]
  SKILL --> References[references/]
  SKILL --> Schema[schema/]
  SKILL --> Scripts[scripts/]
```

---

## Platform Fit

| Capability | Required? | If unsupported |
|------|--------|----------------|
| File read/write | ✅ Required | Saves silently degrade |
| Web search | ⚠️ Optional | Distillation falls back to model knowledge |
| Sub-task dispatch (sub-agent) | ⚠️ Optional | Auto-falls back to main agent |
| thinking mode | ⚠️ Optional | Works without; option reasoning slightly weaker |
| Python runtime | ⚠️ Optional | Memory offload assistant is skipped; original bookkeeping flow continues |

---

## FAQ

**Q: How is this different from a plain prompt?**
A: A plain prompt suggests; this skill enforces. Iron Rule #0, POV discipline, and length windows all have mandatory pre-output checks the AI runs every scene.

**Q: Version history?**
A: Runtime detail lives in `references/changelog.md`; a concise release history lives in `CHANGELOG.md` (appended at release time). The `VERSION` file is the single source of truth.

---

## Reading List

- [ai-with-u](https://github.com/Treasure-hub-agent/ai-with-u) — chat companion / character presence, zero system traces

---

## Content Notes

- This skill provides authoring specs for interactive fiction, supporting many genres and emotional arcs
- Relevant scenes are written per its description specs and emotional escalation rules
- The user is responsible for the content they create; this skill provides craft, not prescribed stories

---

## License

MIT License — free to use, modify, distribute. See [LICENSE](LICENSE). Version history in `references/changelog.md`.

---

> — Treasure-hub-agent · 2026 · Twelfth revision

---

## 🕮 Notes & License

- This skill provides an interactive-fiction authoring spec; mature themes are handled by the writing guidelines and emotional escalation rules
- **AI-generated content** — plots and characters are produced live by the model you configure; they do not represent the author's views, and you are responsible for how you use them
- **Data & privacy** — all runtime data (saves, character cards, ledgers) stays on your own device; nothing is uploaded, collected, or reported
- **Compliance** — for mature-themed material, ensure compliance with your local laws and platform rules
- **Models & cost** — bring your own model and runtime; costs and service terms are between you and your provider
- **No warranty** — provided "as is"; generation quality, continuity, and save safety are not guaranteed — please back up
- **MIT License** — free to use, modify, and distribute; keep the original copyright notice when redistributing
- Full terms: [`DISCLAIMER.en.md`](DISCLAIMER.en.md); changelog: `references/changelog.md`
