# The Sovereign Engineering & Study Companion: Dhriti Handbook (v0.7.0+)

> **Welcome!** If you are reading this, you are looking at **Dhriti** — an open-source, sovereign, on-device attention wall, focus engine, and placement readiness system. 
> 
> You or a friend might have asked:
> *"What on earth is this project? Why does it exist? How do I actually use it without getting overwhelmed by all the architecture docs?"*
> 
> This handbook is written in plain, friendly language for complete beginners and sovereign engineers alike.

---

## 1. The Short Answer: What is Dhriti?

If you've ever:
- Sat down at 10:00 AM promising to prepare for technical interviews, LeetCode, or study core CS,
- But by 3:00 PM found yourself watching YouTube essays, scrolling Twitter/Reddit, browsing tech specs, or prompting AI chatbots for 6 hours straight without writing a single line of real code yourself,
- And ended the day feeling exhausted, guilty, and unprepared...

**Dhriti was built specifically for you.**

Most website blockers fail because they treat you like a toddler: they show you cute timers, guilt-trip you with angry tomato icons, or are so easy to disable that you kill them in Task Manager the second you crave a dopamine hit.

Dhriti takes the opposite approach. It is built on **Sovereignty, Honesty, and Structure**:
1. **The Day Window:** You set your focus hours (e.g. 10:00 AM to 9:00 PM). During this window, you define a single clear daily contract with 1–3 concrete study/code targets.
2. **The Sovereign Wall:** While the day is active, non-study websites (YouTube, Reddit, social media, entertainment) are silently intercepted.
3. **Recall Before Reveal:** Instead of letting you binge-watch videos passively, Dhriti makes you prove you learned the material. You submit a short synthesis recall (>= 50 words) to verify the target.
4. **Placement Defense:** It parses your code and asks you real technical interview questions (architecture, failure modes, complexity) to prepare you for actual placement interviews.
5. **Zero Data Leaks:** Everything runs 100% locally on your own machine (SQLite, local embeddings, local AST analyzer, optional local Ollama). Zero tracking, zero telemetry sent to corporate servers.

---

## 2. When and Why Should You Use It?

| Scenario | How Dhriti Handles It |
| :--- | :--- |
| **Placement & Campus Prep** | Forces you to actually solve DSA problems and defend code rather than just passively reading solutions. |
| **Deep Work / Semester Exams** | Shuts down distracting tab-hopping and holds you to your declared daily contract until your evening release. |
| **AI Addiction / Prompt Consumer Trap** | Prevents you from spending all day talking to chatbots like a customer. Dhriti measures what *you* can author, defend, and compile. |
| **Evening Guilt** | When your targets are met and day close arrives, the system releases early. Your evening is earned, clean, and completely guilt-free. |

---

## 3. The 3-Minute Quickstart (How to Run It)

You do **not** need to remember complicated terminal commands to use Dhriti.

### Step 1: Launch the App (1-Click)
In the project root folder:
- Double-click **`Launch-Dhriti-App.bat`** (or run `dhriti app` in your terminal).
- This automatically starts the local daemon, spins up the bridge, and opens the **Dhriti Tactile Dashboard** in an app window.
- *(Tip: Right-click `Launch-Dhriti-App.bat` -> **Send to -> Desktop (create shortcut)** for an instant desktop app icon!)*

### Step 2: Morning Ritual (Seal Today's Contract)
When the dashboard opens:
1. Enter your **Contract Line** (e.g. *"Solve 2 Medium DP problems and review Graph BFS"*).
2. Add your **Study Targets** (e.g. *"Target 1: DP LCS in Python"*, *"Target 2: Project Defense on bridge.py"*).
3. Click **Seal Contract**. Once sealed, your daily commitment is locked into an immutable audit chain.

### Step 3: Study & Focus Mode
- Use the built-in **Tactile Pomodoro Timer** (with natural procedural chimes — zero audio sample files, zero dependencies).
- When you finish a topic, submit your **Learning Proof** (a 50+ word recall synthesis of what you learned). Once verified, your target is marked claimed!

### Step 4: Placement Defense Drills
Want to prepare for interviews? Open your terminal in the repo:
```powershell
# Generate 5 placement defense questions for any code file
dhriti defense dhriti/day_window.py

# Simulate an Online Assessment (OA) coding drill
dhriti oa

# Verify recall on your study targets
dhriti proof-recall
```

---

## 4. Understanding Dhriti's Surfaces

```
+-----------------------------------------------------------------------+
|                             DHRITI SYSTEM                             |
+------------------------------------+----------------------------------+
|          FRONTEND UX               |         HEADLESS BACKEND         |
+------------------------------------+----------------------------------+
| • Tactile Dual-Mode Dashboard      | • SQLite Ledger (Immutable Chain)|
| • Procedural Audio & Chimes        | • Day Window State Machine       |
| • Chrome Extension Wall (MV3)      | • Vidura Search & Spaced Review  |
| • Topic-Time Stacked Bar Chart     | • AST Placement Defense Engine   |
| • Thought Bubbles (Life Mirror)    | • Topic Gate Semantic Classifier |
+------------------------------------+----------------------------------+
```

1. **The Desk (Dashboard):** Your command center. Shows your daily contract, streak, stage ratio (productive work vs passive browsing), and active study tasks.
2. **The Wall (Browser Extension):** Silent MV3 extension. Intercepts distraction tabs and routes search queries through Vidura (your personal knowledge index).
3. **The Vidura Engine:** An indexed personal repository of your curated videos, bookmarks, and placement flashcards. Press `v <query>` in Chrome's URL bar to search your own study vault!
4. **Thought Bubbles (Life Mirror):** Screensaver floating bubbles that surface offline life alternatives (walks, books, guitar, gym) only when you are decompressing.

---

## 5. Frequently Asked Questions (FAQ)

### Q1: Is my data sent anywhere?
**No.** Never. Dhriti does not connect to any external cloud, analytics service, or marketing tracker. All databases (`~/.dhriti/*.sqlite3`) live locally on your computer.

### Q2: What if I have an emergency or need to research something outside my contract?
Dhriti has two honest release valves:
1. **Declared Pivot (`/pivot/declare`):** If an urgent priority arises (e.g., unexpected exam or aptitude test), you declare a pivot with a short reason. It unlocks a 120-minute study window.
2. **Break-Glass Ladder:** For real emergencies, you can break glass. It honors a calm cooldown delay and logs the event to your permanent ledger without shame.

### Q3: Do I need Ollama or a GPU?
**No.** Ollama is 100% optional. 
- Dhriti has a built-in **AST (Abstract Syntax Tree) Analyzer** that runs instantaneously on your CPU with zero AI dependencies.
- If you *do* want AI-generated placement interview questions, you can install Ollama and run `ollama pull qwen2.5-coder:1.5b`. It uses ~1GB of RAM and runs smoothly on normal laptop CPUs.

### Q4: Why doesn't Dhriti give me confetti, badges, or points?
Because gamification creates addiction to the tool itself rather than real competence. Dhriti follows **L-2 (Honest Metrics)**: It tells you facts without judgment. If you completed your targets, it says so. If you didn't, it records the timestamp. You are treated as an autonomous adult.

---

## 6. Daily Driver Cheatsheet

```powershell
# 1. Start the desktop dashboard
Launch-Dhriti-App.bat

# 2. Check system status & active day window
dhriti status

# 3. Practice interview defense questions on your codebase
dhriti defense <path_to_code.py>

# 4. Search your personal Vidura study vault
dhriti feed

# 5. Check your honest stage ratio (Active Work vs Browsing)
dhriti stats
```
