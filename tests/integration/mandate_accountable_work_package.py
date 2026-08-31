"""Deterministic conformance checks for the packaged Accountable Work Core."""

from mandate.accountable_work import (
    ActorAuthority,
    CanonicalRecord,
    ContractError,
    Decision,
    Result,
    Work,
    project,
)


ACTORS = {
    "ROOT": ActorAuthority(may_issue_work=True),
    "WORKER": ActorAuthority(may_issue_work=False),
}


def self_test() -> None:
    work = CanonicalRecord(
        "W-1",
        "ROOT",
        Work("WORKER", "Do bounded work.", ("Return evidence.",)),
    )
    result = CanonicalRecord(
        "R-1",
        "WORKER",
        Result("W-1", "Evidence returned."),
    )
    continued = CanonicalRecord(
        "D-1",
        "ROOT",
        Decision("R-1", "CONTINUE", "Same Work remains open."),
    )
    projection = project((work, result, continued), ACTORS)
    assert projection.open_work_refs() == {"W-1"}
    assert projection.closed_work_refs() == set()

    accepted = CanonicalRecord(
        "D-2",
        "ROOT",
        Decision("R-1", "ACCEPT", "Acceptance satisfied."),
    )
    projection = project((work, result, continued, accepted), ACTORS)
    assert projection.closed_work_refs() == {"W-1"}

    try:
        project(
            (
                work,
                result,
                CanonicalRecord(
                    "D-X",
                    "WORKER",
                    Decision("R-1", "ACCEPT", "Self acceptance."),
                ),
            ),
            ACTORS,
        )
    except ContractError as exc:
        assert str(exc) == "SELF_ACCEPTANCE_FORBIDDEN"
    else:
        raise AssertionError("SELF_ACCEPTANCE_WAS_NOT_REJECTED")

    print("MANDATE_ACCOUNTABLE_WORK_PACKAGE_SELF_TEST_OK")


if __name__ == "__main__":
    self_test()
