import hmac
import logging

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

router = APIRouter(prefix="/opencode/containers", tags=["OpenCode containers"])
logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

_SAFE_SERVICE_ERROR = "OpenCode 容器服務暫時無法使用"


class ContainerCreated(BaseModel):
    id: str
    url: str
    upload_url: str
    upload_token: str
    cli_install_commands: dict[str, str]
    upload_command: str
    connect_url: str
    connect_token: str
    connect_command: str


class ContainerStatus(BaseModel):
    id: str
    status: Literal["healthy", "unhealthy"]
    url: str
    upload_url: str
    connect_url: str


def _tunnel_targets(url: str) -> tuple[str, str]:
    base = url.rstrip("/")
    if not base:
        return "", ""
    websocket_scheme = "wss" if base.startswith("https://") else "ws"
    return base + "/upload", websocket_scheme + "://" + base.split("://", 1)[1] + "/connect"


def _container_status(container: dict[str, str]) -> ContainerStatus:
    upload_url, connect_url = _tunnel_targets(container["url"])
    return ContainerStatus(**container, upload_url=upload_url, connect_url=connect_url)


def _authorize(request: Request, credentials: HTTPAuthorizationCredentials | None) -> None:
    token = request.app.state.settings.opencode_admin_token
    supplied = credentials.credentials if credentials else ""
    if not token or not hmac.compare_digest(supplied, token):
        raise HTTPException(status_code=401, detail="Management credentials required")


def _service_unavailable(message: str, *args: str) -> HTTPException:
    logger.exception(message, *args)
    return HTTPException(status_code=503, detail=_SAFE_SERVICE_ERROR)


def _cli_install_commands(release_url: str) -> dict[str, str]:
    release_url = release_url.rstrip("/")
    return {
        "windows_powershell": (
            f"$env:OPENCODE_PROJECT_RELEASE_URL = '{release_url}'; "
            f"irm '{release_url}/install.ps1' | iex"
        ),
        "macos": (
            f"curl -fsSL '{release_url}/install.sh' | "
            f"OPENCODE_PROJECT_RELEASE_URL='{release_url}' sh"
        ),
        "linux": (
            f"curl -fsSL '{release_url}/install.sh' | "
            f"OPENCODE_PROJECT_RELEASE_URL='{release_url}' sh"
        ),
    }


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
        cli_install_commands=_cli_install_commands(
            request.app.state.settings.opencode_cli_release_url
        ),
        upload_url=result["url"].rstrip("/") + "/upload",
        upload_command=(
            "opencode-project upload --url "
            + result["url"].rstrip("/") + "/upload"
            + f" --token={result['upload_token']} --project ."
        ),
        connect_url=("wss" if result["url"].startswith("https://") else "ws")
        + "://" + result["url"].split("://", 1)[1].rstrip("/") + "/connect",
        connect_token=connect_token,
        connect_command=(
            "opencode-project connect --url "
            + (("wss" if result["url"].startswith("https://") else "ws") + "://"
               + result["url"].split("://", 1)[1].rstrip("/") + "/connect")
            + f" --token={connect_token}"
        ),
    )


@router.get("", response_model=list[ContainerStatus])
def list_containers(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> list[ContainerStatus]:
    _authorize(request, credentials)
    try:
        return [_container_status(container) for container in request.app.state.container_manager.list()]
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
    return _container_status(container)


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
