"""OSS Reuse Validator - Suggests packages for reimplemented patterns."""

from .patterns import OSS_PATTERNS
from .validator import OSSReuseValidator

__all__ = ["OSSReuseValidator", "OSS_PATTERNS"]
