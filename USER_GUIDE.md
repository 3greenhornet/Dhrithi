# Project Dhriti: Complete Beginner's Field Manual & Operator Guide

> **Dhriti** *(Sanskrit: धृति)* — *The steadfast mental faculty that holds the line when an impulse tries to break it.*

---

## 1. Welcome! What is Dhriti?

If you opened this document because a friend shared it with you, or because you looked at this codebase and thought **"What on earth is all of this?"**, take a deep breath. 

**Dhriti is NOT:**
* It is not a generic to-do list app.
* It is not a moralizing habit tracker that shames you with red streaks or sad emojis.
* It is not a subscription SaaS that sends your private web history to an external server.

**Dhriti IS:**
An **externalized will**. It is a local-first software harness designed for people who **already know what they need to do**, but whose brains get hijacked by digital drift, algorithmic feeds, rabbit-holes, endless browser tabs, and AI chat distraction loops.

### The Problem It Solves
Modern digital tools are engineered with billions of dollars of behavioral psychology designed to extract your attention. 
* You sit down to code or write for 30 minutes.
* You open a tab to check one syntax reference.
* 45 minutes later, you find yourself watching a video essay on bronze age metallurgy or scrolling an AI chat thread about philosophical paradoxes.
* You feel guilt and mental exhaustion, while your actual work remains untouched.

Dhriti removes willpower from the equation. When you are calm and clear-headed (the "cold state"), you set your daily target. Once your day begins, Dhriti acts as an impartial, silent digital fortress: it holds the boundary, keeps your focus locked, and stores your wandering thoughts for later so you can create with total peace of mind.

---

## 2. The Three Pillars of Dhriti

Dhriti is built around three core engines:

```
                      +-----------------------------+
                      |       PROJECT DHRITI        |
                      +-----------------------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
+-------------------+       +-------------------+       +-------------------+
|    1. THE WALL    |       |   2. THE DESK     |       |   3. VIDURA       |
| (Enforcement &    |       | (Tactile Focus    |       | (Personal Archive |
|  Guard Kit)       |       |  Dashboard)       |       |  & Memory Mirror) |
+-------------------+       +-------------------+       +-------------------+
| - Blocks junk     |       | - Return Anchor   |       | - 2,900+ saved    |
| - AI Chat limits  |       | - Solitaire view  |         videos/bookmarks  |
| - Decompression   |       | - Real-time dials |       | - Recall prompt   |
|   strike limits   |       | - Dynamic backlog |       | - Offline life    |
+-------------------+       +-------------------+       +-------------------+
```

### 1. The Wall (Silent Protection)
* **Website Insulation:** During active hours, social media, infinite feeds, and entertainment sites are sealed shut.
* **ChatGuard for AI:** If you use ChatGPT, Claude, or Gemini for work, ChatGuard prevents you from turning LLMs into amusement toys by throttling compulsive message bursts and long unstructured outputs.
* **Search Escape:** When you search for a programming question or tutorial that you *already bookmarked or saved months ago*, a polite card pops up: *"Vidura Escape: You already saved this! Click here to open your note instead of starting from scratch."*

### 2. The Desk (Your Sovereign Command Center)
* **The Return Anchor:** Ever take a 5-minute coffee break, come back, and spend 15 minutes trying to remember what you were working on? The Return Anchor permanently displays your *Next Concrete Step* and *Active Blocker*.
* **Art & Solitaire Mode:** If you just want a calm, beautiful workstation, the dashboard flips into a full-screen gallery with procedurally synthesized wind chimes and ambient physics.
* **Stage Ratio:** Tracks your honest output. It doesn't guilt you with "screen time"; it measures whether your time was spent creating (Stage) vs passively consuming (Audience).

### 3. Vidura (Your Personal Memory Engine)
* **Ending the "Watch Later" Graveyard:** Most of us have hundreds or thousands of videos saved in YouTube's *Watch Later* and *Liked Videos*, or hundreds of browser bookmarks that we never touch again.
* **Recall-Before-Reveal:** Every evening, Vidura pulls up **one** old saved item you forgot about. But before giving you the link, it prompts you: *"You saved this 80 days ago. Before revealing the URL, what was your intention or context?"*
  * If you remember, your memory is consolidated.
  * If you forgot, you acknowledge it without shame, watch it mindfully, or delete it from your mental burden.
* **Life Mirror:** It surfaces real-world, offline alternatives (e.g. practicing an instrument, going for a 15-minute walk, stretching, reading a physical book) through floating screensaver thought bubbles.

---

## 3. Quick Start: How to Run It in 60 Seconds

You don't need to be a programmer to run Dhriti on your Windows machine.

### Prerequisites (Installed Once)
1. **Python 3.10+** installed on Windows.
2. A modern Chromium browser (Brave, Chrome, or Edge).

### Step 1: Launch Dhriti
In the main folder, simply **double-click** the file:
```
Dhriti.bat
```
*(You can right-click `Dhriti.bat` and click "Send to -> Desktop (create shortcut)" so you have a 1-click icon anytime).*

What happens behind the scenes:
1. Dhriti automatically starts the local security daemon in the background.
2. It launches the tactile dashboard in its own clean, dedicated desktop application window.

### Step 2: Enable the Browser Extension (One-time, 30 seconds)
1. Open your browser (Brave or Chrome) and navigate to:
   ```
   brave://extensions   (or chrome://extensions)
   ```
2. Toggle the **Developer mode** switch in the top-right corner to **ON**.
3. Click the **Load unpacked** button in the top-left.
4. Select the `extension` folder located inside the Dhriti project directory:
   ```
   dhriti-repo/extension
   ```
5. That's it! You will see the Dhriti Wall shield icon in your browser toolbar.

---

## 4. The Daily Flow: How to Actually Use It

Here is what an ideal day with Dhriti looks like:

```
+-------------------------------------------------------------------------+
|                               MORNING                                   |
| Cold Contract: Open Dashboard -> Pick your 1 to 3 targets for the day.  |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                              DAYTIME                                    |
| Deep Work: The Wall is armed. Social feeds & entertainment are sealed.  |
| Distractions pop up? Use Quick-Park to deposit thoughts for later.      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                              EVENING                                    |
| Decompression Window: Targets met! Earned 90m release.                  |
| Vidura Recall: One archived gem surfaced on The Desk for memory recall. |
+-------------------------------------------------------------------------+
```

### 1. Morning: Declare Your Target
Open the dashboard and check **The Desk**. Declare what you are shipping today. Keep it small and concrete (e.g., "Implement database schema" or "Write Section 2 of report").

### 2. Daytime: Deep Work & Quick Parking
As you work:
* If an impulse strikes you ("I wonder what the specs of the new M4 Mac are?"):
  * Do not open a new tab!
  * Type it into the **Curiosity Parking Lot** box on The Desk and press Enter.
  * Your thought is safely saved for your evening review, and your brain lets go of the urgency.
* If you search Google for something you already saved in your 2,900+ archive, the extension catches it and offers your saved link.

### 3. Evening: Decompression & Vidura Recall
When your targets are finished:
* Dhriti enters **Decompression Mode**: a bounded 90-minute release window where search and reading are allowed without guilt.
* On The Desk, your **Vidura Memory Card** appears:
  * It shows an archived video or article you saved months ago.
  * Test your memory: *"Why did I save this?"*
  * Click **[I Remember - Unlock]** to watch it as an earned leisure reward!

---

## 5. Frequently Asked Questions (FAQ)

### Q: Is this sending my passwords, browser history, or data to the internet?
**NO.** Dhriti is 100% local-first. It communicates exclusively over your internal loopback address (`127.0.0.1:7311`). No telemetry, no external database, no cloud logins. Your data lives on your own hard drive in an encrypted SQLite database.

### Q: What if I genuinely need to access a blocked site for an emergency?
Dhriti understands that life happens. It features a **Break-Glass Friction Ladder**:
You can break the block, but it is not a free 1-click toggle (which defeats willpower). It requires entering an intentional reason and waiting a short delay. Everything is recorded neutrally in an append-only audit ledger so you can review your patterns honestly.

### Q: How do I sync my YouTube Watch Later and Liked Videos?
1. Open the dashboard.
2. In the top toolbar of **The Desk** (or in **Settings**), click the **Sync YouTube Queue** button.
3. Dhriti will use your exported YouTube session cookies to fetch your latest videos and categorize them into the 4-facet taxonomy (Domain, Intent, Form, Effort).

### Q: Why does my wallpaper look clean now?
In earlier versions, a background blur was enabled by default. Now, Dhriti loads with **0px blur** (crisp, high-definition art) and 100% brightness. If you prefer a frosted glass look, open **Settings** and slide the blur or brightness sliders; your preference saves in real-time.

### Q: What are the floating bubbles that appear on the screen?
That is the **Life Mirror**. It surfaces non-screen, offline alternatives you have declared (e.g. stretching, guitar practice, reading a book). They float gently and dissolve on their own without demanding buttons or clicks.

### Q: How do I change the art or music?
In the top-left of the dashboard, click the **Settings Gear**:
* **Theme:** Choose between Executive Dark (Midnight Navy) and Minimal Light.
* **Audio:** Customize the synthesized physics chimes or mute them entirely.
* **Gallery:** Upload your own background images or activate pre-built art collections.

---

## 6. Glossary for Friends & New Users

* **Cold State:** When you are calm, rested, and not under the immediate pull of dopamine (e.g. first thing in the morning). This is when decisions and rules are made.
* **Hot State:** When you are tired, frustrated, or craving a distraction. Dhriti holds your cold-state commitments when your hot state tries to cheat.
* **Vidura:** Named after the wise counselor in the Mahabharata known for unvarnished truth and foresight; Dhriti's memory archive engine.
* **Return Anchor:** A simple 2-box capsule on The Desk that keeps track of your immediate next step so you never suffer cold-start paralysis.
* **Honest Telemetry (L-2):** Dhriti never shames you, lectures you, or displays patronizing motivational quotes. It records exact facts and leaves the judgment to you.

---

*Dhriti is your digital sovereign space. Run it, protect your attention, and ship what matters.*
