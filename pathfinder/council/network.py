"""
Paperclip Inner Circle — Relationship Network

15 members. Each is a node. Each pair has a directed edge with an affinity score.
Affinity changes based on council interactions. Thresholds trigger events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════
# Core Types
# ═══════════════════════════════════════════════════════════════════════


class EventType(StrEnum):
    # ── Council interactions ──
    AGREE_VOTE = "agree_vote"
    DISAGREE_VOTE = "disagree_vote"
    PUBLIC_PRAISE = "public_praise"
    PUBLIC_CRITICISM = "public_criticism"
    DEFENDED = "defended"
    BETRAYED = "betrayed"
    IGNORED = "ignored"
    # ── Collaboration ──
    COLLABORATION = "collaboration"
    SHIPPED = "shipped"                 # Demi: delivered working artifact +18
    CODE_REVIEW_APPROVAL = "code_review_approval"  # Linus: approved merge +8
    JOINT_PAPER = "joint_paper"         # Sam: co-authored spec +10
    ALLIANCE_FORMED = "alliance_formed" # Sam: formal council alliance +12
    MENTORSHIP = "mentorship"           # Fei-Fei: advisor relationship +5
    DATA_SHARED = "data_shared"         # Fei-Fei: shared training data +7
    # ── Competition / Conflict ──
    SIDED_WITH_ENEMY = "sided_with_enemy"   # Sam: supported opponent -15
    STOLEN_CREDIT = "stolen_credit"         # Sam: took credit for others' work -20
    TALENT_POACHED = "talent_poached"       # Lisa: hired away team member -20
    SHARED_ENEMY = "shared_enemy"           # Musk: +3/cycle transitive
    # ── Hardware (Lisa) ──
    CHIP_SUCCESS = "chip_success"           # +8~15
    CHIP_FAILURE = "chip_failure"           # -5~10
    RESOURCE_SHARED = "resource_shared"     # +3
    RESOURCE_DENIED = "resource_denied"     # -10


class RelationState(StrEnum):
    FEUD = "feud"                # < -75  Irreconcilable — mutual veto, no co-authorship
    HOSTILE = "hostile"          # -55 to -75  Opposition — active blocking
    RIVAL = "rival"              # -35 to -55  Rivalry — competing, edge in debates (Sam)
    COLD = "cold"                # -20 to -35  Cold — distant, minimal interaction
    NEUTRAL = "neutral"          # -20 to +20  Baseline
    CORDIAL = "cordial"          # +20 to +35  Professional respect
    RESPECT = "respect"          # +35 to +50  Respect — productive disagreement, shared vision
    WARM = "warm"                # +50 to +65  Warm — collaboration preference
    ALLIANCE = "alliance"        # +65 to +80  Alliance — co-sign proposals, defend publicly
    DEEP_ALLIANCE = "deep_alliance"  # > +80  Deep Alliance — unconditional trust, co-invest


@dataclass
class Person:
    member_id: str               # feifei, musk, andrej, ...
    name: str                    # Fei-Fei Li, Elon Musk, ...
    title: str                   # Chief AI Scientist
    model: str                   # kimi-2.6 / deepseek-v4-pro / deepseek-v4-flash
    language: str                # EN / CN
    personality: List[str] = field(default_factory=list)  # traits
    mood: str = "neutral"        # current emotional state
    bio: str = ""                # short background


@dataclass
class Relationship:
    """Directed edge between two council members."""
    from_id: str
    to_id: str
    affinity: float = 0.0        # -100 (hate) to +100 (love)
    history: List[Tuple[str, float]] = field(default_factory=list)  # (event, delta)
    last_interaction: str = ""   # timestamp of last event
    real_world_connection: str = ""  # "PhD advisor", "co-founder", "relative", etc.


# ═══════════════════════════════════════════════════════════════════════
# Affinity Mechanics
# ═══════════════════════════════════════════════════════════════════════

class AffinityEngine:
    """Computes affinity deltas and triggers state transitions."""

    # ── Base deltas per event type ──
    BASE_DELTA: Dict[EventType, float] = {
        EventType.AGREE_VOTE:       3.0,
        EventType.DISAGREE_VOTE:   -2.0,
        EventType.PUBLIC_PRAISE:    8.0,
        EventType.PUBLIC_CRITICISM: -10.0,
        EventType.DEFENDED:         15.0,
        EventType.BETRAYED:        -25.0,
        EventType.IGNORED:         -4.0,
        EventType.COLLABORATION:    12.0,
        EventType.SHIPPED:         18.0,
        EventType.CODE_REVIEW_APPROVAL: 8.0,
        EventType.JOINT_PAPER:     10.0,
        EventType.ALLIANCE_FORMED:  12.0,
        EventType.MENTORSHIP:       5.0,
        EventType.DATA_SHARED:      7.0,
        EventType.SIDED_WITH_ENEMY: -15.0,
        EventType.STOLEN_CREDIT:   -20.0,
        EventType.TALENT_POACHED:  -20.0,
        EventType.SHARED_ENEMY:     3.0,
        EventType.CHIP_SUCCESS:    10.0,
        EventType.CHIP_FAILURE:    -7.0,
        EventType.RESOURCE_SHARED:  3.0,
        EventType.RESOURCE_DENIED: -10.0,
    }

    # ── Thresholds ──
    ALLIANCE_THRESHOLD: float = 70.0
    DEEP_ALLIANCE_THRESHOLD: float = 85.0
    RESPECT_THRESHOLD: float = 35.0
    HOSTILE_THRESHOLD: float = -55.0
    FEUD_THRESHOLD: float = -75.0
    RIVAL_THRESHOLD: float = -35.0

    # ── Decay ──
    POSITIVE_DECAY: float = 0.98       # Positive edges: 2%/cycle toward 0
    NEGATIVE_DECAY: float = 0.99       # Negative edges: 1%/cycle (grudges last longer)
    GRUDGE_DECAY_MULT: float = 0.5     # Grudge holders decay at 0.5x normal rate

    # ── Personality ──
    VOLATILE: set = {"musk", "linus", "jobs", "sam", "dijkstra", "jensen"}
    GRUDGE_HOLDERS: set = {"linus", "jobs", "dijkstra"}
    PERSONALITY_AMPLIFIER: float = 1.5
    FEIFEI_DAMPENER: float = 0.7       # Fei-Fei: measured, slow to shift
    MUSK_POSITIVE_AMP: float = 1.5     # Musk: excited fast
    MUSK_NEGATIVE_AMP: float = 1.2     # Musk: doesn't stay mad (unless betrayed)

    # ── Special mechanics ──
    BETRAYAL_FLOOR: float = -40.0      # Once betrayed, affinity can't rise above -40
    HYSTERESIS_CAP: float = 0.5        # After feud, recovery capped at 50% of pre-feud peak
    OSCILLATION_LIMIT: float = 20.0    # Volatile-volatile pairs: max swing per cycle
    PROPAGATION_RATE: float = 0.05     # 5% of edge changes propagate to adjacent edges
    DIMINISHING_RETURNS: float = 0.8   # Same event type repeated: 80% of previous delta

    # ── Romance (narrative flavor only — council vetoed "dating" label) ──
    ROMANCE_THRESHOLD: float = 70.0
    BREAKUP_THRESHOLD: float = 40.0

    def __init__(self):
        self._cycle: int = 0
        self._cooldowns: Dict[Tuple[str, str], int] = {}

    def process_event(
        self, rel: Relationship, event: EventType, cycle: int
    ) -> Tuple[float, List[str]]:
        """Apply an event, return new affinity + triggered state transitions."""
        delta = self.BASE_DELTA[event]

        # ── Personality modifiers ──
        rel.subject = None  # simplified for now
        delta = self._apply_personality_modifier(rel.from_id, delta)
        delta = self._apply_real_world_offset(rel, delta)

        # ── Grudge modifier: negative deltas stick harder ──
        if delta < 0:
            delta *= (1.0 + self.GRUDGE_HOLDING)

        old_affinity = rel.affinity
        new_affinity = max(-100.0, min(100.0, old_affinity + delta))
        rel.affinity = new_affinity
        rel.history.append((event.value, delta))
        self._cycle = cycle

        # ── State transitions ──
        triggers: List[str] = []
        old_state = self._classify(old_affinity)
        new_state = self._classify(new_affinity)

        if new_state != old_state:
            triggers.append(f"STATE_CHANGE: {old_state} → {new_state}")

        # Dating trigger
        if old_affinity < self.DATING_THRESHOLD <= new_affinity:
            triggers.append("DATING_STARTED: private meetings begin")
        elif old_affinity >= self.DATING_THRESHOLD > new_affinity:
            triggers.append("DATING_ENDED")

        # Intimacy trigger
        if old_affinity < self.INTIMATE_THRESHOLD <= new_affinity:
            triggers.append("INTIMATE: relationship deepens")
        elif old_affinity >= self.INTIMATE_THRESHOLD > new_affinity:
            triggers.append("BREAKUP: intimate relationship ends")

        # Hostility trigger
        if old_affinity > self.HOSTILE_THRESHOLD >= new_affinity:
            triggers.append("HOSTILITY: open attacks begin")
        elif old_affinity <= self.HOSTILE_THRESHOLD < new_affinity:
            triggers.append("DETENTE: hostilities cease")

        # Feud trigger
        if old_affinity > self.FEUD_THRESHOLD >= new_affinity:
            triggers.append("FEUD: active sabotage begins")

        return new_affinity, triggers

    def decay(self, rel: Relationship) -> float:
        """Natural affinity drift toward 0 over time (no interaction)."""
        rel.affinity *= self.HISTORY_DECAY
        return rel.affinity

    def _classify(self, affinity: float) -> str:
        if affinity < -50:
            return "hostile"
        if affinity < -20:
            return "cold"
        if affinity < 20:
            return "neutral"
        if affinity < 50:
            return "warm"
        if affinity < 75:
            return "close"
        return "intimate"

    def _apply_personality_modifier(self, member_id: str, delta: float) -> float:
        """Volatile personalities amplify both positive and negative deltas."""
        volatile = {"musk", "linus", "jobs", "sam", "dijkstra"}
        if member_id in volatile:
            return delta * self.PERSONALITY_AMPLIFIER
        return delta

    def _apply_real_world_offset(self, rel: Relationship, delta: float) -> float:
        """Real-world history biases first-impression delta by up to 20%."""
        if rel.real_world_connection:
            if any(w in rel.real_world_connection.lower() for w in
                   ["advisor", "student", "co-founder", "relative", "mentor"]):
                return delta * 1.2 if delta > 0 else delta * 0.8
            if any(w in rel.real_world_connection.lower() for w in
                   ["lawsuit", "rival", "competitor", "fired"]):
                return delta * 0.7 if delta > 0 else delta * 1.3
        return delta


# ═══════════════════════════════════════════════════════════════════════
# Council Network
# ═══════════════════════════════════════════════════════════════════════

# Pre-seeded real-world relationships (one direction shown; symmetric
# by default unless marked asymmetric with *)

REAL_WORLD_EDGES = [
    # Advisor / Student
    ("feifei", "andrej", 40, "PhD advisor — Fei-Fei supervised Andrej at Stanford"),
    ("andrej", "feifei", 45, "PhD student — deep respect for his advisor"),
    ("andrew", "andrej", 30, "Stanford colleague, both taught CS/AI courses"),
    ("andrej", "andrew", 30, ""),
    ("feifei", "andrew", 25, "Stanford AI faculty colleagues"),
    ("andrew", "feifei", 25, ""),
    ("feifei", "demi", 15, "Stanford connection — Demi was a Stanford researcher"),
    ("demi", "feifei", 20, "Admires Fei-Fei's work in computer vision"),

    # OpenAI founders / co-workers
    ("musk", "sam", -45, "Co-founded OpenAI; now lawsuit — deep animosity"),
    ("sam", "musk", -50, "Co-founded OpenAI; now adversarial — views Musk as hostile"),
    ("sam", "andrej", 25, "Overlapped at OpenAI; respects Karpathy's technical depth"),
    ("andrej", "sam", 15, "Worked at OpenAI under Altman's leadership"),
    ("musk", "andrej", 20, "Hired Karpathy at Tesla for Autopilot vision"),
    ("andrej", "musk", 15, "Tesla Autopilot — respects Musk's ambition, wary of volatility"),

    # Semiconductor relatives + rivals
    ("jensen", "lisasu", 10, "Distant relatives, both Taiwanese-American semiconductor leaders"),
    ("lisasu", "jensen", 10, "Distant relatives; professional respect, market competitors"),
    ("jensen", "lisasu", -5, "*Asymmetric: NVIDIA dominates AI chips; AMD fights for share"),
    ("lisasu", "jensen", -5, "*Asymmetric: AMD CPU strong; NVIDIA GPU dominant — tense market rivalry"),

    # Tech industry overlaps
    ("jobs", "musk", -15, "Jobs-era Apple vs Musk ambition — mutual suspicion of style"),
    ("musk", "jobs", -10, "Disrespects Apple's closed ecosystem"),
    ("jobs", "linus", -20, "Apple vs open-source — Jobs famously hostile to Linux"),
    ("linus", "jobs", -25, "Apple's walled garden — Linus' philosophical opposite"),
    ("linus", "musk", -5, "Musk's 'move fast' vs Linus' 'never break userspace'"),
    ("musk", "linus", -5, ""),
    ("guido", "linus", 15, "Open source allies — Python + Linux share philosophy"),
    ("linus", "guido", 15, "Respects Python's design principles"),
    ("guido", "dijkstra", 20, "Dutch computing heritage — mutual respect across generations"),
    ("dijkstra", "guido", 20, "Fellow Dutchman, different era but shared precision"),

    # Sam Altman strategic connections
    ("sam", "demi", 10, "Both YC / startup ecosystem; Demi's Pika Labs is AI generation"),
    ("demi", "sam", 5, "Startup founder in Sam's orbit — cautious of OpenAI's dominance"),

    # Lisa Su hardware connections
    ("lisasu", "xiaolong", 5, "Hardware meets software engineering"),
    ("xiaolong", "lisasu", 5, ""),
    ("lisasu", "jensen", -5, "*Asymmetric: market rivals"),

    # Andrej's connections across Tesla + OpenAI + Stanford
    ("andrej", "demi", 10, "Both Stanford AI, both shipped AI products to consumers"),
    ("demi", "andrej", 15, "Respects Karpathy's deep learning teaching + shipping experience"),

    # Fei-Fei's ethical AI connections
    ("sam", "feifei", -10, "Human-centered AI vs OpenAI — philosophical tension"),
    ("feifei", "sam", -5, "Respects her academically but disagrees on speed vs safety"),
    ("feifei", "musk", 5, "Both concerned about AI safety, different approaches"),
    ("musk", "feifei", 5, ""),

    # ── Jensen's 22 edges (2026-05-21 council debate) ──
    ("jensen", "linus", -5, "Linux driver war — Jensen: past is past"),
    ("linus", "jensen", -35, "Linux driver war — Linus has NOT forgotten the middle finger"),
    ("jensen", "musk", -15, "Customer + hidden competitor (Tesla Dojo vs NVIDIA)"),
    ("musk", "jensen", -20, "Frustration with NVIDIA dependency"),
    ("jensen", "sam", -20, "Sam's $7 trillion chip plan — existential threat"),
    ("sam", "jensen", -10, "Needs NVIDIA now, plans to route around later"),
    ("jensen", "andrej", 20, "Engineering soul — GPU meets deep learning"),
    ("andrej", "jensen", 25, "NVIDIA's critical role in AI infrastructure"),
    ("jensen", "feifei", 5, "GPU compute enables her vision research"),
    ("feifei", "jensen", 10, "Appreciates NVIDIA's platform role"),
    ("jensen", "andrew", 5, "Developer training → more GPU sales"),
    ("andrew", "jensen", 10, "NVIDIA democratized AI compute"),
    ("jensen", "jobs", 10, "Hardware+software empire founders — mutual respect"),
    ("jobs", "jensen", 10, "CUDA is the kind of vertical integration Jobs would admire"),
    ("jensen", "guido", 5, "Python+CUDA symbiosis"),
    ("guido", "jensen", 5, "Python+CUDA symbiosis"),
    ("jensen", "dijkstra", 0, "No intersection"),
    ("dijkstra", "jensen", 0, "No intersection"),
    ("jensen", "demi", 5, "Customer — Pika Labs runs on NVIDIA GPUs"),
    ("demi", "jensen", 10, "Depends on NVIDIA compute infrastructure"),
    ("jensen", "xuefeng", 0, "No intersection"),
    ("jensen", "xiaolong", 0, ""),

    # ── Sam's 10 new edges ──
    ("sam", "guido", 10, "Python ecosystem alignment — mutual respect for elegant design"),
    ("sam", "dijkstra", -5, "Theoretical rigor meets pragmatic strategy — tension"),
    ("sam", "linus", 5, "Both value systems-level thinking, very different domains"),
    ("sam", "xiaolong", 5, "Product+engineering alignment"),
    ("sam", "jobs", 15, "Both product visionaries, different generations — mutual appreciation"),
    ("sam", "fengge", 10, "Strategy meets execution — respects the CTO's management"),
    ("sam", "xuefeng", 5, "Cost audit pairs well with strategic positioning"),
    ("sam", "lisasu", 5, "Strategic interest in hardware independence from NVIDIA"),
    ("sam", "demi", 15, "Both YC ecosystem — startup founder + former YC president"),
    ("guido", "sam", 10, ""),
    ("dijkstra", "sam", -5, ""),
    ("linus", "sam", 5, ""),
    ("xiaolong", "sam", 5, ""),
    ("jobs", "sam", 10, "Product vision — different eras, shared DNA"),
    ("fengge", "sam", 10, ""),
    ("xuefeng", "sam", 5, ""),
    ("lisasu", "sam", 5, ""),
    ("demi", "sam", 20, "YC connection — former president, admiration for scale"),

    # ── Demi's 7 new edges ──
    ("demi", "jobs", 15, "Product instinct — modern generation of Jobs' design philosophy"),
    ("jobs", "demi", 15, "Recognizes product-first thinking in Demi"),
    ("demi", "xiaolong", 10, "Engineering execution + product speed — mutual respect"),
    ("xiaolong", "demi", 10, ""),
    ("demi", "fengge", 15, "CTO who ships — Demi connects with execution-focused leaders"),
    ("fengge", "demi", 15, ""),
    ("demi", "guido", 5, "Python ecosystem — Pika likely Python-based"),
    ("guido", "demi", 5, ""),
    ("demi", "xuefeng", 5, "Cost-driven + speed-driven — productive tension"),
    ("xuefeng", "demi", 5, ""),
    ("demi", "lisasu", 5, "Hardware interest — GPU access critical for video generation"),
    ("lisasu", "demi", 5, ""),

    # ── Linus's 11 new edges ──
    ("linus", "fengge", 15, "CTO who understands kernel-level decisions — rare respect"),
    ("fengge", "linus", 15, ""),
    ("linus", "dijkstra", 35, "Dijkstra's algorithm + Linux scheduling — mutual respect between legends"),
    ("dijkstra", "linus", 20, "Respects Linux kernel — pragmatic realization of CS theory"),
    ("linus", "xuefeng", 5, "Realist audit pairs with kernel pragmatism"),
    ("xuefeng", "linus", 5, ""),
    ("linus", "xiaolong", 15, "Engineering + kernel architecture — Linus respects builders"),
    ("xiaolong", "linus", 15, "Deep respect for Linux kernel architecture"),
    ("linus", "lisasu", 20, "Open hardware respect — AMD's open-source GPU drivers"),
    ("lisasu", "linus", 45, "Linux kernel support for AMD GPUs — deep technical respect"),
    ("linus", "demi", 5, "Startup speed meets kernel stability — different worlds, mutual curiosity"),
    ("demi", "linus", 5, "Shipped consumer AI products — Linus respects shipping"),
    ("linus", "andrew", 10, "Education + open source — shared commitment to accessibility"),
    ("andrew", "linus", 10, "Linux is the backbone of AI infrastructure — gratitude"),
    ("linus", "feifei", 10, "AI safety + kernel security — overlapping concerns"),
    ("feifei", "linus", 5, "Kernel security perspective enriches AI safety thinking"),
    ("linus", "andrej", 10, "Deep learning on Linux — mutual dependency"),
    ("andrej", "linus", 15, "All his AI work runs on Linux — respects the foundation"),

    # ── Lisa's edge adjustments ──
    ("lisasu", "jensen", -25, "Market rivals — AMD fights for GPU share against NVIDIA dominance"),
    ("lisasu", "linus", 45, "AMD open-source GPU drivers — Linus deeply appreciates"),

    # ── Andrej's edge additions ──
    ("andrej", "lisasu", 15, "Hardware curiosity — needs AMD GPUs for open-source ML work"),
    ("lisasu", "andrej", 15, "Appreciates Karpathy's open-source ML contributions"),
    ("andrej", "guido", 10, "Python ecosystem — all his ML code is Python"),
    ("guido", "andrej", 10, "Python underpins modern ML — Karpathy is a premier practitioner"),

    # Andrew Ng connections
    ("andrew", "feifei", 25, "Stanford AI colleagues"),
    ("andrew", "sam", 5, "Both believe in AI democratization, different methods"),
    ("andrew", "demi", 10, "Education + startup — Andrew's teaching reach, Demi's product execution"),
    ("andrew", "andrej", 30, "Both premier AI educators (Coursera + CS231n / Zero to Hero)"),
]

# New members who have no pre-existing relationships get neutral (affinity 0).
# These will evolve purely through council interactions.
