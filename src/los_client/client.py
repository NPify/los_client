import asyncio
import base64
import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pyaes  # type: ignore[import-untyped]
from websockets.asyncio.client import ClientConnection

from los_client import models
from los_client.config import CLIConfig

logger = logging.getLogger(__name__)


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

        for solver_path, token in self.config.solver_pairs:
            await ws.send(
                models.RegisterSolver(solver_token=token).model_dump_json()
            )
            self.response_ok(await ws.recv())
            logger.info(f"Solver at {solver_path} registered")

    async def get_instance(self, ws: ClientConnection) -> bytes:
        await ws.send(models.RequestInstance().model_dump_json())
        self.response_ok(await ws.recv())
        encrypted_instance = await ws.recv()

        logger.info("Waiting for match to start")

        if not self.config.quiet:
            await ws.send(models.RequestStatus().model_dump_json())
            msg = self.response_ok(await ws.recv())
            status = models.Status.model_validate(msg)
            asyncio.create_task(
                self.start_countdown(status.remaining, "Match starting in ")
            )

        await ws.send(models.RequestKey().model_dump_json())
        msg = self.response_ok(await ws.recv())
        keymsg = models.DecryptionKey.model_validate(msg)
        key = base64.b64decode(keymsg.key)
        aes = pyaes.AESModeOfOperationCTR(key)
        return cast(bytes, aes.decrypt(encrypted_instance))

    async def run_solver(
        self,
        ws: ClientConnection,
        solver_index: int,
        instance: bytes,
    ) -> None:
        with open(self.config.output / self.config.problem_path, "w") as f:
            f.write(instance.decode())

        if not self.config.quiet:
            await ws.send(models.RequestStatus().model_dump_json())
            msg = self.response_ok(await ws.recv())
            status = models.Status.model_validate(msg)
            asyncio.create_task(
                self.start_countdown(status.remaining, "Match ending in ")
            )

        logger.info("Running solver...")

        solver = self.config.solver_pairs[solver_index]

        result = await self.execute(solver[0])

        with open(self.config.output / self.config.output_path, "w") as f:
            f.write(result)

        sol = self.parse_result(result)
        if sol is None:
            logger.info("Solver could not determine satisfiability")
            return
        md5_hash = hashlib.md5(str(sol[1]).encode("utf-8")).hexdigest()

        await ws.send(
            models.Solution(
                solver_token=solver[1],
                is_satisfiable=sol[0],
                assignment_hash=md5_hash,
            ).model_dump_json()
        )

        logger.info("Solution submitted")

        if sol[0]:
            await ws.send(
                models.Assignment(
                    solver_token=solver[1], assignment=sol[1]
                ).model_dump_json()
            )
            logger.info("Assignment submitted")

    async def execute(self, solver_path: Path) -> str:
        process = await asyncio.create_subprocess_exec(
            solver_path,
            str(self.config.output / self.config.problem_path),
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
            logger.warning(
                "Solver timed out after 40 minutes,"
                " trying to terminate solver..."
            )
            await self.terminate(process)
            raise

        except asyncio.CancelledError:
            logger.warning("Server is down, trying to terminate solver...")
            await self.terminate(process)
            raise

        except FileNotFoundError:
            logger.warning(
                f"Solver binary "
                f"not found at {solver_path}."
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
    def parse_result(result: str) -> tuple[bool, list[int]] | None:
        satisfiable: bool = False
        assignments: list[int] = []
        for line in result.split("\n"):
            if line.startswith("c"):
                continue
            if line.startswith("s SATISFIABLE"):
                satisfiable = True
                continue
            if line.startswith("s UNSATISFIABLE"):
                return False, assignments
            if line.startswith("s UNKNOWN"):
                return None
            if line.startswith("v"):
                values = line[1:].split()
                assignments += list(map(int, values))
                if values[-1] == "0":
                    break
        return satisfiable, assignments

    async def query_errors(self, ws: ClientConnection) -> None:
        await ws.send(models.RequestErrors().model_dump_json())
        errors = models.SolverErrors.model_validate(
            self.response_ok(await ws.recv())
        ).errors

        if errors:
            logger.error("The following errors were reported by the server:")
        for solver_path, token in self.config.solver_pairs:
            if token in errors:
                logger.error(
                    f"Solver at {solver_path} had the following errors:"
                )
                for error in errors[token]:
                    logger.error(f"  - {error}")

    @staticmethod
    async def start_countdown(
        total_seconds: float, stage_description: str
    ) -> None:
        start_time = time.monotonic()
        end_time = start_time + total_seconds - 2

        while total_seconds > 0:
            current_time = time.monotonic()
            total_seconds = max(0, end_time - current_time)
            minutes = int(total_seconds) // 60
            seconds = int(total_seconds) % 60

            print(
                f"\r{stage_description} {minutes:02d}:{seconds:02d}...",
                end="",
                flush=True,
            )
            await asyncio.sleep(1)
