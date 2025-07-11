from __future__ import annotations

import httpx
from html_to_markdown import convert_to_markdown
from rich.console import Group
from rich.markdown import Markdown
from rich.text import Text

from rune.core.tool_result import ToolResult
from rune.tools.registry import register_tool


def _create_renderable(
    status: str, markdown_content: str | None, url: str | None, error: str | None
) -> Group:
    if status == "error":
        header_text = f"┌─ ! Error visiting {url} "
        header = Text(header_text + "─" * (70 - len(header_text)), style="bold red")
        error_line = Text(f"│  {error or 'Unknown error'}", style="red")
        footer = Text("└" + "─" * 69, style="red")
        return Group(header, error_line, footer)

    header_text = f"┌─ ☍ {url} "
    header = Text(header_text + "─" * (70 - len(header_text)), style="bold blue")

    body = [header]
    if markdown_content:
        body.append(Markdown(markdown_content))

    footer = Text("└" + "─" * 69, style="blue")
    body.append(footer)

    return Group(*body)


@register_tool(needs_ctx=False)
def fetch_url(url: str, *, timeout: int = 30) -> ToolResult:
    """Fetches the content of a given URL and returns it as clean Markdown.

    This tool is suitable for retrieving the content of web pages. It will
    attempt to convert HTML content into a structured Markdown format. It is
    not suitable for downloading binary files. The tool follows redirects and
    will raise an error for non-2xx HTTP status codes.

    Args:
        url: The full URL to fetch, including the scheme (e.g., "https://...").
        timeout: The maximum time in seconds to wait for a response from the
            server. Defaults to 30.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()

        ctype = resp.headers.get("content-type", "")
        if "text/html" not in ctype:
            raise ValueError(f"Expected HTML, got '{ctype}'.")

        markdown = convert_to_markdown(resp.text)

        return ToolResult(
            data={"status": "success", "markdown_content": markdown, "url": url},
            renderable=_create_renderable("success", markdown, url, None),
        )

    except httpx.RequestError as e:
        raise ConnectionError(f"Network error visiting {e.request.url}: {e}") from e
    except httpx.HTTPStatusError as e:
        raise ValueError(
            f"HTTP error {e.response.status_code} for {e.request.url}"
        ) from e
    except Exception as exc:
        raise ValueError(f"Failed HTML→Markdown: {exc}") from exc
