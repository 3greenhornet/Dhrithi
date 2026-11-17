# Research base — evidence snapshot (30 October 2026)

Carried over verbatim from the dossier section 9 so the citations
travel with the repo. **None of these validate the Dhriti
architecture** — they justify specific testable choices, nothing more.

## What the evidence actually supports

1. **Digital disconnection as self-regulation** — Klingelhoefer,
   Gilbert & Meier, *Scientific Reports* (29 May 2026). N=237,
   12,408 situational observations; within-person association of
   temporary disconnection with slightly lower procrastination
   (beta ≈ -0.07). Observational, not causal.
   https://www.nature.com/articles/s41598-026-46218-1

2. **Digital behavior-change scoping review** — *JMIR* (2026), 32
   studies; 84% smartphone-focused, 81% total-time-focused; AI/ML
   rare; follow-ups short. Opportunity for activity-specific,
   theory-driven, longitudinal work — not proof of Dhriti.
   https://www.jmir.org/2026/1/e101150

3. **GenAI vs human conversational intervention** — 2026 randomized
   pilot, N=62; no significant group × time (p=.117); 43.1% reported
   unwanted effects. Argues against assuming conversational AI is an
   effective or harmless intervention. Does not test blocking.
   https://pmc.ncbi.nlm.nih.gov/articles/PMC13402774/

4. **MCII / implementation intentions** — Feb 2026 small study (81
   undergrads, 7 days) lead, improved task initiation. **Re-verify
   before relying on it** (register row 4 marks it UNVERIFIED).
   Broader if–then literature is substantial; pooled effects do not
   transfer to this personal design automatically.

5. **Purpose Mode field study** — CMU extension suppressing infinite
   scroll / autoplay / recommendations; 2-week, N=29 field study:
   lower self-reported distraction, less time on targeted sites.
   Small, not definitive. https://github.com/hankhplee/purpose-mode

6. **Earlier leads needing re-verification** (2021 DSCI review;
   2024 n≈2,209 university RCT; 2025 chatbot pilot (75 completers);
   2026 precommitment deadline replication) — leads, not a review.

## What this means for design decisions

- Restriction is a **testable hypothesis** (experiment A), never a
  guaranteed mechanism.
- The conversational-AI route is treated with suspicion (the Wall
  Principle aligns with the null result above).
- IF–THEN plans live in the launcher profile (experiment C) rather
  than in any AI feature.
- Browser interface inversions (Purpose Mode / Unhook /
   Intentional YouTube — register rows 5, 24–26) are leads for the
  bounded-research environment; test them as extensions, don't build
  a Dhriti YouTube adapter first (dossier 5.3).
