"""
Validation Framework Test Runner

This project is a planning-only project. The actual code and tests
live in ~/.claude/templates/validation/

This file imports and re-exports those tests for CI compatibility.
"""
import sys
from pathlib import Path

# Add templates/validation to path so imports work
templates_path = Path.home() / ".claude" / "templates" / "validation"
sys.path.insert(0, str(templates_path))

# Import test modules - pytest will discover these
from validators.visual.tests.test_pixel_diff import *
from validators.visual.tests.test_perceptual import *
from validators.visual.tests.test_validator import *
from validators.behavioral.tests.test_dom_diff import *
from validators.behavioral.tests.test_validator import *
from validators.multimodal.tests.test_score_fusion import *
from validators.multimodal.tests.test_validator import *
from validators.confidence_loop.tests.test_termination import *
from validators.confidence_loop.tests.test_loop_controller import *
from validators.confidence_loop.tests.test_terminal_reporter import *
from validators.confidence_loop.tests.test_grafana_reporter import *
from validators.confidence_loop.tests.test_orchestrator_integration import *
