#!/usr/bin/env python3
"""Tree Edit Distance for DOM Structure Comparison via Zhang-Shasha algorithm."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

try:
    import zss

    ZSS_AVAILABLE = True
except ImportError:
    ZSS_AVAILABLE = False
    zss = None

FILTERED_ELEMENTS = frozenset(
    {"script", "style", "meta", "link", "noscript", "template", "head"}
)

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
    tag: str
    children: list["DOMNode"] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash((self.tag, tuple(sorted(self.attrs.items()))))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DOMNode):
            return False
        return self.tag == other.tag and self.attrs == other.attrs


@dataclass
class ComparisonResult:
    edit_distance: int
    similarity_score: float
    operations: list[dict[str, Any]]
    tree1_size: int
    tree2_size: int
    zss_available: bool = True


class DOMTreeBuilder(HTMLParser):
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
        self._in_filtered = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        if tag_lower in FILTERED_ELEMENTS:
            self._in_filtered += 1
            return

        if self._in_filtered > 0:
            return

        filtered_attrs = {
            name: " ".join(value.split())
            for name, value in attrs
            if name not in self.ignore_attributes and value is not None
        }

        node = DOMNode(tag=tag_lower, attrs=filtered_attrs)

        if self.stack:
            self.stack[-1].children.append(node)
        else:
            self.root = node

        if tag_lower not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower in FILTERED_ELEMENTS:
            self._in_filtered = max(0, self._in_filtered - 1)
            return

        if self._in_filtered > 0:
            return

        if self.stack and self.stack[-1].tag == tag_lower:
            self.stack.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def error(self, message: str) -> None:
        pass


def parse_html(
    html: str,
    ignore_attributes: list[str] | None = None,
    focus_selectors: list[str] | None = None,
) -> DOMNode | None:
    if not html or not html.strip():
        return None

    parser = DOMTreeBuilder(ignore_attributes, focus_selectors)
    try:
        parser.feed(html)
    except Exception:
        return None
    return parser.root


def count_nodes(node: DOMNode | None) -> int:
    if node is None:
        return 0
    return 1 + sum(count_nodes(child) for child in node.children)


class DOMComparator:
    def __init__(
        self,
        ignore_attributes: list[str] | None = None,
        focus_selectors: list[str] | None = None,
    ):
        self.ignore_attributes = ignore_attributes
        self.focus_selectors = focus_selectors

    def compare(self, baseline_html: str, current_html: str) -> ComparisonResult:
        tree1 = parse_html(baseline_html, self.ignore_attributes, self.focus_selectors)
        tree2 = parse_html(current_html, self.ignore_attributes, self.focus_selectors)

        size1, size2 = count_nodes(tree1), count_nodes(tree2)

        if tree1 is None and tree2 is None:
            return ComparisonResult(
                edit_distance=0,
                similarity_score=1.0,
                operations=[],
                tree1_size=0,
                tree2_size=0,
                zss_available=ZSS_AVAILABLE,
            )

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

        if not ZSS_AVAILABLE:
            return self._fallback_compare(tree1, tree2, size1, size2)

        try:
            distance: float = zss.simple_distance(  # type: ignore[union-attr]
                tree1,
                tree2,
                get_children=lambda n: n.children,
                get_label=lambda n: n.tag,
                label_dist=lambda a, b: 0 if a == b else 1,
            )

            max_size = max(size1, size2)
            similarity = max(
                0.0, min(1.0, 1.0 - (distance / max_size) if max_size > 0 else 1.0)
            )

            return ComparisonResult(
                edit_distance=int(distance),
                similarity_score=similarity,
                operations=[{"type": "edit", "distance": int(distance)}],
                tree1_size=size1,
                tree2_size=size2,
                zss_available=True,
            )
        except Exception as e:
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
        tags1 = self._collect_tags(tree1)
        tags2 = self._collect_tags(tree2)

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
        tags = {node.tag}
        for child in node.children:
            tags.update(self._collect_tags(child))
        return tags


__all__ = [
    "DOMComparator",
    "DOMNode",
    "ComparisonResult",
    "parse_html",
    "count_nodes",
    "ZSS_AVAILABLE",
]
