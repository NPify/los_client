import asyncio
from pathlib import Path

from _pytest.capture import CaptureFixture
from websockets.asyncio.client import connect

from los_client import models
from los_client.cli import SatCLI
from los_client.client import Client


def test_register_and_run(capfd: CaptureFixture) -> None:
    cli = SatCLI()
    cli.output_folder = Path("tests/test_data/")
    cli.config.solver_path = Path("solver")
    cli.config.output_path = Path("output")
    cli.config.problem_path = Path("problem")
    client = Client(cli.config)

    async def helper() -> None:
        async with connect(client.host) as ws:
            models.Welcome.model_validate_json(await ws.recv())
            await client.register_solver(ws)
            await client.run_solver(ws)

    asyncio.run(helper())

    captured = capfd.readouterr()
    assert "Solver registered" in captured.out
    assert "Solution submitted" in captured.out
