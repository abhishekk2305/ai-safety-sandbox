# Product Requirements Document (PRD) — AI Safety Sandbox

## 1. Background
AI coding agents (Replit AI Agent, Copilot, Cursor) face adoption hurdles due to unsafe actions (hallucinations, DB wipes, destructive commands). Trust deficit → churn.

## 2. Problem Statement
Users need **visible guardrails** to feel confident adopting AI agents in production.

## 3. Objectives
- Provide a **sandboxed, visible safety layer** for AI-driven code execution.
- Rebuild **trust and adoption** through transparency and control.
- Demonstrate business impact: lower churn, fewer support incidents, safer brand positioning.

## 4. Users
- **Developers**: want safety & rollback.
- **Educators**: need guarantees for student use.
- **Enterprise buyers**: require audit trails & approvals.

## 5. Features (MVP Scope)
- Env separation (dev/staging/prod)
- Dry-run risk scoring
- Approval workflow for risky actions
- Append-only audit logging
- Snapshot + rollback
- Configurable risk policy (via `config.yaml`)

## 6. Out of Scope
- No real DB or shell execution (DSL only)
- No external identity system (basic approvals only)

## 7. Success Metrics
- % of risky actions flagged/blocked
- Increase in AI feature adoption
- Reduction in “unsafe AI” complaints
- Lower churn among AI-enabled users
