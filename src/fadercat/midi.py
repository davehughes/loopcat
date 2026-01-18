"""MIDI engine for fadercat - focused on CC messages."""

from typing import Optional

import mido


DEFAULT_PORT_NAME = "Fadercat"


class MidiEngine:
    """MIDI output engine for sending control change messages."""

    def __init__(self) -> None:
        """Initialize the MIDI engine."""
        self.output: Optional[mido.ports.BaseOutput] = None
        self.channel: int = 0  # 0-15 (displayed as 1-16)
        self.port_name: str = ""
        self.is_virtual: bool = False

    def list_outputs(self) -> list[str]:
        """Get list of available MIDI output ports.

        Returns:
            List of MIDI output port names.
        """
        return mido.get_output_names()

    def open_virtual(self, port_name: str = DEFAULT_PORT_NAME) -> bool:
        """Open a virtual MIDI output port.

        Creates a virtual port that other applications can connect to.

        Args:
            port_name: Name for the virtual port.

        Returns:
            True if port opened successfully, False otherwise.
        """
        try:
            if self.output:
                self.output.close()
            self.output = mido.open_output(port_name, virtual=True)
            self.port_name = port_name
            self.is_virtual = True
            return True
        except (OSError, IOError):
            self.output = None
            self.port_name = ""
            self.is_virtual = False
            return False

    def connect(self, port_name: str) -> bool:
        """Connect to a MIDI output port.

        Args:
            port_name: Name of the MIDI port to connect to.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            if self.output:
                self.output.close()
            self.output = mido.open_output(port_name)
            self.port_name = port_name
            self.is_virtual = False
            return True
        except (OSError, IOError):
            self.output = None
            self.port_name = ""
            return False

    def disconnect(self) -> None:
        """Disconnect from the current MIDI output."""
        if self.output:
            self.output.close()
            self.output = None
        self.port_name = ""
        self.is_virtual = False

    def set_channel(self, channel: int) -> None:
        """Set the MIDI channel (0-15).

        Args:
            channel: MIDI channel (0-15, displayed as 1-16).
        """
        self.channel = max(0, min(15, channel))

    def cc(self, cc_number: int, value: int) -> None:
        """Send a control change message.

        Args:
            cc_number: CC number (0-127).
            value: CC value (0-127).
        """
        if self.output:
            # Clamp values to valid range
            cc_number = max(0, min(127, cc_number))
            value = max(0, min(127, value))
            msg = mido.Message(
                "control_change",
                control=cc_number,
                value=value,
                channel=self.channel,
            )
            self.output.send(msg)

    def note_on(self, note: int, velocity: int = 100) -> None:
        """Send a note on message.

        Args:
            note: MIDI note number (0-127).
            velocity: Note velocity (0-127).
        """
        if self.output:
            msg = mido.Message(
                "note_on", note=note, velocity=velocity, channel=self.channel
            )
            self.output.send(msg)

    def note_off(self, note: int) -> None:
        """Send a note off message.

        Args:
            note: MIDI note number (0-127).
        """
        if self.output:
            msg = mido.Message("note_off", note=note, velocity=0, channel=self.channel)
            self.output.send(msg)

    @property
    def is_connected(self) -> bool:
        """Check if connected to a MIDI output."""
        return self.output is not None
