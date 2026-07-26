"""Unit tests for pi5buzzer.core.music.MusicBuzzer."""

import time

from pi5buzzer.notes import EMOTION_SOUNDS, NOTES, get_emotion_names


class TestMusicBuzzerPlayNote:
    """Test play_note()."""

    def test_play_note_valid(self, music_buzzer):
        music_buzzer.play_note("C4", 0.1)
        time.sleep(0.3)
        music_buzzer.pi.set_PWM_frequency.assert_called_with(17, 262)

    def test_play_note_case_insensitive(self, music_buzzer):
        music_buzzer.play_note("c4", 0.1)
        time.sleep(0.3)
        music_buzzer.pi.set_PWM_frequency.assert_called_with(17, 262)

    def test_play_note_unknown(self, music_buzzer):
        music_buzzer.play_note("Z9", 0.1)


class TestMusicBuzzerPlaySong:
    """Test play_song()."""

    def test_play_song_queues_notes(self, music_buzzer):
        song = [("C4", 0.05), ("E4", 0.05), ("G4", 0.05)]
        music_buzzer.play_song(song)
        time.sleep(0.5)
        assert music_buzzer.pi.set_PWM_frequency.call_count >= 3

    def test_play_song_handles_pauses(self, music_buzzer):
        song = [("C4", 0.05), ("pause", 0.05), ("E4", 0.05)]
        music_buzzer.play_song(song)
        time.sleep(0.5)
        assert music_buzzer.pi.set_PWM_frequency.call_count >= 2

    def test_play_song_is_nonblocking(self, music_buzzer):
        song = [("C4", 1.0)] * 5
        start = time.time()
        music_buzzer.play_song(song)
        assert time.time() - start < 0.5


class TestMusicBuzzerPlayEmotion:
    """Test play_emotion()."""

    def test_play_emotion_happy(self, music_buzzer):
        music_buzzer.play_emotion("happy")
        time.sleep(1.0)
        assert music_buzzer.pi.set_PWM_frequency.call_count >= 1

    def test_play_emotion_unknown(self, music_buzzer):
        music_buzzer.play_emotion("nonexistent")

    def test_all_emotions_are_valid(self):
        for name, melody in EMOTION_SOUNDS.items():
            for note_name, duration in melody:
                if note_name != "pause":
                    assert note_name in NOTES, f"Emotion '{name}' uses unknown note: {note_name}"
                assert duration > 0, f"Emotion '{name}' has non-positive duration: {duration}"


class TestMusicBuzzerPlayDemo:
    """Test play_demo()."""

    def test_play_demo(self, music_buzzer):
        music_buzzer.play_demo()
        time.sleep(0.5)
        assert music_buzzer.pi.set_PWM_frequency.call_count >= 1


class TestNotesModule:
    """Test the notes module constants."""

    def test_notes_not_empty(self):
        assert len(NOTES) > 0

    def test_notes_contains_a4(self):
        assert NOTES["A4"] == 440

    def test_get_emotion_names(self):
        names = get_emotion_names()
        assert "happy" in names
        assert "sad" in names
        assert len(names) == 14

    def test_emotion_names_sorted(self):
        names = get_emotion_names()
        assert names == sorted(names)
