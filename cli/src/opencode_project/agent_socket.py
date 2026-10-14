from __future__ import annotations

import ctypes
import os
import socket
from ctypes import wintypes

WINDOWS_AGENT_PIPE = r"\\.\pipe\openssh-ssh-agent"


def ssh_agent_address() -> str | None:
    return os.environ.get("SSH_AUTH_SOCK") or (WINDOWS_AGENT_PIPE if os.name == "nt" else None)


class _WindowsAgentPipe:
    """Small byte-stream adapter for the Windows OpenSSH agent named pipe."""

    def __init__(self, path: str):
        if os.name != "nt":
            raise OSError("Windows SSH agent pipes are only available on Windows")
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.CreateFileW.restype = wintypes.HANDLE
        self._kernel.CreateFileW.argtypes = (
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        )
        self._kernel.ReadFile.argtypes = (
            wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
        )
        self._kernel.WriteFile.argtypes = self._kernel.ReadFile.argtypes
        self._kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = self._kernel.CreateFileW(path, 0xC0000000, 0, None, 3, 0, None)
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handle = handle

    def sendall(self, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            remaining = data[offset:]
            buffer = ctypes.create_string_buffer(remaining)
            written = wintypes.DWORD()
            if not self._kernel.WriteFile(
                self._handle, buffer, len(remaining), ctypes.byref(written), None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if not written.value:
                raise OSError("Incomplete write to Windows SSH agent")
            offset += written.value

    def recv(self, size: int) -> bytes:
        buffer = ctypes.create_string_buffer(size)
        received = wintypes.DWORD()
        ok = self._kernel.ReadFile(self._handle, buffer, size, ctypes.byref(received), None)
        error = ctypes.get_last_error() if not ok else 0
        if not ok and error != 234:  # ERROR_MORE_DATA is a valid partial message.
            raise ctypes.WinError(error)
        if not received.value:
            return b""
        return buffer.raw[:received.value]

    def close(self) -> None:
        if self._handle is not None:
            self._kernel.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def connect_agent(address: str):
    if os.name == "nt" and address.startswith("\\\\.\\pipe\\"):
        return _WindowsAgentPipe(address)
    agent = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    agent.connect(address)
    return agent
