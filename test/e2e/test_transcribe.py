import re

import pytest

from test.conftest import skip_if_no_container
from test.e2e.utils import RamalamaExecWorkspace, check_output
from test.e2e.whisper_utils import MODEL, WHISPER_IMAGE, _require_network, _write_silence, require_model


@pytest.mark.e2e
@skip_if_no_container
def test_transcribe_dryrun_container_command(tmp_path):
    _require_network()
    audio = tmp_path / "a.wav"
    _write_silence(audio, seconds=0.1)

    result = check_output(["ramalama", "-q", "--runtime", "whisper.cpp", "--dryrun", "transcribe", MODEL, str(audio)])

    assert "--entrypoint=whisper-cli" in result
    assert WHISPER_IMAGE in result
    assert re.search(r"-otxt\s+-of\s+-\s+-np", result)
    assert "--mount=type=bind" in result
    assert "destination=/mnt/audio/input.wav" in result
    assert re.search(r"-f\s+/mnt/audio/input\.wav", result)


@pytest.mark.e2e
def test_transcribe_dryrun_nocontainer_command(tmp_path):
    _require_network()
    audio = tmp_path / "a.wav"
    _write_silence(audio, seconds=0.1)

    result = check_output(
        ["ramalama", "-q", "--runtime", "whisper.cpp", "--dryrun", "--nocontainer", "transcribe", MODEL, str(audio)]
    )

    assert "whisper-cli" in result
    assert "--entrypoint" not in result
    assert str(audio) in result


@pytest.mark.e2e
@skip_if_no_container
def test_transcribe_wav_to_stdout(tmp_path):
    _require_network()
    require_model(MODEL)

    audio = tmp_path / "silence.wav"
    _write_silence(audio)

    with RamalamaExecWorkspace() as ctx:
        result = ctx.check_output(["ramalama", "-q", "--runtime", "whisper.cpp", "transcribe", MODEL, str(audio)])

    # -np keeps whisper.cpp diagnostics out of the output, leaving the
    # transcript (empty for silence) on stdout.
    assert "whisper_print_timings" not in result
    assert "system_info" not in result
