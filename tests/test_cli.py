import argparse
import asyncio
import os
from pathlib import Path

from _pytest.capture import CaptureFixture

from los_client.cli import CLIConfig, SatCLI

TEST_DATA = Path(__file__).parent / "test_data"


def test_save_load_config() -> None:
    path = TEST_DATA / "config.json"
    config = CLIConfig.load_config(path)
    config.solver = Path("solver_example_path")
    config.output = Path("output_example_path")
    config.problem_path = Path("problem_example_path")
    config.save_config(path)
    config.load_config(path)
    assert config.solver == Path("solver_example_path")
    assert config.output == Path("output_example_path")
    assert config.problem_path == Path("problem_example_path")


def test_load_config_no_file() -> None:
    path = TEST_DATA / "config.json"
    config = CLIConfig.load_config(path)
    try:
        os.remove("test_data/config.json")
    except FileNotFoundError:
        pass
    config.load_config(path)


def test_save_config() -> None:
    config = CLIConfig(
        solver=Path("solver"),
        output=Path("output"),
        problem_path=Path("problem"),
    )
    config.save_config(TEST_DATA / "config.json")


def test_configure_solver() -> None:
    config = CLIConfig.load_config(TEST_DATA / "config.json")
    cli = SatCLI(config)
    args = argparse.Namespace()
    args.config = TEST_DATA / "config.json"
    args.solver = Path("new_solver")
    args.output = None
    args.token = None
    config.overwrite(args)
    cli.configure(args)
    assert cli.config.solver == Path("new_solver").resolve()


def test_configure_output() -> None:
    config = CLIConfig.load_config(TEST_DATA / "config.json")
    cli = SatCLI(config)
    args = argparse.Namespace()
    args.config = TEST_DATA / "config.json"
    args.solver = None
    args.output = Path("new_output")
    args.token = None
    config.overwrite(args)
    cli.configure(args)
    assert cli.config.output == Path("new_output").resolve()


def test_configure_problem() -> None:
    config = CLIConfig.load_config(TEST_DATA / "config.json")
    cli = SatCLI(config)
    args = argparse.Namespace()
    args.config = TEST_DATA / "config.json"
    args.solver = None
    args.output = None
    args.token = "new_token"
    config.overwrite(args)
    cli.configure(args)
    assert cli.config.token == "new_token"


def test_run(capfd: CaptureFixture) -> None:
    config = CLIConfig()
    cli = SatCLI(config)
    asyncio.run(cli.run(cli.config))
    captured = capfd.readouterr()
    assert (
        "Configuration confirmed. Ready to register and run the solver."
        in captured.out
    )
