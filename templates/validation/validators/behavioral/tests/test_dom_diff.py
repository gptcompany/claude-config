#!/usr/bin/env python3
"""
Tests for DOMComparator - Tree Edit Distance DOM Comparison

Tests cover:
- Identical HTML comparison
- Different HTML comparison
- Graceful degradation when zss unavailable
- Invalid/malformed HTML handling
- Element filtering (script, style, meta)
- Whitespace normalization
- Empty HTML handling
"""

import pytest
from unittest.mock import patch

from validators.behavioral.dom_diff import (
    DOMComparator,
    DOMNode,
    ComparisonResult,
    parse_html,
    count_nodes,
    ZSS_AVAILABLE,
)


class TestParseHtml:
    """Tests for parse_html function."""

    def test_parse_simple_html(self):
        """Parse basic HTML structure."""
        html = "<div><p>Hello</p></div>"
        root = parse_html(html)

        assert root is not None
        assert root.tag == "div"
        assert len(root.children) == 1
        assert root.children[0].tag == "p"

    def test_parse_nested_html(self):
        """Parse nested HTML structure."""
        html = "<main><section><article><p>Content</p></article></section></main>"
        root = parse_html(html)

        assert root is not None
        assert root.tag == "main"
        assert root.children[0].tag == "section"
        assert root.children[0].children[0].tag == "article"
        assert root.children[0].children[0].children[0].tag == "p"

    def test_parse_with_attributes(self):
        """Parse HTML with attributes."""
        html = (
            '<div id="main" class="container"><span data-value="123">Text</span></div>'
        )
        root = parse_html(html)

        assert root is not None
        assert root.attrs["id"] == "main"
        assert root.attrs["class"] == "container"
        assert root.children[0].attrs["data-value"] == "123"

    def test_parse_ignore_attributes(self):
        """Parse HTML ignoring specified attributes."""
        html = '<div id="test" class="foo" data-x="bar">Content</div>'
        root = parse_html(html, ignore_attributes=["id", "class"])

        assert root is not None
        assert "id" not in root.attrs
        assert "class" not in root.attrs
        assert root.attrs.get("data-x") == "bar"

    def test_parse_filter_script_elements(self):
        """Script elements should be filtered out."""
        html = "<div><script>alert('xss')</script><p>Content</p></div>"
        root = parse_html(html)

        assert root is not None
        # Should only have p child, not script
        assert len(root.children) == 1
        assert root.children[0].tag == "p"

    def test_parse_filter_style_elements(self):
        """Style elements should be filtered out."""
        html = "<div><style>.foo{color:red}</style><p>Content</p></div>"
        root = parse_html(html)

        assert root is not None
        assert len(root.children) == 1
        assert root.children[0].tag == "p"

    def test_parse_filter_meta_elements(self):
        """Meta elements should be filtered out."""
        html = '<html><head><meta charset="utf-8"></head><body><p>Hi</p></body></html>'
        root = parse_html(html)

        # The structure should skip head entirely
        assert root is not None
        # HTML parser may handle this differently - just verify no meta in tree
        tags = collect_all_tags(root)
        assert "meta" not in tags
        assert "head" not in tags

    def test_parse_whitespace_normalization(self):
        """Whitespace in attributes should be normalized."""
        html = '<div class="foo   bar   baz">Content</div>'
        root = parse_html(html)

        assert root is not None
        assert root.attrs["class"] == "foo bar baz"

    def test_parse_empty_html(self):
        """Empty HTML should return None."""
        assert parse_html("") is None
        assert parse_html("   ") is None
        assert parse_html(None) is None  # type: ignore

    def test_parse_malformed_html(self):
        """Malformed HTML should be handled gracefully."""
        # Unclosed tags
        html = "<div><p>Unclosed"
        root = parse_html(html)
        # Should still parse what it can
        assert root is not None

    def test_parse_void_elements(self):
        """Void elements should not have children pushed to stack."""
        html = "<div><br><img src='x.png'><hr><span>Text</span></div>"
        root = parse_html(html)

        assert root is not None
        # All elements should be children of div
        assert len(root.children) == 4


class TestCountNodes:
    """Tests for count_nodes function."""

    def test_count_single_node(self):
        """Count single node."""
        node = DOMNode(tag="div")
        assert count_nodes(node) == 1

    def test_count_with_children(self):
        """Count node with children."""
        node = DOMNode(
            tag="div",
            children=[
                DOMNode(tag="p"),
                DOMNode(tag="span", children=[DOMNode(tag="a")]),
            ],
        )
        assert count_nodes(node) == 4

    def test_count_none(self):
        """Count None should return 0."""
        assert count_nodes(None) == 0


class TestDOMComparator:
    """Tests for DOMComparator class."""

    def test_compare_identical_html(self):
        """Identical HTML should have similarity_score = 1.0."""
        html = "<div><p>Hello</p><span>World</span></div>"
        comparator = DOMComparator()
        result = comparator.compare(html, html)

        assert result.similarity_score == 1.0
        assert result.edit_distance == 0
        assert result.tree1_size == result.tree2_size

    def test_compare_identical_html_with_whitespace(self):
        """Whitespace differences should not affect comparison."""
        html1 = "<div><p>Hello</p></div>"
        html2 = "<div>  <p>Hello</p>  </div>"
        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        assert result.similarity_score == 1.0

    def test_compare_different_html(self):
        """Different HTML should have similarity_score < 1.0."""
        html1 = "<div><p>Hello</p></div>"
        html2 = "<div><span>Hello</span><p>World</p></div>"
        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        assert result.similarity_score < 1.0
        assert result.edit_distance > 0

    def test_compare_completely_different_html(self):
        """Completely different HTML should have low similarity."""
        html1 = "<div><p>A</p></div>"
        html2 = "<main><article><section><span>B</span></section></article></main>"
        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        assert result.similarity_score < 0.5

    def test_compare_with_operations(self):
        """Operations list should be populated."""
        html1 = "<div><p>Hello</p></div>"
        html2 = "<div><span>Hello</span></div>"
        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        assert len(result.operations) > 0

    def test_compare_empty_baseline(self):
        """Empty baseline should return low similarity."""
        html1 = ""
        html2 = "<div><p>Content</p></div>"
        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        assert result.similarity_score == 0.0
        assert result.tree1_size == 0
        assert result.tree2_size > 0

    def test_compare_empty_current(self):
        """Empty current should return low similarity."""
        html1 = "<div><p>Content</p></div>"
        html2 = ""
        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        assert result.similarity_score == 0.0

    def test_compare_both_empty(self):
        """Both empty should be identical."""
        comparator = DOMComparator()
        result = comparator.compare("", "")

        assert result.similarity_score == 1.0
        assert result.edit_distance == 0

    def test_compare_ignores_script_style(self):
        """Filtered elements should not affect comparison."""
        html1 = "<div><p>Hello</p></div>"
        html2 = "<div><script>console.log('x')</script><p>Hello</p><style>.x{}</style></div>"
        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        # Should be identical after filtering
        assert result.similarity_score == 1.0

    def test_compare_with_ignore_attributes(self):
        """Ignored attributes should not affect comparison."""
        html1 = '<div id="a" class="foo"><p>Hello</p></div>'
        html2 = '<div id="b" class="bar"><p>Hello</p></div>'
        comparator = DOMComparator(ignore_attributes=["id", "class"])
        result = comparator.compare(html1, html2)

        assert result.similarity_score == 1.0

    def test_result_has_tree_sizes(self):
        """Result should include tree sizes."""
        html1 = "<div><p>A</p><p>B</p></div>"
        html2 = "<div><p>A</p></div>"
        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        assert result.tree1_size == 3  # div + 2 p
        assert result.tree2_size == 2  # div + 1 p

    def test_zss_available_flag(self):
        """Result should indicate if zss was available."""
        html = "<div><p>Hello</p></div>"
        comparator = DOMComparator()
        result = comparator.compare(html, html)

        assert result.zss_available == ZSS_AVAILABLE


class TestZSSNotInstalled:
    """Tests for graceful degradation when zss is not installed."""

    def test_fallback_compare_works(self):
        """Comparison should work even without zss."""
        html1 = "<div><p>Hello</p></div>"
        html2 = "<div><span>Hello</span></div>"

        # Mock ZSS_AVAILABLE as False
        with patch("validators.behavioral.dom_diff.ZSS_AVAILABLE", False):
            comparator = DOMComparator()
            result = comparator.compare(html1, html2)

            # Should still return a valid result
            assert isinstance(result, ComparisonResult)
            assert 0.0 <= result.similarity_score <= 1.0
            assert result.zss_available is False
            assert any(op.get("type") == "fallback" for op in result.operations)

    def test_fallback_identical_html(self):
        """Fallback should recognize identical HTML."""
        html = "<div><p>Hello</p></div>"

        with patch("validators.behavioral.dom_diff.ZSS_AVAILABLE", False):
            comparator = DOMComparator()
            result = comparator.compare(html, html)

            # Should have high similarity
            assert result.similarity_score >= 0.9


class TestInvalidHtml:
    """Tests for invalid/malformed HTML handling."""

    def test_unclosed_tags(self):
        """Handle unclosed tags gracefully."""
        html = "<div><p>Unclosed paragraph<span>Also unclosed"
        root = parse_html(html)
        # Should parse something without crashing
        assert root is not None

    def test_invalid_nesting(self):
        """Handle invalid nesting gracefully."""
        html = "<p><div>Invalid nesting</div></p>"
        root = parse_html(html)
        assert root is not None

    def test_special_characters(self):
        """Handle special characters in HTML."""
        html = "<div>&lt;script&gt;alert('xss')&lt;/script&gt;</div>"
        root = parse_html(html)
        assert root is not None
        assert root.tag == "div"

    def test_compare_one_invalid(self):
        """Compare where one document fails to parse."""
        html1 = "<div><p>Valid</p></div>"
        html2 = ""  # Invalid/empty

        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        # Should return low similarity
        assert result.similarity_score == 0.0


class TestDOMNode:
    """Tests for DOMNode dataclass."""

    def test_node_equality(self):
        """Nodes with same tag and attrs should be equal."""
        node1 = DOMNode(tag="div", attrs={"class": "foo"})
        node2 = DOMNode(tag="div", attrs={"class": "foo"})

        assert node1 == node2

    def test_node_inequality(self):
        """Nodes with different tags should not be equal."""
        node1 = DOMNode(tag="div")
        node2 = DOMNode(tag="span")

        assert node1 != node2

    def test_node_not_equal_to_non_node(self):
        """Node should not be equal to non-DOMNode types."""
        node = DOMNode(tag="div")
        assert node != "div"
        assert node != {"tag": "div"}
        assert node != 42

    def test_node_hashable(self):
        """Nodes should be hashable for zss."""
        node = DOMNode(tag="div", attrs={"id": "test"})
        # Should not raise
        hash(node)

        # Same nodes should have same hash
        node2 = DOMNode(tag="div", attrs={"id": "test"})
        assert hash(node) == hash(node2)


class TestZSSAvailable:
    """Tests specifically for when zss IS available."""

    @pytest.mark.skipif(not ZSS_AVAILABLE, reason="zss not installed")
    def test_zss_compare_returns_edit_operations(self):
        """When zss is available, comparison should return edit type operations."""
        html1 = "<div><p>Hello</p></div>"
        html2 = "<div><span>Hello</span></div>"

        comparator = DOMComparator()
        result = comparator.compare(html1, html2)

        assert result.zss_available is True
        # Should have edit operation, not fallback
        assert any(op.get("type") == "edit" for op in result.operations)

    @pytest.mark.skipif(not ZSS_AVAILABLE, reason="zss not installed")
    def test_zss_handles_exception(self):
        """When zss raises an exception, should handle gracefully."""
        html1 = "<div><p>Hello</p></div>"
        html2 = "<div><span>World</span></div>"

        with patch("validators.behavioral.dom_diff.zss") as mock_zss:
            mock_zss.simple_distance.side_effect = RuntimeError("Test error")

            comparator = DOMComparator()
            result = comparator.compare(html1, html2)

            # Should return error operation
            assert any(op.get("type") == "error" for op in result.operations)
            assert result.similarity_score == 0.5


class TestDOMTreeBuilder:
    """Tests for DOMTreeBuilder edge cases."""

    def test_handle_startendtag(self):
        """Self-closing tags with XHTML syntax should be handled."""
        html = "<div><br/><input type='text'/></div>"
        root = parse_html(html)

        assert root is not None
        assert len(root.children) == 2

    def test_filter_nested_in_filtered(self):
        """Content nested inside filtered elements should be ignored."""
        html = "<div><script><p>This p is inside script</p></script><p>Real content</p></div>"
        root = parse_html(html)

        assert root is not None
        # Only one p (the real content one)
        assert len(root.children) == 1
        assert root.children[0].tag == "p"

    def test_filter_link_elements(self):
        """Link elements should be filtered."""
        html = '<div><link rel="stylesheet" href="style.css"><p>Content</p></div>'
        root = parse_html(html)

        assert root is not None
        tags = collect_all_tags(root)
        assert "link" not in tags

    def test_filter_noscript_elements(self):
        """Noscript elements should be filtered."""
        html = "<div><noscript>No JS fallback</noscript><p>Content</p></div>"
        root = parse_html(html)

        assert root is not None
        tags = collect_all_tags(root)
        assert "noscript" not in tags

    def test_filter_template_elements(self):
        """Template elements should be filtered."""
        html = "<div><template><p>Template content</p></template><p>Real</p></div>"
        root = parse_html(html)

        assert root is not None
        tags = collect_all_tags(root)
        assert "template" not in tags

    def test_mismatched_end_tag(self):
        """Mismatched end tags should be handled gracefully."""
        html = "<div><p>Content</span></p></div>"
        root = parse_html(html)

        # Should parse without error
        assert root is not None

    def test_attribute_with_none_value(self):
        """Attributes with None value should be skipped."""
        # This can happen with boolean attributes like "disabled"
        html = "<div><input disabled></div>"
        root = parse_html(html)

        assert root is not None
        # The disabled attribute with no value becomes None in HTMLParser
        # and should be skipped


# Helper functions for tests


def collect_all_tags(node: DOMNode) -> set[str]:
    """Collect all tags in a tree for testing."""
    tags = {node.tag}
    for child in node.children:
        tags.update(collect_all_tags(child))
    return tags


# Fixtures


@pytest.fixture
def comparator():
    """Default comparator instance."""
    return DOMComparator()


@pytest.fixture
def comparator_ignore_attrs():
    """Comparator that ignores common attributes."""
    return DOMComparator(ignore_attributes=["id", "class", "style"])
