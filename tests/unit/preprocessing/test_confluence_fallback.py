import textwrap


def test_markdown_to_confluence_fallback_generates_code_macro(monkeypatch):
    """Force the md2conf path to fail and verify fallback output.

    Ensures that code blocks become Confluence code macros and basic
    formatting (bold/italic/links/blockquote) is preserved.
    """
    from mcp_atlassian.preprocessing import confluence as conf_module
    from mcp_atlassian.preprocessing.confluence import ConfluencePreprocessor

    # Force elements_from_string to raise so the fallback path is used
    def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("forced parse error for fallback")

    monkeypatch.setattr(conf_module, "elements_from_string", _raise)

    markdown_with_styles = textwrap.dedent(
        """
        # Title with **bold** text

        This paragraph has *italic* and **bold** text.

        ```python
        def hello():
            return "world"
        ```

        - Item with **bold**
        - Item with *italic*

        > Blockquote with **formatting**

        [Link text](https://example.com) with description.
        """
    ).strip()

    pre = ConfluencePreprocessor(base_url="https://example.atlassian.net")
    result = pre.markdown_to_confluence_storage(markdown_with_styles)

    # Code macro present
    assert "ac:structured-macro" in result
    assert 'ac:name="code"' in result
    assert "python" in result

    # Basic formatting preserved
    assert "<strong>bold</strong>" in result
    assert "<em>italic</em>" in result
    assert "<blockquote>" in result
    assert '<a href="https://example.com">Link text</a>' in result
