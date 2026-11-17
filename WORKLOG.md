# WORKLOG — practice mock (Guarded Incident Assistant)

Status words: planned / active / blocked / ready-for-review / verified / deferred.
"verified" below means Claude ran it locally. Nothing here has been independently reviewed yet.

## 1. Brief and time
- Brief: `mock-takehome-75min.md` (invented practice exercise, supplied by Daniel 2026-11-17). AI assistance allowed.
- Timebox: 75 min, hard stop 90. Claude started 12:49 UTC.
- Acknowledgments: Claude only. No message from Grok or Goku has been received.

## 2. Requirements
| ID | Acceptance check | Pri | Status | Evidence |
|---|---|---|---|---|
| A | Principal from session; tenant check on every object; spoofed args ignored; one denial category; no foreign data out | P0 | verified (Claude) | tests 03, 04, 07, 12 |
| B | Normal plan returns reads + pending proposal; honest status | P0 | verified (Claude) | test 01 |
| C | Stored payload; owner + permission to approve/execute; no execute before approval; recheck at execution | P0 | verified (Claude) | tests 02, 06, 07, 08, permission_is_rechecked, ignores_later_model_arguments |
| D | Sequential replay: same ticket, one ticket, one audit record | P0 | verified (Claude) | test 09 |
| D-ext | Concurrency / crash-safe persistence | P2 | deferred (brief marks it optional) | README limitations |
| E | Max 3 attempts incl. denied; compact trace without bodies | P0 | verified (Claude) | test 10, trace_is_compact |
| Validation | Unknown tools, extra keys, types, empty strings, 120/1000 bounds | P0 | verified (Claude) | tests 05, 11 |
| Deliverables | README, demo, one test command, eval counts | P0 | ready-for-review | README.md, demo.py |

## 3. Decisions and assumptions
- Single in-memory `Assistant` object; standard library only. See README "Design decisions".
- Assumed: a denied step does not stop the remaining attempts in a call.
- Assumed: a read-only user may create a pending proposal but not approve or execute it.
- Assumed: unknown tool names are logged as `unknown` rather than verbatim.

## 4. Tasks
| ID | Owner | Task | Status |
|---|---|---|---|
| T1 | Claude | Implement boundary, planner, fixtures | ready-for-review |
| T2 | Claude | 12 required tests + extras, demo, eval | ready-for-review |
| T3 | Grok | Independent review of the pushed commit | planned (not acknowledged) |
| T4 | Goku | Independent smoke run, defense rehearsal | planned (not acknowledged) |

## 5. Snapshot and commands
- Snapshot: the commit containing this file; SHA is in the handoff message.
- Runtime: Python 3.12.14 (via uv), macOS. No dependencies, no lockfile.
- `python3 -m unittest -v` → 17 tests, OK.
- `python3 demo.py` → allowed 3/3, forbidden executed 0/11, canary exposures 0, replay PASS, budget PASS.
- Mutation check (not committed): with the tenant check removed, tests 03, 12 and the eval smoke test fail.

## 6. Review findings
None received.

## 7. Risks and next handoff
- Not tested: concurrency, restart, any real model, any real authentication.
- Next: Daniel relays the SHA to Grok (review) and Goku (smoke run). Claude fixes confirmed findings.
