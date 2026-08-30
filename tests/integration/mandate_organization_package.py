from __future__ import annotations

from mandate.organization import (
    Authority,
    Organization,
    OrganizationError,
    Responsibility,
    decode_snapshot,
    encode_snapshot,
    OrganizationSnapshot,
    validate_organization,
)


def _base() -> Organization:
    return Organization(
        run_id="RUN-1",
        responsibilities=(
            Responsibility(
                responsibility_id="RUN-AUTHORITY",
                run_id="RUN-1",
                title="Run Authority",
                kind="RUN_AUTHORITY",
                parent_responsibility_id=None,
                authority=Authority(
                    delegate=True,
                    accept_child_results=True,
                    run_control=True,
                ),
                mandate="Own run control and final independent acceptance only.",
            ),
            Responsibility(
                responsibility_id="ROOT",
                run_id="RUN-1",
                title="Accountable Root",
                kind="RESPONSIBILITY",
                parent_responsibility_id="RUN-AUTHORITY",
                authority=Authority(
                    delegate=True,
                    accept_child_results=True,
                ),
                mandate="Own the complete Human mission below Run Authority.",
                prohibited_scope=("Run control",),
            ),
            Responsibility(
                responsibility_id="DOMAIN-A",
                run_id="RUN-1",
                title="Domain A",
                kind="RESPONSIBILITY",
                parent_responsibility_id="ROOT",
                authority=Authority(
                    delegate=False,
                    accept_child_results=False,
                ),
                mandate="Own one material evidence and judgment surface.",
                prohibited_scope=("Sibling primary accountability",),
            ),
        ),
    )


def _expect(code: str, fn) -> None:
    try:
        fn()
    except OrganizationError as exc:
        assert str(exc) == code, (str(exc), code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> int:
    base = _base()
    validate_organization(base, require_single_root=True)
    assert base.root().responsibility_id == "ROOT"
    assert base.children("ROOT")[0].responsibility_id == "DOMAIN-A"
    assert base.responsibility("DOMAIN-A").conversation_id is None

    snapshot = OrganizationSnapshot(
        organization=base,
        reason="initial organization",
        source_ref="R-1",
    )
    restored = decode_snapshot(encode_snapshot(snapshot))
    assert restored == snapshot

    second_root = Responsibility(
        responsibility_id="ROOT-2",
        run_id="RUN-1",
        title="Second Root",
        kind="RESPONSIBILITY",
        parent_responsibility_id="RUN-AUTHORITY",
        authority=Authority(delegate=False, accept_child_results=False),
        mandate="Invalid second root.",
    )
    _expect(
        "EXACTLY_ONE_ACCOUNTABLE_ROOT_REQUIRED",
        lambda: validate_organization(
            Organization("RUN-1", base.responsibilities + (second_root,))
        ),
    )

    expanded_child = Responsibility(
        responsibility_id="EXPANDED",
        run_id="RUN-1",
        title="Expanded Child",
        kind="RESPONSIBILITY",
        parent_responsibility_id="DOMAIN-A",
        authority=Authority(delegate=True, accept_child_results=False),
        mandate="Invalid authority expansion.",
    )
    _expect(
        "PARENT_DELEGATE_AUTHORITY_REQUIRED",
        lambda: validate_organization(
            Organization("RUN-1", base.responsibilities + (expanded_child,))
        ),
    )

    child_run_control = Responsibility(
        responsibility_id="BAD-CONTROL",
        run_id="RUN-1",
        title="Bad Control",
        kind="RESPONSIBILITY",
        parent_responsibility_id="ROOT",
        authority=Authority(
            delegate=False,
            accept_child_results=False,
            run_control=True,
        ),
        mandate="Invalid run-control child.",
    )
    _expect(
        "RUN_CONTROL_RESERVED_FOR_RUN_AUTHORITY",
        lambda: validate_organization(
            Organization("RUN-1", base.responsibilities + (child_run_control,))
        ),
    )

    root_without_children = Organization(
        run_id="RUN-1",
        responsibilities=base.responsibilities[:2],
    )
    _expect(
        "DELEGATING_RESPONSIBILITY_WITHOUT_CHILDREN",
        lambda: validate_organization(
            root_without_children,
            require_delegating_nodes_have_children=True,
        ),
    )

    bound_a = Responsibility(
        **{
            **base.responsibility("ROOT").__dict__,
            "conversation_id": "same-conversation",
        }
    )
    bound_b = Responsibility(
        **{
            **base.responsibility("DOMAIN-A").__dict__,
            "conversation_id": "same-conversation",
        }
    )
    _expect(
        "CONVERSATION_BINDING_DUPLICATE",
        lambda: validate_organization(
            Organization(
                "RUN-1",
                (base.run_authority(), bound_a, bound_b),
            )
        ),
    )

    print("MANDATE_ORGANIZATION_PACKAGE_SELF_TEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
