# src/rune/adapters/ui/glyphs.py

GLYPH = {
    # User - keep the bright blue, it's energetic and clear
    "user": ("│", "#00b4d8"),  # Slightly deeper, more accessible blue
    # Assistant - warmer, friendlier purple
    "assistant_bar": ("│", "#9c88ff"),  # Lavender purple - softer, more approachable
    # Thinking - subtle but visible
    "thinking_bar": ("│", "#9e9e9e"),  # Cool grey with slight blue tint
    # Tool interactions - unified teal family
    "tool_call": ("⚙️", "#00bfa5"),  # Vibrant teal
    "tool_call_bar": ("│", "#00bfa5"),  # Match the icon color for consistency
    "tool_result": ("✓", "#00c853"),  # Pure success green
    "tool_result_bar": ("│", "#00c853"),  # Match for consistency
    "tool_error": ("✗", "#ff5252"),  # Keep your red, it's perfect
    "tool_error_bar": ("│", "#ff5252"),  # Match the error color
    "thinking_text": ("[Thinking...]", "#9e9e9e"),  # Match thinking bar
}

INDENT = "  "
PREVIEW_TURNS = 5
