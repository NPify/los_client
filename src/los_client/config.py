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
    output_path: Path | None


class CLIConfig(BaseModel):
    solvers: List[Solver] = Field(default_factory=list)
    problem_path: Path = Path("problem.cnf")
    output_folder: Path = (
        Path(__file__).parent.parent.parent / "output"
    ).resolve()
    host: AnyUrl = AnyUrl("wss://los.npify.com/match_server/sat/")
    quiet: bool = False
    write_outputs: bool = False

    def model_post_init(self, context: Any) -> None:
        """
        We only want to overwrite properties if they changed because we
        use __pydantic_fields_set__ to detect explicitly set fields.
        """
        self.solvers = [
            Solver(
                solver.solver_path.resolve(), solver.token, solver.output_path
            )
            for solver in self.solvers
        ]
        resolved_output = self.output_folder.resolve()
        if self.output_folder != resolved_output:
            self.output_folder = resolved_output

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

    def overwrite(self, args: argparse.Namespace) -> None:
        set_args = {
            key: value
            for key, value in vars(args).items()
            if value is not None
        }

        if args.command == "add":
            if args.token not in [solver.token for solver in self.solvers]:
                self.solvers.append(
                    Solver(
                        solver_path=Path(args.solver),
                        token=args.token,
                        output_path=Path(args.output) if args.output else None,
                    )
                )
            else:
                raise ValueError(
                    f"Solver with token {args.token} already exists."
                )

        elif args.command == "delete":
            if args.token not in [solver.token for solver in self.solvers]:
                raise ValueError(
                    f"Solver with token {args.token} does not exist."
                )
            else:
                self.solvers = [
                    solver
                    for solver in self.solvers
                    if solver.token != args.token
                ]

        elif args.command == "modify":
            if args.token not in [solver.token for solver in self.solvers]:
                raise ValueError(
                    f"Solver with token {args.token} does not exist."
                )
            for solver in self.solvers:
                if solver.token == args.token:
                    if args.new_solver is not None:
                        solver.solver_path = Path(args.new_solver)
                    if args.new_output is not None:
                        solver.output_path = Path(args.new_output)
                    if args.new_token is not None:
                        solver.token = args.new_token

        set_args["solvers"] = self.solvers

        args_config = CLIConfig(**set_args)

        for field in args_config.__pydantic_fields_set__:
            setattr(self, field, getattr(args_config, field))

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
