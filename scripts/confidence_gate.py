#!/usr/bin/env python3
"""
Confidence Gate - Multi-Model Verification Chain

Verifica automatica degli output con catena di fallback:
1. Gemini 2.5 Flash (primario)
2. DeepSeek R1 0528 via OpenRouter (fallback)

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

    # Step-specific prompts for better accuracy
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
        """Backward compatibility - returns default prompt template."""
        return self.DEFAULT_PROMPT

    CONFIG_PATH = os.path.expanduser("~/.claude/config/confidence_gate.json")

    # Default max input chars - Gemini Flash supports 1M tokens (~4M chars)
    # 100K chars is a safe default that covers most planning files
    DEFAULT_MAX_INPUT_CHARS = 500000

    def __init__(self):
        self.config = self._load_config()
        self.max_input_chars = self.config.get(
            "max_input_chars", self.DEFAULT_MAX_INPUT_CHARS
        )
        # Load custom prompt from config if present
        self._custom_prompt = self.config.get("verification_prompt")
        # Load custom step prompts from config
        self._custom_step_prompts = self.config.get("step_prompts", {})
        self.providers = self._load_providers()

    def _get_prompt(self, output: str, step_name: str = "unknown") -> str:
        """Build the formatted prompt for a given step and output."""
        template = self.get_prompt_for_step(step_name)
        return template.format(output=output[:self.max_input_chars])

    def get_prompt_for_step(self, step_name: str) -> str:
        """Get the best prompt template for a given step.

        Priority: config step_prompts > config verification_prompt > built-in step prompt > default.
        """
        step_lower = step_name.lower()
        # 1. Custom step prompt from config
        if step_lower in self._custom_step_prompts:
            return self._custom_step_prompts[step_lower]
        # 2. Global custom prompt from config
        if self._custom_prompt:
            return self._custom_prompt
        # 3. Built-in step-specific prompt
        if step_lower in self.STEP_PROMPTS:
            return self.STEP_PROMPTS[step_lower]
        # 4. Default prompt
        return self.DEFAULT_PROMPT

    def _load_config(self) -> Dict:
        """Carica configurazione da file JSON."""
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH) as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Config load failed ({e}), using defaults", file=sys.stderr)
        return {}

    def _load_providers(self) -> Dict[str, Dict]:
        """Carica configurazione provider da config file + dotenvx."""
        providers = {}
        config_providers = self.config.get("providers", [])

        if config_providers:
            # Load from config file
            for p in config_providers:
                if not p.get("enabled", True):
                    continue
                api_key = self._get_env_key(p["env_key"])
                if api_key:
                    name = p["name"]
                    providers[name] = {
                        "api_key": api_key,
                        "model": p["model"],
                        "base_url": p["base_url"],
                        "is_direct": p.get("is_direct", False),
                        "timeout": p.get("timeout", 30),
                        "role": p.get("role", "primary"),
                        "reasoning_field": p.get("reasoning_field"),
                        "fallback_models": p.get("fallback_models", []),
                    }
            if providers:
                loaded = ", ".join(f"{k}({v['model']})" for k, v in providers.items())
                print(f"[GATE] Loaded {len(providers)} providers from config: {loaded}")
                return providers

        # Fallback: hardcoded defaults (backward compatibility)
        gemini_key = self._get_env_key("GEMINI_API_KEY")
        if gemini_key:
            default_model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
            providers["gemini"] = {
                "api_key": gemini_key,
                "model": default_model,
                "fallback_models": ["gemini-2.5-flash"],
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                "is_direct": True,
                "timeout": 30,
                "role": "primary",
            }

        openrouter_key = self._get_env_key("OPENROUTER_API_KEY2")
        if openrouter_key:
            providers["openrouter_deepseek"] = {
                "api_key": openrouter_key,
                "model": "deepseek/deepseek-r1-0528",
                "base_url": "https://openrouter.ai/api/v1",
                "is_direct": False,
                "timeout": 90,
                "role": "cross_verify",
                "reasoning_field": "reasoning",
            }
            providers["openrouter_kimi"] = {
                "api_key": openrouter_key,
                "model": "moonshotai/kimi-k2-thinking",
                "base_url": "https://openrouter.ai/api/v1",
                "is_direct": False,
                "timeout": 30,
                "role": "last_resort",
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

    def _verify_via_gemini_cli(
        self, output: str, timeout: int = 120, step_name: str = "unknown",
        model: str = None
    ) -> Optional[VerificationResult]:
        """Verifica usando Gemini CLI in headless mode (-p flag).

        Supporta selezione modello via -m flag per routing tra pool:
        - gemini-3-flash-preview (Thinking, 300/day con AI Pro)
        - gemini-3-pro-preview (Pro, 100/day con AI Pro)
        - gemini-2.5-flash (fallback)
        """
        import shutil

        gemini_bin = shutil.which("gemini")
        if not gemini_bin:
            return None

        # Resolve model from config if not specified
        if model is None:
            cli_models = self.config.get("gemini_cli_models", {})
            model = cli_models.get("primary", "gemini-3-flash-preview")

        prompt = self._get_prompt(output, step_name)
        start_time = time.time()

        # Prefer OAuth (no key injection needed) over API key with dotenvx
        import pathlib
        gemini_settings = pathlib.Path.home() / ".gemini" / "settings.json"
        use_oauth = False
        if gemini_settings.exists():
            try:
                with open(gemini_settings) as f:
                    gs = json.load(f)
                auth_type = gs.get("security", {}).get("auth", {}).get("selectedType", "")
                use_oauth = "oauth" in auth_type
            except Exception:
                pass

        # For short prompts: -p flag (fast, no stdin needed)
        # For long prompts: pipe via stdin (Gemini CLI reads from stdin without -p)
        use_stdin = len(prompt) > 4000

        if use_oauth:
            cmd = [gemini_bin, "-m", model]
            if not use_stdin:
                cmd.extend(["-p", prompt])
        else:
            dotenvx_bin = shutil.which("dotenvx")
            env_file = "/media/sam/1TB/.env"
            if dotenvx_bin and os.path.exists(env_file):
                cmd = [dotenvx_bin, "run", "-f", env_file, "--", gemini_bin, "-m", model]
            else:
                cmd = [gemini_bin, "-m", model]
            if not use_stdin:
                cmd.extend(["-p", prompt])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=prompt if use_stdin else None,
                env={**os.environ, "NO_COLOR": "1"},
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                # Filter out dotenvx info lines
                stderr_lines = [l for l in stderr.split("\n") if not l.startswith("[dotenvx")]
                stderr_clean = "\n".join(stderr_lines).strip()
                if stderr_clean:
                    print(f"[WARN] Gemini CLI failed (exit {result.returncode}): {stderr_clean[:200]}", file=sys.stderr)
                return None

            latency = int((time.time() - start_time) * 1000)
            # Filter out dotenvx/hook lines from stdout
            content_lines = [l for l in result.stdout.split("\n")
                             if not l.startswith("[dotenvx") and not l.startswith("Hook registry")]
            content = "\n".join(content_lines).strip()

            # Estrai JSON dalla risposta
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(content[json_start:json_end])
                return VerificationResult(
                    approved=parsed.get("approved", False),
                    confidence=parsed.get("confidence", 0),
                    issues=parsed.get("issues", []),
                    provider="gemini_cli",
                    model=model,
                    latency_ms=latency,
                )

        except subprocess.TimeoutExpired:
            print(f"[WARN] Gemini CLI timeout after {timeout}s", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] Gemini CLI failed: {e}", file=sys.stderr)

        return None

    def verify_with_gemini(
        self, output: str, timeout: int = None, step_name: str = "unknown"
    ) -> Optional[VerificationResult]:
        """Verifica con Gemini CLI (preferred) usando due pool indipendenti:
        1. Flash/Thinking (300/day) → primary validation
        2. Pro (100/day) → cross-verify se confidence < threshold
        Fallback ad API key se CLI non disponibile.
        """
        cli_models = self.config.get("gemini_cli_models", {})

        if self.config.get("gemini_cli_preferred", True) and self.config.get("gemini_cli_enabled", True):
            # Primary: Gemini 3 Flash/Thinking (300/day pool)
            primary_model = cli_models.get("primary", "gemini-3-flash-preview")
            cli_result = self._verify_via_gemini_cli(output, step_name=step_name, model=primary_model)
            if cli_result:
                # Cross-verify con Pro se confidence sotto soglia
                cross_threshold = self.config.get("thresholds", {}).get("cross_verify", 60)
                if cli_result.confidence < cross_threshold:
                    cross_model = cli_models.get("cross_verify", "gemini-3-pro-preview")
                    print(f"[INFO] Confidence {cli_result.confidence}% < {cross_threshold}%, cross-verifying with {cross_model}", file=sys.stderr)
                    cross_result = self._verify_via_gemini_cli(output, step_name=step_name, model=cross_model)
                    if cross_result:
                        # Media pesata: Pro ha piu' peso
                        avg_conf = int(cli_result.confidence * 0.4 + cross_result.confidence * 0.6)
                        combined_issues = list(set(cli_result.issues + cross_result.issues))
                        return VerificationResult(
                            approved=avg_conf >= self.config.get("thresholds", {}).get("auto_approve", 85),
                            confidence=avg_conf,
                            issues=combined_issues,
                            provider="gemini_cli_cross",
                            model=f"{primary_model}+{cross_model}",
                            latency_ms=cli_result.latency_ms + cross_result.latency_ms,
                        )
                return cli_result
            print(f"[WARN] Gemini CLI failed, falling back to API...", file=sys.stderr)

        if "gemini" not in self.providers:
            return None

        config = self.providers["gemini"]
        timeout = timeout or config.get("timeout", 30)
        prompt = self._get_prompt(output, step_name)

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
                if e.code in (429, 503):
                    # Rate limit or service unavailable - retry with exponential backoff (max 3 retries per model)
                    retry_key = f"_retry_{model}_{e.code}"
                    retry_count = getattr(self, retry_key, 0)
                    if retry_count < 3:
                        backoff = (2 ** retry_count) * 2  # 2s, 4s, 8s
                        print(f"[WARN] Gemini {model} HTTP {e.code} - waiting {backoff}s (retry {retry_count+1}/3)...", file=sys.stderr)
                        setattr(self, retry_key, retry_count + 1)
                        time.sleep(backoff)
                        # Re-attempt same model
                        models_to_try.insert(models_to_try.index(model) + 1, model)
                        continue
                # Other HTTP errors or max retries → try fallback
                print(f"[WARN] Gemini {model} failed: HTTP {e.code} - trying fallback...", file=sys.stderr)
                continue
            except Exception as e:
                print(f"[WARN] Gemini {model} failed: {e} - trying fallback...", file=sys.stderr)
                continue

        # All API models failed - try Gemini CLI as last resort
        if self.config.get("gemini_cli_enabled", True):
            print(f"[WARN] All Gemini API models failed - trying Gemini CLI (OAuth)...", file=sys.stderr)
            return self._verify_via_gemini_cli(output, timeout=120, step_name=step_name)

        print(f"[WARN] All Gemini models failed", file=sys.stderr)
        return None

    def verify_with_openrouter(
        self, output: str, timeout: int = None, step_name: str = "unknown"
    ) -> Optional[VerificationResult]:
        """Verifica con DeepSeek R1 via OpenRouter (reasoning model, needs longer timeout)."""
        # Try config-based name first, then legacy name
        provider_name = "openrouter_deepseek" if "openrouter_deepseek" in self.providers else "openrouter"
        if provider_name not in self.providers:
            return None

        config = self.providers[provider_name]
        timeout = timeout or config.get("timeout", 90)
        prompt = self._get_prompt(output, step_name)

        start_time = time.time()
        try:
            import urllib.request
            import urllib.error

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

            message = result["choices"][0]["message"]
            content = message.get("content", "") or ""

            # Reasoning models (DeepSeek R1) put output in reasoning field
            reasoning_field = config.get("reasoning_field", "reasoning")
            if not content.strip() and message.get(reasoning_field):
                content = message[reasoning_field]

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

        except urllib.error.HTTPError as e:
            print(f"[WARN] OpenRouter/DeepSeek HTTP error: {e.code} - {e.reason}", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"[WARN] OpenRouter/DeepSeek connection error: {e.reason}", file=sys.stderr)
        except TimeoutError:
            print(f"[WARN] OpenRouter/DeepSeek timeout after {timeout}s", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] OpenRouter/DeepSeek verification failed: {type(e).__name__}: {e}", file=sys.stderr)

        return None

    def verify_with_kimi(
        self, output: str, timeout: int = None, step_name: str = "unknown"
    ) -> Optional[VerificationResult]:
        """Verifica con Kimi K2 Thinking via OpenRouter (ultimo fallback)."""
        if "openrouter_kimi" not in self.providers:
            return None

        config = self.providers["openrouter_kimi"]
        timeout = timeout or config.get("timeout", 30)
        prompt = self._get_prompt(output, step_name)

        start_time = time.time()
        try:
            import urllib.request
            import urllib.error

            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://claude-flow.local",
                "X-Title": "Claude Flow Confidence Gate - Kimi",
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

            content = result["choices"][0]["message"].get("content", "") or ""
            # Estrai JSON dalla risposta
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(content[json_start:json_end])
                return VerificationResult(
                    approved=parsed.get("approved", False),
                    confidence=parsed.get("confidence", 0),
                    issues=parsed.get("issues", []),
                    provider="openrouter_kimi",
                    model=config["model"],
                    latency_ms=latency,
                )

        except urllib.error.HTTPError as e:
            print(f"[WARN] Kimi HTTP error: {e.code} - {e.reason}", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"[WARN] Kimi connection error: {e.reason}", file=sys.stderr)
        except TimeoutError:
            print(f"[WARN] Kimi timeout after {timeout}s", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] Kimi verification failed: {type(e).__name__}: {e}", file=sys.stderr)

        return None

    def verify_chain(self, output: str, step_name: str = "unknown") -> List[VerificationResult]:
        """
        Esegue catena di verifica:
        1. Gemini Flash
        2. DeepSeek R1 (se Gemini fallisce o non approva)
        3. Kimi K2.5 (ultimo fallback)
        """
        results = []

        # 1. Prova Gemini
        gemini_result = self.verify_with_gemini(output, step_name=step_name)
        if gemini_result:
            results.append(gemini_result)
            # Se Gemini approva con alta confidence, basta
            if gemini_result.approved and gemini_result.confidence >= 80:
                return results

        # 2. Fallback a DeepSeek R1
        deepseek_result = self.verify_with_openrouter(output, step_name=step_name)
        if deepseek_result:
            results.append(deepseek_result)

        return results


class ConfidenceGate:
    """
    Gate automatico basato su confidence score ESTERNO (anti-bias).

    Flusso ANTI-BIAS (confidence calcolata da Gemini, NON da Claude):
    1. Gemini calcola confidence score (Claude non decide)
    2. Se Gemini >= 85: AUTO_APPROVE
    3. Se Gemini 60-84: CROSS_VERIFY con DeepSeek R1
    4. Se Gemini < 60: HUMAN_REVIEW

    Il parametro internal_confidence viene IGNORATO per evitare bias.
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
        self._credit_config = config.get("credit_check", {"enabled": True, "warn_below": 0.01})

    def _check_openrouter_credits(self) -> Optional[float]:
        """Check remaining OpenRouter credits. Returns remaining $ or None on failure."""
        try:
            import urllib.request
            key = self.verifier._get_env_key("OPENROUTER_API_KEY2")
            if not key:
                return None
            headers = {"Authorization": f"Bearer {key}"}
            req = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read().decode())
                remaining = result.get("data", {}).get("limit_remaining", None)
                if remaining is not None:
                    return float(remaining)
        except Exception:
            pass
        return None

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

        # Credit check OpenRouter
        credits = None
        if self._credit_config.get("enabled", True):
            credits = self._check_openrouter_credits()
            if credits is not None:
                warn_below = self._credit_config.get("warn_below", 0.01)
                print(f"[GATE] OpenRouter credits remaining: ${credits:.2f}")
                if credits < warn_below:
                    print(f"[WARN] OpenRouter credits nearly exhausted (${credits:.4f}) - paid models may fail", file=sys.stderr)

        # ANTI-BIAS: Sempre verifica con modello esterno
        # Il confidence score viene da Gemini, non da Claude
        print(f"[GATE] {step_name}: Calculating confidence via external model (anti-bias)...")

        # Step 1: Gemini calcola il confidence score
        gemini_result = self.verifier.verify_with_gemini(step_output, step_name=step_name)

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
                print(f"[GATE] {step_name}: Cross-verifying with DeepSeek R1 (confidence: {external_confidence})")
                deepseek_result = self.verifier.verify_with_openrouter(step_output, step_name=step_name)

                if deepseek_result:
                    verifications.append(deepseek_result)
                    print(f"  [openrouter] DeepSeek R1 confidence: {deepseek_result.confidence}")
                    if deepseek_result.issues:
                        print(f"    Issues: {', '.join(deepseek_result.issues[:3])}")

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

        # Gemini fallito: cascata DeepSeek R1 → Kimi K2 Thinking
        print(f"[GATE] {step_name}: Gemini failed, trying DeepSeek R1...")
        deepseek_result = self.verifier.verify_with_openrouter(step_output, step_name=step_name)

        if deepseek_result:
            verifications.append(deepseek_result)
            external_confidence = deepseek_result.confidence

            if deepseek_result.approved and external_confidence >= self.THRESHOLDS["auto_approve"]:
                print(f"[GATE] {step_name}: AUTO_APPROVE via DeepSeek R1 (confidence: {external_confidence})")
                return GateResult(
                    decision=GateDecision.AUTO_APPROVE,
                    confidence_score=external_confidence,
                    verifications=verifications,
                    should_iterate=False,
                    iteration_feedback=None,
                    final_approved=True,
                )

            if deepseek_result.issues:
                iteration_feedback = "\n".join(f"- {issue}" for issue in deepseek_result.issues[:5])

            return GateResult(
                decision=GateDecision.CROSS_VERIFY if external_confidence >= 60 else GateDecision.HUMAN_REVIEW,
                confidence_score=external_confidence,
                verifications=verifications,
                should_iterate=bool(deepseek_result.issues),
                iteration_feedback=iteration_feedback,
                final_approved=False,
            )

        # DeepSeek R1 fallito: ultimo tentativo con Kimi K2 Thinking
        print(f"[GATE] {step_name}: DeepSeek R1 failed, trying Kimi K2 Thinking (last resort)...")
        kimi_result = self.verifier.verify_with_kimi(step_output, step_name=step_name)

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
        print(f"[GATE] {step_name}: All 3 verifiers failed (Gemini, DeepSeek R1, Kimi) - HUMAN_REVIEW required")
        credit_info = ""
        if credits is not None and credits < 0.01:
            credit_info = f" OpenRouter credits: ${credits:.4f} (nearly exhausted)."
        print(f"[GATE] Check: API keys, network, rate limits.{credit_info}")
        return GateResult(
            decision=GateDecision.HUMAN_REVIEW,
            confidence_score=0,
            verifications=[],
            should_iterate=False,
            iteration_feedback=f"All 3 verifiers failed (Gemini, DeepSeek R1, Kimi). Check API keys and credits.{credit_info}",
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
    parser.add_argument("--files", "-f", nargs="+",
                        help="File paths to ingest as input (concatenated)")
    parser.add_argument(
        "--confidence", "-c", type=int, default=70, help="Internal confidence score"
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
                        choices=["gemini-3-flash-preview", "gemini-3-pro-preview",
                                 "gemini-2.5-flash", "gemini-2.5-pro"],
                        default=None,
                        help="Gemini 3/2.5 model to use (free tier)")
    parser.add_argument("--max-input-chars", type=int, default=None,
                        help="Override max input chars (default: 100000)")
    args = parser.parse_args()

    # Set Gemini model if specified
    if args.gemini_model:
        os.environ["GEMINI_MODEL"] = args.gemini_model

    # Leggi output da file, argomento, o stdin
    if args.files:
        # Ingest multiple files
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

    # Check for [E] marker if auto-detect enabled
    use_evolve = args.evolve
    if args.detect_evolve and detect_evolve_marker(output):
        print("[GATE] Detected [E] marker - enabling evolution loop")
        use_evolve = True

    # Valuta
    gate = ConfidenceGate()

    # Override max input chars if specified
    if args.max_input_chars:
        gate.verifier.max_input_chars = args.max_input_chars

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
