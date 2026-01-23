"""
Confidence Loop - Progressive refinement with confidence-based termination.

Implements Self-Refine pattern with three-stage refinement:
1. LAYOUT - Get structure right
2. STYLE - Get appearance right
3. POLISH - Fine-tune details

Components:
- ProgressiveRefinementLoop: Core loop controller
- TerminationEvaluator: Dynamic termination logic
- TerminalReporter: Human-readable terminal output
- GrafanaReporter: Metrics push to Grafana
- ConfidenceLoopOrchestrator: Integration with ValidationOrchestrator
"""

from .grafana_reporter import GrafanaReporter
from .loop_controller import LoopState, ProgressiveRefinementLoop, RefinementStage
from .orchestrator_integration import ConfidenceLoopOrchestrator
from .terminal_reporter import TerminalReporter
from .termination import TerminationEvaluator, TerminationResult

__all__ = [
    # Loop controller
    "ProgressiveRefinementLoop",
    "LoopState",
    "RefinementStage",
    # Termination
    "TerminationEvaluator",
    "TerminationResult",
    # Reporters
    "TerminalReporter",
    "GrafanaReporter",
    # Integration
    "ConfidenceLoopOrchestrator",
]
