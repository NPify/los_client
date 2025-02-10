import argparse
import asyncio
from pathlib import Path, PosixPath

import pytest
from pydantic import AnyUrl

from los_client.cli import CLIConfig, SatCLI
from los_client.config import Solver

TEST_INPUT = Path(__file__).parent / "test_input"
TEST_OUTPUT = Path(__file__).parent / "test_output"


def new_config() -> CLIConfig:
    return CLIConfig(
        solvers=[
            Solver(
                solver_path=Path("default_solver"),
                args=[],
                token="default_token",
                output_path=Path("default_output_file"),
            )
        ],
        output_folder=Path("default_output"),
        problem_path=Path("default_problem"),
    )


def test_save_load_config() -> None:
    config_path = TEST_OUTPUT / "save_load_config.json"

    config = new_config()
    config.save_config(config_path)

    loaded_config = CLIConfig.load_config(config_path)
    assert loaded_config.solvers == config.solvers
    assert loaded_config.output_folder == config.output_folder
    assert loaded_config.problem_path == config.problem_path


def test_load_config_no_file() -> None:
    config_path = TEST_INPUT / "non_existent_config.json"

    config = CLIConfig.load_config(config_path)
    assert config.solvers == []
    assert config.problem_path == PosixPath("problem.cnf")
    assert config.host == AnyUrl("wss://los.npify.com/match_server/sat/")
    assert not config.quiet
    config_path.unlink()


def test_save_config() -> None:
    config_path = TEST_OUTPUT / "save_config_test.json"

    config = new_config()
    config.save_config(config_path)

    assert config_path.exists()


def test_configure_solver() -> None:
    config_path = TEST_OUTPUT / "configure_solver_test.json"

    config = new_config()
    config.save_config(config_path)
    cli = SatCLI(config)

    args = argparse.Namespace(
        command="modify",
        config=config_path,
        token="default_token",
        new_solver=Path("new_solver"),
        new_token="new_token",
        new_output=None,
    )

    cli.config.set_fields(args)
    cli.config.save_config(config_path)
    updated_config = CLIConfig.load_config(config_path)
    assert (
        updated_config.solvers[0].solver_path == Path("new_solver").resolve()
    )
    assert updated_config.solvers[0].token == "new_token"


def test_configure_output_folder() -> None:
    config_path = TEST_OUTPUT / "configure_output_folder.json"

    config = new_config()
    config.save_config(config_path)
    cli = SatCLI(config)

    args = argparse.Namespace(
        command="output_folder",
        config=config_path,
        output_folder=Path("new_output"),
    )

    cli.config.set_fields(args)
    cli.config.save_config(config_path)
    updated_config = CLIConfig.load_config(config_path)
    assert updated_config.output_folder == Path("new_output").resolve()


def test_configure_problem_path() -> None:
    config_path = TEST_OUTPUT / "configure_problem_path.json"

    config = new_config()
    config.save_config(config_path)
    cli = SatCLI(config)

    args = argparse.Namespace(
        command="problem_path",
        config=config_path,
        problem_path=Path("new_problem"),
    )

    cli.config.set_fields(args)
    cli.config.save_config(config_path)
    updated_config = CLIConfig.load_config(config_path)
    assert updated_config.problem_path == Path("new_problem")


@pytest.mark.skip(reason="This test requires solver binaries to be present")
def test_run() -> None:
    config_path = TEST_INPUT / "run_test_config.json"
    config = CLIConfig.load_config(config_path)
    cli = SatCLI(config)
    cli.single_run = True
    asyncio.run(cli.run())
