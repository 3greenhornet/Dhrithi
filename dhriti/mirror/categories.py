"""The mirror's category taxonomy (Part 3 §3.1): the categories the
rule classifier assigns and the aftermath's category facts report.

The taxonomy is a claim about what matters for THIS operator's pile.
It is authored, not discovered — and it is editable in cold state
(profiles mirror_categories override) without a code change.
"""

# The default taxonomy. Order matters only for display; matching is
# keyword-based (classify_rule.py).
CATEGORIES = (
    ("development", ("code", "coding", "programming", "python", "java",
                     "compiler", "javascript", "typescript", "sql",
                     "algorithm", "data structure", "system design",
                     "backend", "frontend", "devops", "kubernetes",
                     "docker", "git", "linux")),
    ("cs_theory", ("complexity", "automata", "turing", "lambda",
                   "type theory", "compiler theory", "parsing",
                   "operating system", "networks", "distributed")),
    ("productivity", ("productivity", "study tips", "note taking",
                      "obsidian", "anki", "pomodoro", "habits",
                      "focus", "time management", "second brain",
                      "motivation", "discipline")),
    ("spiritual", ("gita", "bhagavad", "vedanta", "upanishad",
                   "sanskrit", "meditation", "dharma", "advaita",
                   "philosophy", "stoic")),
    ("music", ("guitar", "piano", "music theory", "cover", "riff",
               "improvisation", "practice routine")),
    ("fitness", ("workout", "gym", "calisthenics", "yoga", "running",
                 "stretching", "posture")),
    ("career", ("interview", "resume", "job hunt", "portfolio",
                "linkedin", "salary", "offer", "recruiter")),
    ("entertainment_misc", ("comedy", "trailer", "reaction", "vlog",
                            "gameplay", "podcast", "documentary",
                            "movie", "series")),
    ("science", ("physics", "math", "mathematics", "chemistry",
                 "biology", "space", "quantum", "astronomy")),
    ("unknown", ()),
)

CATEGORY_NAMES = tuple(name for name, _ in CATEGORIES)


def categories() -> tuple:
    return CATEGORY_NAMES
