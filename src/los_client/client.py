import hashlib
import base64
from typing import Any
import asyncio
import pyaes  # type: ignore[import-untyped]
from los_client import models
from los_client.config import CLIConfig
from dataclasses import dataclass
from websockets.asyncio.client import ClientConnection


@dataclass
class Client:
    config: CLIConfig
    token: str = "dummy"
    host: str = "ws://localhost:8765"

    @staticmethod
    def response_ok(raw_response: str | bytes) -> Any:
        response = models.ResponseAdapter.validate_json(raw_response)
        if response.result == models.MessageTypes.ERROR:
            print(response.error)
        assert response.result == models.MessageTypes.OK
        return response.message

    async def register_solver(self, ws: ClientConnection) -> None:
        await ws.send(models.NextMatch().model_dump_json())
        print("Waiting for registration to open")
        self.response_ok(await ws.recv())
        print("Registration is open, registering solver")
        await ws.send(
            models.RegisterSolver(solver_token=self.token).model_dump_json()
        )
        self.response_ok(await ws.recv())
        print("Solver registered")

    async def run_solver(self, ws: ClientConnection) -> None:
        await ws.send(models.RequestInstance().model_dump_json())
        self.response_ok(await ws.recv())
        encrypted_instance = await ws.recv()

        await ws.send(models.RequestKey().model_dump_json())
        msg = self.response_ok(await ws.recv())
        keymsg = models.DecryptionKey.model_validate(msg)
        key = base64.b64decode(keymsg.key)
        aes = pyaes.AESModeOfOperationCTR(key)
        instance = aes.decrypt(encrypted_instance)
        print(f"Retrieved Problem:\n {instance}")

        with open(
            self.config.output_folder / self.config.problem_path, "w"
        ) as f:
            f.write(instance.decode())

        print("Running solver...")

        result = await self.execute()

        if not result:
            return

        with open(
            self.config.output_folder / self.config.output_path, "w"
        ) as f:
            f.write(result)

        sol = self.parse_result(result)
        if sol is None:
            print("Solver could not determine satisfiability")
            return
        md5_hash = hashlib.md5(str(sol[1]).encode("utf-8")).hexdigest()

        await ws.send(
            models.Solution(
                solver_token=self.token,
                is_satisfiable=sol[0],
                assignment_hash=md5_hash,
            ).model_dump_json()
        )
        self.response_ok(await ws.recv())
        print("Solution submitted")

        if sol[0]:
            await ws.send(
                models.Assignment(
                    solver_token=self.token, assignment=sol[1]
                ).model_dump_json()
            )
            self.response_ok(await ws.recv())
            print("Assignment submitted")

    async def execute(self) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                self.config.solver_path,
                str(self.config.output_folder / self.config.problem_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            print("Solver executed successfully.")
            print(f"stdout: {stdout.decode()}")
            print(f"stderr: {stderr.decode()}")
            return stdout.decode()
        except FileNotFoundError:
            print(
                f"Error: Solver binary "
                f"not found at {self.config.solver_path}."
                f"Ensure the path is correct."
            )
            return ""
        except Exception as e:
            print(
                f"Error: An unexpected error occurred while running the "
                f"solver. Exception: {e}"
            )
            return ""

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
