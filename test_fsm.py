from conductor import Role, Status, validate_transition, FSMError


# Each tuple: (from_status, to_status, actor, expected: "ok" or "error contains substring")
CASES = [
    # 🔵 → 🟡 — planner or builder
    (Status.DRAFTING, Status.AWAITING_JONATHAN, Role.PLANNER, "ok"),
    (Status.DRAFTING, Status.AWAITING_JONATHAN, Role.BUILDER, "ok"),
    (Status.DRAFTING, Status.AWAITING_JONATHAN, Role.HUMAN, "actor"),
    # 🟡 → 🟢 — human only
    (Status.AWAITING_JONATHAN, Status.APPROVED, Role.HUMAN, "ok"),
    (Status.AWAITING_JONATHAN, Status.APPROVED, Role.PLANNER, "actor"),
    (Status.AWAITING_JONATHAN, Status.APPROVED, Role.BUILDER, "actor"),
    # 🟡 → ❌ — human only
    (Status.AWAITING_JONATHAN, Status.REJECTED, Role.HUMAN, "ok"),
    (Status.AWAITING_JONATHAN, Status.REJECTED, Role.BUILDER, "actor"),
    # 🟡 → 🔵 — human only
    (Status.AWAITING_JONATHAN, Status.DRAFTING, Role.HUMAN, "ok"),
    (Status.AWAITING_JONATHAN, Status.DRAFTING, Role.PLANNER, "actor"),
    # 🟢 → 🔵 — human only
    (Status.APPROVED, Status.DRAFTING, Role.HUMAN, "ok"),
    (Status.APPROVED, Status.DRAFTING, Role.BUILDER, "actor"),
    # 🟢 → ⚙️ — builder only
    (Status.APPROVED, Status.IN_PROGRESS, Role.BUILDER, "ok"),
    (Status.APPROVED, Status.IN_PROGRESS, Role.PLANNER, "actor"),
    # 🟢 → ✅ — planner only
    (Status.APPROVED, Status.DONE, Role.PLANNER, "ok"),
    (Status.APPROVED, Status.DONE, Role.BUILDER, "actor"),
    # ⚙️ → ✅ — builder only
    (Status.IN_PROGRESS, Status.DONE, Role.BUILDER, "ok"),
    (Status.IN_PROGRESS, Status.DONE, Role.HUMAN, "actor"),
    # ⚙️ → 🟢 — builder only (retry)
    (Status.IN_PROGRESS, Status.APPROVED, Role.BUILDER, "ok"),
    (Status.IN_PROGRESS, Status.APPROVED, Role.HUMAN, "actor"),
    # ⚙️ → 🟡 — builder only (escalate)
    (Status.IN_PROGRESS, Status.AWAITING_JONATHAN, Role.BUILDER, "ok"),
    # ⚙️ → ❌ — builder or human
    (Status.IN_PROGRESS, Status.REJECTED, Role.BUILDER, "ok"),
    (Status.IN_PROGRESS, Status.REJECTED, Role.HUMAN, "ok"),
    (Status.IN_PROGRESS, Status.REJECTED, Role.PLANNER, "actor"),
    # 🔵 → ❌
    (Status.DRAFTING, Status.REJECTED, Role.BUILDER, "ok"),
    (Status.DRAFTING, Status.REJECTED, Role.HUMAN, "ok"),
    # any → ⏸️ (builder/planner/human; not from ❌ or ✅)
    (Status.DRAFTING, Status.PAUSED, Role.PLANNER, "ok"),
    (Status.IN_PROGRESS, Status.PAUSED, Role.BUILDER, "ok"),
    (Status.DONE, Status.PAUSED, Role.HUMAN, "transition"),
    (Status.REJECTED, Status.PAUSED, Role.HUMAN, "transition"),
    # illegal: 🔵 → 🟢 skipping 🟡
    (Status.DRAFTING, Status.APPROVED, Role.HUMAN, "transition"),
    # illegal: 🟡 → ⚙️
    (Status.AWAITING_JONATHAN, Status.IN_PROGRESS, Role.BUILDER, "transition"),
]


def test_fsm_cases():
    failed = []
    for fr, to, actor, expected in CASES:
        try:
            validate_transition(fr, to, actor)
            actual = "ok"
        except FSMError as exc:
            actual = str(exc)
        if expected == "ok":
            if actual != "ok":
                failed.append((fr, to, actor, expected, actual))
        else:
            if actual == "ok" or expected not in actual.lower():
                failed.append((fr, to, actor, expected, actual))
    assert not failed, f"FSM failures: {failed}"
