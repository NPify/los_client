import asyncio
import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

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
        print(response.message)
        return response.message

    async def register_solver(self, ws: ClientConnection) -> None:
        logger.info("Waiting for registration to open")
        await ws.send(models.NextMatch().model_dump_json())
        self.response_ok(await ws.recv())
        logger.info("Registration is open, registering solver")
        await ws.send(
            models.RegisterSolver(
                solver_token=self.config.token
            ).model_dump_json()
        )
        self.response_ok(await ws.recv())
        logger.info("Solver registered")

    async def run_solver(self, ws: ClientConnection, quiet: bool) -> None:
        await ws.send(models.RequestInstance().model_dump_json())
        self.response_ok(await ws.recv())
        encrypted_instance = await ws.recv()

        logger.info("Waiting for match to start")

        if not quiet:
            # TODO: Get the time from the server
            asyncio.create_task(self.start_countdown(1, "Match starting in "))

        await ws.send(models.RequestKey().model_dump_json())
        msg = self.response_ok(await ws.recv())
        keymsg = models.DecryptionKey.model_validate(msg)
        key = base64.b64decode(keymsg.key)
        aes = pyaes.AESModeOfOperationCTR(key)
        instance = aes.decrypt(encrypted_instance)

        with open(self.config.output / self.config.problem_path, "w") as f:
            f.write(instance.decode())

        if not quiet:
            asyncio.create_task(self.start_countdown(2700, "Match ending in "))

        logger.info("Running solver...")

        result = await self.execute()

        if not result:
            return

        with open(self.config.output / self.config.output_path, "w") as f:
            f.write(result)

        sol = self.parse_result(result)
        if sol is None:
            logger.warning("Solver could not determine satisfiability")
            return
        md5_hash = hashlib.md5(str(sol[1]).encode("utf-8")).hexdigest()

        await ws.send(
            models.Solution(
                solver_token=self.config.token,
                is_satisfiable=sol[0],
                assignment_hash=md5_hash,
            ).model_dump_json()
        )
        self.response_ok(await ws.recv())
        logger.info("Solution submitted")

        if sol[0]:
            await ws.send(
                models.Assignment(
                    solver_token=self.config.token, assignment=sol[1]
                ).model_dump_json()
            )
            self.response_ok(await ws.recv())
            logger.info("Assignment submitted")

    async def execute(self) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                self.config.solver,
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
                return ""

            except asyncio.CancelledError:
                logger.warning("Server is down, trying to terminate solver...")
                await self.terminate(process)
                return ""

            except FileNotFoundError:
                logger.error(
                    f"Error: Solver binary "
                    f"not found at {self.config.solver}."
                    f"Ensure the path is correct."
                )
                return ""
        except Exception as e:
            logger.error(
                f"Error: An unexpected error occurred while running the "
                f"solver. Exception: {e}"
            )
            return ""
        return ""

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

    @staticmethod
    async def start_countdown(total_seconds: int, type: str) -> None:
        while total_seconds > 0:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            print(f"\r{type} {minutes}:{seconds}...", end="", flush=True)
            await asyncio.sleep(1)
            total_seconds -= 1
