import asyncio
import sys
from pathlib import Path
from typing import Text
from unittest.mock import Mock

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

import rasa.model
import rasa.cli.utils
from rasa.core.agent import Agent
from rasa.core.interpreter import RasaNLUInterpreter, RegexInterpreter
from rasa.nlu.test import NO_ENTITY
import rasa.core


def monkeypatch_get_latest_model(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    latest_model = tmp_path / "my_test_model.tar.gz"
    monkeypatch.setattr(rasa.model, "get_latest_model", lambda: str(latest_model))


def test_get_sanitized_model_directory_when_not_passing_model(
    capsys: CaptureFixture, tmp_path: Path, monkeypatch: MonkeyPatch
):
    from rasa.test import _get_sanitized_model_directory

    monkeypatch_get_latest_model(tmp_path, monkeypatch)

    # Create a fake model on disk so that `is_file` returns `True`
    latest_model = Path(rasa.model.get_latest_model())
    latest_model.touch()

    # Input: default model file
    # => Should return containing directory
    new_modeldir = _get_sanitized_model_directory(str(latest_model))
    captured = capsys.readouterr()
    assert not captured.out
    assert new_modeldir == str(latest_model.parent)


def test_get_sanitized_model_directory_when_passing_model_file_explicitly(
    capsys: CaptureFixture, tmp_path: Path, monkeypatch: MonkeyPatch
):
    from rasa.test import _get_sanitized_model_directory

    monkeypatch_get_latest_model(tmp_path, monkeypatch)

    other_model = tmp_path / "my_test_model1.tar.gz"
    assert str(other_model) != rasa.model.get_latest_model()
    other_model.touch()

    # Input: some file
    # => Should return containing directory and print a warning
    new_modeldir = _get_sanitized_model_directory(str(other_model))
    captured = capsys.readouterr()
    assert captured.out
    assert new_modeldir == str(other_model.parent)


def test_get_sanitized_model_directory_when_passing_other_input(
    capsys: CaptureFixture, tmp_path: Path, monkeypatch: MonkeyPatch
):
    from rasa.test import _get_sanitized_model_directory

    monkeypatch_get_latest_model(tmp_path, monkeypatch)

    # Input: anything that is not an existing file
    # => Should return input
    modeldir = "random_dir"
    assert not Path(modeldir).is_file()
    new_modeldir = _get_sanitized_model_directory(modeldir)
    captured = capsys.readouterr()
    assert not captured.out
    assert new_modeldir == modeldir


@pytest.mark.parametrize(
    "targets,predictions,expected_precision,expected_fscore,expected_accuracy",
    [
        (
            ["no_entity", "location", "no_entity", "location", "no_entity"],
            ["no_entity", "location", "no_entity", "no_entity", "person"],
            1.0,
            0.6666666666666666,
            3 / 5,
        ),
        (
            ["no_entity", "no_entity", "no_entity", "no_entity", "person"],
            ["no_entity", "no_entity", "no_entity", "no_entity", "no_entity"],
            0.0,
            0.0,
            4 / 5,
        ),
    ],
)
def test_get_evaluation_metrics(
    targets, predictions, expected_precision, expected_fscore, expected_accuracy
):
    from rasa.test import get_evaluation_metrics

    report, precision, f1, accuracy = get_evaluation_metrics(
        targets, predictions, True, exclude_label=NO_ENTITY
    )

    assert f1 == expected_fscore
    assert precision == expected_precision
    assert accuracy == expected_accuracy
    assert NO_ENTITY not in report


@pytest.mark.parametrize(
    "targets,exclude_label,expected",
    [
        (
            ["no_entity", "location", "location", "location", "person"],
            NO_ENTITY,
            ["location", "person"],
        ),
        (
            ["no_entity", "location", "location", "location", "person"],
            None,
            ["no_entity", "location", "person"],
        ),
        (["no_entity"], NO_ENTITY, []),
        (["location", "location", "location"], NO_ENTITY, ["location"]),
        ([], None, []),
    ],
)
def test_get_label_set(targets, exclude_label, expected):
    from rasa.test import get_unique_labels

    actual = get_unique_labels(targets, exclude_label)
    assert set(expected) == set(actual)


async def test_interpreter_passed_to_agent(
    monkeypatch: MonkeyPatch, trained_rasa_model: Text
):
    from rasa.test import test_core

    # Patching is bit more complicated as we have a module `train` and function
    # with the same name 😬
    monkeypatch.setattr(
        sys.modules["rasa.test"], "_test_core", asyncio.coroutine(lambda *_, **__: True)
    )

    agent_load = Mock()
    monkeypatch.setattr(Agent, "load", agent_load)

    test_core(trained_rasa_model)

    agent_load.assert_called_once()
    _, _, kwargs = agent_load.mock_calls[0]
    assert isinstance(kwargs["interpreter"], RasaNLUInterpreter)


async def test_e2e_warning_if_no_nlu_model(
    monkeypatch: MonkeyPatch, trained_core_model: Text, capsys: CaptureFixture
):
    from rasa.test import test_core

    # Patching is bit more complicated as we have a module `train` and function
    # with the same name 😬
    monkeypatch.setattr(
        sys.modules["rasa.test"], "_test_core", asyncio.coroutine(lambda *_, **__: True)
    )

    agent_load = Mock()
    monkeypatch.setattr(Agent, "load", agent_load)

    test_core(trained_core_model, additional_arguments={"e2e": True})

    assert "No NLU model found. Using default" in capsys.readouterr().out

    agent_load.assert_called_once()
    _, _, kwargs = agent_load.mock_calls[0]
    assert isinstance(kwargs["interpreter"], RegexInterpreter)
