"""Pi Zero 2 W player profile tests."""

from unittest.mock import MagicMock, patch

from linux_voice_assistant.player.libmpv import LibMpvPlayer


def test_pi02w_mpv_constructor_is_low_overhead():
    fake_mpv = MagicMock()
    fake_mpv.event_callback.side_effect = lambda _event: (lambda func: func)

    with patch(
        "linux_voice_assistant.player.libmpv.mpv.MPV",
        return_value=fake_mpv,
    ) as mpv_ctor:
        LibMpvPlayer()

    kwargs = mpv_ctor.call_args.kwargs

    assert kwargs["audio_display"] is False
    assert kwargs["idle"] is True
    assert kwargs["terminal"] is False
    assert kwargs["video"] is False
    assert kwargs["cache"] == "yes"
    assert kwargs["demuxer_max_bytes"] == "8MiB"
    assert kwargs["cache_secs"] == "5"

    fake_mpv.__setitem__.assert_any_call("audio-buffer", 0.8)
    fake_mpv.__setitem__.assert_any_call("audio-stream-silence", True)
