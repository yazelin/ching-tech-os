"""測試 skills/script_utils.py"""

from unittest.mock import patch

from ching_tech_os.skills.script_utils import parse_stdin_json_object


class TestParseStdinJsonObject:
    def test_empty_stdin(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = ""
            payload, err = parse_stdin_json_object()
            assert payload == {}
            assert err is None

    def test_whitespace_only(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "   "
            payload, err = parse_stdin_json_object()
            assert payload == {}
            assert err is None

    def test_valid_json_object(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = '{"key": "value", "num": 42}'
            payload, err = parse_stdin_json_object()
            assert payload == {"key": "value", "num": 42}
            assert err is None

    def test_invalid_json(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "not json"
            payload, err = parse_stdin_json_object()
            assert payload is None
            assert "invalid_input" in err

    def test_non_dict_json(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "[1, 2, 3]"
            payload, err = parse_stdin_json_object()
            assert payload is None
            assert "JSON 物件" in err

    def test_json_string(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = '"hello"'
            payload, err = parse_stdin_json_object()
            assert payload is None
            assert "JSON 物件" in err
