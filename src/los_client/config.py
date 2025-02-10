from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

from pydantic import AnyUrl, BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class Solver:
    solver_path: Path
    token: str
    args: list[str]
    output_path: Path | None


DEFAULT_OUTPUT = (Path(__file__).parent.parent.parent / "output").resolve()


class CLIConfig(BaseModel):
    solvers: List[Solver] = Field(default_factory=list)
    problem_path: Path = Path("problem.cnf")
    output_folder: Path = DEFAULT_OUTPUT
    host: AnyUrl = AnyUrl("wss://los.npify.com/match_server/sat/")
    quiet: bool = False
    write_outputs: bool = False

    def model_post_init(self, context: Any) -> None:
        for solver in self.solvers:
            solver.solver_path = solver.solver_path.resolve()
            if solver.output_path:
                solver.output_path = solver.output_path.resolve()

        self.output_folder = self.output_folder.resolve()

    @staticmethod
    def load_config(json_path: Path) -> CLIConfig:
        os.makedirs(json_path.parent, exist_ok=True)
        try:
            with open(json_path, "r") as config_file:
                return CLIConfig.model_validate_json(config_file.read())
        except FileNotFoundError:
            config = CLIConfig()
            config.save_config(json_path)
            return config

    def set_fields(self, args: argparse.Namespace) -> None:
        match args.command:
            case "add":
                self.add_solver(args)
            case "delete":
                self.delete_solver(args)
            case "modify":
                self.modify_solver(args)
            case "output_folder":
                self.output_folder = args.output_folder
            case "problem_path":
                self.problem_path = args.problem_path
            case _:
                raise AssertionError("Unknown command.")

        self.save_config(args.config)

    def add_solver(self, args: argparse.Namespace) -> None:
        if args.token in [solver.token for solver in self.solvers]:
            raise ValueError(f"Solver with token {args.token} already exists.")
        else:
            self.solvers.append(
                Solver(
                    solver_path=args.solver,
                    args=[],
                    token=args.token,
                    output_path=args.output if args.output else None,
                )
            )

    def delete_solver(self, args: argparse.Namespace) -> None:
        if args.token not in [solver.token for solver in self.solvers]:
            raise ValueError(f"Solver with token {args.token} does not exist.")
        else:
            self.solvers = [
                solver for solver in self.solvers if solver.token != args.token
            ]

    def modify_solver(self, args: argparse.Namespace) -> None:
        if args.token not in [solver.token for solver in self.solvers]:
            raise ValueError(f"Solver with token {args.token} does not exist.")
        for solver in self.solvers:
            if solver.token == args.token:
                if args.new_solver is not None:
                    solver.solver_path = args.new_solver
                if args.new_output is not None:
                    solver.output_path = args.new_output
                if args.new_token is not None:
                    solver.token = args.new_token

    def save_config(self, json_path: Path) -> None:
        os.makedirs(json_path.parent, exist_ok=True)
        with open(json_path, "w") as config_file:
            print(self.model_dump_json(indent=4), file=config_file)

    def show_config(self, config_path: Path) -> None:
        print(f"Showing configuration file at: {config_path}")
        print("Solvers:")
        for solver in self.solvers:
            print(
                f" - Solver: {solver.solver_path}, Token: {solver.token}, "
                f"Output: {solver.output_path}"
            )
        print(f"Problem path: {self.problem_path}")
        print(f"Output Folder: {self.output_folder}")
