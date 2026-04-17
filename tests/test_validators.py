import pytest
from core.exceptions import (
    EmptyMessageError,
    InvalidStageError,
    InvalidRoleError,
    AlzheiCareException,
)
from utils.validators import (
    validate_message,
    validate_stage,
    validate_role,
    validate_language_code,
)


class TestValidateMessage:

    def test_valid_message_passes(self):
        result = validate_message("Bonjour, comment gérer les crises?")
        assert result == "Bonjour, comment gérer les crises?"

    def test_message_is_stripped(self):
        result = validate_message("  Hello  ")
        assert result == "Hello"

    def test_empty_string_raises(self):
        with pytest.raises(EmptyMessageError):
            validate_message("")

    def test_whitespace_only_raises(self):
        with pytest.raises(EmptyMessageError):
            validate_message("   \n\t  ")

    def test_none_raises(self):
        with pytest.raises(EmptyMessageError):
            validate_message(None)

    def test_long_message_is_truncated(self):
        long = "A" * 3000
        result = validate_message(long)
        assert len(result) <= 2000

    def test_normal_length_not_truncated(self):
        msg = "A" * 500
        result = validate_message(msg)
        assert len(result) == 500


class TestValidateStage:

    def test_stage_0_valid(self):
        assert validate_stage(0) == 0

    def test_stage_1_valid(self):
        assert validate_stage(1) == 1

    def test_stage_2_valid(self):
        assert validate_stage(2) == 2

    def test_stage_3_invalid(self):
        with pytest.raises(InvalidStageError):
            validate_stage(3)

    def test_stage_negative_invalid(self):
        with pytest.raises(InvalidStageError):
            validate_stage(-1)


class TestValidateRole:

    def test_caregiver_valid(self):
        assert validate_role("caregiver") == "caregiver"

    def test_doctor_valid(self):
        assert validate_role("doctor") == "doctor"

    def test_admin_valid(self):
        assert validate_role("admin") == "admin"

    def test_invalid_role_raises(self):
        with pytest.raises(InvalidRoleError):
            validate_role("nurse")

    def test_empty_role_raises(self):
        with pytest.raises(InvalidRoleError):
            validate_role("")


class TestValidateLanguageCode:
    def test_supported_language_passes(self):
        assert validate_language_code("fr") == "fr"

    def test_language_is_normalized(self):
        assert validate_language_code(" EN ") == "en"

    def test_none_stays_none(self):
        assert validate_language_code(None) is None

    def test_invalid_language_raises(self):
        with pytest.raises(AlzheiCareException):
            validate_language_code("xx")