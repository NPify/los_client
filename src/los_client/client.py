import asyncio
import base64
import hashlib
import logging
import lzma
import time
from dataclasses import dataclass
from typing import Any, assert_never

import pyaes  # type: ignore[import-untyped]
from websockets.asyncio.client import ClientConnection

from los_client import models
from los_client.config import CLIConfig

logger = logging.getLogger(__name__)


@dataclass
class SAT_solution:
    satisfiable: bool
    assignment: list[int]


@dataclass
class Client:
    config: CLIConfig
    ws: ClientConnection

    @staticmethod
    def response_ok(raw_response: str | bytes) -> Any:
        response = models.ResponseAdapter.validate_json(raw_response)
        if response.result == models.MessageTypes.ERROR:
            raise RuntimeError(response.error)
        return response.message

    async def welcome(self) -> None:
        models.Welcome.model_validate_json(await self.ws.recv())

    async def wait_closed(self) -> None:
        await self.ws.wait_closed()

    async def register_solvers(self) -> None:
        logger.info("Waiting for registration to open")
        await self.ws.send(models.NextMatch().model_dump_json())
        self.response_ok(await self.ws.recv())

        await self.query_errors(self.ws)

        logger.info("Registration is open, registering solvers")

        for solver in self.config.solvers:
            await self.ws.send(
                models.RegisterSolver(
                    solver_token=solver.token
                ).model_dump_json()
            )
            self.response_ok(await self.ws.recv())
            logger.info(f"Solver at {solver.solver_path} registered")

    async def get_instance(self) -> bytes:
        await self.ws.send(models.RequestInstance().model_dump_json())
        self.response_ok(await self.ws.recv())
        encrypted_instance = await self.ws.recv()
        if not isinstance(encrypted_instance, bytes):
            raise AssertionError("Expected bytes message got str.")

        logger.info("Waiting for match to start")

        await self.trigger_countdown()

        await self.ws.send(models.RequestKey().model_dump_json())
        msg = self.response_ok(await self.ws.recv())
        keymsg = models.DecryptionKey.model_validate(msg)
        return await asyncio.to_thread(
            self.decrypt, encrypted_instance, keymsg
        )

    def decrypt(
        self, encrypted_instance: bytes, keymsg: models.DecryptionKey
    ) -> bytes:
        key = base64.b64decode(keymsg.key)
        aes = pyaes.AESModeOfOperationCTR(key)
        return lzma.decompress(aes.decrypt(encrypted_instance))

    async def submit_solution(
        self, solver_token: str, solution: SAT_solution
    ) -> None:
        md5_hash = hashlib.md5(
            str(solution.assignment).encode("utf-8")
        ).hexdigest()

        await self.ws.send(
            models.Solution(
                solver_token=solver_token,
                is_satisfiable=solution.satisfiable,
                assignment_hash=md5_hash,
            ).model_dump_json()
        )

        logger.info("Solution submitted")


        if solution.satisfiable:
            data = models.Assignment(
                    solver_token=solver_token,
                    assignment=solution.assignment,
                ).model_dump_json()

            frame_size = 1024

            await self.ws.send((
                data[frame_size * i: frame_size*i + frame_size]
                for i in range(len(data) // frame_size + 1)
            ))
            logger.info("Assignment submitted")

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

    async def trigger_countdown(self) -> None:
        if not self.config.quiet:
            await self.ws.send(models.RequestStatus().model_dump_json())
            msg = self.response_ok(await self.ws.recv())
            status = models.Status.model_validate(msg)
            asyncio.create_task(self.start_countdown(status))

    async def start_countdown(
        self,
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

        print(
            "\r",
            flush=True,
        )
