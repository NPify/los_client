import argparse
import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import WebSocketException

from los_client import models
from los_client.__about__ import __version__
from los_client.client import Client
from los_client.config import CLIConfig, Solver

logger = logging.getLogger(__name__)


class TerminateTaskGroup(Exception):
    pass


@dataclass
class SatCLI:
    config: CLIConfig
    excluded_solvers: List[Solver] = field(default_factory=list)
    single_run: bool = False

    async def run(self) -> None:
        self.validate_config()
        if self.config.write_outputs:
            self.setup_output_files()

        logger.info(
            "Configuration confirmed. Ready to register and run the solver."
        )

        sleep_time = 1
        client = Client(self.config)

        while True:
            try:
                async with connect(
                    str(client.config.host), max_size=1024 * 1024 * 32
                ) as ws:
                    try:
                        sleep_time = 1
                        models.Welcome.model_validate_json(await ws.recv())
                        await self.process_solvers(ws, client)
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

    async def process_solvers(
        self, ws: ClientConnection, client: Client
    ) -> None:
        while True:
            await client.trigger_countdown(ws)

            await client.register_solvers(ws)

            instance = await client.get_instance(ws)

            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self.wait_for_close(ws))
                    tg.create_task(self.run_solvers(client, ws, instance))
            except* TerminateTaskGroup:
                pass
            if self.single_run:
                break

    @staticmethod
    async def wait_for_close(ws: ClientConnection) -> None:
        await ws.wait_closed()
        raise TerminateTaskGroup()

    async def run_solvers(
        self, client: Client, ws: ClientConnection, instance: bytes
    ) -> None:
        tasks = []
        try:
            task_to_solver = {}
            for solver in self.config.solvers:
                if solver in self.excluded_solvers:
                    continue
                task = asyncio.create_task(
                    client.run_solver(ws, solver, instance)
                )
                tasks.append(task)
                task_to_solver[task] = solver

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for task, result in zip(tasks, results):
                solver = task_to_solver[task]
                if isinstance(result, FileNotFoundError):
                    self.excluded_solvers.append(solver)
                elif isinstance(result, TimeoutError):
                    logger.error(
                        f"Solver at {solver.solver_path} timed out. "
                        f"Will attempt to run it "
                    )

            raise TerminateTaskGroup()
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise


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
        "--quiet",
        default=False,
        action="store_true",
        help="Disable countdown display.",
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

    logging.basicConfig(level=args.log_level)
    try:
        asyncio.run(cli(args))
    except (KeyboardInterrupt, asyncio.CancelledError) as e:
        if args.log_level != logging.DEBUG:
            logger.info("Got Interrupted, Goodbye!")
        else:
            raise e from e
    except Exception as e:
        if args.log_level == logging.DEBUG:
            raise e from e
        else:
            logger.error(f"Error: {e}")
