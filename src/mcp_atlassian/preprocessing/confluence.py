"""Confluence-specific text preprocessing module."""

import logging
import shutil
import tempfile
from pathlib import Path

from md2conf.converter import (
    ConfluenceConverterOptions,
    ConfluenceStorageFormatConverter,
    elements_to_string,
    markdown_to_html,
)

# Handle md2conf API changes:
# elements_from_string may be renamed to elements_from_strings
try:
    from md2conf.converter import elements_from_string
except ImportError:
    from md2conf.converter import elements_from_strings as elements_from_string

from .base import BasePreprocessor

logger = logging.getLogger("mcp-atlassian")


class ConfluencePreprocessor(BasePreprocessor):
    """Handles text preprocessing for Confluence content."""

    def __init__(self, base_url: str) -> None:
        """
        Initialize the Confluence text preprocessor.

        Args:
            base_url: Base URL for Confluence API
        """
        super().__init__(base_url=base_url)

    def markdown_to_confluence_storage(
        self, markdown_content: str, *, enable_heading_anchors: bool = False
    ) -> str:
        """
        Convert Markdown content to Confluence storage format (XHTML)

        Args:
            markdown_content: Markdown text to convert
            enable_heading_anchors: Whether to enable automatic heading
                anchor generation (default: False)

        Returns:
            Confluence storage format (XHTML) string
        """
        try:
            # First convert markdown to HTML
            html_content = markdown_to_html(markdown_content)

            # Create a temporary directory for any potential attachments
            temp_dir = tempfile.mkdtemp()

            try:
                # Parse the HTML into an element tree
                root = elements_from_string(html_content)

                # Create converter options
                options = ConfluenceConverterOptions(
                    ignore_invalid_url=True,
                    heading_anchors=enable_heading_anchors,
                    render_mermaid=False,
                )

                # Create a converter
                converter = ConfluenceStorageFormatConverter(
                    options=options,
                    path=Path(temp_dir) / "temp.md",
                    root_dir=Path(temp_dir),
                    page_metadata={},
                    site_metadata={},
                )

                # Transform the HTML to Confluence storage format
                converter.visit(root)

                # Convert the element tree back to a string
                storage_format = elements_to_string(root)

                return str(storage_format)
            finally:
                # Clean up the temporary directory
                shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Error converting markdown to Confluence storage format: {e}")
            logger.exception(e)

            # Fallback strategy:
            # 1) Convert Markdown to HTML
            # 2) Transform fenced code blocks to Confluence code macro
            # 3) Return HTML (without wrapping in an extra paragraph)
            html_content = markdown_to_html(markdown_content)

            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html_content, "html.parser")

                # Convert <pre><code class="language-xxx">...</code></pre>
                # to Confluence code macro
                for pre in soup.find_all("pre"):
                    code = pre.find("code")
                    if not code:
                        continue

                    # Detect language from class like "language-python"
                    language = None
                    if code.has_attr("class"):
                        for cls in code.get("class", []):
                            if cls.startswith("language-"):
                                language = cls.split("-", 1)[1]
                                break

                    code_text = code.get_text()

                    # Build Confluence code macro fragment
                    # Note: Using plain-text-body with CDATA to preserve content
                    macro_parts = [
                        '<ac:structured-macro ac:name="code" ac:schema-version="1">',
                    ]
                    if language:
                        macro_parts.append(
                            '<ac:parameter ac:name="language">'
                            f"{language}"
                            "</ac:parameter>"
                        )
                    macro_parts.append("<ac:plain-text-body><![CDATA[")
                    macro_parts.append(code_text)
                    macro_parts.append("]]></ac:plain-text-body>")
                    macro_parts.append("</ac:structured-macro>")

                    macro_html = "".join(macro_parts)

                    # Replace the <pre> block with the macro HTML
                    pre.replace_with(BeautifulSoup(macro_html, "html.parser"))

                return str(soup)
            except Exception as inner_e:  # noqa: BLE001
                # If BeautifulSoup is unavailable or transformation fails,
                # return the plain HTML as a last resort.
                logger.warning(
                    (
                        "Fallback conversion to Confluence macros failed; "
                        "returning HTML. Error: %s"
                    ),
                    inner_e,
                )
                return html_content

    # Confluence-specific methods can be added here
