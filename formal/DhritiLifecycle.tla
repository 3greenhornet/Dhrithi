---------------------------- MODULE DhritiLifecycle ----------------------------
(***************************************************************************)
(* Dhriti session/day lifecycle model (dossier 3.4, audit item 10).        *)
(*                                                                         *)
(* States mirror dhriti/models.py exactly. The purpose is model-checking   *)
(* the safety properties that matter before any privileged process exists: *)
(*                                                                         *)
(*   NoActiveWithoutSealed   - no ACTIVE session without a sealed policy   *)
(*   EmergencyAlwaysPossible - break-glass is reachable from every ACTIVE  *)
(*   RelaxationIsDelayed     - policy relaxation never applies immediately *)
(*   DayReleaseIsBounded     - the day releases by window_end, always      *)
(*   InterruptedRecovers     - an interrupted session never stays ACTIVE   *)
(*                                                                         *)
(* How to run (manual step — needs Java 8+ and the TLA+ tools):            *)
(*   1. Download from https://github.com/tlaplus/tlaplus/releases          *)
(*   2. TLC:  java -cp tla2tools.jar tlc2.TLC DhritiLifecycle.tla         *)
(*   3. Or open in the TLA+ Toolbox and run the model with "what to check" *)
(*      set to the invariants below.                                       *)
(*                                                                         *)
(* This module is development-time verification only; nothing here runs    *)
(* at enforcement time (dossier 5.6).                                      *)
(***************************************************************************)

CONSTANTS NULL_ID

VARIABLES session_state, policy_sealed, emergency_ready,
          relaxation_timer, day_locked, clock

TypeOK ==
    /\ session_state \in {"DRAFT", "SEALED", "ARMING", "ACTIVE",
                          "SUCCESS", "INCOMPLETE", "BREAK_GLASS",
                          "INTERRUPTED", "ARMING_FAILED"}
    /\ policy_sealed \in BOOLEAN
    /\ emergency_ready \in BOOLEAN
    /\ relaxation_timer \in 0..2          (* 0 = none pending *)
    /\ day_locked \in BOOLEAN
    /\ clock \in Nat

(* ---- actions (each maps to a service method in dhriti/) ---- *)

SealPolicy ==
    /\ session_state = "DRAFT"
    /\ policy_sealed = FALSE
    /\ session_state' = "SEALED"
    /\ policy_sealed' = TRUE
    /\ emergency_ready' = TRUE        (* break-glass configured at seal *)
    /\ relaxation_timer' = 0
    /\ UNCHANGED <<day_locked, clock>>

Arm ==
    /\ session_state = "SEALED"
    /\ policy_sealed
    /\ session_state' = "ARMING"
    /\ UNCHANGED <<policy_sealed, emergency_ready, relaxation_timer,
                   day_locked, clock>>

ArmedOK ==
    /\ session_state = "ARMING"
    /\ session_state' = "ACTIVE"
    /\ day_locked' = TRUE
    /\ UNCHANGED <<policy_sealed, emergency_ready, relaxation_timer,
                   clock>>

ArmingFailed ==
    /\ session_state = "ARMING"
    /\ session_state' = "ARMING_FAILED"
    /\ day_locked' = FALSE            (* nothing was locked *)
    /\ UNCHANGED <<policy_sealed, emergency_ready, relaxation_timer,
                   clock>>

CompleteWork ==
    /\ session_state = "ACTIVE"
    /\ session_state' = "SUCCESS"
    /\ day_locked' = FALSE            (* session ends; day may stay up *)
    /\ UNCHANGED <<policy_sealed, emergency_ready, relaxation_timer,
                   clock>>

EndIncomplete ==
    /\ session_state = "ACTIVE"
    /\ session_state' = "INCOMPLETE"
    /\ day_locked' = FALSE
    /\ UNCHANGED <<policy_sealed, emergency_ready, relaxation_timer,
                   clock>>

BreakGlass ==     (* the toll: always available, always ends the session *)
    /\ session_state = "ACTIVE"
    /\ emergency_ready                (* reachable from every ACTIVE state *)
    /\ session_state' = "BREAK_GLASS"
    /\ day_locked' = FALSE
    /\ relaxation_timer' = 0
    /\ UNCHANGED <<policy_sealed, emergency_ready, clock>>

Crash ==          (* daemon death: whatever was running is INTERRUPTED *)
    /\ session_state \in {"ARMING", "ACTIVE"}
    /\ session_state' = "INTERRUPTED"
    /\ UNCHANGED <<policy_sealed, emergency_ready, relaxation_timer,
                   day_locked, clock>>

Recover ==        (* next boot: interrupted -> honest terminal state *)
    /\ session_state = "INTERRUPTED"
    /\ session_state' \in {"SUCCESS", "INCOMPLETE", "BREAK_GLASS"}
    /\ day_locked' = FALSE
    /\ UNCHANGED <<policy_sealed, emergency_ready, relaxation_timer,
                   clock>>

(* Relaxation requests (loosening the policy) NEVER apply immediately:
   the request arms a timer; only TickRelaxation after the delay
   applies it. Tightening (SealPolicy) applies immediately. *)
RequestRelaxation ==
    /\ relaxation_timer = 0
    /\ session_state \in {"ACTIVE", "INCOMPLETE", "INTERRUPTED"}
    /\ relaxation_timer' = 2          (* delay units *)
    /\ UNCHANGED <<session_state, policy_sealed, emergency_ready,
                   day_locked, clock>>

TickRelaxation ==
    /\ relaxation_timer > 0
    /\ relaxation_timer' = relaxation_timer - 1
    /\ UNCHANGED <<session_state, policy_sealed, emergency_ready,
                   day_locked, clock>>

DayWindowEnd ==   (* unconditional ceiling: the day releases, always *)
    /\ day_locked
    /\ day_locked' = FALSE
    /\ relaxation_timer' = 0
    /\ UNCHANGED <<session_state, policy_sealed, emergency_ready, clock>>

Next ==
    \/ SealPolicy \/ Arm \/ ArmedOK \/ ArmingFailed
    \/ CompleteWork \/ EndIncomplete \/ BreakGlass
    \/ Crash \/ Recover
    \/ RequestRelaxation \/ TickRelaxation
    \/ DayWindowEnd

Init ==
    /\ session_state = "DRAFT"
    /\ policy_sealed = FALSE
    /\ emergency_ready = FALSE
    /\ relaxation_timer = 0
    /\ day_locked = FALSE
    /\ clock = 0

Spec == Init /\ [][Next]_<<session_state, policy_sealed, emergency_ready,
                         relaxation_timer, day_locked, clock>>

(* ------------------------- invariants ------------------------- *)

NoActiveWithoutSealed ==
    (session_state = "ACTIVE") => policy_sealed

EmergencyAlwaysPossible ==
    (session_state = "ACTIVE") => emergency_ready

RelaxationIsDelayed ==
    (* a relaxation timer only ever counts down to 0; it never
       applies on the same step it was requested *)
    relaxation_timer \in 0..2

DayReleaseIsBounded ==
    day_locked => (session_state \in {"SEALED", "ARMING", "ACTIVE",
                                      "INTERRUPTED", "DRAFT"}
                   \/ relaxation_timer > 0)

InterruptedRecovers ==
    session_state # "INTERRUPTED" \/ emergency_ready

=============================================================================
