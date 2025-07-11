# ctxl_coder/utils/diff.py
# Contains utilities for generating diffs and applying diff patches.

import difflib
import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from rich.text import Text


def generate_and_format_diff(
    original_content: str, new_content: str, path_str: str
) -> Text:
    """Generates a unified diff and formats it for Rich display."""
    diff_text = Text()
    if original_content == new_content:
        return diff_text  # No changes

    original_lines = original_content.splitlines()
    new_lines = new_content.splitlines()
    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{path_str}",
        tofile=f"b/{path_str}",
        lineterm="",
        n=3,  # Context lines
    )

    lines = list(diff)
    if not lines:
        return diff_text  # Should not happen if content differs

    for line in lines:
        style = ""
        if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@ "):
            style = "dim cyan"
        elif line.startswith("-"):
            style = "red"
        elif line.startswith("+"):
            style = "green"
        else:
            style = "dim"  # Context lines
        diff_text.append(line + "\n", style=style)

    return diff_text


# --- DiffApplyer Logic ---

log = logging.getLogger(__name__)  # Logger specific to this module

# --- Constants ---
DEFAULT_FUZZY_THRESHOLD_FOR_ERROR_REPORTING = (
    0.85  # Threshold for suggesting "Did you mean?"
)
FUZZY_CONTEXT_LINES = 2  # Lines of context before/after fuzzy match snippet


# --- Data Structures for Results ---
@dataclass
class MatchResult:
    """Result of attempting to find a search block."""

    found: bool = False
    is_unique: bool = True
    start_index: int | None = None  # Character index
    end_index: int | None = None  # Character index (exclusive)
    match_type: str = "none"  # E.g., 'exact', 'whitespace', 'anchor', 'ellipsis'
    error: str | None = None
    similarity_score: float = 0.0  # For fuzzy reporting if needed
    # Store multiple locations if not unique
    match_locations: list[tuple[int, int]] = field(default_factory=list)
    # Added for fuzzy match reporting:
    best_match_snippet: str | None = None  # The actual lines that matched best
    context_snippet: str | None = None  # Lines around the best match


def _get_common_prefix_indent(lines: list[str]) -> str:
    """Calculates the longest common leading whitespace prefix for non-empty lines."""
    relevant_indents = []
    for line in lines:
        if line.strip():  # Consider non-empty, non-whitespace-only lines
            leading_whitespace = line[: len(line) - len(line.lstrip())]
            relevant_indents.append(leading_whitespace)

    if not relevant_indents:
        return ""  # No relevant lines found or all lines were empty/whitespace

    if not relevant_indents:
        return ""  # Should not happen if lines has content, but defensive

    # Handle case where only one relevant line exists
    if len(relevant_indents) == 1:
        return relevant_indents[0]

    # Start with the shortest indent as the potential common prefix
    common_prefix = min(relevant_indents, key=len)

    # Verify that all other relevant indents start with this prefix, shortening it if necessary
    for indent in relevant_indents:
        while not indent.startswith(common_prefix):
            if not common_prefix:  # Cannot shorten further, no common prefix exists
                return ""
            common_prefix = common_prefix[:-1]  # Shorten by one character from the end

    return common_prefix


@dataclass
class AppliedBlockInfo:
    """Information about a successfully applied block."""

    original_index: int  # Index in the input diff string
    match_type: str
    applied_at_char_index: int
    similarity_score: float | None = None  # Only relevant for non-exact matches


@dataclass
class FailedBlockInfo:
    """Information about a block that failed to apply."""

    original_index: int  # Index in the input diff string, or -1 for pre-check failures
    error_reason: str
    search_content: str  # Raw search content (or type like <validation>)
    # Fuzzy match details (populated if match failed & fuzzy score > threshold)
    best_match_snippet: str | None = None
    context_snippet: str | None = None
    best_match_score: float = 0.0
    # Non-unique match details (populated if match found but not unique)
    multiple_match_locations: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class ApplyDiffResult:
    """Detailed result of applying all diff blocks."""

    success: bool  # True ONLY if NO validation/parsing errors occurred AND ALL blocks applied successfully.
    final_content: str | None = (
        None  # Final content after applying blocks up to the first failure, or original content if pre-check fails/empty diff.
    )
    applied_blocks: list[AppliedBlockInfo] = field(default_factory=list)
    failed_blocks: list[FailedBlockInfo] = field(
        default_factory=list
    )  # Contains at most one item if success=False due to stop-on-error


def _get_similarity(a: str, b: str) -> float:
    """Calculates the similarity ratio between two strings."""
    return SequenceMatcher(isjunk=None, a=a, b=b, autojunk=False).ratio()


# --- Core Diff Logic Class ---
class DiffApplyer:
    def __init__(
        self,
        # Fuzzy threshold for *reporting* 'did you mean' errors
        fuzzy_threshold_error: float = DEFAULT_FUZZY_THRESHOLD_FOR_ERROR_REPORTING,
    ):
        self.fuzzy_threshold_error = fuzzy_threshold_error
        # Threshold for *applying* fuzzy matches is effectively 1.0 (only exact/whitespace/anchor/ellipsis apply)
        log.info(
            f"DiffApplyer initialized (Error Report Threshold={fuzzy_threshold_error})"
        )

    def _validate_marker_sequencing(self, diff_content: str) -> str | None:
        """Checks for correct marker sequence."""
        current_state = "START"
        line_num = 0
        SEARCH_MARKER = "<<<<<<< SEARCH"
        SEP_MARKER = "======="
        REPLACE_MARKER = ">>>>>>> REPLACE"
        MARKER_PREFIXES = ("<<<<<<<", "=======", ">>>>>>>")

        lines = diff_content.splitlines()
        for line in lines:
            line_num += 1
            marker = line.strip()
            is_escaped = line.startswith("\\") and marker.lstrip("\\") in (
                SEARCH_MARKER,
                SEP_MARKER,
                REPLACE_MARKER,
            )
            is_real_marker = not is_escaped and marker in (
                SEARCH_MARKER,
                SEP_MARKER,
                REPLACE_MARKER,
            )

            # Skip escaped markers
            if is_escaped:
                continue

            # Check for potential *unescaped* markers within content lines
            if current_state != "START" and not is_real_marker:
                # Check if line *looks* like a marker but isn't the expected one
                if any(
                    marker.startswith(p) for p in MARKER_PREFIXES
                ) and marker not in (SEARCH_MARKER, SEP_MARKER, REPLACE_MARKER):
                    return f"ERROR: Malformed diff: Found potential invalid marker '{marker}' at line {line_num}. Check syntax or escape it like '\\{marker.lstrip()}'."
                elif any(marker.startswith(p) for p in MARKER_PREFIXES):
                    # This case should be caught by state transitions below, but added for extra safety
                    pass  # Let state machine handle valid markers

            # State machine transitions
            if current_state == "START":
                if is_real_marker and marker != SEARCH_MARKER:
                    return f"ERROR: Malformed diff: Expected '{SEARCH_MARKER}' but found '{marker}' at line {line_num}."
                if is_real_marker and marker == SEARCH_MARKER:
                    current_state = "AFTER_SEARCH"
            elif current_state == "AFTER_SEARCH":
                if is_real_marker and marker != SEP_MARKER:
                    return f"ERROR: Malformed diff: Expected '{SEP_MARKER}' but found '{marker}' at line {line_num}."
                if is_real_marker and marker == SEP_MARKER:
                    current_state = "AFTER_SEPARATOR"
            elif current_state == "AFTER_SEPARATOR":
                if is_real_marker and marker != REPLACE_MARKER:
                    return f"ERROR: Malformed diff: Expected '{REPLACE_MARKER}' but found '{marker}' at line {line_num}."
                if is_real_marker and marker == REPLACE_MARKER:
                    current_state = "START"  # Ready for next block or end of diff

        if current_state != "START":
            expected = SEP_MARKER if current_state == "AFTER_SEARCH" else REPLACE_MARKER
            return (
                f"ERROR: Unexpected end of diff: Expected '{expected}' but not found."
            )

        return None

    def _unescape_markers(self, content: str) -> str:
        """Removes escaping backslashes from diff markers if they are at the start of a line."""
        content = re.sub(r"^\\(<<<<<<< SEARCH)", r"\1", content, flags=re.MULTILINE)
        content = re.sub(r"^\\(=======)", r"\1", content, flags=re.MULTILINE)
        content = re.sub(r"^\\(>>>>>>> REPLACE)", r"\1", content, flags=re.MULTILINE)
        return content

    def _char_index_to_line_num(self, text: str, char_index: int) -> int:
        """Converts a character index to a 0-based line number."""
        # Efficiently count newlines up to the index
        return text.count("\n", 0, char_index)

    def _line_num_to_char_index(self, text_lines: list[str], line_num: int) -> int:
        """Converts a 0-based line number to its starting character index."""
        if line_num < 0:
            return 0
        if line_num >= len(text_lines):
            return sum(len(line) + 1 for line in text_lines)  # End of text approx

        char_index = 0
        for i in range(line_num):
            char_index += len(text_lines[i]) + 1  # Add 1 for the newline character
        return char_index

    def _find_match(self, content_to_search_in: str, search_block: str) -> MatchResult:
        """Finds the unique location of the search_block using various strategies."""
        if not search_block.strip():
            return MatchResult(
                error="Empty SEARCH block is not allowed for replacement."
            )

        # --- 1. Exact Match ---
        match_indices = []
        start_index = 0
        while (found_at := content_to_search_in.find(search_block, start_index)) != -1:
            match_indices.append(found_at)
            start_index = found_at + 1  # Start next search after this match

        if len(match_indices) == 1:
            idx = match_indices[0]
            return MatchResult(
                found=True,
                is_unique=True,
                start_index=idx,
                end_index=idx + len(search_block),  # Exact length
                match_type="exact",
                similarity_score=1.0,
            )
        elif len(match_indices) > 1:
            log.warning(
                f"Exact match failed: Found {len(match_indices)} locations for SEARCH block."
            )
            locations = [(idx, idx + len(search_block)) for idx in match_indices]
            return MatchResult(
                found=True,
                is_unique=False,
                error=f"Search block matched {len(match_indices)} exact locations.",
                match_locations=locations,
            )

        # --- 2. Whitespace-Flexible Match ---
        # This needs to return the actual matched segment's start/end in the original content
        ws_results = self._find_whitespace_flexible_match(
            content_to_search_in, search_block
        )
        if len(ws_results) == 1:
            start_idx, end_idx = ws_results[0]
            return MatchResult(
                found=True,
                is_unique=True,
                start_index=start_idx,
                end_index=end_idx,  # Use actual end index from matched segment
                match_type="whitespace",
                similarity_score=0.99,  # Assign high score
            )
        elif len(ws_results) > 1:
            log.warning(
                f"Whitespace-flexible match failed: Found {len(ws_results)} locations."
            )
            return MatchResult(
                found=True,
                is_unique=False,
                error=f"Search block matched {len(ws_results)} locations (whitespace-flexible).",
                match_locations=ws_results,  # Store the found locations
            )

        # --- 3. Block-Anchor Match (Optional but Recommended) ---
        # This also needs to return the actual matched segment's start/end
        if len(search_block.splitlines()) >= 3:
            anchor_results = self._find_anchor_match(content_to_search_in, search_block)
            if len(anchor_results) == 1:
                start_idx, end_idx = anchor_results[0]
                return MatchResult(
                    found=True,
                    is_unique=True,
                    start_index=start_idx,
                    end_index=end_idx,  # Use actual end index
                    match_type="anchor",
                    similarity_score=0.95,  # Assign good score
                )
            elif len(anchor_results) > 1:
                log.warning(
                    f"Anchor match failed: Found {len(anchor_results)} locations."
                )
                return MatchResult(
                    found=True,
                    is_unique=False,
                    error=f"Search block matched {len(anchor_results)} locations (anchor match).",
                    match_locations=anchor_results,  # Store the found locations
                )

        # --- 4. Fuzzy Match (For Error Reporting Only) ---
        # Fuzzy matching does not lead to application, only error reporting.
        # We find the best fuzzy match info here to include in the failure result.
        (
            best_score,
            best_snippet,
            context_snippet,
            _best_indices,
        ) = self._find_best_fuzzy_match_info(content_to_search_in, search_block)

        error_msg = f"No unique match found (best fuzzy score: {best_score:.1%})."
        return MatchResult(
            found=False,  # Explicitly not found by application strategies
            is_unique=False,  # Not unique if not found
            error=error_msg,
            similarity_score=best_score,
            best_match_snippet=best_snippet
            if best_score >= self.fuzzy_threshold_error
            else None,
            context_snippet=context_snippet
            if best_score >= self.fuzzy_threshold_error
            else None,
        )

    def _find_whitespace_flexible_match(
        self, content: str, search: str
    ) -> list[tuple[int, int]]:
        """Finds matches ignoring leading/trailing whitespace on each line. Returns list of (start_char_index, end_char_index)."""
        search_lines = search.splitlines()
        search_lines_stripped = [line.strip() for line in search_lines]
        # Keep empty lines in search for matching structure
        if not search_lines:
            return []  # Cannot match empty search

        content_lines = content.splitlines()
        match_locations = []
        num_search_lines = len(search_lines)
        num_content_lines = len(content_lines)

        if num_search_lines > num_content_lines:
            return []  # Cannot match if search is longer

        current_char_index = 0
        for i in range(num_content_lines - num_search_lines + 1):
            # Calculate start index for this potential match *before* checking lines
            start_char_index = current_char_index

            match = True
            for j in range(num_search_lines):
                if content_lines[i + j].strip() != search_lines_stripped[j]:
                    match = False
                    break
            if match:
                # Calculate end character index based on matched lines
                end_char_index = start_char_index
                for k in range(num_search_lines):
                    end_char_index += len(content_lines[i + k]) + 1  # +1 for newline

                # Adjust end index: remove the last +1 if it's not the end of the *entire* content
                # or if the last matched line didn't have a newline in the original splitlines list
                # A simpler way is to calculate based on the start index and the lengths.
                end_char_index = start_char_index + sum(
                    len(content_lines[i + k]) + 1 for k in range(num_search_lines)
                )
                # If the match extends to the very end of the file AND the original content didn't end with a newline,
                # the last +1 might be wrong. Let's adjust.
                if i + num_search_lines == num_content_lines and not content.endswith(
                    "\n"
                ):
                    end_char_index -= 1

                # More robust end index: start + length of matched segment
                # Account for potentially missing final newline if match is at EOF
                if i + num_search_lines == num_content_lines and not content.endswith(
                    "\n"
                ):
                    # The join added newlines we didn't have in the original segment string
                    # Let's calculate end based on character indices more directly
                    end_char_index = self._line_num_to_char_index(
                        content_lines, i + num_search_lines
                    )
                    # If not EOF, the index is start of next line. If EOF without newline, need to adjust.
                    if end_char_index > 0 and content[end_char_index - 1] == "\n":
                        end_char_index -= 1  # remove trailing newline char count

                else:
                    # If not at EOF, the end index should be the start of the line *after* the match
                    end_char_index = self._line_num_to_char_index(
                        content_lines, i + num_search_lines
                    )

                # Correct approach: Find start index of line i, find start index of line i + num_search_lines
                start_idx_calc = self._line_num_to_char_index(content_lines, i)
                end_idx_calc = self._line_num_to_char_index(
                    content_lines, i + num_search_lines
                )

                match_locations.append((start_idx_calc, end_idx_calc))

            # Update current_char_index for the next iteration
            current_char_index += len(content_lines[i]) + 1

        return match_locations

    def _find_anchor_match(self, content: str, search: str) -> list[tuple[int, int]]:
        """Finds matches based on first and last lines (stripped). Returns list of (start_char_index, end_char_index)."""
        search_lines = search.splitlines()
        if len(search_lines) < 3:
            return []  # Anchor requires at least 3 lines

        search_first_stripped = search_lines[0].strip()
        search_last_stripped = search_lines[-1].strip()
        search_len_lines = len(search_lines)  # Number of lines in search block

        if not search_first_stripped or not search_last_stripped:
            log.debug(
                "Anchor match skipped: First or last line of search block is empty/whitespace."
            )
            return []  # Avoid matching purely on whitespace anchors

        content_lines = content.splitlines()
        match_locations = []
        num_content_lines = len(content_lines)

        if search_len_lines > num_content_lines:
            return []

        for i in range(num_content_lines - search_len_lines + 1):
            first_content_line = content_lines[i]
            last_content_line = content_lines[i + search_len_lines - 1]

            if (
                first_content_line.strip() == search_first_stripped
                and last_content_line.strip() == search_last_stripped
            ):
                # Calculate precise start and end character indices
                start_char_index = self._line_num_to_char_index(content_lines, i)
                end_char_index = self._line_num_to_char_index(
                    content_lines, i + search_len_lines
                )
                match_locations.append((start_char_index, end_char_index))

        return match_locations

    def _find_best_fuzzy_match_info(
        self, content_to_search_in: str, search_block: str
    ) -> tuple[float, str | None, str | None, tuple[int, int] | None]:
        """Finds the best fuzzy match for error reporting. Returns (score, best_match_snippet, context_snippet, (start_line, end_line))."""
        if not search_block or not content_to_search_in:
            return 0.0, None, None, None

        search_lines = search_block.splitlines()
        content_lines = content_to_search_in.splitlines()
        len_search = len(search_lines)
        len_content = len(content_lines)

        if len_search == 0 or len_content == 0 or len_search > len_content:
            return 0.0, None, None, None

        best_score = 0.0
        best_match_line_indices = None  # Store 0-based line indices

        # Iterate through all possible subsegments of content_lines matching search_lines length
        for i in range(len_content - len_search + 1):
            original_slice_lines = content_lines[i : i + len_search]
            original_slice_str = "\n".join(original_slice_lines)
            # Use SequenceMatcher on the joined strings for fuzzy comparison
            similarity = _get_similarity(original_slice_str, search_block)

            if similarity > best_score:
                best_score = similarity
                # Store 0-based line indices
                best_match_line_indices = (i, i + len_search)

        if best_match_line_indices is None:
            return 0.0, None, None, None

        # Construct snippets if a best match was found
        start_line, end_line = best_match_line_indices
        best_match_snippet = "\n".join(content_lines[start_line:end_line])

        # Get context snippet
        context_start = max(0, start_line - FUZZY_CONTEXT_LINES)
        context_end = min(len_content, end_line + FUZZY_CONTEXT_LINES)
        context_snippet = "\n".join(content_lines[context_start:context_end])

        # Return 1-based line numbers for potential display
        display_indices = (start_line + 1, end_line)

        return best_score, best_match_snippet, context_snippet, display_indices

    def _apply_indentation(
        self,
        matched_original_segment: str,
        search_block_content: str,
        replace_block_content: str,
        line_ending: str = "\n",
    ) -> str:
        """Applies relative indentation based on common prefixes of non-empty lines."""
        # Edge case: If replace block is empty, return empty string
        if (
            not replace_block_content.strip() and not replace_block_content
        ):  # Truly empty
            return ""

        original_lines = matched_original_segment.splitlines()
        search_lines = search_block_content.splitlines()
        replace_lines = replace_block_content.splitlines()

        # Determine the significant base indentation of the original matched block
        base_indent = _get_common_prefix_indent(original_lines)
        # Determine the significant base indentation within the user's SEARCH block
        search_base_indent = _get_common_prefix_indent(search_lines)

        indented_replace_lines = []
        for line in replace_lines:
            if not line.strip():  # Handle empty or whitespace-only lines
                # If line has only whitespace, preserve it relative to the new base indent
                # If line is truly empty, keep it empty.
                indented_replace_lines.append(base_indent + line if line else "")
                continue

            # For lines with content:
            current_line_indent = line[: len(line) - len(line.lstrip())]
            # relative_indent = "" # Removed as final_line is now determined in each branch

            if search_base_indent and current_line_indent.startswith(
                search_base_indent
            ):
                # Line in REPLACE is indented same or more than SEARCH block's base
                relative_indent = current_line_indent[len(search_base_indent) :]
                final_line = base_indent + relative_indent + line.lstrip()
            elif not search_base_indent:
                # SEARCH block has no specific base indent (e.g., starts at column 0).
                # The REPLACE line's indent is added to the file's matched base_indent.
                relative_indent = current_line_indent
                final_line = base_indent + relative_indent + line.lstrip()
            else:  # search_base_indent exists AND current_line_indent does NOT start with search_base_indent (outdent/cross-indent)
                log.warning(
                    f"Replace line indentation '{current_line_indent.encode('unicode_escape').decode()}' "
                    f"is an outdent/cross-indent relative to SEARCH block base indent "
                    f"'{search_base_indent.encode('unicode_escape').decode()}'. "
                    f"Honoring REPLACE line's indentation directly."
                )
                # Key change: For outdents, the line's own indentation is used directly from the REPLACE block,
                # effectively ignoring base_indent from the matched file segment for this line.
                final_line = current_line_indent + line.lstrip()

            indented_replace_lines.append(final_line)

        replace_final_indented = line_ending.join(indented_replace_lines)

        # Preserve trailing newline if present in the original replace_block_content *and*
        # if the result doesn't already end with the detected line ending.
        # This handles cases where the replace content is a single line without a newline.
        if replace_block_content.endswith(
            line_ending
        ) and not replace_final_indented.endswith(line_ending):
            replace_final_indented += line_ending
        # Also handle CRLF consistency if original had it
        elif (
            replace_block_content.endswith("\r\n")
            and not replace_final_indented.endswith("\r\n")
            and line_ending == "\n"
        ):
            # Less common case, but be safe
            replace_final_indented += "\n"

        return replace_final_indented

    def _handle_ellipsis_block(
        self,
        current_content: str,
        search_block: str,
        replace_block: str,
        line_ending: str,
    ) -> tuple[str | None, str | None]:
        """
        Attempts to apply an edit block containing '...' ellipses.
        Returns (new_content, error_message). error_message is None on success.
        """
        log.debug("Attempting ellipsis block handling.")
        dots_re = re.compile(
            r"^( *\.\.\. *)\n?", re.MULTILINE
        )  # Match lines with just ... and maybe spaces

        search_pieces = dots_re.split(search_block)
        replace_pieces = dots_re.split(replace_block)

        # Filter out empty strings that might result from split
        search_pieces = [p for p in search_pieces if p is not None]
        replace_pieces = [p for p in replace_pieces if p is not None]

        # Basic validation
        if len(search_pieces) != len(replace_pieces):
            return (
                None,
                "Mismatch in the number of '...' sections between SEARCH and REPLACE.",
            )
        if (
            len(search_pieces) <= 1
        ):  # Should have at least one ... separator, meaning >= 3 pieces
            return (
                None,
                "Invalid '...' structure. Must have content around '...' lines.",
            )

        # Ensure pieces alternate between content and '...' marker (cleaned)
        temp_content = current_content
        offset = 0  # Keep track of character offset changes due to replacements

        for i in range(len(search_pieces)):
            is_dots_piece = (
                dots_re.match(search_pieces[i].strip() + "\n") is not None
            )  # Check if the piece *is* a dots line

            if i % 2 == 1:  # Expecting a dots piece
                if not is_dots_piece:
                    return (
                        None,
                        f"Invalid '...' structure: Expected '...' at piece {i + 1} in SEARCH.",
                    )
                if search_pieces[i].strip() != replace_pieces[i].strip():
                    return (
                        None,
                        f"Mismatch in '...' marker content between SEARCH and REPLACE at piece {i + 1}.",
                    )
                # Dots match, continue
                continue
            else:  # Expecting a content piece
                if is_dots_piece:
                    return (
                        None,
                        f"Invalid '...' structure: Expected content, found '...' at piece {i + 1} in SEARCH.",
                    )

                search_part = search_pieces[i]
                replace_part = replace_pieces[i]

                # If both parts are empty (e.g., diff starts/ends with ...), skip finding
                if not search_part.strip() and not replace_part.strip():
                    continue

                # Find the search_part *in the current state of temp_content* starting from the offset
                try:
                    # Exact match required for ellipsis parts
                    found_at = temp_content.index(search_part, offset)
                except ValueError:
                    # Try whitespace flexible match for the part? Could be complex.
                    # Let's stick to exact match for ellipsis parts for now.
                    log.warning(
                        f"Ellipsis sub-part not found exactly: ```{search_part[:100]}...```"
                    )
                    return (
                        None,
                        f"Could not find exact match for content piece {i // 2 + 1} within the '...' block.",
                    )

                # Check for ambiguity? If the part appears multiple times before the next part?
                # This adds complexity, let's assume unique parts for now.

                # Apply indentation based on this specific matched segment
                # We need the original matched segment to calculate base indent
                original_matched_part = temp_content[
                    found_at : found_at + len(search_part)
                ]
                replace_part_indented = self._apply_indentation(
                    original_matched_part, search_part, replace_part, line_ending
                )

                # Replace in temp_content
                temp_content = (
                    temp_content[:found_at]
                    + replace_part_indented
                    + temp_content[found_at + len(search_part) :]
                )
                # Update offset for next search to start *after* the replaced content
                offset = found_at + len(replace_part_indented)

        # If loop completes without error
        log.info("Ellipsis block applied successfully.")
        return temp_content, None

    def apply_diff(self, original_content: str, diff_content: str) -> ApplyDiffResult:
        """
        Applies the multi-block diff string sequentially, stopping on the first error.
        Supports standard blocks and blocks with '...' ellipsis.
        """
        log.info("Starting diff application...")

        # Handle empty diff input gracefully
        if not diff_content.strip():
            log.info("Received empty diff content. No changes to apply.")
            return ApplyDiffResult(success=True, final_content=original_content)

        # --- 1. Validation ---
        validation_error = self._validate_marker_sequencing(diff_content)
        if validation_error:
            log.error(f"Diff validation failed: {validation_error}")
            return ApplyDiffResult(
                success=False,
                final_content=original_content,  # Return original on pre-check fail
                failed_blocks=[
                    FailedBlockInfo(
                        original_index=-1,
                        error_reason=validation_error,
                        search_content="<validation>",
                    )
                ],
            )

        # --- 2. Block Parsing ---
        # Regex to find blocks, ensuring markers are at line start/end properly
        # Handles optional newline before ======= and >>>>>>>
        # Uses non-capturing group (?: ) for marker prefixes
        # Correctly handles escaped markers using negative lookbehind (?<!\\)
        regex_pattern = r"(?:^|\n)(?<!\\)<<<<<<< SEARCH\s*\n([\s\S]*?)(?:\n?)(?<!\\)=======\s*\n([\s\S]*?)(?:\n?)(?<!\\)>>>>>>> REPLACE(?=\n|$)"
        matches = list(re.finditer(regex_pattern, diff_content))

        if not matches:
            # If content exists but no blocks found, it's a parsing error
            log.error(
                "ERROR: Invalid diff format - Could not parse any valid SEARCH/REPLACE blocks. Check markers and escaping (`\\`)."
            )
            return ApplyDiffResult(
                success=False,
                final_content=original_content,
                failed_blocks=[
                    FailedBlockInfo(
                        original_index=-1,
                        error_reason="Invalid diff format: Could not parse any valid SEARCH/REPLACE blocks. Check markers (<<<<<<< SEARCH, =======, >>>>>>> REPLACE), newlines, and escaping (`\\`).",
                        search_content="<parsing>",
                    )
                ],
            )

        # --- 3. Sequential Block Application ---
        current_content = original_content
        applied_blocks_info: list[AppliedBlockInfo] = []
        failed_blocks_info: list[FailedBlockInfo] = []  # Should contain max 1 item
        line_ending = "\r\n" if "\r\n" in original_content else "\n"
        dots_re = re.compile(
            r"^\s*\.\.\.\s*$", re.MULTILINE
        )  # Simple check for ellipsis lines

        for i, match in enumerate(matches):
            search_raw = match.group(1)
            replace_raw = match.group(2)

            search_final = self._unescape_markers(search_raw)
            replace_final = self._unescape_markers(replace_raw)

            log.debug(f"--- Processing Block {i + 1}/{len(matches)} ---")
            log.debug(f"SEARCH (unescaped):\n{search_final[:100]}...")
            log.debug(f"REPLACE (unescaped):\n{replace_final[:100]}...")

            # Check for Ellipsis ('...') presence
            has_ellipsis = dots_re.search(search_final) and dots_re.search(
                replace_final
            )
            match_result = None
            applied_content = None
            ellipsis_error = None

            if has_ellipsis:
                log.debug("Ellipsis detected, attempting specific handler.")
                applied_content, ellipsis_error = self._handle_ellipsis_block(
                    current_content, search_final, replace_final, line_ending
                )
                if ellipsis_error:
                    log.warning(
                        f"Block {i + 1} ellipsis handling failed: {ellipsis_error}"
                    )
                    # Create a failure block and stop processing
                    fail_info = FailedBlockInfo(
                        original_index=i,
                        error_reason=f"Ellipsis block error: {ellipsis_error}",
                        search_content=search_final,
                        # Fuzzy info not applicable here unless we add it to _handle_ellipsis_block
                    )
                    failed_blocks_info.append(fail_info)
                    break  # Stop on first failure
                else:
                    # Ellipsis applied successfully
                    match_result = MatchResult(
                        found=True,
                        is_unique=True,
                        match_type="ellipsis",
                        start_index=-1,
                        end_index=-1,
                    )  # Mark success, indices less relevant here
            else:
                # Standard block: Find match in the *current* content
                match_result = self._find_match(current_content, search_final)

            # --- Handle Match Result (Standard or Ellipsis Success/Failure) ---
            if match_result and match_result.found and match_result.is_unique:
                # --- Apply Change In Memory ---
                log.info(
                    f"Block {i + 1}: Found unique match ({match_result.match_type}). Applying change."
                )

                if match_result.match_type == "ellipsis":
                    # Content already updated by _handle_ellipsis_block
                    current_content = applied_content
                    applied_at_index = (
                        -1
                    )  # Index less meaningful for multi-part ellipsis
                else:
                    # Standard block application
                    match_start = match_result.start_index
                    match_end = match_result.end_index
                    assert match_start is not None and match_end is not None

                    matched_original_segment = current_content[match_start:match_end]

                    # Apply indentation
                    replace_final_indented = self._apply_indentation(
                        matched_original_segment,
                        search_final,
                        replace_final,
                        line_ending,
                    )

                    current_content = (
                        current_content[:match_start]
                        + replace_final_indented
                        + current_content[match_end:]
                    )
                    applied_at_index = match_start

                applied_blocks_info.append(
                    AppliedBlockInfo(
                        original_index=i,
                        match_type=match_result.match_type,
                        applied_at_char_index=applied_at_index,
                        similarity_score=match_result.similarity_score
                        if match_result.match_type != "exact"
                        else None,
                    )
                )
                log.info(
                    f"Applied block {i + 1} using {match_result.match_type} match."
                )

            else:
                # --- Match Failed or Ambiguous (Standard Block) or Ellipsis Failed ---
                reason = (
                    match_result.error
                    if match_result
                    else "Ellipsis block processing failed."
                )
                log.warning(f"Block {i + 1} failed: {reason}")

                fail_info = FailedBlockInfo(
                    original_index=i,
                    error_reason=reason,
                    search_content=search_final,
                    # Populate details from match_result if it exists (standard block failure)
                    best_match_snippet=match_result.best_match_snippet
                    if match_result
                    else None,
                    context_snippet=match_result.context_snippet
                    if match_result
                    else None,
                    best_match_score=match_result.similarity_score
                    if match_result
                    else 0.0,
                    multiple_match_locations=match_result.match_locations
                    if match_result
                    else [],
                )
                failed_blocks_info.append(fail_info)
                # --- Stop on first failure ---
                log.warning(
                    f"Stopping diff application due to failure in block {i + 1}."
                )
                break  # Exit the loop

        # --- Loop Finished (Either completed all blocks or stopped on error) ---
        final_success = not bool(failed_blocks_info)
        if final_success:
            log.info(
                f"Diff application finished successfully. Applied all {len(applied_blocks_info)} blocks."
            )
        else:
            log.warning(
                f"Diff application failed. Applied {len(applied_blocks_info)} block(s) before encountering an error "
                f"in block {failed_blocks_info[0].original_index + 1}."
            )

        return ApplyDiffResult(
            success=final_success,
            final_content=current_content,  # Return content state after successful blocks / up to failure point
            applied_blocks=applied_blocks_info,
            failed_blocks=failed_blocks_info,  # Contains at most one item if success=False
        )
