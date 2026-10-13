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
    cli_install_command: str = "uv tool install ./cli"
    upload_command: str


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
    )


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
