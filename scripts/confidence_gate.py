#!/usr/bin/env python3
"""
Confidence Gate - Multi-Model Verification Chain

Verifica automatica degli output con catena di fallback:
1. Gemini 2.5 Flash (primario)
2. Kimi K2.5 via OpenRouter (fallback)

Elimina le domande "il piano va bene?" quando confidence alta.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict
import time

# Aggiungi path per importare confidence scorer
sys.path.insert(0, os.path.expanduser("~/.claude/templates/validation"))


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
    Verifica output con catena di modelli esterni.
    Non usa Anthropic per evitare "giudicare se stesso".
    """

    VERIFICATION_PROMPT = """Sei un reviewer tecnico. Valuta questo output di un agente AI.

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

    def __init__(self):
        self.providers = self._load_providers()

    def _load_providers(self) -> Dict[str, Dict]:
        """Carica configurazione provider da dotenvx."""
        providers = {}

        # PRIMARY: Gemini diretto (FREE TIER)
        # Modelli disponibili (priorità: Gemini 3 > 2.5):
        # - gemini-3-flash-preview (PRIORITARIO - Gemini 3 Flash)
        # - gemini-3-pro-preview (Gemini 3 Pro)
        # - gemini-2.5-flash (Gemini 2.5 Flash stabile - FALLBACK)
        # - gemini-2.5-pro (Gemini 2.5 Pro)
        gemini_key = self._get_env_key("GEMINI_API_KEY")
        if gemini_key:
            # Default: Gemini 3 Flash (prioritario), con fallback a 2.5-flash
            default_model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
            providers["gemini"] = {
                "api_key": gemini_key,
                "model": default_model,
                "fallback_models": ["gemini-2.5-flash", "gemini-2.5-pro"],  # Fallback chain
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                "is_direct": True,
            }

        # FALLBACK: Kimi K2.5 via OpenRouter (paid, ma più economico)
        openrouter_key = self._get_env_key("OPENROUTER_API_KEY2")
        if openrouter_key:
            providers["openrouter"] = {
                "api_key": openrouter_key,
                "model": "moonshotai/kimi-k2.5",
                "base_url": "https://openrouter.ai/api/v1",
                "is_direct": False,
            }

        return providers

    def _get_env_key(self, key_name: str) -> Optional[str]:
        """Ottiene API key da dotenvx SSOT."""
        # Prima prova environment
        if os.environ.get(key_name):
            return os.environ[key_name]

        # Poi prova dotenvx
        try:
            result = subprocess.run(
                ["dotenvx", "get", key_name, "-f", "/media/sam/1TB/.env"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

        return None

    def verify_with_gemini(
        self, output: str, timeout: int = 30
    ) -> Optional[VerificationResult]:
        """Verifica con Gemini diretto (free tier) con fallback chain."""
        if "gemini" not in self.providers:
            return None

        config = self.providers["gemini"]
        prompt = self.VERIFICATION_PROMPT.format(output=output[:8000])

        # Build models to try: primary + fallbacks
        models_to_try = [config["model"]]
        if "fallback_models" in config:
            models_to_try.extend(config["fallback_models"])

        import urllib.request
        import urllib.error

        for model in models_to_try:
            start_time = time.time()
            try:
                # Headers per API diretta
                if config.get("is_direct"):
                    headers = {
                        "Authorization": f"Bearer {config['api_key']}",
                        "Content-Type": "application/json",
                    }
                else:
                    headers = {
                        "Authorization": f"Bearer {config['api_key']}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://claude-flow.local",
                        "X-Title": "Claude Flow Confidence Gate - Gemini",
                    }

                data = json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                }).encode()

                req = urllib.request.Request(
                    f"{config['base_url']}/chat/completions",
                    data=data,
                    headers=headers,
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=timeout) as response:
                    result = json.loads(response.read().decode())

                latency = int((time.time() - start_time) * 1000)

                content = result["choices"][0]["message"]["content"]
                # Estrai JSON dalla risposta
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    parsed = json.loads(content[json_start:json_end])
                    return VerificationResult(
                        approved=parsed.get("approved", False),
                        confidence=parsed.get("confidence", 0),
                        issues=parsed.get("issues", []),
                        provider="gemini",
                        model=model,
                        latency_ms=latency,
                    )

            except urllib.error.HTTPError as e:
                # Rate limit (429) o model not found (404) → try fallback
                print(f"[WARN] Gemini {model} failed: HTTP {e.code} - trying fallback...", file=sys.stderr)
                continue
            except Exception as e:
                print(f"[WARN] Gemini {model} failed: {e} - trying fallback...", file=sys.stderr)
                continue

        print(f"[WARN] All Gemini models failed", file=sys.stderr)
        return None

    def verify_with_openrouter(
        self, output: str, timeout: int = 45
    ) -> Optional[VerificationResult]:
        """Verifica con Kimi K2.5 via OpenRouter."""
        if "openrouter" not in self.providers:
            return None

        config = self.providers["openrouter"]
        prompt = self.VERIFICATION_PROMPT.format(output=output[:8000])

        start_time = time.time()
        try:
            import urllib.request

            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://claude-flow.local",
                "X-Title": "Claude Flow Confidence Gate",
            }

            data = json.dumps(
                {
                    "model": config["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                }
            ).encode()

            req = urllib.request.Request(
                f"{config['base_url']}/chat/completions",
                data=data,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode())

            latency = int((time.time() - start_time) * 1000)

            content = result["choices"][0]["message"]["content"]
            # Estrai JSON dalla risposta
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(content[json_start:json_end])
                return VerificationResult(
                    approved=parsed.get("approved", False),
                    confidence=parsed.get("confidence", 0),
                    issues=parsed.get("issues", []),
                    provider="openrouter",
                    model=config["model"],
                    latency_ms=latency,
                )

        except Exception as e:
            print(f"[WARN] OpenRouter verification failed: {e}", file=sys.stderr)

        return None

    def verify_chain(self, output: str) -> List[VerificationResult]:
        """
        Esegue catena di verifica:
        1. Gemini 2.5 Flash
        2. Kimi K2.5 (se Gemini fallisce o non approva)
        """
        results = []

        # 1. Prova Gemini
        gemini_result = self.verify_with_gemini(output)
        if gemini_result:
            results.append(gemini_result)
            # Se Gemini approva con alta confidence, basta
            if gemini_result.approved and gemini_result.confidence >= 80:
                return results

        # 2. Fallback a Kimi K2.5
        kimi_result = self.verify_with_openrouter(output)
        if kimi_result:
            results.append(kimi_result)

        return results


class ConfidenceGate:
    """
    Gate automatico basato su confidence score ESTERNO (anti-bias).

    Flusso ANTI-BIAS (confidence calcolata da Gemini, NON da Claude):
    1. Gemini calcola confidence score (Claude non decide)
    2. Se Gemini >= 85: AUTO_APPROVE
    3. Se Gemini 60-84: CROSS_VERIFY con Kimi
    4. Se Gemini < 60: HUMAN_REVIEW

    Il parametro internal_confidence viene IGNORATO per evitare bias.
    """

    THRESHOLDS = {
        "auto_approve": 85,
        "cross_verify": 60,
    }

    def __init__(self):
        self.verifier = MultiModelVerifier()

    def evaluate(
        self,
        step_output: str,
        internal_confidence: int,
        step_name: str = "unknown",
    ) -> GateResult:
        """
        Valuta output usando SOLO modelli esterni (anti-bias).

        Args:
            step_output: Output dello step da valutare
            internal_confidence: IGNORATO - confidence calcolata da Gemini
            step_name: Nome dello step per logging
        """
        verifications = []
        should_iterate = False
        iteration_feedback = None

        # ANTI-BIAS: Sempre verifica con modello esterno
        # Il confidence score viene da Gemini, non da Claude
        print(f"[GATE] {step_name}: Calculating confidence via external model (anti-bias)...")

        # Step 1: Gemini calcola il confidence score
        gemini_result = self.verifier.verify_with_gemini(step_output)

        if gemini_result:
            verifications.append(gemini_result)
            external_confidence = gemini_result.confidence

            print(f"  [gemini] External confidence: {external_confidence}")
            if gemini_result.issues:
                print(f"    Issues: {', '.join(gemini_result.issues[:3])}")

            # Decision basata su confidence ESTERNA (da Gemini)
            if external_confidence >= self.THRESHOLDS["auto_approve"] and gemini_result.approved:
                print(f"[GATE] {step_name}: AUTO_APPROVE (external confidence: {external_confidence})")
                return GateResult(
                    decision=GateDecision.AUTO_APPROVE,
                    confidence_score=external_confidence,
                    verifications=verifications,
                    should_iterate=False,
                    iteration_feedback=None,
                    final_approved=True,
                )

            if external_confidence >= self.THRESHOLDS["cross_verify"]:
                # Cross-verify con Kimi
                print(f"[GATE] {step_name}: Cross-verifying with Kimi (confidence: {external_confidence})")
                kimi_result = self.verifier.verify_with_openrouter(step_output)

                if kimi_result:
                    verifications.append(kimi_result)
                    print(f"  [openrouter] Kimi confidence: {kimi_result.confidence}")
                    if kimi_result.issues:
                        print(f"    Issues: {', '.join(kimi_result.issues[:3])}")

                    # Decisione: almeno 1 verifier approva con confidence >= 70
                    approved_count = sum(1 for v in verifications if v.approved)
                    avg_confidence = sum(v.confidence for v in verifications) / len(verifications)

                    if approved_count >= 1 and avg_confidence >= 70:
                        print(f"[GATE] {step_name}: APPROVED by cross-verification (avg: {avg_confidence:.0f})")
                        return GateResult(
                            decision=GateDecision.AUTO_APPROVE,
                            confidence_score=int(avg_confidence),
                            verifications=verifications,
                            should_iterate=False,
                            iteration_feedback=None,
                            final_approved=True,
                        )

                # Collect issues for iteration
                all_issues = []
                for v in verifications:
                    all_issues.extend(v.issues)

                # Calculate avg_confidence if not set
                if verifications:
                    avg_confidence = sum(v.confidence for v in verifications) / len(verifications)
                else:
                    avg_confidence = external_confidence

                if all_issues:
                    iteration_feedback = "\n".join(f"- {issue}" for issue in all_issues[:5])
                    print(f"[GATE] {step_name}: ITERATE suggested")
                    return GateResult(
                        decision=GateDecision.CROSS_VERIFY,
                        confidence_score=int(avg_confidence),
                        verifications=verifications,
                        should_iterate=True,
                        iteration_feedback=iteration_feedback,
                        final_approved=False,
                    )

            # Bassa confidence esterna
            print(f"[GATE] {step_name}: HUMAN_REVIEW (external confidence: {external_confidence})")
            return GateResult(
                decision=GateDecision.HUMAN_REVIEW,
                confidence_score=external_confidence,
                verifications=verifications,
                should_iterate=False,
                iteration_feedback=None,
                final_approved=False,
            )

        # Gemini fallito: fallback a Kimi solo
        print(f"[GATE] {step_name}: Gemini failed, trying Kimi only...")
        kimi_result = self.verifier.verify_with_openrouter(step_output)

        if kimi_result:
            verifications.append(kimi_result)
            external_confidence = kimi_result.confidence

            if kimi_result.approved and external_confidence >= self.THRESHOLDS["auto_approve"]:
                print(f"[GATE] {step_name}: AUTO_APPROVE via Kimi (confidence: {external_confidence})")
                return GateResult(
                    decision=GateDecision.AUTO_APPROVE,
                    confidence_score=external_confidence,
                    verifications=verifications,
                    should_iterate=False,
                    iteration_feedback=None,
                    final_approved=True,
                )

            if kimi_result.issues:
                iteration_feedback = "\n".join(f"- {issue}" for issue in kimi_result.issues[:5])

            return GateResult(
                decision=GateDecision.CROSS_VERIFY if external_confidence >= 60 else GateDecision.HUMAN_REVIEW,
                confidence_score=external_confidence,
                verifications=verifications,
                should_iterate=bool(kimi_result.issues),
                iteration_feedback=iteration_feedback,
                final_approved=False,
            )

        # Nessun verifier disponibile: HUMAN_REVIEW obbligatorio
        print(f"[GATE] {step_name}: No external verifiers available - HUMAN_REVIEW required")
        return GateResult(
            decision=GateDecision.HUMAN_REVIEW,
            confidence_score=0,
            verifications=[],
            should_iterate=False,
            iteration_feedback="No external verifiers available. Check API keys.",
            final_approved=False,
        )


def detect_evolve_marker(text: str) -> bool:
    """Detect [E] or evolve marker in task/plan text."""
    import re
    patterns = [
        r'\[E\]',           # [E] marker
        r'\[evolve\]',      # [evolve] marker
        r'label.*evolve',   # GitHub label
        r'iterative',       # iterative keyword
        r'convergence',     # convergence keyword
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
) -> GateResult:
    """
    Evolution loop: iterate until convergence or max iterations.

    Args:
        gate: ConfidenceGate instance
        initial_output: Initial step output
        initial_confidence: Initial confidence score
        step_name: Step name for tracking
        max_iterations: Max iterations before giving up
        iteration_callback: Optional callback(output, feedback) -> new_output

    Returns:
        Final GateResult after convergence or max iterations
    """
    current_output = initial_output
    current_confidence = initial_confidence

    for i in range(max_iterations):
        iteration_name = f"{step_name}-v{i+1}" if i > 0 else step_name
        result = gate.evaluate(current_output, current_confidence, iteration_name)

        print(f"[EVOLVE] Iteration {i+1}/{max_iterations}: {result.decision.value} (confidence: {result.confidence_score})")

        if result.final_approved:
            print(f"[EVOLVE] Converged at iteration {i+1}")
            return result

        if not result.should_iterate:
            # Human review required
            print(f"[EVOLVE] Human review required at iteration {i+1}")
            return result

        # Apply feedback for next iteration
        if iteration_callback and result.iteration_feedback:
            print(f"[EVOLVE] Applying feedback: {result.iteration_feedback[:100]}...")
            current_output = iteration_callback(current_output, result.iteration_feedback)
        else:
            # No callback, can't improve
            print(f"[EVOLVE] No iteration callback, stopping")
            return result

    print(f"[EVOLVE] Max iterations ({max_iterations}) reached without convergence")
    # result is guaranteed to be set from at least one iteration
    return result  # type: ignore[possibly-undefined]


def main():
    """CLI per testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Confidence Gate")
    parser.add_argument("--output", "-o", help="Output to verify (or stdin)")
    parser.add_argument(
        "--confidence", "-c", type=int, default=70, help="Internal confidence score"
    )
    parser.add_argument("--step", "-s", default="test", help="Step name")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--evolve", "-e", action="store_true",
                        help="Enable evolution loop (auto-iterate until convergence)")
    parser.add_argument("--max-iterations", "-m", type=int, default=3,
                        help="Max iterations for evolve loop (default: 3)")
    parser.add_argument("--detect-evolve", action="store_true",
                        help="Auto-detect [E] marker and enable evolve if found")
    parser.add_argument("--gemini-model", "-g",
                        choices=["gemini-3-flash-preview", "gemini-3-pro-preview",
                                 "gemini-2.5-flash", "gemini-2.5-pro"],
                        default=None,
                        help="Gemini 3/2.5 model to use (free tier)")
    args = parser.parse_args()

    # Set Gemini model if specified
    if args.gemini_model:
        os.environ["GEMINI_MODEL"] = args.gemini_model

    # Leggi output
    if args.output:
        output = args.output
    else:
        output = sys.stdin.read()

    # Check for [E] marker if auto-detect enabled
    use_evolve = args.evolve
    if args.detect_evolve and detect_evolve_marker(output):
        print("[GATE] Detected [E] marker - enabling evolution loop")
        use_evolve = True

    # Valuta
    gate = ConfidenceGate()

    if use_evolve:
        # Evolution loop - iterate until convergence
        result = evolve_loop(
            gate=gate,
            initial_output=output,
            initial_confidence=args.confidence,
            step_name=args.step,
            max_iterations=args.max_iterations,
            iteration_callback=None,  # CLI mode: no auto-iteration
        )
    else:
        # Single evaluation
        result = gate.evaluate(output, args.confidence, args.step)

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
