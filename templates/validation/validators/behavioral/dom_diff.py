#!/usr/bin/env python3
"""
DOMComparator - Tree Edit Distance for DOM Structure Comparison

Uses Zhang-Shasha algorithm via zss library to compare DOM trees.
Computes edit distance and similarity score between two HTML documents.

Graceful degradation when zss library is not installed.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

# zss imports with fallback
try:
    import zss

    ZSS_AVAILABLE = True
except ImportError:
    ZSS_AVAILABLE = False
    zss = None


# Elements to filter out (not meaningful for structural comparison)
FILTERED_ELEMENTS = frozenset(
    {"script", "style", "meta", "link", "noscript", "template", "head"}
)

# Self-closing elements that shouldn't have children
VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


@dataclass
class DOMNode:
    """
    A node in the DOM tree suitable for zss comparison.

    Attributes:
        tag: The HTML tag name (e.g., 'div', 'p', 'span')
        children: List of child DOMNode objects
        attrs: Optional dict of attributes (normalized)
    """

    tag: str
    children: list["DOMNode"] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)

    def __hash__(self) -> int:
        """Hash for zss comparison."""
        return hash((self.tag, tuple(sorted(self.attrs.items()))))

    def __eq__(self, other: object) -> bool:
        """Equality for zss comparison."""
        if not isinstance(other, DOMNode):
            return False
        return self.tag == other.tag and self.attrs == other.attrs


@dataclass
class ComparisonResult:
    """Result of DOM comparison."""

    edit_distance: int
    similarity_score: float  # 0.0 to 1.0
    operations: list[dict[str, Any]]
    tree1_size: int
    tree2_size: int
    zss_available: bool = True


class DOMTreeBuilder(HTMLParser):
    """
    HTML parser that builds a DOMNode tree.

    Filters out non-meaningful elements (script, style, meta, etc.)
    and normalizes whitespace.
    """

    def __init__(
        self,
        ignore_attributes: list[str] | None = None,
        focus_selectors: list[str] | None = None,
    ):
        super().__init__()
        self.ignore_attributes = set(ignore_attributes or [])
        self.focus_selectors = focus_selectors
        self.root: DOMNode | None = None
        self.stack: list[DOMNode] = []
        self._in_filtered = 0  # Counter for nested filtered elements

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle opening tag."""
        tag_lower = tag.lower()

        # Track if we're inside filtered elements
        if tag_lower in FILTERED_ELEMENTS:
            self._in_filtered += 1
            return

        # Skip if inside filtered element
        if self._in_filtered > 0:
            return

        # Filter attributes
        filtered_attrs = {}
        for name, value in attrs:
            if name not in self.ignore_attributes and value is not None:
                # Normalize whitespace in attribute values
                filtered_attrs[name] = " ".join(value.split())

        node = DOMNode(tag=tag_lower, attrs=filtered_attrs)

        if self.stack:
            self.stack[-1].children.append(node)
        else:
            self.root = node

        # Don't push void elements to stack
        if tag_lower not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        """Handle closing tag."""
        tag_lower = tag.lower()

        # Track filtered elements
        if tag_lower in FILTERED_ELEMENTS:
            self._in_filtered = max(0, self._in_filtered - 1)
            return

        # Skip if inside filtered element
        if self._in_filtered > 0:
            return

        # Pop from stack if matching
        if self.stack and self.stack[-1].tag == tag_lower:
            self.stack.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle self-closing tags."""
        self.handle_starttag(tag, attrs)

    def error(self, message: str) -> None:
        """Handle parse errors gracefully."""
        pass  # Ignore parse errors


def parse_html(
    html: str,
    ignore_attributes: list[str] | None = None,
    focus_selectors: list[str] | None = None,
) -> DOMNode | None:
    """
    Parse HTML string into a DOMNode tree.

    Args:
        html: HTML string to parse
        ignore_attributes: Attribute names to ignore (e.g., ['id', 'class'])
        focus_selectors: CSS selectors to focus on (not implemented in basic version)

    Returns:
        Root DOMNode of the tree, or None if parsing fails
    """
    if not html or not html.strip():
        return None

    parser = DOMTreeBuilder(
        ignore_attributes=ignore_attributes, focus_selectors=focus_selectors
    )

    try:
        parser.feed(html)
    except Exception:
        return None

    return parser.root


def count_nodes(node: DOMNode | None) -> int:
    """Count total nodes in a tree."""
    if node is None:
        return 0
    return 1 + sum(count_nodes(child) for child in node.children)


def _get_children(node: DOMNode) -> list[DOMNode]:
    """Get children of a node (for zss)."""
    return node.children


def _get_label(node: DOMNode) -> str:
    """Get label of a node (for zss)."""
    return node.tag


def _label_dist(label1: str, label2: str) -> int:
    """Distance between two labels (for zss)."""
    return 0 if label1 == label2 else 1


class DOMComparator:
    """
    Compare DOM trees using Zhang-Shasha tree edit distance.

    Usage:
        comparator = DOMComparator()
        result = comparator.compare(baseline_html, current_html)
        print(f"Similarity: {result.similarity_score}")
    """

    def __init__(
        self,
        ignore_attributes: list[str] | None = None,
        focus_selectors: list[str] | None = None,
    ):
        """
        Initialize comparator with options.

        Args:
            ignore_attributes: Attributes to ignore in comparison (e.g., ['id', 'class', 'style'])
            focus_selectors: CSS selectors to focus on (future feature)
        """
        self.ignore_attributes = ignore_attributes
        self.focus_selectors = focus_selectors

    def compare(self, baseline_html: str, current_html: str) -> ComparisonResult:
        """
        Compare two HTML documents.

        Args:
            baseline_html: Expected/reference HTML
            current_html: Actual/current HTML

        Returns:
            ComparisonResult with edit_distance, similarity_score, and operations
        """
        # Parse both documents
        tree1 = parse_html(
            baseline_html,
            ignore_attributes=self.ignore_attributes,
            focus_selectors=self.focus_selectors,
        )
        tree2 = parse_html(
            current_html,
            ignore_attributes=self.ignore_attributes,
            focus_selectors=self.focus_selectors,
        )

        # Handle empty/invalid HTML
        size1 = count_nodes(tree1)
        size2 = count_nodes(tree2)

        # Both empty or invalid
        if tree1 is None and tree2 is None:
            return ComparisonResult(
                edit_distance=0,
                similarity_score=1.0,
                operations=[],
                tree1_size=0,
                tree2_size=0,
                zss_available=ZSS_AVAILABLE,
            )

        # One empty, one not
        if tree1 is None or tree2 is None:
            max_size = max(size1, size2)
            return ComparisonResult(
                edit_distance=max_size,
                similarity_score=0.0,
                operations=[{"type": "replace", "count": max_size}],
                tree1_size=size1,
                tree2_size=size2,
                zss_available=ZSS_AVAILABLE,
            )

        # Check if zss is available
        if not ZSS_AVAILABLE:
            # Graceful degradation: simple heuristic comparison
            return self._fallback_compare(tree1, tree2, size1, size2)

        # Use Zhang-Shasha algorithm
        try:
            distance = zss.simple_distance(
                tree1,
                tree2,
                get_children=_get_children,
                get_label=_get_label,
                label_dist=_label_dist,
            )

            # Calculate similarity score
            max_size = max(size1, size2)
            similarity = 1.0 - (distance / max_size) if max_size > 0 else 1.0
            similarity = max(0.0, min(1.0, similarity))  # Clamp to [0, 1]

            return ComparisonResult(
                edit_distance=int(distance),
                similarity_score=similarity,
                operations=[{"type": "edit", "distance": int(distance)}],
                tree1_size=size1,
                tree2_size=size2,
                zss_available=True,
            )
        except Exception as e:
            # Fall back on error
            return ComparisonResult(
                edit_distance=max(size1, size2),
                similarity_score=0.5,
                operations=[{"type": "error", "message": str(e)}],
                tree1_size=size1,
                tree2_size=size2,
                zss_available=True,
            )

    def _fallback_compare(
        self, tree1: DOMNode, tree2: DOMNode, size1: int, size2: int
    ) -> ComparisonResult:
        """
        Fallback comparison when zss is not available.

        Uses simple heuristic based on tree structure.
        """
        # Simple heuristic: compare tags at each level
        tags1 = self._collect_tags(tree1)
        tags2 = self._collect_tags(tree2)

        # Jaccard similarity of tag sets
        common = len(tags1 & tags2)
        total = len(tags1 | tags2)

        similarity = common / total if total > 0 else 1.0
        estimated_distance = abs(size1 - size2) + int(
            (1 - similarity) * max(size1, size2)
        )

        return ComparisonResult(
            edit_distance=estimated_distance,
            similarity_score=similarity,
            operations=[{"type": "fallback", "message": "zss not installed"}],
            tree1_size=size1,
            tree2_size=size2,
            zss_available=False,
        )

    def _collect_tags(self, node: DOMNode) -> set[str]:
        """Collect all tags in a tree."""
        tags = {node.tag}
        for child in node.children:
            tags.update(self._collect_tags(child))
        return tags


# Export for testing
__all__ = [
    "DOMComparator",
    "DOMNode",
    "ComparisonResult",
    "parse_html",
    "count_nodes",
    "ZSS_AVAILABLE",
]
