import argparse
import os
import sys
import json
from typing import Any


class SatCLI:
    output_folder = os.path.join(os.path.dirname(__file__) , "output")
    config = os.path.join(output_folder, "config.json")
    def __init__(self) -> None:
        self.solver_path = ""
        self.output_path = ""
        self.problem_path = ""

        self.load_config()

    def load_config(self) -> None:

        if os.path.exists(self.config):
            try:
                with open(self.config, "r") as config_file:
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
            with open(self.config, "w") as config_file:
                json.dump(config_json, config_file)
        except IOError as e:
            print(f"Error saving configuration: {e}", file=sys.stderr)

    def configure(self, args:Any) -> None:

        if args.solver:
            if isinstance(args.solver, Dummy):
                print("Current path to solver is: ", (self.solver_path
                                if self.solver_path!="" else "No path set"))
            else:
                self.solver_path = args.solver
                print(f"Solver path set to: {self.solver_path}")
                self.save_config()

        if args.output:
            if isinstance(args.output, Dummy) :
                print("Current path to output file is: ", self.output_path
                                if self.output_path!="" else "No path set")
            else:
                self.output_path = args.output
                print(f"Output path set to: {self.output_path}")
                self.save_config()

        if args.problem:
            if isinstance(args.problem, Dummy):
                print("Current path to problem file is: ", self.problem_path
                                if self.problem_path!="" else "No path set")
            else:
                self.problem_path = args.problem
                print(f"Problem path set to: {self.problem_path}")
                self.save_config()

    def confirm(self) -> None:
        if not (self.solver_path and self.output_path and self.problem_path):
            print("Error: Please provide all paths (-path, -output, -problem) "
                  "before confirmation.")
            return

        # TODO: Confirm solver works
        if False:
            print(f"Error: Solver executable not found at {self.solver_path}.")
            return

        if not os.path.isfile(self.problem_path):
            open(os.path.join(self.output_folder,
                              self.problem_path + ".txt"), "w").close()

        if not os.path.isfile(self.output_path):
            open(os.path.join(self.output_folder,
                              self.output_path + ".txt"), "w").close()

        print("Configuration confirmed. Ready to run the solver.")
        # TODO: Do stuff with backend


class Dummy:
    pass

def main() -> None:
    parser = argparse.ArgumentParser(description="League of Solvers CLI.")
    parser.add_argument("-solver",nargs='?', const=Dummy(), help="Path"
                    " to the SAT solver executable. If no path is provided, "
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
