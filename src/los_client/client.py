import hashlib
import base64
from typing import cast

import pyaes  # type: ignore[import-untyped]
from los_client import models
from los_client.config import CLIConfig
from dataclasses import dataclass
from websockets.asyncio.client import ClientConnection

from los_client.models import OkResponse


@dataclass
class Client:
    config: CLIConfig
    token: str = "dummy"
    host: str = "ws://localhost:8765"

    async def register_solver(self, ws: ClientConnection) -> None:
        models.Welcome.model_validate_json(await ws.recv())
        await ws.send(models.NextMatch().model_dump_json())
        print("Waiting for registration to open")
        await ws.recv()
        print("Registration is open, registering solver")
        await ws.send(
            models.RegisterSolver(solver_token=self.token).model_dump_json()
        )
        await ws.recv()
        print("Solver registered")

    async def run_solver(self, ws: ClientConnection) -> None:
        await ws.send(models.RequestInstance().model_dump_json())
        await ws.recv()
        encrypted_instance = await ws.recv()

        await ws.send(models.RequestKey().model_dump_json())
        msg = await ws.recv()
        keymsg = models.DecryptionKey.model_validate(
            cast(
                OkResponse, (models.ResponseAdapter.validate_json(msg))
            ).message
        )
        key = base64.b64decode(keymsg.key)
        aes = pyaes.AESModeOfOperationCTR(key)
        instance = aes.decrypt(encrypted_instance)
        print(instance)
        # TODO: run solver on instance
        dummy_sol = (True, [1, -2, 3])
        md5_hash = hashlib.md5(str(dummy_sol[1]).encode("utf-8")).hexdigest()

        await ws.send(
            models.Solution(
                solver_token=self.token,
                is_satisfiable=dummy_sol[0],
                assignment_hash=md5_hash,
            ).model_dump_json()
        )
        await ws.recv()

        await ws.send(
            models.Assignment(
                solver_token=self.token, assignment=dummy_sol[1]
            ).model_dump_json()
        )
        await ws.recv()
        print("Solution submitted")
