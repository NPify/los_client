import argparse
import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from los_client.__about__ import __version__
from los_client.client import Client
from los_client.config import CLIConfig, Solver
from los_client.run_solver import SolverRunner
from los_client.exceptions import SolverException
logger = logging.getLogger(__name__)


class TerminateTaskGroup(Exception):
    pass


@dataclass
class SatCLI:
    config: CLIConfig
    excluded_solvers: List[Solver] = field(default_factory=list)
    single_run: bool = False
    client: Client = field(init=False)

    async def run(self) -> None:
        self.validate_config()
        if self.config.write_outputs:
            self.setup_output_files()

        logger.info(
            "Configuration confirmed. Ready to register and run the solver."
        )

        sleep_time = 1

        while True:
            try:
                async with connect(
                    str(self.config.host), max_size=1024 * 1024 * 32
                ) as ws:
                    self.client = Client(self.config, ws)
                    try:
                        sleep_time = 1
                        await self.client.welcome()
                        await self.process_solvers()
                    except OSError as e:
                        # TODO: we do not want to catch OSErrors from inside,
                        # so let us just repackage it for now
                        raise RuntimeError(e) from e
            except (OSError, WebSocketException) as e:
                logger.error(
                    f"Error: Connection failed: {e} "
                    "Waiting for server to come back up. "
                    f"Retry in {sleep_time} seconds. "
                )
                await asyncio.sleep(sleep_time)
                sleep_time *= 2
                if sleep_time > 60:
                    sleep_time = 60
            if self.single_run:
                break

    def validate_config(self) -> None:
        try:
            open(self.config.output_folder / self.config.problem_path, "w").close()
        except OSError as e:
            e.add_note("Can't write problem file. You may need to adjust the configuration.")
            raise

        if not self.config.solvers:
            raise ValueError("No solvers are configured. ")

    def setup_output_files(self) -> None:
        os.makedirs(self.config.output_folder, exist_ok=True)
        open(self.config.output_folder / self.config.problem_path, "w").close()
        for solver in self.config.solvers:
            if solver.output_path:
                open(
                    self.config.output_folder / solver.output_path, "w"
                ).close()

    async def process_solvers(self) -> None:
        while len(self.excluded_solvers) < len(self.config.solvers):
            await self.client.trigger_countdown()
            await self.client.register_solvers()

            instance = await self.client.get_instance()
            instance_path = (
                self.config.output_folder / self.config.problem_path
            )
            with open(instance_path, "wb") as f:
                f.write(instance)

            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self.stop_on_connection_close())
                    tg.create_task(self.run_solvers(instance_path))
            except* TerminateTaskGroup:
                pass
            if self.single_run:
                break

    async def stop_on_connection_close(self) -> None:
        await self.client.wait_closed()
        raise TerminateTaskGroup()

    async def run_solver(self, solver: Solver, instance_path: Path) -> None:
        if solver in self.excluded_solvers:
            return

        runner = SolverRunner(self.config, solver, self.client)

        try:
            await runner.run_solver(instance_path)
        except SolverException as e:
            logging.error(str(e))
            logger.warning(
                f"Excluding solver from further runs: {solver.solver_path}"
            )
            self.excluded_solvers.append(solver)
        except TimeoutError:
            logger.info(f"Solver at {solver.solver_path} timed out.")

    async def run_solvers(self, instance_path: Path) -> None:
        async with asyncio.TaskGroup() as tg:
            for solver in self.config.solvers:
                tg.create_task(self.run_solver(solver, instance_path))

        raise TerminateTaskGroup()


async def cli(args: argparse.Namespace) -> None:
    config = CLIConfig.load_config(args.config)

    if args.command == "run":
        app = SatCLI(config)
        await app.run()
    elif args.command == "show":
        config.show_config(args.config)
    elif args.command in [
        "add",
        "delete",
        "modify",
        "output_folder",
        "problem_path",
    ]:
        config.set_fields(args)


def main() -> None:
    parser = argparse.ArgumentParser(description="League of Solvers CLI.")
    parser.add_argument(
        "--config",
        help="Configuration file.",
        type=Path,
        default=Path(__file__).parent.parent.parent / "configs/default.json",
    )
    parser.add_argument(
        "--version",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Print verbose information.",
        dest="log_level",
        const=logging.INFO,
        action="store_const",
    )
    parser.add_argument(
        "--debug",
        help="Enable debug information.",
        dest="log_level",
        const=logging.DEBUG,
        action="store_const",
    )
    parser.add_argument(
        "--write_outputs",
        default=False,
        action="store_true",
        help="Write problem and solver outputs.",
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )

    # Subcommand: run
    subparsers.add_parser("run", help="Register and run the solvers.")

    # Subcommand: show
    subparsers.add_parser("show", help="Show the current configuration.")

    # Subcommand: add
    add_parser = subparsers.add_parser("add", help="Add a new solver.")
    add_parser.add_argument("token", help="Token for the solver.")
    add_parser.add_argument(
        "solver",
        help="Path to the SAT solver binary.",
        type=Path,
        default=None,
    )
    add_parser.add_argument(
        "--output",
        help="Path to the output file.",
        type=Path,
        default=None,
    )

    # Subcommand: delete
    delete_parser = subparsers.add_parser("delete", help="Delete a solver.")
    delete_parser.add_argument("token", help="Token of the solver to delete.")

    # Subcommand: modify
    modify_parser = subparsers.add_parser(
        "modify", help="Modify an existing solver."
    )
    modify_parser.add_argument("token", help="Token of the solver to modify.")
    modify_parser.add_argument(
        "--solver",
        help="Path to the SAT solver binary.",
        dest="new_solver",
        type=Path,
        default=None,
    )
    modify_parser.add_argument(
        "--token", help="Token for the solver.", dest="new_token"
    )
    modify_parser.add_argument(
        "--output",
        help="Path to the output file.",
        dest="new_output",
        type=Path,
        default=None,
    )

    output_folder_parser = subparsers.add_parser(
        "output_folder",
        help="Update the output folder path in the configuration file.",
    )

    output_folder_parser.add_argument(
        "output_folder",
        help="New output folder path to set in the configuration.",
    )

    problem_path_parser = subparsers.add_parser(
        "problem_path",
        help="Update the problem path in the configuration file.",
    )

    problem_path_parser.add_argument(
        "problem_path",
        help="New problem directory path to set in the configuration.",
    )

    args = parser.parse_args()

    if args.version:
        print("version:", __version__)

    if not args.command:
        print("No command given. Use --help for help.")

    debug = args.log_level == logging.DEBUG

    fmt = "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d %(message)s"
    logging.basicConfig(level=args.log_level, format=fmt)
    try:
        asyncio.run(cli(args), debug=debug)
    except KeyboardInterrupt as e:
        if args.log_level != logging.DEBUG:
            logger.info("Got Interrupted, Goodbye!")
        else:
            raise e from e
    except Exception as e:
        if debug:
            raise e from e
        else:
            logger.error(f"Error: {e}")
