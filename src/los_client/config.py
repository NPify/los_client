from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, List

from pydantic import AnyUrl, BaseModel, Field


class CLIConfig(BaseModel):
    solvers: List[Path] = Field(default_factory=list)
    output_path: Path = Path("stdout.txt")
    problem_path: Path = Path("problem.cnf")
    output: Path = (Path(__file__).parent.parent.parent / "output").resolve()
    tokens: List[str] = Field(default_factory=list)
    host: AnyUrl = AnyUrl("wss://los.npify.com/match_server/sat/")
    quiet: bool = False

    def model_post_init(self, context: Any) -> None:
        """
        We only want to overwrite properties if they changed because we
        use __pydantic_fields_set__ to detect explicitly set fields.
        """
        # Resolve each solver path
        self.solvers = [solver.resolve() for solver in self.solvers]

        # Resolve the output path
        resolved_output = self.output.resolve()
        if self.output != resolved_output:
            self.output = resolved_output

    @staticmethod
    def load_config(json_path: Path) -> CLIConfig:
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
        args_config = CLIConfig(**set_args)
        for field in args_config.__pydantic_fields_set__:
            setattr(self, field, getattr(args_config, field))

    def save_config(self, json_path: Path) -> None:
        with open(json_path, "w") as config_file:
            print(self.model_dump_json(indent=4), file=config_file)

    def show_config(self) -> None:
        print(f"Solver paths: {self.solvers}")
        print(f"Output path: {self.output}")
        print(f"Token: {self.tokens}")
