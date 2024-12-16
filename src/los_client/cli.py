import argparse
import os
import sys
import json
import subprocess
import asyncio
from dataclasses import dataclass
from typing import Any

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
    output_folder = os.path.join(os.path.dirname(__file__) , "output")
    config : CLIConfig

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

    def confirm(self) -> None:
        if not (self.config.solver_path and self.config.output_path
                and self.config.problem_path):
            print("Error: Please provide all paths (-path, -output, -problem) "
                  "before confirmation.")
            return
        # TODO: Ensure the solver script is executable
        if False:
            try:
                result = subprocess.run(
                    [self.solver_path],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    print(f"Error: Build script at {self.solver_path} "
                          f"failed with return code {result.returncode}.")
                    print(f"stderr: {result.stderr}")
                    return

                print("Build script executed successfully.")
                print(f"stdout: {result.stdout}")
            except FileNotFoundError:
                print(f"Error: Build script not found at {self.solver_path}."
                      f" Ensure the path is correct.")
            except Exception as e:
                print(f"Error: An unexpected occurred while running the"
                      f" build script. Exception: {e}")

        open(os.path.join(self.output_folder,
                              self.config.problem_path + ".txt"), "w").close()
        open(os.path.join(self.output_folder,
                              self.config.output_path + ".txt"), "w").close()

        print("Configuration confirmed. Ready to run the solver.")

        from los_client.client import Client
        client = Client(self.config)
        asyncio.run(client.register_solver())
        asyncio.run(client.run_solver())


class Dummy:
    pass

def main() -> None:
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
        app.confirm()
    else:
        app.configure(args)

if __name__ == "__main__":
    main()
