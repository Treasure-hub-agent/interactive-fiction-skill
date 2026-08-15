# interactive-fiction

> **Complete interactive-fiction authoring spec v10.0.0** — turns any AI agent into a writer of tense, choice-driven, immersive stories.

🌐 **[中文](README.md) | English**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-10.0.0-orange.svg)](VERSION)

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

## What's New (v10.0.0 · Emotion Narrative Upgrade)

**💗 Much stronger emotional storytelling (headline)**
- New three-stage "emotional progression": spark → ambiguity → commitment, each stage with clear beats and resolution signals
- Built-in sample prose for the spark stage: how to write micro-expressions, eye contact, and verbal teasing
- Expanded emotion motif library: subtext dialogue, keepsakes, sharing an umbrella in rain, walking side by side, formality-to-intimacy name shifts, whispers
- Revamped option tag pool: gentle approach / restrained heartbeat / active probe / warm response / step back & leave space / words left unsaid / feelings stirring beneath

**🧭 Complete command system**
- New command domains: Scene Card, Recap, Undo/Redo — plus Foreshadowing/Suspense in the Query domain; 16 domains in total
- "Load save #N" / "Delete save #N" for multi-save management
- Distillation now offers "dialogue rehearsal": chat freely with the character, get a five-dimension fidelity report, and save the session into the character card

**📦 Experience & engineering**
- Full-story export with md/txt formats, chapter-separated
- Transmigration openings: ask the AI for recommendations, auto-detect existing character cards to skip re-distillation
- New validation gate: version consistency, tag uniqueness, file-reference integrity — automated before release

> Full history: [`references/changelog.md`](references/changelog.md). The version number is authoritative in the root `VERSION` file.

---

## Install

### Option 1: npx skills (recommended)

```bash
npx skills add Treasure-hub-agent/interactive-fiction-skill
```

### Option 2: Manual copy

Copy the repo into your agent's skills directory:

| Client | Skills directory |
|--------|------------------|
| Hermes | `~/.hermes/skills/creative/interactive-fiction/` |
| Claude Code | `~/.claude/skills/interactive-fiction/` |
| Cursor | `~/.cursor/skills/interactive-fiction/` |

Reload / restart your client, then send the trigger phrase to start (default is "加载小说包" — you can configure your own trigger in the skill file).

### Option 3: Bundled in the dsh-story plugin (in development)

The `dsh-story` plugin will bundle this skill (in development) — installing / upgrading the plugin installs / upgrades the skill automatically, no manual copy needed.

### Upgrading

- npx install: `npx skills update Treasure-hub-agent/interactive-fiction-skill` (or re-add)
- Manual copy: overwrite with the latest [GitHub Releases](https://github.com/Treasure-hub-agent/interactive-fiction-skill/releases) package, or incrementally overwrite changed files (keep your runtime data directory)
- dsh-story plugin (in development): updates automatically with the plugin
- Upgrades never touch your existing runtime data (novel saves and character cards live in a separate storage directory)

---

## Why You Need It

The most common failures when asking an AI to write interactive fiction:

- ❌ Forgets to offer choices at the end of each scene → the story becomes a monologue
- ❌ POV drift: "you" and "he/she" get mixed up, breaking immersion
- ❌ Wildly inconsistent length: 300 words for a fight scene, 2000 for filler
- ❌ Every character sounds the same
- ❌ Multiple plot threads contradict each other; saves and switches break

**With interactive-fiction**, all of the above become enforced rules with a per-turn self-check — choices, POV, length, and consistency are guaranteed before output.

---

## A Taste of It

```
You stand at the gates of the city, torchlight flickering across the walls.
The guard eyes you up and down.

A. "I'm here to see the Duke. Official business."
B. Slip through the shadowed side gate.
C. Ask what's happened here tonight.
D. Turn around and leave — this city feels wrong.

> B

You press yourself into the shadows. Two guards pass within arm's reach,
laughing about something you can't quite catch...
```

Every scene ends this way — choices that shape what happens next.

---

## Core Capabilities

| Capability | Description |
|------------|-------------|
| 🔴 Rule #0 (non-negotiable): Choice mechanism | A/B/C/D/E options after every scene (with guidance + fallback); free input carries equal/higher weight; the scene never ends the conversation |
| 🎭 POV consistency | Hard rules for "I/you" protagonist and "he/she" others; formatting constraints for multi-character switches |
| 📏 Length windows | 500–1200 words main range; 250–400 for urgent fights; 800–1200 for emotional/atmosphere beats |
| 💾 Save system | Lightweight / persistent / milestone tiers; session recovery after interruption, story switching, export |
| 🎴 Character card system | Quick-add / edit / deep-create / short-form cards; background characters auto-saved |
| 📖 Three modes | Mainline / Immersion / Power Fantasy |
| 🧩 P0/P1/P2 layering | Always-on rules stay lean; everything else loads on demand — no persistent context overhead |
| 🤖 Sub-agent mode | Optional: delegate scene generation to a sub-agent (automatically falls back to main agent if unsupported) |

---

## Quick Start

1. Load the skill in your agent client (Hermes `skill_view`, Claude Code skill mechanism, etc.)
2. Send the trigger phrase → pick an opening route
3. Choose route A (reincarnate as a character from the original work) / B (create your own) / C (worldbuilder mode) / 🎲 random opening → the story begins
4. After each scene, pick A/B/C/D/E to advance
5. Send the help command anytime for the full command reference (default: "帮助")

> Works out of the box with the main agent producing scenes directly — no extra setup. Sub-agent mode and online distillation are optional enhancements.

---

## Storage & Permissions

The skill creates a storage root in your user directory (default `~/novels/`, overridable via env var `NOVEL_STORAGE_ROOT`) for:

- Novel saves and runtime state (`{story}/meta/novel_runtime.json`)
- Character cards (`{story}/characters/` and `通用角色卡/`)
- Distillation intermediates (`output/characters/`, gitignored)

**File read/write permission is required.** In environments without write access, the skill degrades gracefully (story continues, saves don't persist).

---

## Contributing

Issues, ideas, and pull requests are welcome — [open an issue](https://github.com/Treasure-hub-agent/interactive-fiction-skill/issues) or fork the repo.

## License

MIT © 2026 Treasure-hub-agent. See [LICENSE](LICENSE).
