---
name: swarm
description: Swarm intelligence for parallel task execution. Initialize hive-mind, spawn workers, and coordinate multi-agent work.
---

# Swarm Command

Control claude-flow hive-mind swarm for parallel task execution.

## Commands

### `/swarm init [topology]`

Initialize a new swarm with specified topology.

**Arguments:**
- `topology` (optional): hierarchical-mesh (default), mesh, star, ring

**Example:**
```
/swarm init
/swarm init hierarchical-mesh
```

**Action:**
```bash
python3 /media/sam/1TB/claude-hooks-shared/hooks/swarm/hive_manager.py --action init --topology {topology}
```

Output: "Swarm initialized" + hive_id if available

---

### `/swarm status`

Show current swarm status.

**Example:**
```
/swarm status
```

**Action:**
```bash
python3 /media/sam/1TB/claude-hooks-shared/hooks/swarm/hive_manager.py --action status
```

Output: Brief status (workers, tasks, health)

---

### `/swarm spawn [count]`

Spawn workers into the swarm.

**Arguments:**
- `count` (optional): Number of workers (default: 3)

**Example:**
```
/swarm spawn
/swarm spawn 5
```

**Action:**
```bash
python3 /media/sam/1TB/claude-hooks-shared/hooks/swarm/hive_manager.py --action spawn --count {count}
```

Output: "Spawned N workers"

---

### `/swarm task "description"`

Submit a task to the swarm for parallel execution.

**Arguments:**
- `description` (required): Task description

**Example:**
```
/swarm task "Implement user authentication"
```

**Action:**
```bash
python3 /media/sam/1TB/claude-hooks-shared/hooks/swarm/hive_manager.py --action task --description "{description}"
```

Output: Task ID and status

---

### `/swarm shutdown`

Gracefully shutdown the swarm.

**Example:**
```
/swarm shutdown
```

**Action:**
```bash
python3 /media/sam/1TB/claude-hooks-shared/hooks/swarm/hive_manager.py --action shutdown
```

Output: "Swarm shutdown complete"

---

## Execution Instructions

When the user invokes `/swarm {subcommand} [args]`:

1. Parse the subcommand (init, status, spawn, task, shutdown)
2. Execute the corresponding hive_manager.py command
3. Parse JSON output and show MINIMAL confirmation:
   - Success: Brief confirmation message
   - Error: Show error message

**KISS Principle**: Keep output minimal. User wants to see "it worked" and get back to work.

## Example Flow

```
User: /swarm init
Agent: Swarm initialized with hierarchical-mesh topology (hive-1234)

User: /swarm spawn 3
Agent: Spawned 3 workers

User: /swarm status
Agent: Swarm active: 3 workers, 0 queued tasks

User: /swarm shutdown
Agent: Swarm shutdown complete
```
