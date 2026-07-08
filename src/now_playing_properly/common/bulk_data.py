import os
import mmap
import fcntl
from typing import Optional


class BulkData:
    """
    Ancillary Data. The bytes in this class are not sent in band over unix domain sockets,
    instead they are placed in a shm segment, and the fd is sent over unix domain sockets.
    """

    def __init__(self, data: bytes | bytearray, name: str, size: Optional[int] = None):
        self.data = data
        self.name = name
        self.size = size if size else len(data)

    def ready_shrmem(self):
        shm = os.memfd_create(self.name, os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        os.ftruncate(shm, self.size)
        with mmap.mmap(
            shm, self.size, flag=mmap.MAP_SHARED, prot=mmap.PROT_WRITE
        ) as shm_view:
            shm_view[: self.size] = self.data
        seals = (
            fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_SEAL
        )
        fcntl.fcntl(shm, fcntl.F_ADD_SEALS, seals)
        return self.size, shm

    @classmethod
    def from_shmem(cls, fd: int, size: int, name: str = "recovered_shm"):
        """Reads data back out of a sealed shared memory file descriptor."""
        with mmap.mmap(fd, size, flag=mmap.MAP_SHARED, prot=mmap.PROT_READ) as shm_view:
            data = shm_view.read(size)
        os.close(fd)

        return cls(data=data, name=name, size=size)
