from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, List, Tuple

from pydantic import AnyUrl, BaseModel, Field


class CLIConfig(BaseModel):
    solver_pairs: List[Tuple[Path, str]] = Field(default_factory=list)
    output_path: Path = Path("stdout.txt")
    problem_path: Path = Path("problem.cnf")
    output: Path = (Path(__file__).parent.parent.parent / "output").resolve()
    host: AnyUrl = AnyUrl("wss://los.npify.com/match_server/sat/")
    quiet: bool = False

    def model_post_init(self, context: Any) -> None:
        """
        We only want to overwrite properties if they changed because we
        use __pydantic_fields_set__ to detect explicitly set fields.
        """
        self.solver_pairs = [
            (solver.resolve(), token) for solver, token in self.solver_pairs
        ]
        resolved_output = self.output.resolve()
        if self.output != resolved_output:
            self.output = resolved_output

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

        solvers = set_args.pop("solvers", [])
        tokens = set_args.pop("tokens", [])
        if solvers and tokens:
            if len(solvers) != len(tokens):
                raise ValueError()

            solver_pairs = [
                (Path(solver), token) for solver, token in zip(solvers, tokens)
            ]
            set_args["solver_pairs"] = solver_pairs

        args_config = CLIConfig(**set_args)

        for field in args_config.__pydantic_fields_set__:
            if field == "solver_pairs" and not solvers and not tokens:
                continue
            setattr(self, field, getattr(args_config, field))

    def save_config(self, json_path: Path) -> None:
        os.makedirs(json_path.parent, exist_ok=True)
        with open(json_path, "w") as config_file:
            print(self.model_dump_json(indent=4), file=config_file)

    def show_config(self) -> None:
        print("Solver pairs (path, token):")
        for solver, token in self.solver_pairs:
            print(f"  Solver: {solver}, Token: {token}")
        print(f"Problem path: {self.problem_path}")
        print(f"Output path: {self.output}")
