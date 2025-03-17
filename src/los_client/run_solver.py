import asyncio
import logging
from dataclasses import dataclass

from los_client.client import Client, SAT_solution
from los_client.config import CLIConfig, Solver

logger = logging.getLogger(__name__)


@dataclass
class SolverRunner:
    config: CLIConfig
    solver: Solver
    client: Client

    async def run_solver(
        self,
        instance: bytes,
    ) -> None:
        with open(
            self.config.output_folder / self.config.problem_path, "w"
        ) as f:
            f.write(instance.decode())

        logger.info("Running solver...")

        result = await self.execute()

        if self.config.write_outputs and self.solver.output_path:
            with open(
                self.config.output_folder / self.solver.output_path, "w"
            ) as f:
                f.write(result)

        solution = self.parse_result(result)

        if solution is None:
            logger.info("Solver could not determine satisfiability")
            return

        await self.client.submit_solution(self.solver.token, solution)

    async def execute(self) -> str:
        args = list(self.solver.args) + [
            str(self.config.output_folder / self.config.problem_path)
        ]

        process = await asyncio.create_subprocess_exec(
            self.solver.solver_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
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
                f"not found at {self.solver.solver_path}."
                f"Ensure the path is correct. Pausing this solver's"
                f" execution in future matches."
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
        satisfiable: bool = False
        assignments: list[int] = []
        for line in result.split("\n"):
            if line.startswith("c"):
                continue
            if line.startswith("s SATISFIABLE"):
                satisfiable = True
                continue
            if line.startswith("s UNSATISFIABLE"):
                return SAT_solution(False, assignments)
            if line.startswith("s UNKNOWN"):
                return None
            if line.startswith("v"):
                values = line[1:].split()
                assignments += list(map(int, values))
                if values[-1] == "0":
                    break
        return SAT_solution(satisfiable, assignments)
