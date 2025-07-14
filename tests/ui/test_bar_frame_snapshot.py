from rich.text import Text
from rune.adapters.ui.components import bar_frame

def test_bar_frame_snapshot(snapshot):
    result = bar_frame(
        body=Text("Hello, world!\nThis is a test."),
        glyph=">",
        bar_style="bold green",
    )
    snapshot.assert_match(str(result))
