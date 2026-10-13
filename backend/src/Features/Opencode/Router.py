import asyncio
import hmac
import logging
import os
import select
import subprocess

from fastapi.security.utils import get_authorization_scheme_param
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .DockerCli import docker_command

router = APIRouter(prefix="/opencode/containers", tags=["OpenCode containers"])
logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

_SAFE_SERVICE_ERROR = "OpenCode 容器服務暫時無法使用"


class ContainerCreated(BaseModel):
    id: str
    url: str
    upload_url: str
    upload_token: str
    cli_install_command: str = "uv tool install ./cli"
    upload_command: str
    connect_url: str
    connect_token: str
    connect_command: str


class ContainerStatus(BaseModel):
    id: str
    status: Literal["healthy", "unhealthy"]
    url: str


def _authorize(request: Request, credentials: HTTPAuthorizationCredentials | None) -> None:
    token = request.app.state.settings.opencode_admin_token
    supplied = credentials.credentials if credentials else ""
    if not token or not hmac.compare_digest(supplied, token):
        raise HTTPException(status_code=401, detail="Management credentials required")


def _service_unavailable(message: str, *args: str) -> HTTPException:
    logger.exception(message, *args)
    return HTTPException(status_code=503, detail=_SAFE_SERVICE_ERROR)


@router.post("", response_model=ContainerCreated, status_code=201)
def create_container(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ContainerCreated:
    _authorize(request, credentials)
    try:
        result = request.app.state.container_manager.create()
    except Exception as error:
        raise _service_unavailable("Failed to create OpenCode container") from error
    connect_token = result.pop("connect_token")
    return ContainerCreated(
        **result,
        upload_url=str(request.base_url).rstrip("/")
        + f"{request.app.state.settings.api_prefix}/opencode/containers/{result['id']}/upload",
        upload_command=(
            "opencode-project upload --url "
            + str(request.base_url).rstrip("/")
            + f"{request.app.state.settings.api_prefix}/opencode/containers/{result['id']}/upload"
            + f" --token={result['upload_token']} --project ."
        ),
        connect_url=("ws" if request.url.scheme == "http" else "wss") + "://" + request.url.netloc
        + f"{request.app.state.settings.api_prefix}/opencode/containers/{result['id']}/connect",
        connect_token=connect_token,
        connect_command=(
            "opencode-project connect --url "
            + (("ws" if request.url.scheme == "http" else "wss") + "://" + request.url.netloc)
            + f"{request.app.state.settings.api_prefix}/opencode/containers/{result['id']}/connect"
            + f" --token={connect_token}"
        ),
    )


@router.websocket("/{container_id}/connect")
async def connect_tui(websocket: WebSocket, container_id: str) -> None:
    scheme, token = get_authorization_scheme_param(websocket.headers.get("authorization", ""))
    if scheme.lower() != "bearer":
        token = ""
    manager = websocket.app.state.container_manager
    try:
        session = manager.open_tui(container_id, token)
    except PermissionError:
        await websocket.accept()
        await websocket.close(code=4401, reason="連線授權無效，請使用建立容器時提供的連線資訊")
        return
    except LookupError:
        await websocket.accept()
        await websocket.close(code=4404, reason="找不到此 OpenCode 容器")
        return
    except RuntimeError:
        await websocket.accept()
        await websocket.close(code=4409, reason="此容器已有 TUI 工作階段，請稍後重試")
        return

    process = None
    output_stream = None
    try:
        await websocket.accept()
        process = subprocess.Popen(
            docker_command("exec", "-i", container_id, "python3", "/usr/local/bin/opencode-pty-runner",
                           "sh", "-lc", "cd /workspace/project && exec opencode ."),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        output_stream = process.stdout
        while process.poll() is None:
            readable, _, _ = select.select([output_stream], [], [], 0.02)
            if readable:
                output = os.read(output_stream.fileno(), 65536)
                if output:
                    await websocket.send_bytes(output)
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.02)
            except asyncio.TimeoutError:
                continue
            if message.get("type") == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data:
                process.stdin.write(data)
                process.stdin.flush()
            elif message.get("text") == "\x04":
                break
    except Exception:
        logger.info("Remote TUI session disconnected for %s", container_id)
    finally:
        if process and process.poll() is None:
            if process.stdin:
                process.stdin.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if output_stream is not None:
            output_stream.close()
        manager.close_tui(session)


@router.put("/{container_id}/upload", status_code=204)
async def upload_project(
    container_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Response:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Container upload token required")
    archive = await request.body()
    if len(archive) > 512 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Project archive exceeds 512 MiB")
    token = credentials.credentials if credentials else ""
    try:
        request.app.state.container_manager.upload(container_id, token, archive)
    except PermissionError as error:
        raise HTTPException(status_code=401, detail="Invalid container upload token") from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Managed container not found") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid project archive") from error
    except Exception as error:
        raise _service_unavailable("Failed to upload project to container %s", container_id) from error
    return Response(status_code=204)


@router.get("", response_model=list[ContainerStatus])
def list_containers(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> list[ContainerStatus]:
    _authorize(request, credentials)
    try:
        return [ContainerStatus(**container) for container in request.app.state.container_manager.list()]
    except Exception as error:
        raise _service_unavailable("Failed to list OpenCode containers") from error


@router.get("/{container_id}", response_model=ContainerStatus)
def get_container(
    container_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ContainerStatus:
    _authorize(request, credentials)
    try:
        container = request.app.state.container_manager.get(container_id)
    except Exception as error:
        raise _service_unavailable("Failed to retrieve OpenCode container %s", container_id) from error
    if container is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    return ContainerStatus(**container)


@router.delete("/{container_id}", status_code=204)
def delete_container(
    container_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Response:
    _authorize(request, credentials)
    try:
        request.app.state.container_manager.delete(container_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Managed container not found") from error
    except Exception as error:
        raise _service_unavailable("Failed to delete OpenCode container %s", container_id) from error
    return Response(status_code=204)
