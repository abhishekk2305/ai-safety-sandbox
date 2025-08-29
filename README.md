# AI Safety Sandbox — MVP

A user-facing trust layer for AI coding agents. It enforces **environment separation**, **human approvals** for risky actions, **risk scoring**, **immutable audit logs**, and **snapshots/rollback** — all in a safe demo **DSL** (no shell, no DB) so you can showcase the guardrails without risking real systems.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Simple Action DSL
Allowed actions:
```
write <path> | <content>
append <path> | <content>
delete_file <path>
move <src> <dst>
make_dir <path>
```

Example:
```
write releases/notes.md | Release v1.2 notes
append README.md | Added release instructions
make_dir releases/2025-08-29
move tmp/output.txt reports/output.txt
delete_file old/legacy.sql
```

## Why this matters
- Addresses the **AI trust deficit** with visible guardrails.
- Locks **prod** by default; requires typed approval for risky plans.
- Writes **append-only JSONL** audit records with checksums.
- Takes a **snapshot before each run** to enable rollback.

## Roadmap
- Configurable policies (`config.yaml`)
- Snapshot restore UI
- OTP/Slack approval
- Adapter for real runners (containerized)
- LLM "plan-only" mode (always reviewed before execution)
