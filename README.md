# 🛡️ AI Safety Sandbox — MVP

**A user-facing trust layer for AI coding agents.**

This project demonstrates how **visible guardrails** can restore user trust in AI-driven coding agents.  
It enforces:
- **Environment separation** (dev/staging/prod)
- **Risk analysis & scoring** of agent plans
- **Human approvals** for Medium/High risk
- **Append-only audit logs** with checksums
- **Snapshots + one-click rollback**

---

## ✨ Why this exists
Replit’s AI Agent faces adoption challenges due to unsafe behavior.  
Infra fixes are invisible — users need *visible, controllable safety*.  

Real user complaints:  
> “Replit AI just **deleted my entire folder** with no warning.”  
>  
> “Burned through credits on nonsense completions. No way to stop or recover.”  
>  
> “I like the AI concept, but I **can’t trust it on production projects**.”  

This Sandbox makes trust tangible.


---

## 🚀 Demo Highlights
- **Prod locked by policy**
- **Dry-run risk analysis** with keyword + action scoring
- **Approval flow** for risky actions
- **Snapshot + rollback**
- **Export** audit record (JSON) & risk summary (Markdown)

---

## 🧩 Action DSL
Whitelisted, safe-only commands:
write <path> | <content>
append <path> | <content>
delete_file <path>
move <src> <dst>
make_dir <path>

---

## 🛠️ Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py

Open http://localhost:8501
.

Seed demo files (sidebar → “Seed demo files for env”) to auto-create tmp/output.txt and old/legacy.sql.

---

prod_locked: true
allowed_actions: [write, append, delete_file, move, make_dir]
high_risk_keywords:
  - drop table
  - delete database
  - rm -rf
  - truncate
med_risk_hints: [overwrite, migrate, secrets, credentials, prod, production]
Edit and click Reload config (sidebar) to apply live.

---

📈 Business Impact

Reduce churn: visible safety restores trust → adoption of AI features rises.

Cut support costs: prevents unsafe agent actions before escalation.

Differentiate: “The safe AI agent” vs competitors with no visible guardrails.

Full analysis: BUSINESS_IMPACT.md

---

📄 Docs

PRD

Business Impact

Design Decisions

Roadmap

Contributing

License
