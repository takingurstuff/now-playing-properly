import asyncio
import subprocess
from concurrent.futures import ProcessPoolExecutor
from ..common.communication_models import ConcExecResp, ConcExecReq


class ConcExecutor:
    def __init__(
        self, tqueue: asyncio.Queue[ConcExecReq], rqueue: asyncio.Queue[ConcExecResp]
    ):
        self.qin = tqueue
        self.qout = rqueue

    def execute_in_thread(self):
        pass
