#!/usr/bin/env python3
"""
Confidence Gate - Multi-Model Verification via Gemini CLI

Verifica automatica degli output con Gemini CLI (Google AI Pro subscription):
1. Gemini 3 Flash (primario, 300/day)
2. Gemini 2.5 Pro (cross-verify, stabile)
3. Gemini 2.5 Flash (fallback)

Elimina le domande "il piano va bene?" quando confidence alta.
Usa subscription OAuth, zero API key management.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict
import time


class GateDecision(Enum):
    AUTO_APPROVE = "auto_approve"
    CROSS_VERIFY = "cross_verify"
    HUMAN_REVIEW = "human_review"


@dataclass
class VerificationResult:
    approved: bool
    confidence: int
    issues: List[str]
    provider: str
    model: str
    latency_ms: int


@dataclass
class GateResult:
    decision: GateDecision
    confidence_score: int
    verifications: List[VerificationResult]
    should_iterate: bool
    iteration_feedback: Optional[str]
    final_approved: bool


class MultiModelVerifier:
    """
    Verifica output con Gemini CLI (subscription OAuth).
    Non usa Anthropic per evitare "giudicare se stesso".
    """

    DEFAULT_PROMPT = """Sei un reviewer tecnico. Valuta questo output di un agente AI.

CRITERI DI VALUTAZIONE:
1. Completezza: tutti i requisiti sono coperti?
2. Correttezza: la logica è corretta?
3. Qualità: il codice/piano è ben strutturato?
4. Rischi: ci sono problemi di sicurezza o edge cases non gestiti?

Rispondi SOLO con JSON valido (nessun altro testo):
{{
  "approved": true/false,
  "confidence": 0-100,
  "issues": ["issue1", "issue2"],
  "strengths": ["strength1"],
  "recommendation": "proceed/iterate/reject"
}}

OUTPUT DA VALUTARE:
---
{output}
---"""

    STEP_PROMPTS = {
        "plan": """Sei un reviewer tecnico di piani di implementazione.

Valuta questo piano generato da un agente AI, verificando:
1. Completezza: tutti i requisiti sono coperti? Ci sono gap evidenti?
2. Fattibilità: gli step sono realistici e ben ordinati?
3. Rischi: ci sono dipendenze non gestite o rischi architetturali?
4. Qualità: il piano è chiaro, specifico, e actionable (non vago)?

Rispondi SOLO con JSON valido (nessun altro testo):
{{
  "approved": true/false,
  "confidence": 0-100,
  "issues": ["issue1", "issue2"],
  "strengths": ["strength1"],
  "recommendation": "proceed/iterate/reject"
}}

PIANO DA VALUTARE:
---
{output}
---""",
        "implement": """Sei un code reviewer esperto.

Valuta questo codice/implementazione generato da un agente AI:
1. Correttezza: la logica è corretta? Ci sono bug evidenti?
2. Sicurezza: ci sono vulnerabilità (injection, path traversal, etc)?
3. Qualità: il codice segue best practices, è testabile, manutenibile?
4. Completezza: l'implementazione copre tutti i requisiti?

Rispondi SOLO con JSON valido (nessun altro testo):
{{
  "approved": true/false,
  "confidence": 0-100,
  "issues": ["issue1", "issue2"],
  "strengths": ["strength1"],
  "recommendation": "proceed/iterate/reject"
}}

CODICE DA VALUTARE:
---
{output}
---""",
        "verify": """Sei un QA engineer. Valuta i risultati di verifica di un agente AI.

Controlla:
1. Test coverage: i test coprono i casi critici?
2. Risultati: tutti i test passano? Ci sono flaky tests?
3. Edge cases: sono stati considerati i casi limite?
4. Regressioni: ci sono rischi di regressione?

Rispondi SOLO con JSON valido (nessun altro testo):
{{
  "approved": true/false,
  "confidence": 0-100,
  "issues": ["issue1", "issue2"],
  "strengths": ["strength1"],
  "recommendation": "proceed/iterate/reject"
}}

RISULTATI DI VERIFICA:
---
{output}
---""",
        "security-review": """Sei un security auditor. Valuta questo codice/output per vulnerabilità.

Controlla:
1. Injection: SQL, command, path traversal, XSS
2. Auth: autenticazione/autorizzazione corretta?
3. Secrets: credenziali o dati sensibili esposti?
4. OWASP Top 10: altre vulnerabilità comuni?

Rispondi SOLO con JSON valido (nessun altro testo):
{{
  "approved": true/false,
  "confidence": 0-100,
  "issues": ["issue1", "issue2"],
  "strengths": ["strength1"],
  "recommendation": "proceed/iterate/reject"
}}

CODICE DA VALUTARE:
---
{output}
---""",
        "test": """Sei un QA engineer. Valuta questo output di test.

Controlla:
1. Tutti i test passano? Ci sono fallimenti?
2. Coverage: i test coprono i casi importanti?
3. Qualità: i test sono significativi o superficiali?
4. Edge cases: mancano test per casi limite critici?

Rispondi SOLO con JSON valido (nessun altro testo):
{{
  "approved": true/false,
  "confidence": 0-100,
  "issues": ["issue1", "issue2"],
  "strengths": ["strength1"],
  "recommendation": "proceed/iterate/reject"
}}

OUTPUT TEST:
---
{output}
---""",
    }

    @property
    def VERIFICATION_PROMPT(self):
        """Backward compatibility."""
        return self.DEFAULT_PROMPT

    CONFIG_PATH = os.path.expanduser("~/.claude/config/confidence_gate.json")
    DEFAULT_MAX_INPUT_CHARS = 500000

    def __init__(self):
        self.config = self._load_config()
        self.max_input_chars = self.config.get(
            "max_input_chars", self.DEFAULT_MAX_INPUT_CHARS
        )
        self._custom_prompt = self.config.get("verification_prompt")
        self._custom_step_prompts = self.config.get("step_prompts", {})

    def _get_prompt(self, output: str, step_name: str = "unknown") -> str:
        """Build the formatted prompt for a given step and output."""
        template = self.get_prompt_for_step(step_name)
        return template.format(output=output[:self.max_input_chars])

    def _get_prompt_parts(self, output: str, step_name: str = "unknown") -> tuple:
        """Split prompt into (content_for_stdin, instruction_for_p_flag).

        Gemini CLI appends -p AFTER stdin, so:
        - stdin = the content to evaluate (comes first)
        - -p = the review instruction (appended after)

        This triggers headless mode and avoids directory scanning.
        """
        template = self.get_prompt_for_step(step_name)
        content = output[:self.max_input_chars]
        # Replace {output} with placeholder reference in the instruction
        instruction = template.replace(
            "{output}", "<<vedi il testo fornito sopra>>"
        )
        # Templates use {{ }} for literal braces (Python .format() escaping).
        # Since we use .replace() instead of .format(), unescape them.
        instruction = instruction.replace("{{", "{").replace("}}", "}")
        return content, instruction

    CALIBRATION_PREFIX = """CALIBRAZIONE SCORE:
- 95-100: Eccezionale, zero difetti trovati, test completi, edge cases gestiti
- 80-94: Buono, problemi minori trovati, potrebbe migliorare
- 60-79: Mediocre, problemi significativi che richiedono iterazione
- 40-59: Scarso, problemi critici, necessita riscrittura parziale
- 0-39: Inaccettabile, problemi fondamentali

REGOLE:
- DEVI trovare almeno 2 issues (nessun codice è perfetto)
- Score > 90 SOLO se non trovi difetti significativi
- Valuta con lo standard di un senior engineer in code review

"""

    def get_prompt_for_step(self, step_name: str) -> str:
        """Get the best prompt template for a given step, with calibration prefix."""
        step_lower = step_name.lower()
        if step_lower in self._custom_step_prompts:
            template = self._custom_step_prompts[step_lower]
        elif self._custom_prompt:
            template = self._custom_prompt
        elif step_lower in self.STEP_PROMPTS:
            template = self.STEP_PROMPTS[step_lower]
        else:
            template = self.DEFAULT_PROMPT
        return self.CALIBRATION_PREFIX + template

    def _load_config(self) -> Dict:
        """Carica configurazione da file JSON."""
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH) as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Config load failed ({e}), using defaults", file=sys.stderr)
        return {}

    def verify_with_gemini_cli(
        self, output: str, timeout: int = 0, step_name: str = "unknown",
        model: str = "", include_dirs: Optional[List[str]] = None
    ) -> Optional[VerificationResult]:
        """Verifica usando Gemini CLI con OAuth subscription.

        Modelli disponibili (Google AI Pro):
        - gemini-3-flash-preview: Thinking, 300/day
        - gemini-2.5-pro: Pro, 100/day
        - gemini-2.5-flash: Fallback stabile

        Timeout scala con input: 120s base + 1s per 1000 chars, max 300s.
        """
        import shutil

        if not timeout:
            # Gemini 3 preview models need 60-90s for thinking mode.
            # --include-directories adds ~60s for directory scanning.
            base = 180 if include_dirs else 120
            timeout = min(300, base + len(output) // 1000)

        gemini_bin = shutil.which("gemini")
        if not gemini_bin:
            print("[WARN] Gemini CLI not found in PATH", file=sys.stderr)
            return None

        if not model:
            cli_models = self.config.get("gemini_cli_models", {})
            model = cli_models.get("primary", "gemini-3-flash-preview")

        start_time = time.time()

        # When include_dirs is set, Gemini browses files natively via
        # --include-directories.  The -p prompt carries only the review
        # instruction (+ any extra textual context the caller provided).
        if include_dirs:
            template = self.get_prompt_for_step(step_name)
            if output.strip():
                instruction = template.replace(
                    "{output}",
                    "<<Esamina i file nelle directory incluse nel workspace. "
                    "Contesto aggiuntivo:>>\n" + output[:self.max_input_chars],
                )
            else:
                instruction = template.replace(
                    "{output}",
                    "<<Esamina i file nelle directory incluse nel workspace.>>",
                )
            instruction = instruction.replace("{{", "{").replace("}}", "}")
            cmd = [gemini_bin, "-m", model, "-p", instruction]
            for d in include_dirs:
                cmd.extend(["--include-directories", d])
            stdin_data = None
        else:
            prompt = self._get_prompt(output, step_name)

            # -p triggers headless mode (avoids interactive directory scanning).
            # For prompts < 1MB, pass everything via -p (most reliable).
            # For very large prompts, split: stdin=content, -p=instruction.
            if len(prompt) < 1_000_000:
                cmd = [gemini_bin, "-m", model, "-p", prompt]
                stdin_data = None
            else:
                content, instruction = self._get_prompt_parts(output, step_name)
                cmd = [gemini_bin, "-m", model, "-p", instruction]
                stdin_data = content

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=stdin_data,
                env={**os.environ, "NO_COLOR": "1"},
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                stderr_lines = [line for line in stderr.split("\n")
                                if not line.startswith("[dotenvx") and not line.startswith("Hook registry")]
                stderr_clean = "\n".join(stderr_lines).strip()
                if stderr_clean:
                    print(f"[WARN] Gemini CLI {model} failed (exit {result.returncode}): {stderr_clean[:200]}", file=sys.stderr)
                return None

            latency = int((time.time() - start_time) * 1000)
            content_lines = [line for line in result.stdout.split("\n")
                             if not line.startswith("[dotenvx") and not line.startswith("Hook registry")
                             and not line.startswith("Loaded cached")]
            content = "\n".join(content_lines).strip()

            # Extract JSON - try last complete JSON object first
            json_end = content.rfind("}") + 1
            if json_end > 0:
                depth = 0
                json_start = -1
                for i in range(json_end - 1, -1, -1):
                    if content[i] == "}":
                        depth += 1
                    elif content[i] == "{":
                        depth -= 1
                        if depth == 0:
                            json_start = i
                            break

                if json_start >= 0:
                    try:
                        parsed = json.loads(content[json_start:json_end])
                        if "approved" in parsed or "confidence" in parsed:
                            return VerificationResult(
                                approved=parsed.get("approved", False),
                                confidence=parsed.get("confidence", 0),
                                issues=parsed.get("issues", []),
                                provider="gemini_cli",
                                model=model,
                                latency_ms=latency,
                            )
                    except json.JSONDecodeError:
                        pass

            # Fallback: first { to last }
            json_start = content.find("{")
            if json_start >= 0 and json_end > json_start:
                try:
                    parsed = json.loads(content[json_start:json_end])
                    return VerificationResult(
                        approved=parsed.get("approved", False),
                        confidence=parsed.get("confidence", 0),
                        issues=parsed.get("issues", []),
                        provider="gemini_cli",
                        model=model,
                        latency_ms=latency,
                    )
                except json.JSONDecodeError:
                    print(f"[WARN] Gemini CLI {model}: could not parse JSON from response", file=sys.stderr)

        except subprocess.TimeoutExpired:
            print(f"[WARN] Gemini CLI {model} timeout after {timeout}s", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] Gemini CLI {model} failed: {e}", file=sys.stderr)

        return None

    def verify_chain(
        self, output: str, step_name: str = "unknown",
        include_dirs: Optional[List[str]] = None,
    ) -> List[VerificationResult]:
        """
        Catena di verifica via Gemini CLI (subscription OAuth):
        1. Flash (primario) - SEMPRE
        2. Pro (cross-verify) - SEMPRE
        3. 2.5 Flash (fallback solo se entrambi falliscono)
        """
        cli_models = self.config.get("gemini_cli_models", {})
        primary = cli_models.get("primary", "gemini-3-flash-preview")
        cross = cli_models.get("cross_verify", "gemini-2.5-pro")
        fallback = cli_models.get("fallback", "gemini-2.5-flash")

        results = []

        # 1. Primary: Flash (always)
        flash_result = self.verify_with_gemini_cli(
            output, step_name=step_name, model=primary, include_dirs=include_dirs)
        if flash_result:
            results.append(flash_result)

        # 2. Cross-verify: Pro (always)
        pro_result = self.verify_with_gemini_cli(
            output, step_name=step_name, model=cross, include_dirs=include_dirs)
        if pro_result:
            results.append(pro_result)

        # 3. Fallback: 2.5 Flash (only if both failed)
        if not results:
            fb_result = self.verify_with_gemini_cli(
                output, step_name=step_name, model=fallback, include_dirs=include_dirs)
            if fb_result:
                results.append(fb_result)

        return results


class ConfidenceGate:
    """
    Gate automatico basato su confidence score ESTERNO (anti-bias).

    Flusso ANTI-BIAS (confidence calcolata da Gemini CLI, NON da Claude):
    1. Gemini Flash valuta → salva risultato
    2. Gemini Pro valuta SEMPRE → salva risultato
    3. Media pesata: avg = Flash*0.4 + Pro*0.6
    4. AUTO_APPROVE solo se avg >= 95 E entrambi approved
    5. CROSS_VERIFY se avg >= 75
    6. HUMAN_REVIEW se avg < 75
    """

    DEFAULT_THRESHOLDS = {
        "auto_approve": 85,
        "cross_verify": 60,
    }

    def __init__(self):
        self.verifier = MultiModelVerifier()
        config = self.verifier.config
        self.THRESHOLDS = {
            **self.DEFAULT_THRESHOLDS,
            **config.get("thresholds", {}),
        }

    def evaluate(
        self,
        step_output: str,
        internal_confidence: int = 0,
        step_name: str = "unknown",
        include_dirs: Optional[List[str]] = None,
    ) -> GateResult:
        """
        Valuta output usando Gemini CLI (anti-bias, subscription OAuth).

        Args:
            step_output: Output dello step da valutare
            internal_confidence: IGNORATO - confidence calcolata da Gemini
            step_name: Nome dello step per logging
            include_dirs: Directory da includere nel workspace Gemini
        """
        if include_dirs:
            print(f"[GATE] {step_name}: Calculating confidence via Gemini CLI (anti-bias, dirs: {len(include_dirs)})...")
        else:
            print(f"[GATE] {step_name}: Calculating confidence via Gemini CLI (anti-bias)...")

        cli_models = self.verifier.config.get("gemini_cli_models", {})
        primary = cli_models.get("primary", "gemini-3-flash-preview")
        cross = cli_models.get("cross_verify", "gemini-2.5-pro")

        fallback_model = cli_models.get("fallback", "gemini-2.5-flash")
        verifications: List[VerificationResult] = []

        # Step 1: Primary verification (Flash)
        flash_result = self.verifier.verify_with_gemini_cli(
            step_output, step_name=step_name, model=primary, include_dirs=include_dirs
        )

        if flash_result:
            verifications.append(flash_result)
            print(f"  [{primary}] confidence: {flash_result.confidence}, approved: {flash_result.approved}")
            if flash_result.issues:
                print(f"    Issues: {', '.join(flash_result.issues[:3])}")
        else:
            print(f"  [{primary}] FAILED")

        # Step 2: ALWAYS cross-verify with Pro (anti single-model bias)
        print(f"[GATE] {step_name}: Cross-verifying with {cross}...")
        pro_result = self.verifier.verify_with_gemini_cli(
            step_output, step_name=step_name, model=cross, include_dirs=include_dirs
        )

        if pro_result:
            verifications.append(pro_result)
            print(f"  [{cross}] confidence: {pro_result.confidence}, approved: {pro_result.approved}")
            if pro_result.issues:
                print(f"    Issues: {', '.join(pro_result.issues[:3])}")
        else:
            print(f"  [{cross}] FAILED")

        # Step 3: If both failed, try fallback
        if not verifications:
            print(f"[GATE] {step_name}: Both models failed, trying {fallback_model}...")
            fb_result = self.verifier.verify_with_gemini_cli(
                step_output, step_name=step_name, model=fallback_model, include_dirs=include_dirs
            )
            if fb_result:
                verifications.append(fb_result)
            else:
                print(f"[GATE] {step_name}: All Gemini models failed - HUMAN_REVIEW required")
                print("[GATE] Check: Gemini CLI installed, OAuth configured, network")
                return GateResult(
                    decision=GateDecision.HUMAN_REVIEW,
                    confidence_score=0,
                    verifications=[],
                    should_iterate=False,
                    iteration_feedback="All Gemini CLI models failed. Check: gemini CLI, OAuth, network.",
                    final_approved=False,
                )

        # Step 4: Decision based on weighted average of all results
        if len(verifications) == 2 and flash_result and pro_result:
            # Both Flash and Pro succeeded: weighted average (Pro weighs more)
            avg_conf = int(flash_result.confidence * 0.4 + pro_result.confidence * 0.6)
            both_approved = flash_result.approved and pro_result.approved
        elif len(verifications) == 1:
            # Only one model succeeded (the other failed)
            avg_conf = verifications[0].confidence
            both_approved = verifications[0].approved
        else:
            # Fallback-only case
            avg_conf = verifications[0].confidence
            both_approved = verifications[0].approved

        # Collect all issues
        all_issues: List[str] = []
        for v in verifications:
            all_issues.extend(v.issues)

        # AUTO_APPROVE: high avg confidence AND all models approved
        if avg_conf >= self.THRESHOLDS["auto_approve"] and both_approved:
            print(f"[GATE] {step_name}: AUTO_APPROVE (avg confidence: {avg_conf}, models: {len(verifications)})")
            return GateResult(
                decision=GateDecision.AUTO_APPROVE,
                confidence_score=avg_conf,
                verifications=verifications,
                should_iterate=False,
                iteration_feedback=None,
                final_approved=True,
            )

        # CROSS_VERIFY / ITERATE: medium confidence with issues
        if avg_conf >= self.THRESHOLDS["cross_verify"]:
            if all_issues:
                feedback = "\n".join(f"- {issue}" for issue in all_issues[:5])
                print(f"[GATE] {step_name}: ITERATE suggested (avg confidence: {avg_conf})")
                return GateResult(
                    decision=GateDecision.CROSS_VERIFY,
                    confidence_score=avg_conf,
                    verifications=verifications,
                    should_iterate=True,
                    iteration_feedback=feedback,
                    final_approved=False,
                )
            # Medium confidence, no issues but not high enough for auto_approve
            print(f"[GATE] {step_name}: CROSS_VERIFY (avg confidence: {avg_conf}, below auto_approve threshold)")
            return GateResult(
                decision=GateDecision.CROSS_VERIFY,
                confidence_score=avg_conf,
                verifications=verifications,
                should_iterate=False,
                iteration_feedback=None,
                final_approved=False,
            )

        # LOW confidence
        feedback = None
        if all_issues:
            feedback = "\n".join(f"- {issue}" for issue in all_issues[:5])
        print(f"[GATE] {step_name}: HUMAN_REVIEW (avg confidence: {avg_conf})")
        return GateResult(
            decision=GateDecision.HUMAN_REVIEW,
            confidence_score=avg_conf,
            verifications=verifications,
            should_iterate=bool(all_issues),
            iteration_feedback=feedback,
            final_approved=False,
        )


def detect_evolve_marker(text: str) -> bool:
    """Detect [E] or evolve marker in task/plan text."""
    import re
    patterns = [
        r'\[E\]',
        r'\[evolve\]',
        r'label.*evolve',
        r'iterative',
        r'convergence',
    ]
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def evolve_loop(
    gate: "ConfidenceGate",
    initial_output: str,
    initial_confidence: int,
    step_name: str,
    max_iterations: int = 3,
    iteration_callback=None,
    include_dirs: Optional[List[str]] = None,
) -> GateResult:
    """Evolution loop: iterate until convergence or max iterations."""
    current_output = initial_output
    current_confidence = initial_confidence

    for i in range(max_iterations):
        iteration_name = f"{step_name}-v{i+1}" if i > 0 else step_name
        result = gate.evaluate(current_output, current_confidence, iteration_name, include_dirs=include_dirs)

        print(f"[EVOLVE] Iteration {i+1}/{max_iterations}: {result.decision.value} (confidence: {result.confidence_score})")

        if result.final_approved:
            print(f"[EVOLVE] Converged at iteration {i+1}")
            return result

        if not result.should_iterate:
            print(f"[EVOLVE] Human review required at iteration {i+1}")
            return result

        if iteration_callback and result.iteration_feedback:
            print(f"[EVOLVE] Applying feedback: {result.iteration_feedback[:100]}...")
            current_output = iteration_callback(current_output, result.iteration_feedback)
        else:
            print("[EVOLVE] No iteration callback, stopping")
            return result

    print(f"[EVOLVE] Max iterations ({max_iterations}) reached without convergence")
    return result  # type: ignore[possibly-undefined]


def main():
    """CLI per testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Confidence Gate (Gemini CLI)")
    parser.add_argument("--output", "--input", "-o", "-i", help="Output to verify (or stdin)")
    parser.add_argument("--files", "-f", nargs="+",
                        help="File paths to ingest as input (concatenated)")
    parser.add_argument("--include-dirs", nargs="+",
                        help="Directories for Gemini to browse natively via --include-directories")
    parser.add_argument(
        "--confidence", "-c", type=int, default=70, help="Internal confidence score (ignored, anti-bias)"
    )
    parser.add_argument("--step", "-s", default="unknown",
                        help="Step name (plan|implement|verify|test|security-review)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--evolve", "-e", action="store_true",
                        help="Enable evolution loop (auto-iterate until convergence)")
    parser.add_argument("--max-iterations", "-m", type=int, default=3,
                        help="Max iterations for evolve loop (default: 3)")
    parser.add_argument("--detect-evolve", action="store_true",
                        help="Auto-detect [E] marker and enable evolve if found")
    parser.add_argument("--gemini-model", "-g",
                        choices=["gemini-3-flash-preview", "gemini-2.5-pro",
                                 "gemini-2.5-flash", "gemini-2.5-pro"],
                        default=None,
                        help="Override Gemini model")
    parser.add_argument("--max-input-chars", type=int, default=None,
                        help="Override max input chars (default: 500000)")
    args = parser.parse_args()

    # Leggi output da file, argomento, o stdin
    if args.files:
        parts = []
        for fpath in args.files:
            fpath = os.path.expanduser(fpath)
            if os.path.isfile(fpath):
                with open(fpath) as fp:
                    content = fp.read()
                parts.append(f"=== FILE: {os.path.basename(fpath)} ===\n{content}")
            else:
                print(f"[WARN] File not found: {fpath}", file=sys.stderr)
        output = "\n\n".join(parts)
        if not output:
            print("Error: No valid files found.", file=sys.stderr)
            sys.exit(1)
        print(f"[GATE] Ingested {len(parts)} file(s), {len(output)} chars total")
    elif args.output:
        output = args.output
    else:
        output = sys.stdin.read()

    # Validate and resolve include-dirs
    include_dirs = None
    if args.include_dirs:
        include_dirs = []
        for d in args.include_dirs:
            d = os.path.expanduser(d)
            d = os.path.abspath(d)
            if os.path.isdir(d):
                include_dirs.append(d)
            else:
                print(f"[WARN] Directory not found, skipping: {d}", file=sys.stderr)
        if include_dirs:
            print(f"[GATE] Including {len(include_dirs)} dir(s) in Gemini workspace")
        else:
            include_dirs = None

    # Check for [E] marker
    use_evolve = args.evolve
    if args.detect_evolve and detect_evolve_marker(output):
        print("[GATE] Detected [E] marker - enabling evolution loop")
        use_evolve = True

    gate = ConfidenceGate()

    if args.max_input_chars:
        gate.verifier.max_input_chars = args.max_input_chars

    # Override model if specified
    if args.gemini_model:
        gate.verifier.config.setdefault("gemini_cli_models", {})["primary"] = args.gemini_model

    if use_evolve:
        result = evolve_loop(
            gate=gate,
            initial_output=output,
            initial_confidence=args.confidence,
            step_name=args.step,
            max_iterations=args.max_iterations,
            iteration_callback=None,
            include_dirs=include_dirs,
        )
    else:
        result = gate.evaluate(output, args.confidence, args.step, include_dirs=include_dirs)

    if args.json:
        print(
            json.dumps(
                {
                    "decision": result.decision.value,
                    "confidence_score": result.confidence_score,
                    "final_approved": result.final_approved,
                    "should_iterate": result.should_iterate,
                    "iteration_feedback": result.iteration_feedback,
                    "verifications": [
                        {
                            "provider": v.provider,
                            "model": v.model,
                            "approved": v.approved,
                            "confidence": v.confidence,
                            "issues": v.issues,
                            "latency_ms": v.latency_ms,
                        }
                        for v in result.verifications
                    ],
                },
                indent=2,
            )
        )
    else:
        print(f"\nDecision: {result.decision.value}")
        print(f"Confidence: {result.confidence_score}")
        print(f"Final Approved: {result.final_approved}")
        if result.should_iterate:
            print(f"\nSuggested iterations:\n{result.iteration_feedback}")


if __name__ == "__main__":
    main()
