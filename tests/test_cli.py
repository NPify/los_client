import argparse
import asyncio
import os
from pathlib import Path

from _pytest.capture import CaptureFixture

from los_client.cli import CLIConfig, SatCLI


def test_save_load_config() -> None:
    config = CLIConfig(Path("test_data/config.json"))
    config.solver_path = Path("solver_example_path")
    config.output_path = Path("output_example_path")
    config.problem_path = Path("problem_example_path")
    config.save_config()
    config.load_config()
    assert config.solver_path == Path("solver_example_path")
    assert config.output_path == Path("output_example_path")
    assert config.problem_path == Path("problem_example_path")


def test_load_config_no_file() -> None:
    config = CLIConfig(Path("test_data/config.json"))
    try:
        os.remove("test_data/config.json")
    except FileNotFoundError:
        pass
    config.load_config()


def test_save_config() -> None:
    config = CLIConfig(
        Path("test_data/config.json"),
        Path("solver"),
        Path("output"),
        Path("problem"),
    )
    config.save_config()


def test_configure_solver() -> None:
    cli = SatCLI()
    cli.config = CLIConfig(Path("test_data/config.json"))
    args = argparse.Namespace()
    args.solver = Path("new_solver")
    args.output = None
    args.problem = None
    cli.configure(args)
    assert cli.config.solver_path == Path("new_solver")


def test_configure_output() -> None:
    cli = SatCLI()
    cli.config = CLIConfig(Path("test_data/config.json"))
    args = argparse.Namespace()
    args.solver = None
    args.output = Path("new_output")
    args.problem = None
    cli.configure(args)
    assert cli.config.output_path == Path("new_output")


def test_configure_problem() -> None:
    cli = SatCLI()
    cli.config = CLIConfig(Path("test_data/config.json"))
    args = argparse.Namespace()
    args.solver = None
    args.output = None
    args.problem = Path("new_problem")
    cli.configure(args)
    assert cli.config.problem_path == Path("new_problem")


def test_run(capfd: CaptureFixture) -> None:
    cli = SatCLI()
    cli.output_folder = Path("tests/test_data/")
    cli.config.solver_path = Path("solver")
    cli.config.output_path = Path("output")
    cli.config.problem_path = Path("problem")
    asyncio.run(cli.run(cli.config))
    captured = capfd.readouterr()
    assert (
        "Configuration confirmed. Ready to register and run the solver."
        in captured.out
    )
