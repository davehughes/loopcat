"""Tests for fadercat MIDI fader controller."""

from unittest.mock import MagicMock, patch
import tempfile
import os

import pytest


# Fixture to isolate config for each test
@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Use a temporary config directory for each test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


class TestMidiEngineCC:
    """Tests for fadercat MidiEngine CC functionality."""

    def test_midi_engine_creation(self):
        """MidiEngine can be instantiated."""
        from fadercat.midi import MidiEngine

        engine = MidiEngine()
        assert engine.output is None
        assert engine.channel == 0

    def test_midi_engine_cc_sends_message(self):
        """cc() sends control_change message."""
        from fadercat.midi import MidiEngine

        with patch("fadercat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            engine.connect("Test Port")

            engine.cc(1, 64)
            mock_port.send.assert_called()
            call_args = mock_port.send.call_args[0][0]
            assert call_args.type == "control_change"
            assert call_args.control == 1
            assert call_args.value == 64
            assert call_args.channel == 0

    def test_midi_engine_cc_clamps_values(self):
        """cc() clamps values to valid range."""
        from fadercat.midi import MidiEngine

        with patch("fadercat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            engine.connect("Test Port")

            # Test clamping high value
            engine.cc(1, 200)
            call_args = mock_port.send.call_args[0][0]
            assert call_args.value == 127

            # Test clamping low value
            engine.cc(1, -10)
            call_args = mock_port.send.call_args[0][0]
            assert call_args.value == 0

    def test_midi_engine_cc_respects_channel(self):
        """cc() uses current channel setting."""
        from fadercat.midi import MidiEngine

        with patch("fadercat.midi.mido.open_output") as mock_open:
            mock_port = MagicMock()
            mock_open.return_value = mock_port

            engine = MidiEngine()
            engine.connect("Test Port")
            engine.set_channel(10)

            engine.cc(7, 100)
            call_args = mock_port.send.call_args[0][0]
            assert call_args.channel == 10


class TestFaderWidget:
    """Tests for FaderWidget."""

    def test_fader_widget_creation(self):
        """FaderWidget can be created."""
        from fadercat.tui import FaderWidget

        fader = FaderWidget(
            fader_index=0,
            cc_number=1,
            label="Mod",
            key_up="Q",
            key_down="A",
        )
        assert fader.fader_index == 0
        assert fader.cc_number == 1
        assert fader.label == "Mod"
        assert fader.value == 0

    def test_fader_widget_value_change(self):
        """FaderWidget tracks value changes."""
        from fadercat.tui import FaderWidget

        fader = FaderWidget(
            fader_index=0,
            cc_number=1,
            label="Mod",
            key_up="Q",
            key_down="A",
        )
        assert fader.value == 0

        fader.value = 64
        assert fader.value == 64

    def test_fader_widget_selection(self):
        """FaderWidget tracks selection state."""
        from fadercat.tui import FaderWidget

        fader = FaderWidget(
            fader_index=0,
            cc_number=1,
            label="Mod",
            key_up="Q",
            key_down="A",
        )
        assert fader.selected is False

        fader.selected = True
        assert fader.selected is True


class TestFaderValueClamp:
    """Tests for fader value clamping."""

    @pytest.mark.asyncio
    async def test_fader_value_stays_in_range(self):
        """Values stay in 0-127 range."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)

                    # Get first fader using accessor
                    faders = screen._get_active_faders()
                    assert len(faders) == 8
                    fader = faders[0]

                    # Set to max and try to increase
                    fader.value = 127
                    screen._adjust_fader(0, 10)
                    assert fader.value == 127  # Should stay at max

                    # Set to min and try to decrease
                    fader.value = 0
                    screen._adjust_fader(0, -10)
                    assert fader.value == 0  # Should stay at min


class TestDualKeyControl:
    """Tests for dual-key fader control."""

    def test_fader_keys_structure(self):
        """Fader key lists have correct structure."""
        from fadercat.tui import FADER_KEYS_UP, FADER_KEYS_DOWN

        assert len(FADER_KEYS_UP) == 8
        assert len(FADER_KEYS_DOWN) == 8

        # Top row Q-I
        assert FADER_KEYS_UP == ["q", "w", "e", "r", "t", "y", "u", "i"]
        # Bottom row A-K
        assert FADER_KEYS_DOWN == ["a", "s", "d", "f", "g", "h", "j", "k"]

    @pytest.mark.asyncio
    async def test_k_increases_selected_fader(self):
        """K increases the selected fader (vertical mode)."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)

                    # Select fader 1
                    await pilot.press("1")
                    await pilot.pause()

                    faders = screen._get_active_faders()
                    initial_value = faders[0].value

                    await pilot.press("k")
                    await pilot.pause()

                    assert faders[0].value > initial_value

    @pytest.mark.asyncio
    async def test_j_decreases_selected_fader(self):
        """J decreases the selected fader (vertical mode)."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)

                    # Select fader 1 and set initial value above 0
                    await pilot.press("1")
                    await pilot.pause()
                    faders = screen._get_active_faders()
                    faders[0].value = 64

                    await pilot.press("j")
                    await pilot.pause()

                    assert faders[0].value < 64


class TestFadercatApp:
    """Tests for FadercatApp."""

    def test_fadercat_app_creation(self):
        """FadercatApp can be instantiated."""
        from fadercat.tui import FadercatApp

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            app = FadercatApp()
            assert app.midi is not None

    @pytest.mark.asyncio
    async def test_fadercat_app_starts(self):
        """FadercatApp starts and shows fader screen."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()

                    assert isinstance(app.screen, FaderScreen)

    @pytest.mark.asyncio
    async def test_fadercat_renders_8_faders(self):
        """FadercatApp renders 8 fader widgets."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)
                    faders = screen._get_active_faders()
                    assert len(faders) == 8


class TestFaderSelection:
    """Tests for fader selection."""

    @pytest.mark.asyncio
    async def test_number_key_selects_fader(self):
        """Number keys 1-8 select corresponding fader."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)

                    # Initially no fader selected
                    assert screen.selected_fader == -1

                    # Press 1 to select first fader
                    await pilot.press("1")
                    await pilot.pause()
                    assert screen.selected_fader == 0

                    # Press 5 to select fifth fader
                    await pilot.press("5")
                    await pilot.pause()
                    assert screen.selected_fader == 4

    @pytest.mark.asyncio
    async def test_space_resets_selected_fader(self):
        """Space resets selected fader to 0."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)

                    # Select fader 1 and set value
                    screen.selected_fader = 0
                    faders = screen._get_active_faders()
                    faders[0].value = 100

                    # Press space to reset
                    await pilot.press("space")
                    await pilot.pause()

                    assert faders[0].value == 0


class TestHelpScreen:
    """Tests for help screen."""

    @pytest.mark.asyncio
    async def test_help_screen_opens(self):
        """Help screen opens with ? key."""
        from fadercat.tui import FadercatApp, HelpScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()

                    await pilot.press("question_mark")
                    await pilot.pause()

                    assert isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_help_screen_closes(self):
        """Help screen closes with escape."""
        from fadercat.tui import FadercatApp, HelpScreen, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()

                    await pilot.press("question_mark")
                    await pilot.pause()
                    assert isinstance(app.screen, HelpScreen)

                    await pilot.press("escape")
                    await pilot.pause()
                    assert isinstance(app.screen, FaderScreen)


class TestHorizontalMode:
    """Tests for horizontal display mode."""

    def test_horizontal_fader_widget_creation(self):
        """HorizontalFaderWidget can be created."""
        from fadercat.tui import HorizontalFaderWidget

        fader = HorizontalFaderWidget(
            fader_index=0,
            cc_number=1,
            label="Test",
        )
        assert fader.fader_index == 0
        assert fader.cc_number == 1
        assert fader.label == "Test"
        assert fader.value == 0

    @pytest.mark.asyncio
    async def test_mode_toggle(self):
        """Pressing v toggles between modes."""
        from fadercat.tui import FadercatApp, FaderScreen, MODE_VERTICAL, MODE_HORIZONTAL

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)
                    # Starts in vertical mode (default for fresh config)
                    initial_mode = screen.display_mode
                    assert initial_mode == MODE_VERTICAL

                    # Toggle to horizontal
                    await pilot.press("v")
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild
                    assert screen.display_mode == MODE_HORIZONTAL

                    # Toggle back to vertical
                    await pilot.press("v")
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild
                    assert screen.display_mode == MODE_VERTICAL

    @pytest.mark.asyncio
    async def test_horizontal_mode_key_bindings(self):
        """In horizontal mode, j/k selects and h/l adjusts."""
        from fadercat.tui import FadercatApp, FaderScreen, MODE_HORIZONTAL

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)

                    # Switch to horizontal mode
                    await pilot.press("v")
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild
                    assert screen.display_mode == MODE_HORIZONTAL

                    # j should select next fader (down)
                    assert screen.selected_fader == -1
                    await pilot.press("j")
                    await pilot.pause()
                    assert screen.selected_fader == 0

                    # j again should go to next
                    await pilot.press("j")
                    await pilot.pause()
                    assert screen.selected_fader == 1

                    # k should go back up
                    await pilot.press("k")
                    await pilot.pause()
                    assert screen.selected_fader == 0

    @pytest.mark.asyncio
    async def test_horizontal_mode_adjust_with_hl(self):
        """In horizontal mode, l increases and h decreases selected fader."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)

                    # Switch to horizontal mode
                    await pilot.press("v")
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    # Select fader 1
                    await pilot.press("1")
                    await pilot.pause()
                    assert screen.selected_fader == 0

                    # Get initial value - use _get_active_faders() for robustness
                    faders = screen._get_active_faders()
                    assert len(faders) == 8
                    fader = faders[0]
                    initial_value = fader.value

                    # l should increase
                    await pilot.press("l")
                    await pilot.pause()
                    assert fader.value > initial_value

                    # h should decrease
                    current_value = fader.value
                    await pilot.press("h")
                    await pilot.pause()
                    assert fader.value < current_value

    @pytest.mark.asyncio
    async def test_values_preserved_on_mode_toggle(self):
        """Fader values are preserved when toggling modes."""
        from fadercat.tui import FadercatApp, FaderScreen

        with patch("fadercat.midi.mido.get_output_names", return_value=[]):
            with patch("fadercat.midi.mido.open_output"):
                app = FadercatApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    screen = app.screen
                    assert isinstance(screen, FaderScreen)

                    # Set a value on fader 1
                    await pilot.press("1")
                    await pilot.pause()
                    faders = screen._get_active_faders()
                    faders[0].value = 100

                    # Toggle to horizontal
                    await pilot.press("v")
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    # Value should be preserved
                    faders = screen._get_active_faders()
                    assert faders[0].value == 100

                    # Toggle back
                    await pilot.press("v")
                    await pilot.pause()
                    await pilot.pause()  # Extra pause for rebuild

                    # Value still preserved
                    faders = screen._get_active_faders()
                    assert faders[0].value == 100
