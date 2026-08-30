from mandate.accountable_work import (
    ActorAuthority,
    CanonicalRecord,
    ContractError,
    Decision,
    Result,
    Work,
    project,
)


def self_test() -> None:
    actors = {
        "ISSUER": ActorAuthority(may_issue_work=True),
        "WORKER": ActorAuthority(may_issue_work=False),
    }
    work = CanonicalRecord(
        ref="W1",
        actor="ISSUER",
        value=Work(to="WORKER", objective="Produce X", acceptance=("X is valid",)),
    )
    result = CanonicalRecord(
        ref="R1",
        actor="WORKER",
        value=Result(work_ref="W1", body="candidate"),
    )
    cont = CanonicalRecord(
        ref="D1",
        actor="ISSUER",
        value=Decision(result_ref="R1", decision="CONTINUE", judgment="revise"),
    )
    p = project((work, result, cont), actors)
    assert p.open_work_refs() == {"W1"}
    assert p.closed_work_refs() == set()

    result2 = CanonicalRecord(
        ref="R2",
        actor="WORKER",
        value=Result(work_ref="W1", body="accepted candidate"),
    )
    accept = CanonicalRecord(
        ref="D2",
        actor="ISSUER",
        value=Decision(result_ref="R2", decision="ACCEPT", judgment="meets contract"),
    )
    p = project((work, result, cont, result2, accept), actors)
    assert p.closed_work_refs() == {"W1"}

    try:
        project(
            (
                work,
                result,
                CanonicalRecord(
                    ref="BAD",
                    actor="WORKER",
                    value=Decision(
                        result_ref="R1",
                        decision="ACCEPT",
                        judgment="self acceptance",
                    ),
                ),
            ),
            actors,
        )
    except ContractError as exc:
        assert str(exc) == "SELF_ACCEPTANCE_FORBIDDEN"
    else:
        raise AssertionError("self acceptance was not rejected")

    print("MANDATE_ACCOUNTABLE_WORK_PACKAGE_SELF_TEST_OK")


if __name__ == "__main__":
    self_test()
