import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from los_client.client import Client, SAT_solution
from los_client.config import CLIConfig, Solver

logger = logging.getLogger(__name__)


@dataclass
class SolverRunner:
    config: CLIConfig
    solver: Solver
    client: Client

    async def run_solver(self, instance_path: Path) -> None:
        logger.info(f"Running solver {self.solver.solver_path}.")

        result = await self.execute(instance_path)

        if self.config.write_outputs and self.solver.output_path:
            with open(
                self.config.output_folder / self.solver.output_path, "w"
            ) as f:
                f.write(result)

        solution = self.parse_result(result)

        if solution is None:
            logger.info(f"Unknown answer from {self.solver.solver_path}.")
            return

        if solution.satisfiable:
            logger.info(f"SAT answer from {self.solver.solver_path}.")
        else:
            logger.info(f"UNSSAT answer from {self.solver.solver_path}.")

        await self.client.submit_solution(self.solver.token, solution)

    async def execute(self, path: Path) -> str:
        args = list(self.solver.args) + [str(path)]

        try:
            process = await asyncio.create_subprocess_exec(
                self.solver.solver_path,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 60 * 40
            )
            logger.debug(f"stdout: {stdout.decode()}")
            logger.debug(f"stderr: {stderr.decode()}")
            return stdout.decode()

        except TimeoutError:
            await self.terminate(process)
            raise

        except asyncio.CancelledError:
            await self.terminate(process)
            raise

        except FileNotFoundError:
            logger.error(
                f"Solver binary "
                f"not found at {self.solver.solver_path}. "
                f"Ensure the path is correct."
            )
            raise

    @staticmethod
    async def terminate(process: asyncio.subprocess.Process) -> None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 30)
        except TimeoutError:
            process.kill()
            await process.wait()
        logger.info("Solver terminated.")

    @staticmethod
    def parse_result(result: str) -> SAT_solution | None:
        parsed_successfull = False
        satisfiable: bool = False
        assignments: list[int] = []
        for line in result.split("\n"):
            if line.startswith("c"):
                continue
            if line.startswith("s SATISFIABLE"):
                satisfiable = True
                parsed_successfull = True
                continue
            if line.startswith("s UNSATISFIABLE"):
                parsed_successfull = True
                return SAT_solution(False, assignments)
            if line.startswith("s UNKNOWN"):
                parsed_successfull = True
                return None
            if line.startswith("v"):
                values = line[1:].split()
                assignments += list(map(int, values))
                if values[-1] == "0":
                    break

        if not parsed_successfull:
            raise RuntimeError("Failed to parse SAT solver output.")

        return SAT_solution(satisfiable, assignments)
