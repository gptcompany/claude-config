# Hybrid Validation Templates

Four-round UAT workflow with confidence scoring and TUI dashboard.

## Philosophy: "Prove Me Wrong"

Even HIGH confidence (80%+) results require human review. Automation assists but never replaces human judgment.

## Templates

### `confidence.py.j2`

Confidence scoring module (0-100 scale).

**Factors:**
- Test pass rate (35% weight)
- Code coverage (25% weight)
- Flaky test penalty (20% weight)
- Known issues penalty (10% weight)
- Historical pass rate (10% weight)

**Classification:**
- HIGH: >= 80 (configurable)
- MEDIUM: 50-79 (configurable)
- LOW: < 50

**Usage:**
```python
from confidence import calculate_confidence

result = calculate_confidence(
    total_tests=100,
    passed_tests=95,
    flaky_tests=2,
    coverage_percent=85.0,
    known_issues=1,
    historical_pass_rate=0.92,
)

print(f"Score: {result.score}%")  # e.g., 82%
print(f"Level: {result.level}")   # ConfidenceLevel.HIGH
print(result.recommendation)
```

### `dashboard.py.j2`

Textual TUI dashboard with three modes.

**Modes:**
1. **Live Monitor** (`1`) - Real-time validation progress with progress bar and log
2. **Review Station** (`2`) - Human UAT interface with review queue
3. **Report Viewer** (`3`) - Historical results browser

**Keybindings:**
- `1/2/3` - Switch modes
- `r` - Refresh
- `p/f/s/n` - Pass/Fail/Skip/Notes (Review Station)
- `q` - Quit

**Usage:**
```bash
python dashboard.py
```

### `verify_work.py.j2`

Four-round UAT orchestrator.

**Workflow:**
1. **Auto Round** - Run all automated validators (pytest, playwright, etc.)
2. **Human-All Round** - Human reviews ALL results regardless of confidence
3. **Fix Round** - Address issues, re-validate failed tests
4. **Edge+Regression Round** - Edge cases and regression tests

**Usage:**
```python
import asyncio
from verify_work import run_verify_work

async def human_handler(test, confidence, message):
    # Display message, get user input
    print(message)
    verdict = input("Enter verdict (p/f/s): ")
    return {"verdict": verdict, "notes": ""}

state = asyncio.run(run_verify_work(
    project_name="MyProject",
    human_input_handler=human_handler,
))

print(f"Final confidence: {state.final_confidence.score}%")
print(f"Approved: {state.approved}")
```

## Jinja2 Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `project_name` | "Project" | Project identifier |
| `confidence_thresholds` | `{high: 80, medium: 50}` | Confidence level boundaries |
| `dashboard_title` | "Validation Dashboard" | TUI header title |
| `validators` | `["pytest", "playwright"]` | Enabled validator types |

## Rendering Templates

```bash
# Using Jinja2 CLI
jinja2 confidence.py.j2 -D project_name=MyApp -o confidence.py

# Or in Python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/validation/hybrid"))
template = env.get_template("verify_work.py.j2")
output = template.render(
    project_name="MyApp",
    confidence_thresholds={"high": 85, "medium": 60},
    validators=["pytest", "playwright", "cypress"],
)
```

## Integration with GSD

Use with `/gsd:verify-work`:

```bash
/gsd:verify-work --hybrid --dashboard
```

This automatically:
1. Renders templates with project config
2. Runs four-round workflow
3. Opens dashboard in Review Station mode
4. Syncs results to `.planning/verify/`

## Dependencies

- Python 3.10+
- textual >= 0.40.0
- jinja2 >= 3.1.0
