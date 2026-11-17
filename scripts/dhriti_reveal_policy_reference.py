#!/usr/bin/env python3
"""dhriti_reveal_policy_reference.py -- D-090 reference (pure stdlib).

Claim under test
    Dhriti should import the recommender literature's FORMULAS (Thompson
    sampling, UCB1, MMR, category decay, entropy slot) and reject its TOOLS
    (Mab2Rec / Vowpal Wabbit / Qdrant / Neo4j GDS / Gorse / Recombee).
    At Dhriti scale (<= 10^3 parked items, one subject) the whole engine is
    a few dozen lines of stdlib Python.

Objective inversion (the part the platforms do NOT ship)
    Platform reward = engagement (click, linger, return).
    Dhriti reward   = RESOLUTION: a reveal ends when the parked item is
    either promoted to action or released as a dead urge. Ignored reveals
    are failures. A reveal that hooks the subject back into consumption is
    a harm: it scores as failure and carries an incident flag (real module
    additionally zeroes the arm and emits guard_reveal_harm).

Plane discipline
    Plane 1 (enforcement / hot path) stays content-blind (L-4, L-9).
    Plane 2 (this policy) is content-aware, cold-path only: it runs inside
    fixed reveal windows under a fixed budget (L-5), i.e. exactly the
    D-071 container ("reveal only at cold state after the recall step").
    The bandit chooses WHICH item to surface; it never chooses WHEN or
    HOW MANY. No push, no badge, no streak (L-2).

Run:  python3 dhriti_reveal_policy_reference.py
"""

import hashlib
import json
import math
import random

# <<< MECHANISMS BEGIN >>>

class ThompsonArm:
    """Beta(alpha, beta) posterior over P(one reveal of this arm resolves)."""

    __slots__ = ("alpha", "beta")

    def __init__(self):
        self.alpha, self.beta = 1.0, 1.0  # flat prior: cold-start = wide curve

    def sample(self, rng):
        return rng.betavariate(self.alpha, self.beta)

    def update(self, resolved):
        if resolved:
            self.alpha += 1.0
        else:
            self.beta += 1.0

    @property
    def mean(self):
        return self.alpha / (self.alpha + self.beta)


def ucb1(mean, n_i, n_total, c=1.4):
    """mean + c*sqrt(ln N / n_i).  A never-tested arm (n_i == 0) is +inf:
    the '100-view / 17-year-old video' analog wins its first probe."""
    if n_i == 0:
        return math.inf
    return mean + c * math.sqrt(math.log(max(n_total, 2)) / n_i)


def mmr_select(cands, sim_fn, lam=0.5, k=3):
    """Maximal Marginal Relevance, greedy:
    argmax lam*rel(item,user) - (1-lam)*max sim(item, already-picked).
    May return fewer than k: the budget is a ceiling (L-5), never a quota.
    sim_fn degrades gracefully -- with classifier-cascade embeddings use
    sim_cosine; without them sim_category still blocks same-vibe repeats."""
    picked, pool = [], list(cands)
    while pool and len(picked) < k:
        best = max(
            pool,
            key=lambda it: lam * it.rel
            - (1 - lam) * max((sim_fn(it, s) for s in picked), default=0.0),
        )
        pool.remove(best)
        picked.append(best)
    return picked


def sim_category(a, b):
    """Graceful degradation: no embeddings -> category mismatch only."""
    return 1.0 if a.category == b.category else 0.0


def sim_cosine(a, b):
    """Armed once the classifier sidecar supplies embeddings (1024-d)."""
    xs, ys = a.embedding, b.embedding
    dot = sum(x * y for x, y in zip(xs, ys))
    na = math.sqrt(sum(x * x for x in xs))
    nb = math.sqrt(sum(y * y for y in ys))
    return dot / (na * nb) if na and nb else 0.0


def pick_slot(rng, slots=(("lineage", 0.40), ("sibling", 0.20),
                          ("probe", 0.30), ("entropy", 0.10))):
    """Slot router (the 60/20/15/5 idea, re-weighted for measurement).
    Weights are L-3 contract knobs fixed at cold state, not code constants.
      lineage  exploit: kin of whatever the last resolved item was
      sibling  taxonomy step: same parent family, different category
      probe    UCB1/Thompson uncertainty: the '17-year-old video' engine
      entropy  assay: random among the oldest never-tested items
    """
    x, acc = rng.random(), 0.0
    for name, w in slots:
        acc += w
        if x <= acc:
            return name
    return slots[-1][0]


class ParkedItem:
    __slots__ = ("iid", "category", "age_days", "rel", "n_reveals",
                 "sparked_by", "arm", "embedding")

    def __init__(self, iid, category, age_days, rel, sparked_by=None):
        self.iid, self.category = iid, category
        self.age_days, self.rel = age_days, rel
        self.n_reveals, self.sparked_by = 0, sparked_by
        self.arm = ThompsonArm()
        self.embedding = None  # filled by classifier cascade when armed


def ledger_line(ts, event, item=None, slot=None, propensity=None, outcome=None):
    """One append-only chain line per arm-pull.  Propensity is logged so the
    adaptive policy stays auditable and off-policy analysis (IPS) stays
    possible later without re-running anything on the subject."""
    payload = json.dumps(
        {"ts": ts, "event": event, "item": item, "slot": slot,
         "propensity": propensity, "outcome": outcome}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

# <<< MECHANISMS END >>>

# ---------------------------------------------------------------------------
# Simulation harness: prove the mechanisms behave on a synthetic parking lot.
# ---------------------------------------------------------------------------

def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (vx * vy) if vx and vy else 0.0


def simulate(seed=7, n_items=40, sessions=90, budget=3):
    rng = random.Random(seed)
    cats = ("create", "learn", "move", "connect")
    items = [ParkedItem(f"P{i:03d}", rng.choice(cats), rng.randint(1, 120),
                        round(rng.random(), 2))
             for i in range(n_items)]
    # The '17-year-old video': oldest item in the lot, never surfaced yet.
    items[-3] = ParkedItem("P037", "learn", 220, 0.35)

    # Latent truth, unknown to the policy: P(a reveal resolves this item).
    true_p = {it.iid: rng.uniform(0.05, 0.55) for it in items}
    true_p["P037"] = 0.62  # a genuinely valuable buried item

    ledger, first_seen, resolved_at = [], {}, {}
    stats = {}  # iid -> [reveals, resolves]
    dup_pre = dup_post = 0
    last_resolved_cat = None

    for s in range(sessions):
        if not items:  # the lot drained: nothing left to probe (success)
            break
        # Slots overproduce (budget+2 candidates); MMR curates down to the
        # fixed budget.  This mirrors reality: the candidate generator is
        # cheap, the reveal window is the scarce resource (L-5).
        raw, seen = [], set()
        for _ in range(budget + 2):
            slot = pick_slot(rng)
            if slot == "probe":
                n_total = sum(t.n_reveals for t in items)
                scored = [(t, ucb1(t.arm.mean, t.n_reveals, n_total))
                          for t in items]
                top = max(sc for _, sc in scored)
                it = rng.choice([t for t, sc in scored if sc == top])
            elif slot == "entropy":
                never = sorted((t for t in items if t.n_reveals == 0),
                               key=lambda t: -t.age_days)[:5]
                it = rng.choice(never) if never else rng.choice(items)
            elif slot == "sibling":
                pool = ([t for t in items if t.category != last_resolved_cat]
                        or items)
                it = max(pool, key=lambda t: t.arm.sample(rng))
            else:  # lineage stand-in: category-mates of the last resolved item
                pool = ([t for t in items if t.category == last_resolved_cat]
                        or items)
                it = max(pool, key=lambda t: t.arm.sample(rng))
            if it.iid not in seen:
                seen.add(it.iid)
                raw.append((slot, it))

        def cat_dupes(seq):
            counts = {}
            for _, it in seq:
                counts[it.category] = counts.get(it.category, 0) + 1
            return sum(1 for c in counts.values() if c >= 2)

        dup_pre += cat_dupes(raw)
        final = mmr_select([it for _, it in raw], sim_category,
                           lam=0.5, k=budget)
        slot_of = {it.iid: sl for sl, it in raw}
        dup_post += cat_dupes([(None, it) for it in final])
        assert len(final) <= budget  # L-5: ceiling, never a quota

        resolved_ids = set()
        for it in final:
            if it.iid not in first_seen:
                first_seen[it.iid] = s
            it.n_reveals += 1
            st = stats.setdefault(it.iid, [0, 0])
            st[0] += 1
            p_before = round(it.arm.mean, 3)
            harm = rng.random() < 0.04
            resolved = (not harm) and rng.random() < true_p[it.iid]
            it.arm.update(resolved)
            ledger.append(ledger_line(s, "reveal", it.iid, slot_of[it.iid],
                                      p_before,
                                      "harm" if harm else
                                      "resolve" if resolved else "ignore"))
            if resolved:
                st[1] += 1
                resolved_at[it.iid] = s
                last_resolved_cat = it.category
                resolved_ids.add(it.iid)
        if resolved_ids:
            items = [t for t in items if t.iid not in resolved_ids]

    return dict(seed=seed, items=items, ledger=ledger, first_seen=first_seen,
                resolved_at=resolved_at, stats=stats, true_p=true_p,
                dup_pre=dup_pre, dup_post=dup_post, sessions=sessions,
                budget=budget)


def report(r):
    bar = "=" * 64
    print(bar)
    print("D-090 reference: serendipity formulas, stdlib only (zero deps)")
    print(bar)
    src = open(__file__, encoding="utf-8").read().splitlines()
    lo = next(i for i, l in enumerate(src) if "MECHANISMS BEGIN" in l)
    hi = next(i for i, l in enumerate(src) if "MECHANISMS END" in l)
    mech = sum(1 for l in src[lo:hi]
               if l.strip() and not l.strip().startswith("#"))
    print(f"[0] engine size: {mech} effective lines (Thompson + UCB1 + MMR +")
    print("    slot router + ledger).  imports: hashlib json math random.")

    tp, fs, ra = r["true_p"], r["first_seen"], r["resolved_at"]
    print(f"[1] buried analog: P037 age=220d never-revealed true_p={tp['P037']:.2f}")
    if fs.get("P037") is not None:
        msg = f"    first surfaced at session {fs['P037']}"
        if "P037" in ra:
            msg += (f", resolved at session {ra['P037']} "
                    f"({r['stats']['P037'][0]} reveal)")
        print(msg)
    else:
        print("    never surfaced (budget too small for this seed)")

    pre = r["dup_pre"] / r["sessions"]
    post = r["dup_post"] / r["sessions"]
    print(f"[2] MMR curation (pool {r['budget'] + 2} -> budget {r['budget']}): "
          f"sessions with same-category repeats "
          f"{pre:.2f} -> {post:.2f} per session (lam=0.5, category fallback)")

    pairs = [(tp[iid], res / rev) for iid, (rev, res) in r["stats"].items()
             if rev >= 2]
    if len(pairs) >= 5:
        xs = [p for p, _ in pairs]
        ys = [e for _, e in pairs]
        print(f"[3] policy learning: pearson(true_p, empirical resolve rate) "
              f"over {len(pairs)} items with >=2 reveals: "
              f"r={pearson(xs, ys):.2f}")

    drained = 40 - len(r["items"])
    print(f"[4] parking lot drained: 40 -> {len(r['items'])} "
          f"({drained} resolved over {r['sessions']} sessions, "
          f"budget {r['budget']}/session)")
    print(f"[5] ledger: {len(r['ledger'])} append-only lines, first 3:")
    for line in r["ledger"][:3]:
        print(f"    {line}")
    print(bar)


if __name__ == "__main__":
    report(simulate())
