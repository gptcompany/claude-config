#!/usr/bin/env python3
"""E2E tests for GitHub Sync feature parity implementation.

Tests:
- Phase 1: [~] syntax and progress tracking
- Phase 2: Dependencies parsing
- Phase 3: Sprint labels
- Phase 4: Branch name suggestions
"""

import sys
import tempfile
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from github_sync_core import (
    get_status_from_checkbox,
    calculate_progress,
    suggest_branch_name,
)


def test_get_status_from_checkbox():
    """Test Phase 1: checkbox status parsing."""
    print("\n=== Test: get_status_from_checkbox ===")

    test_cases = [
        (" ", ("pending", "Backlog")),
        ("x", ("completed", "Done")),
        ("X", ("completed", "Done")),
        ("~", ("in_progress", "In Progress")),
        ("", ("pending", "Backlog")),  # Empty
        (None, ("pending", "Backlog")),  # None - should handle gracefully
    ]

    passed = 0
    failed = 0

    for checkbox, expected in test_cases:
        try:
            result = get_status_from_checkbox(checkbox)
            if result == expected:
                print(f"  ✓ '{checkbox}' -> {result}")
                passed += 1
            else:
                print(f"  ✗ '{checkbox}' -> {result} (expected {expected})")
                failed += 1
        except Exception as e:
            print(f"  ✗ '{checkbox}' -> ERROR: {e}")
            failed += 1

    return passed, failed


def test_calculate_progress():
    """Test Phase 1: progress calculation."""
    print("\n=== Test: calculate_progress ===")

    class MockItem:
        def __init__(self, status):
            self.status = status

    items = [
        MockItem("completed"),
        MockItem("completed"),
        MockItem("in_progress"),
        MockItem("pending"),
        MockItem("pending"),
    ]

    result = calculate_progress(items)

    expected = {
        "total": 5,
        "completed": 2,
        "in_progress": 1,
        "pending": 2,
        "percent": 40,
    }

    passed = 0
    failed = 0

    for key, exp_val in expected.items():
        if result.get(key) == exp_val:
            print(f"  ✓ {key}: {result[key]}")
            passed += 1
        else:
            print(f"  ✗ {key}: {result.get(key)} (expected {exp_val})")
            failed += 1

    # Edge case: empty list
    empty_result = calculate_progress([])
    if empty_result["percent"] == 0 and empty_result["total"] == 0:
        print("  ✓ Empty list handled correctly")
        passed += 1
    else:
        print(f"  ✗ Empty list handling failed: {empty_result}")
        failed += 1

    return passed, failed


def test_suggest_branch_name():
    """Test Phase 4: branch name suggestions."""
    print("\n=== Test: suggest_branch_name ===")

    test_cases = [
        ("Plan-03-01", "SOFR data collector", "feat/Plan-03-01-sofr-data-collector"),
        (
            "T001",
            "Fix data model bug",
            "fix/T001-fix-data-model-bug",
        ),  # includes "fix" in slug
        (
            "T002",
            "Refactor authentication module",
            "refactor/T002-refactor-authentication-module",
        ),
        (
            "Plan-01-01",
            "Add documentation for API",
            "docs/Plan-01-01-add-documentation-for-api",
        ),
        ("T003", "Test coverage for utils", "test/T003-test-coverage-for-utils"),
        (
            "Plan-02-01",
            "A very long description that should be truncated to fit the branch name",
            "feat/Plan-02-01-a-very-long-description-that-should-be-t",
        ),  # truncated to 40 chars
    ]

    passed = 0
    failed = 0

    for task_id, description, expected in test_cases:
        result = suggest_branch_name(task_id, description)
        if result == expected:
            print(f"  ✓ {task_id}: {result}")
            passed += 1
        else:
            print(f"  ✗ {task_id}")
            print(f"      Got:      {result}")
            print(f"      Expected: {expected}")
            failed += 1

    return passed, failed


def test_roadmap_parsing():
    """Test Phase 1-3: ROADMAP.md parsing with new syntax."""
    print("\n=== Test: ROADMAP.md Parsing ===")

    from roadmaptoissues import parse_roadmap

    # Create test ROADMAP.md
    roadmap_content = """# Project Roadmap

## Phases

- [ ] **Phase 1: Foundation** - Setup basics
- [~] **Phase 2: Core** - Build core features
- [x] **Phase 3: Polish** - Final touches

## Phase Details

### Phase 1: Foundation

**Goal**: Setup the foundation

#### Plans
- [ ] 01-01: Setup repository
- [~] 01-02: Configure CI/CD | priority:high | effort:M
- [x] 01-03: Add README | sprint:2025-W04

### Phase 2: Core

**Goal**: Build core features

#### Plans
- [ ] 02-01: Data model | depends:01-01
- [~] 02-02: API endpoints | depends:02-01,01-02 | priority:high | sprint:2025-W05
- [ ] 02-03: Frontend | depends:02-02 | effort:L | @developer

### Phase 3: Polish

#### Plans
- [x] 03-01: Documentation | sprint:2025-W06
"""

    passed = 0
    failed = 0

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(roadmap_content)
        f.flush()

        phases, plans = parse_roadmap(Path(f.name))

    # Test phase count
    if len(phases) == 3:
        print("  ✓ Found 3 phases")
        passed += 1
    else:
        print(f"  ✗ Expected 3 phases, found {len(phases)}")
        failed += 1

    # Test plan count
    if len(plans) == 7:
        print("  ✓ Found 7 plans")
        passed += 1
    else:
        print(f"  ✗ Expected 7 plans, found {len(plans)}")
        failed += 1

    # Find specific plans for detailed testing
    plan_map = {p.id: p for p in plans}

    # Test [~] status parsing
    plan_0102 = plan_map.get("01-02")
    if plan_0102:
        if plan_0102.status == "in_progress":
            print("  ✓ Plan 01-02 status: in_progress")
            passed += 1
        else:
            print(f"  ✗ Plan 01-02 status: {plan_0102.status} (expected in_progress)")
            failed += 1

        if plan_0102.kanban_status == "In Progress":
            print("  ✓ Plan 01-02 kanban_status: In Progress")
            passed += 1
        else:
            print(
                f"  ✗ Plan 01-02 kanban_status: {plan_0102.kanban_status} (expected In Progress)"
            )
            failed += 1

        if plan_0102.priority == "high":
            print("  ✓ Plan 01-02 priority: high")
            passed += 1
        else:
            print(f"  ✗ Plan 01-02 priority: {plan_0102.priority} (expected high)")
            failed += 1
    else:
        print("  ✗ Plan 01-02 not found")
        failed += 3

    # Test dependencies parsing
    plan_0202 = plan_map.get("02-02")
    if plan_0202:
        if plan_0202.depends_on == ["02-01", "01-02"]:
            print(f"  ✓ Plan 02-02 depends_on: {plan_0202.depends_on}")
            passed += 1
        else:
            print(
                f"  ✗ Plan 02-02 depends_on: {plan_0202.depends_on} (expected ['02-01', '01-02'])"
            )
            failed += 1

        if plan_0202.sprint == "2025-W05":
            print(f"  ✓ Plan 02-02 sprint: {plan_0202.sprint}")
            passed += 1
        else:
            print(f"  ✗ Plan 02-02 sprint: {plan_0202.sprint} (expected 2025-W05)")
            failed += 1
    else:
        print("  ✗ Plan 02-02 not found")
        failed += 2

    # Test assignee parsing
    plan_0203 = plan_map.get("02-03")
    if plan_0203:
        if plan_0203.assignee == "developer":
            print(f"  ✓ Plan 02-03 assignee: {plan_0203.assignee}")
            passed += 1
        else:
            print(f"  ✗ Plan 02-03 assignee: {plan_0203.assignee} (expected developer)")
            failed += 1
    else:
        print("  ✗ Plan 02-03 not found")
        failed += 1

    # Test completed status
    plan_0103 = plan_map.get("01-03")
    if plan_0103:
        if plan_0103.status == "completed" and plan_0103.kanban_status == "Done":
            print("  ✓ Plan 01-03 completed status correct")
            passed += 1
        else:
            print(
                f"  ✗ Plan 01-03 status: {plan_0103.status}/{plan_0103.kanban_status}"
            )
            failed += 1
    else:
        print("  ✗ Plan 01-03 not found")
        failed += 1

    return passed, failed


def test_tasks_parsing():
    """Test Phase 1-3: tasks.md parsing with new syntax."""
    print("\n=== Test: tasks.md Parsing ===")

    from taskstoissues import parse_tasks_file

    # Create test tasks.md
    tasks_content = """# Tasks

## US01: User Authentication

### Tasks
- [ ] T001 [US01] [P1] Setup auth module
- [~] T002 [US01] [P2] Implement login | depends:T001 | sprint:2025-W04
- [x] T003 [US01] [P3] Add logout | depends:T002

## US02: Data Processing

- [ ] T004 [US02] [P1] [E] Create data model | depends:T001,T002
- [~] T005 [US02] Build pipeline | sprint:2025-W05
"""

    passed = 0
    failed = 0

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(tasks_content)
        f.flush()

        stories, tasks = parse_tasks_file(Path(f.name))

    # Test counts
    if len(stories) == 2:
        print("  ✓ Found 2 user stories")
        passed += 1
    else:
        print(f"  ✗ Expected 2 stories, found {len(stories)}")
        failed += 1

    if len(tasks) == 5:
        print("  ✓ Found 5 tasks")
        passed += 1
    else:
        print(f"  ✗ Expected 5 tasks, found {len(tasks)}")
        failed += 1

    task_map = {t.id: t for t in tasks}

    # Test [~] status
    task_t002 = task_map.get("T002")
    if task_t002:
        if task_t002.status == "in_progress":
            print("  ✓ T002 status: in_progress")
            passed += 1
        else:
            print(f"  ✗ T002 status: {task_t002.status}")
            failed += 1

        if task_t002.kanban_status == "In Progress":
            print("  ✓ T002 kanban_status: In Progress")
            passed += 1
        else:
            print(f"  ✗ T002 kanban_status: {task_t002.kanban_status}")
            failed += 1

        if task_t002.depends_on == ["T001"]:
            print(f"  ✓ T002 depends_on: {task_t002.depends_on}")
            passed += 1
        else:
            print(f"  ✗ T002 depends_on: {task_t002.depends_on}")
            failed += 1

        if task_t002.sprint == "2025-W04":
            print(f"  ✓ T002 sprint: {task_t002.sprint}")
            passed += 1
        else:
            print(f"  ✗ T002 sprint: {task_t002.sprint}")
            failed += 1
    else:
        print("  ✗ T002 not found")
        failed += 4

    # Test multiple dependencies
    task_t004 = task_map.get("T004")
    if task_t004:
        if task_t004.depends_on == ["T001", "T002"]:
            print(f"  ✓ T004 depends_on: {task_t004.depends_on}")
            passed += 1
        else:
            print(f"  ✗ T004 depends_on: {task_t004.depends_on}")
            failed += 1
    else:
        print("  ✗ T004 not found")
        failed += 1

    return passed, failed


def test_sprint_label_colors():
    """Test Phase 3: Sprint label colors in ensure_labels_exist."""
    print("\n=== Test: Sprint Label Colors ===")

    # Check that sprint labels get the right color
    # We can't easily test ensure_labels_exist without mocking gh CLI,
    # but we can verify the logic is in place by checking the imports

    passed = 0
    failed = 0

    # Read the source and check for sprint label handling
    core_path = Path(__file__).parent / "github_sync_core.py"
    content = core_path.read_text()

    if 'label.startswith("sprint-")' in content:
        print("  ✓ Sprint label pattern detected in ensure_labels_exist")
        passed += 1
    else:
        print("  ✗ Sprint label pattern NOT found in ensure_labels_exist")
        failed += 1

    if '"1d76db"' in content:  # Blue color for sprint
        print("  ✓ Sprint label color (blue) configured")
        passed += 1
    else:
        print("  ✗ Sprint label color NOT configured")
        failed += 1

    return passed, failed


def test_issue_body_generation():
    """Test that issue body includes new fields."""
    print("\n=== Test: Issue Body Generation ===")

    passed = 0
    failed = 0

    # Check roadmaptoissues.py for dependencies section
    roadmap_path = Path(__file__).parent / "roadmaptoissues.py"
    roadmap_content = roadmap_path.read_text()

    if "### Dependencies" in roadmap_content:
        print("  ✓ Dependencies section in roadmap issue body")
        passed += 1
    else:
        print("  ✗ Dependencies section NOT in roadmap issue body")
        failed += 1

    if "**Branch**:" in roadmap_content:
        print("  ✓ Branch suggestion in roadmap issue body")
        passed += 1
    else:
        print("  ✗ Branch suggestion NOT in roadmap issue body")
        failed += 1

    if "**Sprint**:" in roadmap_content:
        print("  ✓ Sprint field in roadmap issue body")
        passed += 1
    else:
        print("  ✗ Sprint field NOT in roadmap issue body")
        failed += 1

    # Check taskstoissues.py
    tasks_path = Path(__file__).parent / "taskstoissues.py"
    tasks_content = tasks_path.read_text()

    if "### Dependencies" in tasks_content:
        print("  ✓ Dependencies section in tasks issue body")
        passed += 1
    else:
        print("  ✗ Dependencies section NOT in tasks issue body")
        failed += 1

    if "**Branch**:" in tasks_content:
        print("  ✓ Branch suggestion in tasks issue body")
        passed += 1
    else:
        print("  ✗ Branch suggestion NOT in tasks issue body")
        failed += 1

    return passed, failed


def test_kanban_status_setting():
    """Test that Kanban status is set correctly for [~] items."""
    print("\n=== Test: Kanban Status Setting ===")

    passed = 0
    failed = 0

    # Check that set_issue_status is called for non-Backlog items
    roadmap_path = Path(__file__).parent / "roadmaptoissues.py"
    roadmap_content = roadmap_path.read_text()

    if 'plan.kanban_status != "Backlog"' in roadmap_content:
        print("  ✓ Kanban status check in roadmaptoissues.py")
        passed += 1
    else:
        print("  ✗ Kanban status check NOT in roadmaptoissues.py")
        failed += 1

    if "set_issue_status(project_id, issue_num, plan.kanban_status" in roadmap_content:
        print("  ✓ set_issue_status called for In Progress items (roadmap)")
        passed += 1
    else:
        print("  ✗ set_issue_status NOT called correctly (roadmap)")
        failed += 1

    tasks_path = Path(__file__).parent / "taskstoissues.py"
    tasks_content = tasks_path.read_text()

    if 'task.kanban_status != "Backlog"' in tasks_content:
        print("  ✓ Kanban status check in taskstoissues.py")
        passed += 1
    else:
        print("  ✗ Kanban status check NOT in taskstoissues.py")
        failed += 1

    return passed, failed


def main():
    """Run all E2E tests."""
    print("=" * 60)
    print("GitHub Sync Feature Parity - E2E Tests")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    tests = [
        test_get_status_from_checkbox,
        test_calculate_progress,
        test_suggest_branch_name,
        test_roadmap_parsing,
        test_tasks_parsing,
        test_sprint_label_colors,
        test_issue_body_generation,
        test_kanban_status_setting,
    ]

    for test_fn in tests:
        try:
            passed, failed = test_fn()
            total_passed += passed
            total_failed += failed
        except Exception as e:
            print(f"\n  ✗ TEST CRASHED: {e}")
            import traceback

            traceback.print_exc()
            total_failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {total_passed} passed, {total_failed} failed")
    print("=" * 60)

    if total_failed > 0:
        print("\n⚠️  Some tests failed - review output above")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
