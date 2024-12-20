import os
import sys
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CLIConfig:
    solver_path: Path = Path()
    output_path: Path = Path()
    problem_path: Path = Path()
    output_folder: Path = Path(__file__).resolve().parent / "output"
    json_path: Path = output_folder / "config.json"

    def load_config(self) -> None:
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r") as config_file:
                    config_json = json.load(config_file)
                    self.solver_path = config_json.get("solver_path")
                    self.output_path = config_json.get("output_path")
                    self.problem_path = config_json.get("problem_path")
            except (json.JSONDecodeError, IOError):
                print(
                    "Warning: Failed to load configuration."
                    " Creating new one."
                )
                self.save_config()
        else:
            print("No existing configuration found. Creating new one.")
            self.save_config()

    def save_config(self) -> None:
        config_json = {
            "solver_path": str(self.solver_path),
            "output_path": str(self.output_path),
            "problem_path": str(self.problem_path),
        }
        try:
            with open(self.json_path, "w") as config_file:
                json.dump(config_json, config_file)
        except IOError as e:
            print(f"Error saving configuration: {e}", file=sys.stderr)

    def show_config(self) -> None:
        print(f"Solver path: {self.solver_path}")
        print(f"Output path: {self.output_path}")
        print(f"Problem path: {self.problem_path}")
