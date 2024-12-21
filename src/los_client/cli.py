import argparse
import asyncio
import sys
from dataclasses import dataclass

from websockets.asyncio.client import connect

from los_client import models
from los_client.client import Client
from los_client.config import CLIConfig
from pathlib import Path
import os

@dataclass
class SatCLI:
    config: CLIConfig

    def configure(self, args: argparse.Namespace) -> None:
        if args.solver:
            print(f"Solver path set to: {self.config.solver}")

        if args.output:
            print(f"Output path set to: {self.config.output}")

        if args.token:
            print(f"Token set to: {self.config.token}")

        self.config.save_config(args.config)

    async def run(self, config: CLIConfig) -> None:
        if not (
            self.config.solver
            and self.config.output_path
            and self.config.problem_path
        ):
            print(
                "Error: Please provide all paths (-path, -output, -problem) "
                "before running."
            )
            return

        os.makedirs(self.config.output, exist_ok=True)
        open(self.config.output / self.config.problem_path, "w").close()
        open(self.config.output / self.config.output_path, "w").close()

        print("Configuration confirmed. Ready to register and run the solver.")

        client = Client(config)
        try:
            async with connect(str(client.config.host)) as ws:
                models.Welcome.model_validate_json(await ws.recv())
                await client.register_solver(ws)
                await client.run_solver(ws)
        except OSError:
            print(
                "Error: Connection refused. "
                "Please ensure the server is running."
            )


async def cli() -> None:
    parser = argparse.ArgumentParser(description="League of Solvers CLI.")
    parser.add_argument(
        "--config",
        help="Configuration file.",
        type=Path,
        default=Path(__file__).parent.parent.parent / "configs/default.json"
    )
    parser.add_argument(
        "--debug",
        default=False,
        action="store_true",
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )

    run_parser = subparsers.add_parser(
        "run", help="Register and run the solver."
    )
    run_parser.add_argument(
        "--solver", help="Path to the SAT solver binary."
    )
    run_parser.add_argument(
        "--output",
        help="Path to the file where you want the solution to be written. ",
    )
    run_parser.add_argument(
        "--token",
        help="Token for the solver optained from 'http://los.npify.com'.",
    )

    # Subcommand: show
    subparsers.add_parser("show", help="Show the current configuration.")

    # Subcommand: set
    set_parser = subparsers.add_parser("set", help="Set the path.")
    set_parser.add_argument(
        "--solver",
        help="Path to the SAT solver execution script.",
    )
    set_parser.add_argument(
        "--output",
        help="Path to the file where you want the solution to be written.",
    )
    set_parser.add_argument(
        "--token",
        help="Token for the solver optained from 'http://los.npify.com'.",
    )

    args = parser.parse_args()

    try:
        config = CLIConfig.load_config(args.config)
        config.overwrite(args)

        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(1)

        app = SatCLI(config)

        if args.command == "run":
            await app.run(app.config)
        elif args.command == "show":
            app.config.show_config()
        elif args.command == "set":
            app.configure(args)
    except Exception as e:
        if not args.debug:
            print(f"Error: {e}", file=sys.stderr)
        else:
            raise e


def main() -> None:
    asyncio.run(cli())
