from enum import StrEnum, auto
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, Field, TypeAdapter


class ProtocolVersion(BaseModel):
    major: int = 1
    minor: int = 0


class Welcome(BaseModel):
    version: ProtocolVersion = Field(default_factory=ProtocolVersion)


class MessageTypes(StrEnum):
    OK = auto()
    ERROR = auto()
    RegisterSolver = auto()
    RequestStatus = auto()
    RequestKey = auto()
    RequestInstance = auto()
    Solution = auto()
    Assignment = auto()
    NextMatch = auto()


class RegisterSolver(BaseModel):
    message_type: Literal[MessageTypes.RegisterSolver] = (
        MessageTypes.RegisterSolver
    )
    solver_token: str


class RequestStatus(BaseModel):
    message_type: Literal[MessageTypes.RequestStatus] = (
        MessageTypes.RequestStatus
    )


class State(StrEnum):
    registration = auto()
    running = auto()
    finished = auto()


class Status(BaseModel):
    state: State
    remaining: float = Field(description="Remaining time in current state.")


class RequestKey(BaseModel):
    message_type: Literal[MessageTypes.RequestKey] = MessageTypes.RequestKey


class DecryptionKey(BaseModel):
    key: str = Field(
        description="Base64 encoded AES/CTR key" " to decrypt the instance."
    )


class RequestInstance(BaseModel):
    message_type: Literal[MessageTypes.RequestInstance] = (
        MessageTypes.RequestInstance
    )


class InstanceInfo(BaseModel):
    size: int


class Solution(BaseModel):
    message_type: Literal[MessageTypes.Solution] = MessageTypes.Solution
    solver_token: str
    is_satisfiable: bool
    assignment_hash: str | None = None


class Assignment(BaseModel):
    message_type: Literal[MessageTypes.Assignment] = MessageTypes.Assignment
    solver_token: str
    assignment: list[int]


class NextMatch(BaseModel):
    message_type: Literal[MessageTypes.NextMatch] = MessageTypes.NextMatch


MainMessage: TypeAlias = (
    RegisterSolver
    | RequestStatus
    | RequestKey
    | Solution
    | Assignment
    | NextMatch
    | RequestInstance
)

MainMessageAdapter: TypeAdapter[MainMessage] = TypeAdapter(
    Annotated[MainMessage, Field(discriminator="message_type")]
)


class OkResponse(BaseModel):
    result: Literal[MessageTypes.OK] = MessageTypes.OK
    message: Any


class ErrorResponse(BaseModel):
    result: Literal[MessageTypes.ERROR] = MessageTypes.ERROR
    error: Any


Response = Annotated[OkResponse | ErrorResponse, Field(discriminator="result")]


ResponseAdapter: TypeAdapter[Response] = TypeAdapter(Response)
# Use ResponseAdapter.model_validate_json(data) to validate the message.
