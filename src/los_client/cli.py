import argparse
import os
import sys
import json
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from websockets.asyncio.client import connect

@dataclass
class CLIConfig:
    json_path: str
    solver_path: str = ""
    output_path: str = ""
    problem_path: str = ""

    def load_config(self) -> None:

        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r") as config_file:
                    config_json = json.load(config_file)
                    self.solver_path = config_json.get("solver_path")
                    self.output_path = config_json.get("output_path")
                    self.problem_path = config_json.get("problem_path")
            except (json.JSONDecodeError, IOError):
                print("Warning: Failed to load configuration."
                      " Creating new one.")
                self.save_config()
        else:
            print("No existing configuration found. Creating new one.")
            self.save_config()

    def save_config(self) -> None:

        config_json = {
            "solver_path": self.solver_path,
            "output_path": self.output_path,
            "problem_path": self.problem_path,
        }
        try:
            with open(self.json_path, "w") as config_file:
                json.dump(config_json, config_file)
        except IOError as e:
            print(f"Error saving configuration: {e}", file=sys.stderr)

@dataclass
class SatCLI:
    config : CLIConfig
    output_folder: Path = Path(__file__).resolve().parent / "output"

    def __init__(self) -> None:
        self.config = CLIConfig(os.path.join(
            self.output_folder, "config.json"))
        self.config.load_config()

    def configure(self, args:Any) -> None:

        if args.solver:
            if isinstance(args.solver, Dummy):
                print("Current path to solver is: ", (self.config.solver_path
                            if self.config.solver_path!="" else "No path set"))
            else:
                self.config.solver_path = args.solver
                print(f"Solver path set to: {self.config.solver_path}")
                self.config.save_config()

        if args.output:
            if isinstance(args.output, Dummy) :
                print("Current path to output file is: ", self.config.
                output_path if self.config.output_path!="" else "No path set")
            else:
                self.config.output_path = args.output
                print(f"Output path set to: {self.config.output_path}")
                self.config.save_config()

        if args.problem:
            if isinstance(args.problem, Dummy):
                print("Current path to problem file is: ", self.config.
                problem_path if self.config.problem_path!=""else "No path set")
            else:
                self.config.problem_path = args.problem
                print(f"Problem path set to: {self.config.problem_path}")
                self.config.save_config()

    async def confirm(self) -> None:
        if not (self.config.solver_path and self.config.output_path
                and self.config.problem_path):
            print("Error: Please provide all paths (-path, -output, -problem) "
                  "before confirmation.")
            return
        # TODO: Ensure the solver script is executable
        if False:
            try:
                process = await asyncio.create_subprocess_exec(
                    self.solver_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    print(f"Error: Build script at {self.solver_path} "
                          f"failed with return code {process.returncode}.")
                    print(f"stderr: {stderr.decode()}")
                    return

                print("Build script executed successfully.")
                print(f"stdout: {stdout.decode()}")
            except FileNotFoundError:
                print(f"Error: Build script not found at {self.solver_path}. "
                      f"Ensure the path is correct.")
            except Exception as e:
                print(f"Error: An unexpected error occurred while running the "
                      f"build script. Exception: {e}")

        open(os.path.join(self.output_folder,
                              self.config.problem_path + ".txt"), "w").close()
        open(os.path.join(self.output_folder,
                              self.config.output_path + ".txt"), "w").close()

        print("Configuration confirmed. Ready to run the solver.")

        from los_client.client import Client
        client = Client(self.config)  # type: ignore
        async with connect(client.host) as ws:
            await client.register_solver(ws)
            await client.run_solver(ws)


class Dummy:
    pass

async def cli() -> None:
    parser = argparse.ArgumentParser(description="League of Solvers CLI.")
    parser.add_argument("-solver",nargs='?', const=Dummy(), help="Path"
                " to the SAT solver execution script. If no path is provided, "
                "then current path is displayed.")
    parser.add_argument("-output", nargs="?", const=Dummy(), help="Path"
                " to the file where you want the solution to be written. "
                "If no path is provided, then current path is displayed.")
    parser.add_argument("-problem", nargs="?", const=Dummy(), help="Path"
                " to the file where you want the problem to be written. "
                "If no path is provided, then current path is displayed.")
    parser.add_argument("-confirm", action="store_true", help=
                "Confirm configuration and register the solver")
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    app = SatCLI()

    if args.confirm:
        await app.confirm()
    else:
        app.configure(args)

def main()->None:
    asyncio.run(cli())

if __name__ == "__main__":
    main()
