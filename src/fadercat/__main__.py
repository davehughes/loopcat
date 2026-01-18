"""Entry point for fadercat."""

import argparse


def main() -> None:
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        prog="fadercat",
        description="TUI MIDI fader controller - control CC values with your keyboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Fader Layout (8 faders):
  [Q] [W] [E] [R] [T] [Y] [U] [I]   Increase
  [A] [S] [D] [F] [G] [H] [J] [K]   Decrease

Controls:
  h / l          Select fader left/right
  j / k          Decrease/increase selected fader
  Shift + key    Fine adjustment (+/- 1)
  Ctrl + key     Coarse adjustment (+/- 16)
  Space          Reset selected fader to 0
  ?              Help
  Esc            Quit

Fadercat creates a virtual MIDI port named "Fadercat" that you can
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
        default="Fadercat",
        help="name for the virtual MIDI port (default: Fadercat)",
    )

    args = parser.parse_args()

    # Import and run the TUI
    from fadercat.tui import FadercatApp
    from fadercat.midi import DEFAULT_PORT_NAME

    # Update default port name if specified
    if args.port != DEFAULT_PORT_NAME:
        import fadercat.midi
        fadercat.midi.DEFAULT_PORT_NAME = args.port

    app = FadercatApp()
    app.run()


if __name__ == "__main__":
    main()
