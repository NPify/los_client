import asyncio
import base64
import hashlib
import logging
import lzma
import time
from dataclasses import dataclass
from typing import Any, assert_never, cast

import pyaes  # type: ignore[import-untyped]
from websockets.asyncio.client import ClientConnection

from los_client import models
from los_client.config import CLIConfig, Solver

logger = logging.getLogger(__name__)


@dataclass
class SAT_solution:
    satisfiable: bool
    assignment: list[int]


@dataclass
class Client:
    config: CLIConfig

    @staticmethod
    def response_ok(raw_response: str | bytes) -> Any:
        response = models.ResponseAdapter.validate_json(raw_response)
        if response.result == models.MessageTypes.ERROR:
            raise RuntimeError(response.error)
        return response.message

    async def register_solvers(self, ws: ClientConnection) -> None:
        logger.info("Waiting for registration to open")
        await ws.send(models.NextMatch().model_dump_json())
        self.response_ok(await ws.recv())

        await self.query_errors(ws)

        logger.info("Registration is open, registering solvers")

        for solver in self.config.solvers:
            await ws.send(
                models.RegisterSolver(
                    solver_token=solver.token
                ).model_dump_json()
            )
            self.response_ok(await ws.recv())
            logger.info(f"Solver at {solver.solver_path} registered")

    async def get_instance(self, ws: ClientConnection) -> bytes:
        await ws.send(models.RequestInstance().model_dump_json())
        self.response_ok(await ws.recv())
        encrypted_instance = await ws.recv()

        logger.info("Waiting for match to start")

        await self.trigger_countdown(ws)

        await ws.send(models.RequestKey().model_dump_json())
        msg = self.response_ok(await ws.recv())
        keymsg = models.DecryptionKey.model_validate(msg)
        key = base64.b64decode(keymsg.key)
        aes = pyaes.AESModeOfOperationCTR(key)
        return cast(bytes, lzma.decompress(aes.decrypt(encrypted_instance)))

    async def run_solver(
        self,
        ws: ClientConnection,
        solver: Solver,
        instance: bytes,
    ) -> None:
        if self.config.write_outputs:
            with open(
                self.config.output_folder / self.config.problem_path, "w"
            ) as f:
                f.write(instance.decode())

        logger.info("Running solver...")

        result = await self.execute(solver)

        if self.config.write_outputs and solver.output_path:
            with open(
                self.config.output_folder / solver.output_path, "w"
            ) as f:
                f.write(result)

        sol = self.parse_result(result)

        if sol is None:
            logger.info("Solver could not determine satisfiability")
            return
        md5_hash = hashlib.md5(str(sol.assignment).encode("utf-8")).hexdigest()

        await ws.send(
            models.Solution(
                solver_token=solver.token,
                is_satisfiable=sol.satisfiable,
                assignment_hash=md5_hash,
            ).model_dump_json()
        )

        logger.info("Solution submitted")

        if sol.satisfiable:
            await ws.send(
                models.Assignment(
                    solver_token=solver.token, assignment=sol.assignment
                ).model_dump_json()
            )
            logger.info("Assignment submitted")

    async def execute(self, solver: Solver) -> str:
        args = list(solver.args) + [
            str(self.config.output_folder / self.config.problem_path)
        ]

        process = await asyncio.create_subprocess_exec(
            solver.solver_path,
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
            logger.error("Server is down, trying to terminate solver...")
            await self.terminate(process)
            raise

        except FileNotFoundError:
            logger.error(
                f"Solver binary "
                f"not found at {solver.solver_path}."
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

    async def query_errors(self, ws: ClientConnection) -> None:
        await ws.send(models.RequestErrors().model_dump_json())
        errors = models.SolverErrors.model_validate(
            self.response_ok(await ws.recv())
        ).errors

        if errors:
            logger.error("The following errors were reported by the server:")
        for solver in self.config.solvers:
            if solver.token in errors:
                logger.error(
                    f"Solver at {solver.solver_path} had the following errors:"
                )
                for error in errors[solver.token]:
                    logger.error(f"  - {error}")

    async def trigger_countdown(self, ws: ClientConnection) -> None:
        if not self.config.quiet:
            await ws.send(models.RequestStatus().model_dump_json())
            msg = self.response_ok(await ws.recv())
            status = models.Status.model_validate(msg)
            asyncio.create_task(self.start_countdown(status))

    @staticmethod
    async def start_countdown(
        status: models.Status,
    ) -> None:
        start_time = time.monotonic()
        end_time = start_time + status.remaining - 1

        while status.remaining > 0:
            current_time = time.monotonic()
            status.remaining = max(0, end_time - current_time)
            minutes = int(status.remaining) // 60
            seconds = int(status.remaining) % 60
            match status.state:
                case models.State.running:
                    message = "Match ending in "
                case models.State.registration:
                    message = "Match starting in "
                case models.State.finished:
                    message = "Match has ended"
                case other:
                    assert_never(other)

            print(
                f"\r{message} {minutes:02d}:{seconds:02d}...",
                end="",
                flush=True,
            )
            await asyncio.sleep(1)
