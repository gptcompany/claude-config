#!/usr/bin/env python3
"""
CAS Client - HTTP client for local CAS microservice.

Connects to localhost:8769 for formula validation.
Falls back gracefully when CAS unavailable.
"""

from dataclasses import dataclass
from typing import Literal

# httpx import with fallback
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@dataclass
class CASResponse:
    """Response from CAS validation."""

    success: bool
    cas: str
    input_latex: str
    simplified: str | None = None
    factored: str | None = None
    is_identity: bool | None = None
    confidence: str = "UNKNOWN"
    time_ms: int = 0
    error: str | None = None
    cas_available: bool = True


CASEngine = Literal["maxima", "sagemath", "matlab"]


class CASClient:
    """
    HTTP client for CAS microservice.

    Usage:
        client = CASClient()
        if client.is_available():
            result = client.validate("x^2 + 2*x + 1")
            print(result.simplified)
    """

    DEFAULT_URL = "http://localhost:8769"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self._client = None
        self._available: bool | None = None

    def _get_client(self):
        """Get or create httpx client."""
        if not HTTPX_AVAILABLE:
            return None
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def health_check(self) -> dict:
        """
        Check CAS microservice health.

        Returns:
            dict with status and available CAS engines
        """
        client = self._get_client()
        if not client:
            return {"status": "unavailable", "error": "httpx not installed"}

        try:
            response = client.get(f"{self.base_url}/health")
            return response.json()
        except Exception as e:
            return {"status": "unavailable", "error": str(e)}

    def is_available(self) -> bool:
        """Check if CAS microservice is available."""
        if self._available is not None:
            return self._available

        health = self.health_check()
        self._available = health.get("status") == "healthy"
        return self._available or False

    def validate(
        self,
        latex: str,
        cas: CASEngine = "maxima",
    ) -> CASResponse:
        """
        Validate a LaTeX formula via CAS microservice.

        Args:
            latex: LaTeX formula string
            cas: CAS engine to use (maxima, sagemath, matlab)

        Returns:
            CASResponse with validation results
        """
        client = self._get_client()

        if not client:
            return CASResponse(
                success=False,
                cas=cas,
                input_latex=latex,
                error="httpx not installed",
                cas_available=False,
            )

        try:
            response = client.post(
                f"{self.base_url}/validate",
                json={"latex": latex, "cas": cas},
            )
            data = response.json()

            return CASResponse(
                success=data.get("success", False),
                cas=data.get("cas", cas),
                input_latex=latex,
                simplified=data.get("simplified"),
                factored=data.get("factored"),
                is_identity=data.get("is_identity"),
                confidence=data.get("confidence", "UNKNOWN"),
                time_ms=data.get("time_ms", 0),
                error=data.get("error"),
                cas_available=True,
            )

        except Exception as e:
            err_type = type(e).__name__
            err_str = str(e).lower()

            # Connection error - CAS unavailable
            if "connect" in err_type.lower() or "connect" in err_str:
                self._available = False
                return self._wolfram_fallback(latex, cas)

            # Timeout error
            if "timeout" in err_type.lower() or "timeout" in err_str:
                return CASResponse(
                    success=False,
                    cas=cas,
                    input_latex=latex,
                    error="CAS validation timeout",
                    cas_available=True,
                )

            # Other errors
            return CASResponse(
                success=False,
                cas=cas,
                input_latex=latex,
                error=str(e),
                cas_available=self._available or False,
            )

    def _wolfram_fallback(self, latex: str, cas: str) -> CASResponse:
        """
        Fallback to Wolfram MCP when local CAS unavailable.

        Note: MCP tools cannot be called directly from Python code.
        This is a stub that returns an unavailable status.
        Claude should call mcp__wolframalpha__ask_llm directly when this returns.
        """
        return CASResponse(
            success=False,
            cas=cas,
            input_latex=latex,
            error="CAS unavailable, Wolfram fallback not implemented (use MCP directly)",
            cas_available=False,
        )

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Export for testing
__all__ = ["CASClient", "CASResponse", "CASEngine", "HTTPX_AVAILABLE"]
