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
    return ContainerCreated(**result)


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
