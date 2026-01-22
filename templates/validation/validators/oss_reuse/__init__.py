"""OSS Reuse Validator - Suggests packages for reimplemented patterns."""

from .validator import OSSReuseValidator
from .patterns import OSS_PATTERNS

__all__ = ["OSSReuseValidator", "OSS_PATTERNS"]
