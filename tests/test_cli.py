import argparse
import asyncio
from pathlib import Path, PosixPath

from pydantic import AnyUrl

from los_client.cli import CLIConfig, SatCLI

TEST_INPUT = Path(__file__).parent / "test_input"
TEST_OUTPUT = Path(__file__).parent / "test_output"


def new_config() -> CLIConfig:
    return CLIConfig(
        solver_pairs=[(Path("default_solver"), "default_token")],
        output=Path("default_output"),
        problem_path=Path("default_problem"),
    )


def test_save_load_config() -> None:
    config_path = TEST_OUTPUT / "save_load_config.json"

    config = new_config()
    config.save_config(config_path)

    loaded_config = CLIConfig.load_config(config_path)
    assert loaded_config.solver_pairs == config.solver_pairs
    assert loaded_config.output == config.output
    assert loaded_config.problem_path == config.problem_path


def test_load_config_no_file() -> None:
    config_path = TEST_INPUT / "non_existent_config.json"

    config = CLIConfig.load_config(config_path)
    assert config.solver_pairs == []
    assert config.output == PosixPath(
        "/home/amr/PycharmProjects/LeagueOfSolvers/los_client/output"
    )
    assert config.problem_path == PosixPath("problem.cnf")
    assert config.output_path == PosixPath("stdout.txt")
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
        config=config_path,
        solvers=[Path("new_solver")],
        output=None,
        tokens=["new_token"],
    )

    cli.config.overwrite(args)
    cli.configure(args)
    updated_config = CLIConfig.load_config(config_path)
    assert updated_config.solver_pairs[0][0] == Path("new_solver").resolve()
    assert updated_config.solver_pairs[0][1] == "new_token"


def test_configure_output() -> None:
    config_path = TEST_OUTPUT / "configure_solver_test.json"

    config = new_config()
    config.save_config(config_path)
    cli = SatCLI(config)

    args = argparse.Namespace(
        config=config_path,
        solvers=None,
        output=Path("new_output"),
        tokens=None,
    )

    cli.config.overwrite(args)
    cli.configure(args)
    updated_config = CLIConfig.load_config(config_path)
    assert updated_config.output == Path("new_output").resolve()


def test_run() -> None:
    config_path = TEST_INPUT / "run_test_config.json"
    config = CLIConfig.load_config(config_path)
    cli = SatCLI(config)
    cli.single_run = True
    asyncio.run(cli.run())
