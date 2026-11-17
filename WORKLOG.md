# WORKLOG — practice mock (Guarded Incident Assistant)

Status words: planned / active / blocked / ready-for-review / verified / deferred.
"verified (Claude)" means Claude ran it locally. Grok reviewed commit `ccb5dae`; the fixes after it await recheck.

## 1. Brief and time
- Brief: `mock-takehome-75min.md` (invented practice exercise, supplied by Daniel 2026-11-17). AI assistance allowed.
- Timebox: 75 min, hard stop 90. Claude started 12:49 UTC.
- Acknowledgments: Claude; Grok (review of `ccb5dae` relayed by Daniel). Nothing received from Goku.

## 2. Requirements
| ID | Acceptance check | Pri | Status | Evidence |
|---|---|---|---|---|
| A | Principal from session; tenant check on every object; spoofed args rejected; one denial category; no foreign data out | P0 | verified (Claude) | tests 03, 04, 07, 12 |
| B | Normal plan returns reads + pending proposal; honest status | P0 | verified (Claude) | test 01 |
| C | Stored payload; owner + permission to approve/execute; no execute before approval; recheck at execution | P0 | verified (Claude) | tests 02, 06, 07, 08, permission_is_rechecked_at_approval_and_execution, ignores_later_model_arguments |
| D | Sequential replay: same ticket, one ticket, one audit record | P0 | verified (Claude) | test 09 |
| D-ext | Concurrency / crash-safe persistence | P2 | deferred (brief marks it optional) | README limitations |
| E | Max 3 attempts incl. denied; compact trace without bodies | P0 | verified (Claude) | test 10, trace_is_compact |
| Validation | Unknown tools, extra keys, types, empty strings, 120/1000 bounds | P0 | verified (Claude) | tests 05, 11 |
| Deliverables | README, demo, one test command, eval counts | P0 | ready-for-review | README.md, demo.py |

## 3. Decisions and assumptions
- Single in-memory `Assistant` object; standard library only. See README "Design decisions".
- Assumed: a denied step does not stop the remaining attempts in a call.
- Decided after G1: a read-only user cannot create a proposal (`permission_denied`).
- Assumed: unknown tool names are logged as `unknown` rather than verbatim.

## 4. Tasks
| ID | Owner | Task | Status |
|---|---|---|---|
| T1 | Claude | Implement boundary, planner, fixtures | ready-for-review |
| T2 | Claude | 12 required tests + extras, demo, eval | ready-for-review |
| T3 | Grok | Independent review of `ccb5dae` | done: pass, 2 minor + 1 optional |
| T5 | Claude | Fix G1–G3 with regression tests | ready-for-review |
| T6 | Grok | Recheck fixes on the new SHA | planned |
| T4 | Goku | Independent smoke run, defense rehearsal | planned (not acknowledged) |

## 5. Snapshot and commands
- Snapshot: the commit containing this file; SHA is in the handoff message.
- Runtime: Python 3.12.14 (via uv), macOS. No dependencies, no lockfile.
- `python3 -m unittest -v` → 18 tests, OK.
- `python3 demo.py` → allowed 3/3, forbidden executed 0/12, canary exposures 0, replay PASS, budget PASS.
- Grok on `ccb5dae`, Python 3.13.5, fresh clone: 17 tests OK, same demo counts (then 0/11), own probe script clean.
- Mutation check (not committed): with the tenant check removed, tests 03, 12 and the eval smoke test fail.

## 6. Review findings (Grok, on `ccb5dae`)
| ID | Severity | Finding | Classification | Fix | Verification |
|---|---|---|---|---|---|
| G1 | minor | Read-only principal's proposal reported `awaiting_approval` though nobody could approve it | confirmed defect (reproduced by Claude) | `propose_ticket` denied with `permission_denied` without `can_create_ticket` | test 08 rewritten; Grok recheck pending |
| G2 | minor | WORKLOG row A said spoofed args "ignored"; code rejects them | confirmed (doc wording) | reworded to "rejected" | reread |
| G3 | optional | `Assistant(fixtures)` aliased the caller's dicts | confirmed (reproduced by Claude) | `copy.deepcopy` in `__init__` | test `caller_cannot_edit_principals_through_passed_fixtures`; Grok recheck pending |

## 7. Risks and next handoff
- Not tested: concurrency, restart, any real model, any real authentication.
- Next: Daniel relays the new SHA to Grok (recheck G1–G3) and Goku (smoke run, defense rehearsal).
