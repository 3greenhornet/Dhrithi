# VIDURA — the spaced-review scheduler for your own answers

Vidura (named for the counsel who says the thing once) schedules the
declarations you made in cold state — the research-pass answers first.
It is **not** the saved-content mirror; the mirror (saved videos,
articles) is a separate subsystem. Vidura is for the things *you*
wrote down.

## 1. What Vidura is for

A research pass ends with a typed answer. That answer is a fact you
declared about the world ("Arrays.asList does not reverse in place").
Vidura resurfaces those declarations at spaced intervals so they are
*seen* again, cold — not so they are tested. The recall prompt is the
question you asked; the reveal is the answer you typed.

## 2. Item kinds

| Kind | Source | Example |
|---|---|---|
| research_answer | a returned research pass | "does Arrays.asList reverse in place?" |
| identity_line | the contract's identity statement | (v0.5.0; see the v0.6.0 correction) |
| note | a hand-added item | `dhriti` has no CLI for this yet — service only |

## 3. The scheduler (an SM-2 variant)

The scheduler is an SM-2 variant: the ease-factor update and the
grade-to-outcome mapping follow SM-2, but the interval sequence is
I(n) = I(n-1) · EF' from the first review onward (a ~2.5x growth on
the second review with the default EF), not the textbook SM-2
I(1)=1, I(2)=6, I(n)=I(n-1)·EF (a 6x jump on the second review). The
divergence is deliberate — the slower growth avoids burying the user
in future-due items before the FSRS upgrade gate can be evaluated.
When the FSRS gate opens, this scheduler's review log is the baseline
it must beat.

```
again -> reps=0, lapses+=1, interval = 1 day
hard  -> interval = max(1, interval * 1.2)
good  -> reps+=1; interval = 1 if reps==1 else interval * EF'
easy  -> reps+=1; interval = 1 if reps==1 else interval * EF' * 1.3
```

EF' follows the classic SM-2 ease update, clamped to [1.3, 2.5];
"again" resets EF to the floor (1.3).

First-review behaviour: the first good or easy on a new item produces
a 1-day interval; the SM-2 multiplication applies from the second
review onward.

## 4. The commands

```
dhriti vidura ingest --date YYYY-MM-DD   # a day's pass answers -> items
dhriti vidura due                        # what is due
dhriti vidura review <item> <grade>      # again|hard|good|easy
```

## 5. The law

Vidura is off by default (L-6). Enabling it is a cold-state act
(`vidura.enabled = true` in the config). The items are your words;
the schedule is the only thing the system adds.
