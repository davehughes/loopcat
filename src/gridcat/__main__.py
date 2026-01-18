"""Entry point for gridcat."""

import argparse
import sys


def main() -> None:
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        prog="gridcat",
        description="TUI MIDI grid controller - play notes with your keyboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Grid Layout (32 keys):
  [1] [2] [3] [4] [5] [6] [7] [8]   Row 1
  [Q] [W] [E] [R] [T] [Y] [U] [I]   Row 2
  [A] [S] [D] [F] [G] [H] [J] [K]   Row 3
  [Z] [X] [C] [V] [B] [N] [M] [,]   Row 4

Controls:
  Arrow keys     Octave up/down
  Shift + key    Soft velocity
  Ctrl + key     Hard velocity
  :              Command palette (output, channel, theme)
  ?              Help
  Esc            Quit

Gridcat creates a virtual MIDI port named "Gridcat" that you can
connect to in your DAW or other MIDI software.
""",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    parser.add_argument(
        "--port",
        metavar="NAME",
        default="Gridcat",
        help="name for the virtual MIDI port (default: Gridcat)",
    )

    args = parser.parse_args()

    # Import and run the TUI
    from gridcat.tui import GridcatApp
    from gridcat.midi import DEFAULT_PORT_NAME

    # Update default port name if specified
    if args.port != DEFAULT_PORT_NAME:
        import gridcat.midi
        gridcat.midi.DEFAULT_PORT_NAME = args.port

    app = GridcatApp()
    app.run()


if __name__ == "__main__":
    main()
