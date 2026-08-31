# Migration from Modelrail

This document is the durable fidelity record for extracting Mandate from `0bLad20x/llm-browser-modelrail` into the standalone `0bLad20x/mandate` repository.

## Authoritative source

Frozen source evidence:

- source repository: `0bLad20x/llm-browser-modelrail`;
- source commit: `9db1f45c7ebcb5e7fd908db72911a9d583edb274`;
- source root tree: `216e44cee4ce22d6cbd00a3140cf7b238f1fe930`;
- source `src/mandate` tree: `7aa1487659041739926d248eedc4d25675523dcb`.

The transferred production tree contained exactly 11 files.

## Exact transfer checkpoint

Standalone transfer evidence:

- repository: `0bLad20x/mandate`;
- transfer commit: `b126e21a9027dc7198db6de2c3cb9a3e0fab356b`;
- transfer root tree: `ff5651c6afdccd123318c0a111e741ce35867b80`;
- transferred `src/mandate` tree: `7aa1487659041739926d248eedc4d25675523dcb`.

Because the source and transferred `src/mandate` trees have the same Git tree SHA, the production-package transfer is byte-identical at this checkpoint.

The transfer commit also copied the then-current Mandate architecture/core documentation and the two Mandate integration tests without rewriting their content.

## Production blob provenance

| Path | Frozen source blob |
| --- | --- |
| `src/mandate/__init__.py` | `dedd743128aa56bb2ce5b276d1a31fc88ecf8f05` |
| `src/mandate/accountable_work/__init__.py` | `88f5c9ef0e9525646b2b51c873bb7cbcc264c86c` |
| `src/mandate/accountable_work/core.py` | `8b8a45a9401c0d5e54fa2c7eb98975cab109a136` |
| `src/mandate/accountable_work/ledger.py` | `5e5f2d3bae15d641cf3331e55c663c47e8866a5f` |
| `src/mandate/bootstrap/__init__.py` | `a7ba967fcec314936f09b31b0a3d1c4d27106c1f` |
| `src/mandate/bootstrap/__main__.py` | `1e9c625da38b2949101803955d84da5dd6ab02cf` |
| `src/mandate/bootstrap/api.py` | `59627c8736f5fc7a25b8d1939768f86e079f6860` |
| `src/mandate/bootstrap/contract.py` | `87c6a8aa5538f5afb1b45bcd8a3eaa6589d476e7` |
| `src/mandate/persistence/__init__.py` | `8911419dcd068b77a9595e1c4cbd9bdd3e5f5244` |
| `src/mandate/persistence/base.py` | `a38c3da77676b5cb789f7d18972e4e77ee2f8ff8` |
| `src/mandate/persistence/github.py` | `a466ec274cf209264a7327b941f8a8f0c4ea31ee` |

## Intentional post-transfer changes

The standalone repository is not expected to remain byte-identical forever. Fidelity means the source was transferred exactly before independent evolution began.

At the standalone composition boundary, ten of the eleven original production files remain byte-identical. The only intentional production-file change is `src/mandate/bootstrap/__main__.py`: the old implicit persistence target pointing to the Modelrail repository was removed and `--repository` became explicit. This changes deployment composition, not Accountable Work, Bootstrap API/contract, or Persistence semantics.

Other intentional standalone changes are repository/package concerns:

- project distribution renamed and limited to `src/mandate`;
- Modelrail removed from the Mandate wheel namespace;
- explicit standalone `.gitignore` and secret/runtime configuration boundary;
- composition and runtime-integration tests added;
- Modelrail declared as an external immutable runtime dependency;
- `uv.lock` committed for reproducible resolution;
- architecture documentation updated to describe standalone ownership.

No post-transfer change silently replaces the frozen source record. The exact transfer checkpoint remains independently addressable.

## Live separation proof

The external-runtime boundary was tested end-to-end with run `MANDATE-LIVE-20260831-1244`.

The run executed:

```text
standalone Mandate
    -> pinned external Modelrail TurnAPI
    -> live ChatGPT
    -> Mandate GitHubPersistence
    -> canonical Work / Result / Decision
```

The final RUN-AUTHORITY Decision was `ACCEPT`, with no external input required. The durable stream is Mandate issue `#129`. This proves that the standalone repository can own semantic coordination while consuming Modelrail only as external execution infrastructure.

## Historical-document provenance

`docs/MANDATE_ACCOUNTABLE_WORK_CORE.md` is intentionally preserved as the transferred provisional core-contract artifact. Historical issue/comment references inside that document belong to the source-era evidence context and are not rewritten to manufacture standalone provenance.

New standalone documentation should point here when explaining that history rather than editing historical references in place.

## Archive rule

The exact-transfer evidence must remain reachable even after temporary migration branches are cleaned. A permanent archive ref may replace the temporary `migration/modelrail-current-exact` branch, but it must continue to point to transfer commit `b126e21a9027dc7198db6de2c3cb9a3e0fab356b`.