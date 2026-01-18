"""Tests for gridcat MIDI grid controller."""

from unittest.mock import MagicMock, patch

import pytest


class TestMidiEngine:
    """Tests for gridcat MidiEngine."""

    def test_midi_engine_creation(self):
        """MidiEngine can be instantiated."""
        from gridcat.midi import MidiEngine

        engine = MidiEngine()
        assert engine.output is None
        assert engine.channel == 0
        assert engine.port_name == ""
        assert engine.is_virtual is False

    def test_midi_engine_list_outputs(self):
        """MidiEngine.list_outputs() returns list."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.get_output_names") as mock_get_outputs:
            mock_get_outputs.return_value = ["IAC Driver 1", "USB MIDI"]

            engine = MidiEngine()
            outputs = engine.list_outputs()

            assert isinstance(outputs, list)
            assert len(outputs) == 2
            assert "IAC Driver 1" in outputs

    def test_midi_engine_connect(self):
        """MidiEngine.connect() opens output port."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            result = engine.connect("Test Port")

            assert result is True
            assert engine.is_connected
            mock_open.assert_called_once_with("Test Port")

    def test_midi_engine_connect_failure(self):
        """MidiEngine.connect() handles connection failure."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.open_output") as mock_open:
            mock_open.side_effect = OSError("Port not found")

            engine = MidiEngine()
            result = engine.connect("Invalid Port")

            assert result is False
            assert not engine.is_connected

    def test_midi_engine_note_on_off(self):
        """note_on/note_off send correct messages."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            engine.connect("Test Port")

            # Test note on
            engine.note_on(60, 100)
            mock_port.send.assert_called()
            call_args = mock_port.send.call_args[0][0]
            assert call_args.type == "note_on"
            assert call_args.note == 60
            assert call_args.velocity == 100
            assert call_args.channel == 0

            # Test note off
            mock_port.reset_mock()
            engine.note_off(60)
            mock_port.send.assert_called()
            call_args = mock_port.send.call_args[0][0]
            assert call_args.type == "note_off"
            assert call_args.note == 60
            assert call_args.velocity == 0

    def test_midi_engine_channel_setting(self):
        """MidiEngine respects channel setting."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            engine.connect("Test Port")
            engine.set_channel(5)

            engine.note_on(60, 100)
            call_args = mock_port.send.call_args[0][0]
            assert call_args.channel == 5

    def test_midi_engine_channel_clamping(self):
        """MidiEngine clamps channel to valid range."""
        from gridcat.midi import MidiEngine

        engine = MidiEngine()

        engine.set_channel(-1)
        assert engine.channel == 0

        engine.set_channel(20)
        assert engine.channel == 15

    def test_midi_engine_all_notes_off(self):
        """all_notes_off sends CC 123."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            engine.connect("Test Port")

            engine.all_notes_off()
            call_args = mock_port.send.call_args[0][0]
            assert call_args.type == "control_change"
            assert call_args.control == 123
            assert call_args.value == 0

    def test_midi_engine_disconnect(self):
        """MidiEngine.disconnect() closes port."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            engine.connect("Test Port")
            assert engine.is_connected

            engine.disconnect()
            assert not engine.is_connected
            mock_port.close.assert_called_once()

    def test_midi_engine_open_virtual(self):
        """MidiEngine.open_virtual() creates virtual port."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            result = engine.open_virtual("Gridcat")

            assert result is True
            assert engine.is_connected
            assert engine.is_virtual is True
            assert engine.port_name == "Gridcat"
            mock_open.assert_called_once_with("Gridcat", virtual=True)

    def test_midi_engine_open_virtual_failure(self):
        """MidiEngine.open_virtual() handles failure."""
        from gridcat.midi import MidiEngine

        with patch("gridcat.midi.mido.open_output") as mock_open:
            mock_open.side_effect = OSError("Cannot create virtual port")

            engine = MidiEngine()
            result = engine.open_virtual("Gridcat")

            assert result is False
            assert not engine.is_connected
            assert engine.is_virtual is False
            assert engine.port_name == ""


class TestPadWidget:
    """Tests for PadWidget."""

    def test_pad_widget_creation(self):
        """PadWidget can be created with key and config."""
        from gridcat.tui import PadWidget, PadConfig

        config = PadConfig(note=60)
        pad = PadWidget("Q", config, row=0, col=0)
        assert pad.key_label == "Q"
        assert pad.config.note == 60
        assert pad.pressed is False
        assert pad.selected is False

    def test_pad_widget_renders(self):
        """PadWidget displays key and note name."""
        from gridcat.tui import PadWidget, PadConfig

        config = PadConfig(note=60)  # C4
        pad = PadWidget("Q", config, row=0, col=0)
        content = pad.render()

        assert "Q" in content
        assert "C4" in content

    def test_pad_widget_pressed_state(self):
        """PadWidget tracks pressed state."""
        from gridcat.tui import PadWidget, PadConfig

        config = PadConfig(note=60)
        pad = PadWidget("Q", config, row=0, col=0)
        assert pad.pressed is False

        pad.pressed = True
        assert pad.pressed is True

    def test_pad_widget_selected_state(self):
        """PadWidget tracks selected state."""
        from gridcat.tui import PadWidget, PadConfig

        config = PadConfig(note=60)
        pad = PadWidget("Q", config, row=0, col=0)
        assert pad.selected is False

        pad.selected = True
        assert pad.selected is True

    def test_pad_config_cc_type(self):
        """PadConfig can be configured for CC messages."""
        from gridcat.tui import PadWidget, PadConfig

        config = PadConfig(msg_type="cc", cc_number=7, cc_value=100)
        pad = PadWidget("Q", config, row=0, col=0)
        content = pad.render()

        assert "Q" in content
        assert "CC7" in content


class TestGridKeyMapping:
    """Tests for grid key to note mapping."""

    def test_note_to_name_conversion(self):
        """note_to_name converts MIDI notes correctly."""
        from gridcat.tui import note_to_name

        assert note_to_name(60) == "C4"  # Middle C
        assert note_to_name(69) == "A4"  # A440
        assert note_to_name(48) == "C3"
        assert note_to_name(61) == "C#4"

    def test_key_rows_structure(self):
        """KEY_ROWS has correct structure."""
        from gridcat.tui import KEY_ROWS

        assert len(KEY_ROWS) == 4  # 4 rows
        for row in KEY_ROWS:
            assert len(row) == 8  # 8 columns each

    def test_grid_has_all_expected_keys(self):
        """Grid contains all expected keyboard keys."""
        from gridcat.tui import KEY_ROWS

        # Row 0: 1-8
        assert KEY_ROWS[0] == ["1", "2", "3", "4", "5", "6", "7", "8"]

        # Row 1: Q-I
        assert KEY_ROWS[1] == ["q", "w", "e", "r", "t", "y", "u", "i"]

        # Row 2: A-K
        assert KEY_ROWS[2] == ["a", "s", "d", "f", "g", "h", "j", "k"]

        # Row 3: Z-,
        assert KEY_ROWS[3] == ["z", "x", "c", "v", "b", "n", "m", "comma"]


class TestGridcatApp:
    """Tests for GridcatApp."""

    def test_gridcat_app_creation(self):
        """GridcatApp can be instantiated."""
        from gridcat.tui import GridcatApp

        with patch("gridcat.midi.mido.get_output_names", return_value=[]):
            app = GridcatApp()
            assert app.midi is not None

    @pytest.mark.asyncio
    async def test_gridcat_app_starts(self):
        """GridcatApp starts and shows grid screen."""
        from gridcat.tui import GridcatApp, GridScreen
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        # Should be on grid screen
                        assert isinstance(app.screen, GridScreen)

    @pytest.mark.asyncio
    async def test_gridcat_renders_pads(self):
        """GridcatApp renders pad widgets."""
        from gridcat.tui import GridcatApp, PadWidget
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        # Should have 32 pads (4x8 grid)
                        pads = app.screen.query(PadWidget)
                        assert len(list(pads)) == 32


class TestOctaveShift:
    """Tests for octave shifting."""

    @pytest.mark.asyncio
    async def test_octave_up(self):
        """Octave up increases octave."""
        from gridcat.tui import GridcatApp, GridScreen
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        screen = app.screen
                        assert isinstance(screen, GridScreen)

                        initial_octave = screen.octave

                        await pilot.press("up")
                        await pilot.pause()

                        assert screen.octave == initial_octave + 1

    @pytest.mark.asyncio
    async def test_octave_down(self):
        """Octave down decreases octave."""
        from gridcat.tui import GridcatApp, GridScreen
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        screen = app.screen
                        assert isinstance(screen, GridScreen)

                        initial_octave = screen.octave

                        await pilot.press("down")
                        await pilot.pause()

                        assert screen.octave == initial_octave - 1

    @pytest.mark.asyncio
    async def test_octave_shift_updates_notes(self):
        """Octave shift updates all pad notes by 12."""
        from gridcat.tui import GridcatApp, GridScreen, PadWidget
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        screen = app.screen
                        pads = list(screen.query(PadWidget))

                        # Get note of first pad before octave change
                        initial_note = pads[0].config.note

                        await pilot.press("up")
                        await pilot.pause()

                        # Note should increase by 12 (one octave)
                        assert pads[0].config.note == initial_note + 12


class TestHelpScreen:
    """Tests for help screen."""

    @pytest.mark.asyncio
    async def test_help_screen_opens(self):
        """Help screen opens with ? key."""
        from gridcat.tui import GridcatApp, HelpScreen, KeyboardHelpScreen
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        await pilot.press("question_mark")
                        await pilot.pause()

                        # Accept either help screen type
                        assert isinstance(app.screen, (HelpScreen, KeyboardHelpScreen))

    @pytest.mark.asyncio
    async def test_help_screen_closes_with_escape(self):
        """Help screen closes with escape."""
        from gridcat.tui import GridcatApp, HelpScreen, KeyboardHelpScreen, GridScreen, KeyboardScreen
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        await pilot.press("question_mark")
                        await pilot.pause()
                        assert isinstance(app.screen, (HelpScreen, KeyboardHelpScreen))

                        await pilot.press("escape")
                        await pilot.pause()
                        assert isinstance(app.screen, (GridScreen, KeyboardScreen))


class TestCommandPalette:
    """Tests for command palette."""

    @pytest.mark.asyncio
    async def test_command_palette_opens(self):
        """Command palette opens with : key."""
        from gridcat.tui import GridcatApp, CommandPalette
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        await pilot.press("colon")
                        await pilot.pause()

                        assert isinstance(app.screen, CommandPalette)

    @pytest.mark.asyncio
    async def test_command_palette_closes_with_escape(self):
        """Command palette closes with escape."""
        from gridcat.tui import GridcatApp, CommandPalette, GridScreen, KeyboardScreen
        from gridcat.settings import GridcatSettings

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        await pilot.press("colon")
                        await pilot.pause()
                        assert isinstance(app.screen, CommandPalette)

                        await pilot.press("escape")
                        await pilot.pause()
                        assert isinstance(app.screen, (GridScreen, KeyboardScreen))

    @pytest.mark.asyncio
    async def test_command_palette_shows_commands(self):
        """Command palette shows commands for current view."""
        from gridcat.tui import GridcatApp, CommandPalette, COMMANDS_GRID
        from gridcat.settings import GridcatSettings
        from textual.widgets import OptionList

        mock_settings = GridcatSettings(view="grid")
        with patch("gridcat.tui.get_settings", return_value=mock_settings):
            with patch("gridcat.midi.mido.get_output_names", return_value=[]):
                with patch("gridcat.midi.mido.open_output"):
                    app = GridcatApp()
                    async with app.run_test() as pilot:
                        await pilot.pause()

                        await pilot.press("colon")
                        await pilot.pause()

                        palette = app.screen
                        assert isinstance(palette, CommandPalette)

                        option_list = palette.query_one("#palette-list", OptionList)
                        assert option_list.option_count == len(COMMANDS_GRID)
