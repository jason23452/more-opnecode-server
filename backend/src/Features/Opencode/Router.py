import hmac
import logging
import shlex

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

router = APIRouter(prefix="/opencode/containers", tags=["OpenCode containers"])
cli_router = APIRouter(prefix="/opencode", tags=["OpenCode CLI"])
logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)
CommandEnvironment = Literal["mac", "windows", "linux"]

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
    upload_command: str | None = None
    connect_command: str | None = None


class CliInstallCommand(BaseModel):
    environment: CommandEnvironment
    command: str


def _tunnel_targets(url: str) -> tuple[str, str]:
    base = url.rstrip("/")
    if not base:
        return "", ""
    websocket_scheme = "wss" if base.startswith("https://") else "ws"
    return base + "/upload", websocket_scheme + "://" + base.split("://", 1)[1] + "/connect"


def _container_status(
    container: dict[str, str],
    environment: CommandEnvironment | None = None,
    command_tokens: dict[str, str] | None = None,
) -> ContainerStatus:
    upload_url, connect_url = _tunnel_targets(container["url"])
    result = {
        "id": container["id"],
        "status": container["status"],
        "url": container["url"],
        "upload_url": upload_url,
        "connect_url": connect_url,
    }
    if environment and command_tokens:
        if environment == "windows":
            quote = lambda value: "'" + value.replace("'", "''") + "'"
        else:
            quote = shlex.quote
        result["upload_command"] = (
            "opencode-project upload --url " + quote(upload_url)
            + " --token=" + quote(command_tokens["upload_token"]) + " --project ."
        )
        result["connect_command"] = (
            "opencode-project connect --url " + quote(connect_url)
            + " --token=" + quote(command_tokens["connect_token"])
        )
    return ContainerStatus(**result)


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


def _selected_release_url(release: dict) -> str:
    return f"https://github.com/jason23452/more-opnecode-server/releases/download/{release['tag_name']}"


def _resolve_cli_release(request: Request) -> dict:
    try:
        return request.app.state.cli_release_selector.select(
            request.app.state.settings.opencode_cli_channel
        )
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="目前無法取得此 CLI 發布通道的可用版本",
        ) from error


def _cli_install_command(release_url: str, environment: CommandEnvironment) -> str:
    key = {"mac": "macos", "windows": "windows_powershell", "linux": "linux"}[environment]
    return _cli_install_commands(release_url)[key]


@router.post("", response_model=ContainerCreated, status_code=201)
def create_container(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ContainerCreated:
    _authorize(request, credentials)
    release = _resolve_cli_release(request)
    try:
        result = request.app.state.container_manager.create()
    except Exception as error:
        raise _service_unavailable("Failed to create OpenCode container") from error
    connect_token = result.pop("connect_token")
    _, connect_url = _tunnel_targets(result["url"])
    return ContainerCreated(
        **result,
        cli_install_commands=_cli_install_commands(_selected_release_url(release)),
        upload_url=result["url"].rstrip("/") + "/upload",
        upload_command=(
            "opencode-project upload --url "
            + result["url"].rstrip("/") + "/upload"
            + f" --token={result['upload_token']} --project ."
        ),
        connect_url=connect_url,
        connect_token=connect_token,
        connect_command=(
            "opencode-project connect --url "
            + connect_url
            + f" --token={connect_token}"
        ),
    )


@router.get("", response_model=list[ContainerStatus], response_model_exclude_none=True)
def list_containers(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> list[ContainerStatus]:
    _authorize(request, credentials)
    try:
        return [_container_status(container) for container in request.app.state.container_manager.list()]
    except Exception as error:
        raise _service_unavailable("Failed to list OpenCode containers") from error


@router.get("/{container_id}", response_model=ContainerStatus, response_model_exclude_none=True)
def get_container(
    container_id: str,
    request: Request,
    environment: CommandEnvironment | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ContainerStatus:
    _authorize(request, credentials)
    try:
        container = request.app.state.container_manager.get(container_id)
    except Exception as error:
        raise _service_unavailable("Failed to retrieve OpenCode container %s", container_id) from error
    if container is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    command_tokens = None
    if environment:
        try:
            command_tokens = request.app.state.container_manager.get_command_tokens(container_id)
        except Exception as error:
            raise _service_unavailable("Failed to retrieve CLI command credentials for container %s", container_id) from error
    return _container_status(container, environment, command_tokens)


@cli_router.get("/cli-install-command", response_model=CliInstallCommand)
def get_cli_install_command(
    request: Request,
    environment: CommandEnvironment = Query(...),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CliInstallCommand:
    _authorize(request, credentials)
    release = _resolve_cli_release(request)
    return CliInstallCommand(
        environment=environment,
        command=_cli_install_command(_selected_release_url(release), environment),
    )


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
