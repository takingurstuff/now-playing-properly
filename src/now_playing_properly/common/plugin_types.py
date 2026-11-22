import abc
import asyncio
import inspect
from pydantic import BaseModel
from dataclasses import dataclass
from .metadata_spec import AudioMetadata, AudioMetadata
from typing import (
    Any,
    Dict,
    Type,
    Union,
    Literal,
    Callable,
    Optional,
    Awaitable,
)
from .communication_models import (
    ReqType,
    NetworkReq,
    NetworkResp,
    SeekRequest,
    ConcExecReq,
    ConcExecResp,
    SubprocessReq,
    ActionRequest,
    SubprocessResp,
    PluginReqTypes,
    PluginRespTypes,
    PluginEventTypes,
)
import random


@dataclass
class PluginResponse:
    modified_keys: Optional[AudioMetadata]
    added_keys: Optional[Dict[str, Any]]


class BasePluginConfig(BaseModel):
    priority: int = 0
    enabled: bool = True


@dataclass
class Hook:
    name: str
    condition: Callable[[PluginEventTypes, BasePluginConfig], bool]
    handler: Callable[
        [PluginEventTypes, BasePluginConfig],
        Optional[PluginResponse | Awaitable[PluginResponse]],
    ]


@dataclass
class CoreComms:
    q_in: asyncio.Queue[PluginRespTypes]
    q_out: asyncio.Queue[PluginReqTypes]


def hook(condition=None):
    def dec(func):
        func._is_hook = True
        func._condition = condition
        return func

    return dec


class BasePluginContent(abc.ABC):

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Check if the subclass defined its own __init__
        if "__init__" in cls.__dict__:
            raise TypeError(
                f"Plugin '{cls.__name__}' is defining an __init__ method! "
                f"Plugin authors must not use __init__. Use 'setup()' (sync or async) instead."
            )
        cls._hooks: list[Hook] = []
        for n, v in cls.__dict__.items():
            if getattr(v, "_is_hook", False):
                cls._hooks.append(Hook(n, v._condition, v))

    def __init__(self, corecomms: CoreComms, loop: asyncio.AbstractEventLoop):
        self._q_in = corecomms.q_in
        self._q_out = corecomms.q_out
        self._loop = loop
        self._pending: dict[str, asyncio.Future] = {}

    def begin(self):
        self._respt = self._loop.create_task(self._resp())

    async def finish(self):
        await self._respt.cancel()

    async def _resp(self):
        try:
            while True:
                resp = await self._q_in.get()
                if resp.id in self._pending:
                    if resp.exc:
                        self._pending[resp.id].set_exception(resp.exc)
                    else:
                        self._pending[resp.id].set_result(resp)
        except asyncio.CancelledError:
            pass

    async def run_in_process(self, func: Callable, *args, **kwargs) -> ConcExecResp:
        fut = asyncio.Future()
        id = random.randbytes(16)
        self._pending[id] = fut
        await self._q_out.put(ConcExecReq(False, func, args, kwargs, id))
        return await fut

    async def run_in_thread(self, func: Callable, *args, **kwargs) -> ConcExecResp:
        fut = asyncio.Future()
        id = random.randbytes(16)
        self._pending[id] = fut
        await self._q_out.put(ConcExecReq(True, func, args, kwargs, id))
        return await fut

    async def run_command_subprocess(self, *args) -> SubprocessResp:
        fut = asyncio.Future()
        id = random.randbytes(16)
        self._pending[id] = fut
        await self._q_out.put(SubprocessReq(args, id))
        return await fut

    # ONLY SUPPORTS CRUD ENDPOINTS. WS and etc may come at a later version
    async def networkreqest(
        self,
        url: str,
        req_type: ReqType,
        params: dict[str, Any],
        extra_headers: dict[str, Any],
    ) -> NetworkResp:
        fut = asyncio.Future()
        id = random.randbytes(16)
        self._pending[id] = fut
        await self._q_out.put(NetworkReq(req_type, url, params, extra_headers, id))
        return await fut

    @abc.abstractmethod
    def init(self, config: BasePluginConfig) -> None | Awaitable[None]: ...
    @abc.abstractmethod
    def deinit(self, config: BasePluginConfig) -> None | Awaitable[None]: ...


@dataclass
class BasePlugin:
    name: str
    config: Type[BasePluginConfig]
    content: Type[BasePluginContent]


@dataclass
class UnixFD:
    """
    small helper class, when a plugin wants to return a unixfd in its custom data, wrap the file descriptor integer in this class so later marshalling can understand it
    """

    fd: int
