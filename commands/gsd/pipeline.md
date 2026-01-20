---
name: gsd:pipeline
description: Full GSD pipeline orchestrator with claude-flow state sync and /research integration
argument-hint: '"Project description" | --phase N | --research N | --resume | --status'
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
  - TodoWrite
  - AskUserQuestion
  - Skill
  - WebSearch
  - WebFetch
  - mcp__claude-flow__memory_store
  - mcp__claude-flow__memory_retrieve
  - mcp__claude-flow__memory_search
  - mcp__claude-flow__session_save
  - mcp__claude-flow__session_restore
  - mcp__claude-flow__session_list
---

# /gsd:pipeline - Full GSD Orchestrator

Complete GSD workflow orchestration with crash recovery and deep research integration.

## Usage

```bash
/gsd:pipeline "Project description"     # Full flow from scratch
/gsd:pipeline --phase 3                 # Execute single phase
/gsd:pipeline --research 3              # Deep research + plan for phase
/gsd:pipeline --resume                  # Resume from last checkpoint
/gsd:pipeline --status                  # Show pipeline status
/gsd:pipeline --sync                    # Sync to GitHub only
```

## Arguments

```
$ARGUMENTS
```

## Pipeline Modes

### Mode 1: Full Pipeline (new project)
```
/gsd:pipeline "Bitcoin on-chain analytics platform"
```

### Mode 2: Single Phase
```
/gsd:pipeline --phase 3
```

### Mode 3: Deep Research Phase
```
/gsd:pipeline --research 3
```
Uses `/research` for academic papers + `/gsd:research-phase` for ecosystem.

### Mode 4: Resume
```
/gsd:pipeline --resume
```

## State Management (Unified: claude-flow + QuestDB)

### Architecture
```
claude-flow memory  → Runtime state, crash recovery
        ↓ sync
QuestDB (port 9009) → Metrics persistence, Grafana dashboards
```

### On Start - Load or Create State
```python
project = basename(cwd)
state_key = f"gsd:pipeline:{project}"

# Check for existing state
existing = mcp__claude-flow__memory_retrieve(key=state_key)

if existing and existing.status != "completed":
    # Ask user to resume or start fresh
    response = AskUserQuestion(
        questions=[{
            "header": "Resume?",
            "question": f"Found incomplete pipeline at step '{existing.current_step}'. Resume?",
            "options": [
                {"label": "Resume", "description": "Continue from last checkpoint"},
                {"label": "Start Fresh", "description": "Begin new pipeline run"}
            ]
        }]
    )
    if response == "Resume":
        mcp__claude-flow__session_restore(sessionId=f"gsd-pipeline-{project}")
```

### On Each Step - Save Checkpoint (dual-write)
```python
def save_checkpoint(step_name, step_data, phase=None, plan=None):
    start_time = time.time()

    # 1. claude-flow: runtime state
    mcp__claude-flow__memory_store(
        key=state_key,
        value={
            "status": "in_progress",
            "current_step": step_name,
            "completed_steps": completed_steps,
            "step_data": step_data,
            "updated_at": timestamp()
        }
    )
    mcp__claude-flow__session_save(sessionId=f"gsd-pipeline-{project}-{step_name}")

    # 2. QuestDB: metrics persistence (for Grafana)
    Bash: python ~/.claude/scripts/pipeline_sync.py step \
        --project {project} \
        --step {step_name} \
        --status in_progress \
        --phase {phase} --plan {plan}
```

### On Complete - Mark Done (dual-write)
```python
duration_ms = int((time.time() - start_time) * 1000)

# claude-flow
mcp__claude-flow__memory_store(
    key=state_key,
    value={
        "status": "completed",
        "completed_at": timestamp(),
        "results": pipeline_results
    }
)

# QuestDB
Bash: python ~/.claude/scripts/pipeline_sync.py step \
    --project {project} \
    --step {step_name} \
    --status completed \
    --duration {duration_ms}
```

## Full Pipeline Flow

### Step 0: Initialize
```
save_checkpoint("init", {})

# Check if .planning exists
if not exists(".planning/PROJECT.md"):
    proceed_to_step_1 = True
else:
    # Ask if starting new or continuing
    AskUserQuestion: "Project exists. What to do?"
    - "Continue from roadmap" → skip to step 4
    - "Start new milestone" → /gsd:new-milestone
```

### Step 1: New Project (if needed)
```
save_checkpoint("new_project", {})
Skill(skill="gsd:new-project")
```

### Step 2: Research Project (if complex domain)
```
# Auto-detect if research needed based on project description
RESEARCH_KEYWORDS = ["ML", "AI", "algorithm", "trading", "blockchain", "optimization", "statistical"]

if any(kw in project_description for kw in RESEARCH_KEYWORDS):
    save_checkpoint("research_project", {})
    Skill(skill="gsd:research-project")
```

### Step 3: Define Requirements
```
save_checkpoint("requirements", {})
Skill(skill="gsd:define-requirements")
```

### Step 4: Create Roadmap
```
save_checkpoint("roadmap", {})
Skill(skill="gsd:create-roadmap")
```

### Step 5: Execute Phases (loop)
```
# Read ROADMAP.md to get phases
phases = parse_roadmap(".planning/ROADMAP.md")

for phase in phases:
    # Check if phase needs deep research
    ACADEMIC_KEYWORDS = ["paper", "research", "algorithm", "methodology", "empirical", "theory"]
    needs_deep_research = any(kw in phase.description.lower() for kw in ACADEMIC_KEYWORDS)

    if needs_deep_research:
        # Step 5a: Deep Research (uses /research)
        save_checkpoint(f"deep_research_{phase.number}", {"phase": phase.number})
        Skill(skill="research", args=f"{phase.description} academic paper study")
        # Output goes to current directory, move to phase folder

    # Step 5b: Plan Phase
    save_checkpoint(f"plan_{phase.number}", {"phase": phase.number})
    Skill(skill="gsd:plan-phase", args=str(phase.number))

    # Step 5c: Execute Phase
    save_checkpoint(f"execute_{phase.number}", {"phase": phase.number})
    Skill(skill="gsd:execute-phase", args=str(phase.number))

    # Step 5d: Sync to GitHub
    save_checkpoint(f"sync_{phase.number}", {"phase": phase.number})
    Skill(skill="gsd:sync-github")
```

### Step 6: Complete Milestone
```
save_checkpoint("complete", {})
Skill(skill="gsd:complete-milestone")

# Mark pipeline as done
mcp__claude-flow__memory_store(key=state_key, value={"status": "completed", ...})
```

## Single Phase Mode (--phase N)

```
phase_num = parse_args("--phase")

save_checkpoint(f"single_phase_{phase_num}", {"phase": phase_num})

# Plan if not planned
if not exists(f".planning/phases/*-*/{phase_num}-*-PLAN.md"):
    Skill(skill="gsd:plan-phase", args=phase_num)

# Execute
Skill(skill="gsd:execute-phase", args=phase_num)

# Sync
Skill(skill="gsd:sync-github")
```

## Deep Research Mode (--research N)

```
phase_num = parse_args("--research")
phase_desc = get_phase_description(phase_num)

save_checkpoint(f"deep_research_{phase_num}", {"phase": phase_num})

# 1. Academic research with /research
Skill(skill="research", args=f"{phase_desc} academic paper methodology")

# 2. Ecosystem research with GSD
Skill(skill="gsd:research-phase", args=phase_num)

# 3. Merge outputs
# /research output is in current dir or spec context
# /gsd:research-phase output is in .planning/phases/XX-name/RESEARCH.md
# Merge both into final RESEARCH.md

# 4. Plan phase with research context
Skill(skill="gsd:plan-phase", args=phase_num)
```

**⚠️ Accesso ai dati RAG completi:**
Le fonti in research output sono metadata. Per il contenuto RAG dei papers:
1. Attendi notifica Discord (processing 15-30 min)
2. Usa `/research-papers "query"` per query semantiche

## Resume Mode (--resume)

```
state = mcp__claude-flow__memory_retrieve(key=state_key)

if not state:
    print("No pipeline state found. Start with: /gsd:pipeline 'description'")
    return

print(f"Resuming from: {state.current_step}")
print(f"Completed: {state.completed_steps}")

mcp__claude-flow__session_restore(sessionId=f"gsd-pipeline-{project}-{state.current_step}")

# Continue from current_step
```

## Status Mode (--status)

```
state = mcp__claude-flow__memory_retrieve(key=state_key)

if not state:
    print("No active pipeline")
else:
    print(f"Status: {state.status}")
    print(f"Current Step: {state.current_step}")
    print(f"Completed: {', '.join(state.completed_steps)}")
    print(f"Last Updated: {state.updated_at}")
```

## Error Handling

On any error during execution:
```python
try:
    execute_step(step)
except Exception as e:
    mcp__claude-flow__memory_store(
        key=state_key,
        value={
            "status": "failed",
            "failed_step": current_step,
            "error": str(e),
            "failed_at": timestamp()
        }
    )
    mcp__claude-flow__session_save(sessionId=f"gsd-pipeline-{project}-error")

    print(f"Pipeline failed at step '{current_step}'")
    print(f"Error: {e}")
    print("Resume with: /gsd:pipeline --resume")
```

## Output

After completion, report:
```
GSD Pipeline Complete!

Project: {project_name}
Phases: {num_phases} completed
Issues: {num_issues} synced to GitHub
Project Board: {project_url}

State saved to claude-flow for future reference.
```
