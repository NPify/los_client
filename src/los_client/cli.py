import argparse
import sys
import asyncio

from los_client import models
from los_client.config import CLIConfig
from los_client.client import Client
from dataclasses import dataclass
from websockets.asyncio.client import connect


@dataclass
class SatCLI:
    config: CLIConfig

    def __init__(self) -> None:
        self.config = CLIConfig()
        self.config.load_config()

    def configure(self, args: argparse.Namespace) -> None:
        if args.solver:
            self.config.solver_path = args.solver
            print(f"Solver path set to: {self.config.solver_path}")

        elif args.output:
            self.config.output_path = args.output
            print(f"Output path set to: {self.config.output_path}")

        elif args.problem:
            self.config.problem_path = args.problem
            print(f"Problem path set to: {self.config.problem_path}")
        self.config.save_config()

    async def run(self, config: CLIConfig) -> None:
        if not (
            self.config.solver_path
            and self.config.output_path
            and self.config.problem_path
        ):
            print(
                "Error: Please provide all paths (-path, -output, -problem) "
                "before running."
            )
            return

        open(self.config.output_folder / self.config.problem_path, "w").close()
        open(self.config.output_folder / self.config.output_path, "w").close()

        print("Configuration confirmed. Ready to register and run the solver.")

        client = Client(config)
        try:
            async with connect(client.host) as ws:
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
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )

    run_parser = subparsers.add_parser(
        "run", help="Register and run the solver."
    )
    run_parser.add_argument(
        "-solver", nargs="?", help="Path to the SAT solver binary."
    )
    run_parser.add_argument(
        "-output",
        nargs="?",
        help="Path to the file where you want the solution to be written. ",
    )
    run_parser.add_argument(
        "-problem",
        nargs="?",
        help="Path to the file where you want the problem to be written.",
    )

    # Subcommand: show
    subparsers.add_parser("show", help="Show the current configuration.")

    # Subcommand: set
    set_parser = subparsers.add_parser("set", help="Set the path.")
    set_parser.add_argument(
        "-solver",
        help="Path to the SAT solver execution script.",
    )
    set_parser.add_argument(
        "-output",
        help="Path to the file where you want the solution to be written.",
    )
    set_parser.add_argument(
        "-problem",
        help="Path to the file where you want the problem to be written.",
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    app = SatCLI()

    if args.command == "run":
        await app.run(app.config)
    elif args.command == "show":
        app.config.show_config()
    elif args.command == "set":
        app.configure(args)


def main() -> None:
    asyncio.run(cli())
