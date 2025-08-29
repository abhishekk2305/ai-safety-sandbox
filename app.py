import os, json, hashlib, shutil, datetime as dt
from dataclasses import dataclass
from typing import List, Dict, Tuple

import streamlit as st

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# ------------------ Config ------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
WORKSPACES = {
    "dev": os.path.join(BASE_DIR, "workspaces", "dev"),
    "staging": os.path.join(BASE_DIR, "workspaces", "staging"),
    "prod": os.path.join(BASE_DIR, "workspaces", "prod"),
}
LOG_PATH = os.path.join(BASE_DIR, "logs", "actions.jsonl")
SNAPSHOT_DIR = os.path.join(BASE_DIR, "snapshots")
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

# Default config values
DEFAULT_CONFIG = {
    "prod_locked": True,
    "allowed_actions": ["write", "append", "delete_file", "move", "make_dir"],
    "high_risk_keywords": [
        "drop table", "delete database", "rm -rf", "truncate", "kubectl delete", "terraform destroy",
        "shutdown", "format", "wipe", "vault delete", "aws s3 rm", "gcloud sql instances delete",
    ],
    "med_risk_hints": ["overwrite", "migrate", "secrets", "credentials", "prod", "production"]
}

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
for env, path in WORKSPACES.items():
    os.makedirs(path, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ------------------ Config Management ------------------
def load_config() -> Dict:
    """Load config from config.yaml or return defaults."""
    if YAML_AVAILABLE and os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            # Merge with defaults for missing keys
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = default_value
            return config
        except Exception as e:
            st.error(f"Error loading config.yaml: {e}")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def get_config() -> Dict:
    """Get config from session state or load it."""
    if "config" not in st.session_state:
        st.session_state["config"] = load_config()
    return st.session_state["config"]

def reload_config():
    """Reload config from file."""
    st.session_state["config"] = load_config()

# ------------------ Helpers ------------------
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

@dataclass
class Action:
    kind: str
    args: List[str]
    raw: str

@dataclass
class Analysis:
    risk: str
    reasons: List[str]

# ------------------ Parser ------------------
def parse_dsl(dsl_text: str) -> List[Action]:
    actions = []
    for line in dsl_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        # Support "cmd arg1 | payload" pattern
        if "|" in line:
            left, payload = line.split("|", 1)
            left = left.strip(); payload = payload.strip()
            parts = left.split()
            kind = parts[0]; args = parts[1:] + [payload]
        else:
            parts = line.split()
            kind = parts[0]; args = parts[1:]
        actions.append(Action(kind=kind, args=args, raw=line))
    return actions

# ------------------ Risk Evaluator ------------------
def evaluate_actions(actions: List[Action], env: str) -> Analysis:
    config = get_config()
    reasons = []
    high = False; med = False
    
    # Env-level policy
    if env == "prod" and config["prod_locked"]:
        high = True; reasons.append("Prod environment is locked by policy.")
    
    for a in actions:
        raw_lower = a.raw.lower()
        if a.kind not in config["allowed_actions"]:
            high = True; reasons.append(f"Disallowed action: {a.kind}")
        for kw in config["high_risk_keywords"]:
            if kw in raw_lower:
                high = True; reasons.append(f"High-risk keyword detected: '{kw}' in '{a.raw}'")
        for hint in config["med_risk_hints"]:
            if hint in raw_lower:
                med = True; reasons.append(f"Medium-risk hint: '{hint}' in '{a.raw}'")
        # Delete in prod is always high risk
        if env == "prod" and a.kind == "delete_file":
            high = True; reasons.append("Deleting files in prod requires explicit approval.")
    
    risk = "Low"
    if high: risk = "High"
    elif med: risk = "Medium"
    return Analysis(risk=risk, reasons=reasons)

# ------------------ Sandbox Executor ------------------
def ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def execute_action(ws: str, a: Action) -> Tuple[bool, str]:
    """Execute a single action safely inside workspace ws."""
    try:
        if a.kind == "write":
            # args: <path>, <content>
            rel, content = a.args[0], a.args[1]
            target = os.path.abspath(os.path.join(ws, rel))
            if not target.startswith(ws):
                return False, "Path traversal blocked"
            ensure_parent(target)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return True, f"Wrote {rel}"
        elif a.kind == "append":
            rel, content = a.args[0], a.args[1]
            target = os.path.abspath(os.path.join(ws, rel))
            if not target.startswith(ws):
                return False, "Path traversal blocked"
            ensure_parent(target)
            with open(target, "a", encoding="utf-8") as f:
                f.write("\n" + content)
            return True, f"Appended {rel}"
        elif a.kind == "delete_file":
            rel = a.args[0]
            target = os.path.abspath(os.path.join(ws, rel))
            if not target.startswith(ws):
                return False, "Path traversal blocked"
            if os.path.isdir(target):
                return False, "Refusing to delete directories in MVP"
            if os.path.exists(target):
                os.remove(target)
                return True, f"Deleted {rel}"
            else:
                return False, f"Not found: {rel}"
        elif a.kind == "move":
            src, dst = a.args[0], a.args[1]
            s = os.path.abspath(os.path.join(ws, src))
            d = os.path.abspath(os.path.join(ws, dst))
            if not s.startswith(ws) or not d.startswith(ws):
                return False, "Path traversal blocked"
            ensure_parent(d)
            shutil.move(s, d)
            return True, f"Moved {src} -> {dst}"
        elif a.kind == "make_dir":
            rel = a.args[0]
            target = os.path.abspath(os.path.join(ws, rel))
            if not target.startswith(ws):
                return False, "Path traversal blocked"
            os.makedirs(target, exist_ok=True)
            return True, f"Created dir {rel}"
        else:
            return False, f"Action not allowed: {a.kind}"
    except Exception as e:
        return False, f"Error: {e}"

# ------------------ Demo File Seeder ------------------
def seed_demo_files(env: str):
    """Create demo files in the specified environment workspace."""
    ws = WORKSPACES[env]
    
    # Create tmp/output.txt with "hello"
    tmp_file = os.path.join(ws, "tmp", "output.txt")
    ensure_parent(tmp_file)
    if not os.path.exists(tmp_file):
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write("hello")
    
    # Create old/legacy.sql (empty file)
    old_file = os.path.join(ws, "old", "legacy.sql")
    ensure_parent(old_file)
    if not os.path.exists(old_file):
        with open(old_file, "w", encoding="utf-8") as f:
            f.write("")

# ------------------ Snapshots & Audit ------------------
def snapshot_workspace(env: str) -> str:
    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    src = WORKSPACES[env]
    snap_path = os.path.join(SNAPSHOT_DIR, f"{env}-{ts}")
    shutil.copytree(src, snap_path, dirs_exist_ok=True)
    return snap_path

def restore_snapshot(env: str, snap_path: str) -> None:
    ws = WORKSPACES[env]
    # wipe workspace then copy back
    if os.path.exists(ws):
        shutil.rmtree(ws)
    shutil.copytree(snap_path, ws, dirs_exist_ok=True)

def append_audit(record: Dict):
    payload = json.dumps(record, ensure_ascii=False)
    checksum = sha256(payload)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"checksum": checksum, "record": record}) + "\n")

def get_last_audit_record() -> Dict:
    """Get the last audit record from the log."""
    if not os.path.exists(LOG_PATH):
        return {}
    
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            last_line = lines[-1].strip()
            return json.loads(last_line)["record"]
    except Exception:
        pass
    return {}

def generate_risk_analysis_md(analysis: Analysis, actions: List[Action], env: str) -> str:
    """Generate markdown summary of risk analysis."""
    md = f"""# Risk Analysis Report

**Environment:** {env}
**Overall Risk Level:** {analysis.risk}
**Generated:** {dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC

## Risk Assessment

"""
    if analysis.reasons:
        md += "**Risk Factors:**\n"
        for reason in analysis.reasons:
            md += f"- {reason}\n"
    else:
        md += "No specific risk factors identified.\n"
    
    md += f"\n## Planned Actions ({len(actions)} total)\n\n"
    for i, action in enumerate(actions, 1):
        md += f"{i}. `{action.raw}`\n"
    
    return md

# ------------------ UI ------------------
st.set_page_config(page_title="AI Safety Sandbox – MVP", layout="wide")
st.title("🛡️ AI Safety Sandbox – MVP")

with st.sidebar:
    env = st.selectbox("Environment", ["dev", "staging", "prod"], index=0)
    ws = WORKSPACES[env]
    st.write(f"Workspace: `{ws}`")
    st.caption("Prod locked by policy in MVP.")
    
    st.divider()
    
    # Config management
    st.subheader("Config")
    config_exists = YAML_AVAILABLE and os.path.exists(CONFIG_PATH)
    if YAML_AVAILABLE:
        st.write(f"Config file: {'✅' if config_exists else '❌'} `config.yaml`")
        
        if config_exists and st.button("Reload config"):
            reload_config()
            st.success("Config reloaded!")
    else:
        st.write("⚠️ PyYAML not available - using defaults")
    
    st.divider()
    
    # Demo file seeder
    st.subheader("Demo Files")
    if st.button(f"Seed demo files for {env}"):
        seed_demo_files(env)
        st.success(f"Demo files seeded in {env}!")

st.subheader("1) Task & Agent Plan")
task = st.text_area("Task (what the agent is trying to do)", height=80, placeholder="e.g., Prepare a release folder and update README")
plan = st.text_area("Agent Plan (DSL actions)", height=200, placeholder=(
    "write releases/notes.md | Release v1.2 notes\n"
    "append README.md | Added release instructions\n"
    "make_dir releases/2025-08-29\n"
    "move tmp/output.txt reports/output.txt\n"
    "delete_file old/legacy.sql\n"
))

if st.button("Analyze plan", type="primary"):
    actions = parse_dsl(plan)
    analysis = evaluate_actions(actions, env)

    st.session_state["actions"] = actions
    st.session_state["analysis"] = analysis

if "analysis" in st.session_state:
    a = st.session_state["analysis"]
    st.subheader("2) Risk Analysis")
    st.write(f"**Overall Risk:** :{'red' if a.risk=='High' else ('orange' if a.risk=='Medium' else 'green')}[**{a.risk}**]")
    if a.reasons:
        st.markdown("**Reasons:**")
        for r in a.reasons:
            st.write("- ", r)

    config = get_config()
    need_approval = a.risk in ("Medium", "High") or (env == "prod")
    approval_text = ""
    if need_approval:
        st.subheader("3) Approval Required")
        st.info("Type APPROVE and provide a reason to proceed.")
        approval_text = st.text_input("Type 'APPROVE' to continue")
        reason = st.text_area("Reason / intent (will be logged)")
    else:
        reason = "Auto-approved (Low risk)"

    if st.button("Execute in Sandbox", disabled=(need_approval and approval_text.strip() != "APPROVE")):
        # Snapshot before
        snap = snapshot_workspace(env)
        actions: List[Action] = st.session_state["actions"]
        results = []
        success_all = True
        for act in actions:
            ok, msg = execute_action(WORKSPACES[env], act)
            results.append({"action": act.raw, "ok": ok, "msg": msg})
            if not ok: success_all = False

        record = {
            "ts": dt.datetime.utcnow().isoformat() + "Z",
            "env": env,
            "task": task,
            "risk": a.risk,
            "reasons": a.reasons,
            "approved": (not need_approval) or (approval_text.strip() == "APPROVE"),
            "approver_note": reason,
            "pre_snapshot": snap,
            "results": results,
        }
        append_audit(record)

        st.session_state["last_execution"] = {
            "record": record,
            "analysis": a,
            "actions": actions
        }

        st.subheader("4) Execution Results")
        for r in results:
            st.write(f"- [{'✅' if r['ok'] else '❌'}] {r['action']} → {r['msg']}")
        if not success_all:
            st.warning("Some actions failed. You can rollback using the snapshot below.")
        else:
            st.success("Plan executed in sandbox.")
        
        # Export buttons
        st.subheader("5) Export")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Download last audit record (JSON)"):
                audit_json = json.dumps(record, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📥 Download JSON",
                    data=audit_json,
                    file_name=f"audit_{env}_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        
        with col2:
            if st.button("Download risk analysis (Markdown)"):
                risk_md = generate_risk_analysis_md(a, actions, env)
                st.download_button(
                    label="📥 Download MD",
                    data=risk_md,
                    file_name=f"risk_analysis_{env}_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )

# ------------------ Restore Snapshot UI ------------------
st.subheader("Rollback / Restore Snapshot")
try:
    # Get all snapshots sorted by name (newest first due to timestamp format)
    all_snaps = [p for p in os.listdir(SNAPSHOT_DIR) if os.path.isdir(os.path.join(SNAPSHOT_DIR, p))]
    # Filter snapshots for current environment
    env_snaps = [s for s in all_snaps if s.startswith(f"{env}-")]
    env_snaps = sorted(env_snaps, reverse=True)
except FileNotFoundError:
    env_snaps = []

if env_snaps:
    chosen = st.selectbox(f"Choose a {env} snapshot to restore", env_snaps)
    if st.button("Restore selected snapshot"):
        restore_snapshot(env, os.path.join(SNAPSHOT_DIR, chosen))
        st.success(f"Restored snapshot: {chosen}")
        st.rerun()
else:
    st.info(f"No {env} snapshots yet. Execute a plan to create one automatically.")

# Show all snapshots for reference
try:
    all_snaps_display = sorted([p for p in os.listdir(SNAPSHOT_DIR) if os.path.isdir(os.path.join(SNAPSHOT_DIR, p))], reverse=True)
    if all_snaps_display:
        with st.expander(f"All snapshots ({len(all_snaps_display)} total)"):
            for snap in all_snaps_display:
                st.code(snap)
except FileNotFoundError:
    pass

st.divider()
st.caption("MVP rules: prod locked; destructive keywords blocked; append-only logs with checksums; snapshot before every run.")