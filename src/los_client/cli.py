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
from los_client.config import CLIConfig

logger = logging.getLogger(__name__)


class TerminateTaskGroup(Exception):
    pass


@dataclass
class SatCLI:
    config: CLIConfig
    excluded_solvers: List[int] = field(default_factory=list)
    single_run: bool = False

    def configure(self, args: argparse.Namespace) -> None:
        if args.solvers:
            logger.info(f"Solver paths added: {args.solvers}")

        if args.output:
            logger.info(f"Output path set to: {self.config.output}")

        if args.tokens:
            logger.info(f"Tokens added: {args.tokens}")
        print("LMAO", args)
        self.config.save_config(args.config)

    async def run(self) -> None:
        self.validate_config()
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
        if not (
            self.config.solver_pairs
            and self.config.output_path
            and self.config.problem_path
        ):
            raise ValueError(
                "Missing required paths: -path, -output, -problem"
            )

    def setup_output_files(self) -> None:
        os.makedirs(self.config.output, exist_ok=True)
        open(self.config.output / self.config.problem_path, "w").close()
        open(self.config.output / self.config.output_path, "w").close()

    async def process_solvers(
        self, ws: ClientConnection, client: Client
    ) -> None:
        while True:
            await client.register_solvers(ws)
            instance = await client.get_instance(ws)

            if not self.config.quiet:
                await ws.send(models.RequestStatus().model_dump_json())
                msg = client.response_ok(await ws.recv())
                status = models.Status.model_validate(msg)
                asyncio.create_task(
                    client.start_countdown(
                        status.remaining, "Match ending in "
                    )
                )
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
            # TODO: Change the x to the actual pair
            x_to_task = {}
            for x in range(len(self.config.solver_pairs)):
                if x in self.excluded_solvers:
                    continue
                task = asyncio.create_task(client.run_solver(ws, x, instance))
                tasks.append(task)
                x_to_task[task] = x

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for task, result in zip(tasks, results):
                x = x_to_task[task]
                if isinstance(result, FileNotFoundError):
                    self.excluded_solvers.append(x)
                elif isinstance(result, TimeoutError):
                    logger.warning(
                        f"Solver at {x} timed out. Will attempt to run it "
                        f"again next match."
                    )

            raise TerminateTaskGroup()
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise


async def cli(args: argparse.Namespace) -> None:
    config = CLIConfig.load_config(args.config)
    config.overwrite(args)

    app = SatCLI(config)

    if args.command == "run":
        await app.run()
    elif args.command == "show":
        app.config.show_config()
    elif args.command == "set":
        app.configure(args)


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

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )

    run_parser = subparsers.add_parser(
        "run", help="Register and run the solvers."
    )
    run_parser.add_argument(
        "--solvers",
        nargs="+",
        help="Paths to one or more SAT solver binaries.",
    )
    run_parser.add_argument(
        "--output",
        help="Path to the file where you want the solution to be written. ",
    )
    run_parser.add_argument(
        "--tokens",
        nargs="+",
        help="Token for the solvers obtained from 'http://los.npify.com'.",
    )

    # Subcommand: show
    subparsers.add_parser("show", help="Show the current configuration.")

    # Subcommand: set
    set_parser = subparsers.add_parser("set", help="Set the path.")
    set_parser.add_argument(
        "--solvers",
        nargs="+",
        help="Paths to one or more SAT solver binaries.",
    )
    set_parser.add_argument(
        "--output",
        help="Path to the file where you want the solution to be written.",
    )
    set_parser.add_argument(
        "--tokens",
        nargs="+",
        help="Token for the solver obtained from 'http://los.npify.com'.",
    )

    args = parser.parse_args()

    if args.version:
        print("version:", __version__)

    if not args.command:
        print("No command given. Use --help for help.")

    logging.basicConfig(level=args.log_level)
    try:
        asyncio.run(cli(args))
    except KeyboardInterrupt as e:
        if args.log_level != logging.DEBUG:
            logger.info("Got KeyboardInterrupt, Goodbye!")
        else:
            raise e from e
    except Exception as e:
        if args.log_level == logging.DEBUG:
            raise e from e
        else:
            logger.error(f"Error: {e}")
