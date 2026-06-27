import asyncio
from types import SimpleNamespace

from commands.command_processor import create_command_processor


def test_process_input_returns_dict_and_supports_get():
    proc = create_command_processor(SimpleNamespace())

    # Basic help command should return a dict and include 'success'
    res = asyncio.run(proc.process_input('help'))
    assert isinstance(res, dict), "process_input should return a dict"
    # .get must be usable and return a boolean-like success flag
    assert 'success' in res
    assert res.get('success') is True

    # Asking for help about help should return the detailed/manpage output
    res2 = asyncio.run(proc.process_input('help help'))
    assert isinstance(res2, dict)
    assert 'success' in res2
    assert res2.get('success') is True

    # Unknown command returns an error dict with error code
    res3 = asyncio.run(proc.process_input('no-such-command-xyz'))
    assert isinstance(res3, dict)
    assert res3.get('error') == 'unknown_command'

