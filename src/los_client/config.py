from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pydantic import AnyUrl, BaseModel


class CLIConfig(BaseModel):
    solver: Path = Path().resolve()
    output_path: Path = Path("stdout.txt")
    problem_path: Path = Path("problem.cnf")
    output: Path = (Path(__file__).parent.parent.parent / "output").resolve()
    token: str = "dummy"
    host: AnyUrl = AnyUrl("wss://los.npify.com/match_server/sat/")

    def model_post_init(self, context: Any) -> None:
        """
        We only want to overwrite poperties if they changed because we
        use __pydantic_fields_set__ to detect explicitly set fields.
        """
        resolved = self.solver.resolve()
        if self.solver != resolved:
            self.solver = resolved
        resolved = self.output.resolve()
        if self.output != resolved:
            self.output = resolved

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
        print(f"Solver path: {self.solver}")
        print(f"Output path: {self.output}")
        print(f"Token: {self.token}")
