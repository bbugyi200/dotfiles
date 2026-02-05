"""Tests for the strip_html_comments function."""

from gemini_wrapper.file_references import strip_html_comments


def test_no_comments_unchanged() -> None:
    """Text without comments should be returned unchanged."""
    text = "Hello world\nNo comments here."
    assert strip_html_comments(text) == text


def test_single_line_comment_stripped() -> None:
    """Single-line HTML comment should be stripped."""
    text = "Before <!-- comment --> After"
    assert strip_html_comments(text) == "Before  After"


def test_multi_line_comment_stripped() -> None:
    """Multi-line HTML comment should be stripped."""
    text = "Before\n<!-- this is\na multi-line\ncomment -->\nAfter"
    assert strip_html_comments(text) == "Before\n\nAfter"


def test_prettier_ignore_stripped() -> None:
    """<!-- prettier-ignore --> comments should be stripped."""
    text = "<!-- prettier-ignore -->\n| Column 1 | Column 2 |"
    assert strip_html_comments(text) == "\n| Column 1 | Column 2 |"


def test_multiple_comments_stripped() -> None:
    """Multiple comments should all be stripped."""
    text = "Start <!-- c1 --> Middle <!-- c2 --> End"
    assert strip_html_comments(text) == "Start  Middle  End"


def test_comments_in_code_blocks_preserved() -> None:
    """Comments inside fenced code blocks should be preserved."""
    text = """Some text
```html
<!-- This comment should stay -->
<div>Content</div>
```
More text"""
    result = strip_html_comments(text)
    assert "<!-- This comment should stay -->" in result
    assert "Some text" in result
    assert "More text" in result


def test_mixed_comments_in_and_outside_code_blocks() -> None:
    """Comments outside code blocks stripped, inside preserved."""
    text = """<!-- strip this -->
```python
# <!-- keep this -->
print("hello")
```
<!-- strip this too -->
Done"""
    result = strip_html_comments(text)
    assert "strip this" not in result
    assert "<!-- keep this -->" in result
    assert "Done" in result


def test_empty_string() -> None:
    """Empty string should return empty string."""
    assert strip_html_comments("") == ""


def test_text_that_is_only_comment() -> None:
    """Text that is only a comment should return empty string."""
    assert strip_html_comments("<!-- just a comment -->") == ""


def test_comment_with_dashes_inside() -> None:
    """Comment with dashes inside should be handled correctly."""
    text = "Before <!-- comment -- with -- dashes --> After"
    assert strip_html_comments(text) == "Before  After"


def test_code_block_with_language_specifier() -> None:
    """Code blocks with language specifier should be handled."""
    text = """<!-- remove me -->
```javascript
// <!-- keep this comment -->
const x = 1;
```"""
    result = strip_html_comments(text)
    assert "remove me" not in result
    assert "<!-- keep this comment -->" in result


def test_multiple_code_blocks() -> None:
    """Multiple code blocks should all preserve their comments."""
    text = """<!-- strip 1 -->
```html
<!-- keep 1 -->
```
<!-- strip 2 -->
```xml
<!-- keep 2 -->
```
<!-- strip 3 -->"""
    result = strip_html_comments(text)
    assert "strip 1" not in result
    assert "strip 2" not in result
    assert "strip 3" not in result
    assert "<!-- keep 1 -->" in result
    assert "<!-- keep 2 -->" in result
