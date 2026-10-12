import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

router = APIRouter(prefix="/opencode/containers", tags=["OpenCode containers"])
logger = logging.getLogger(__name__)

_SAFE_SERVICE_ERROR = "OpenCode 容器服務暫時無法使用"


class ContainerCreated(BaseModel):
    id: str
    url: str


class ContainerStatus(BaseModel):
    id: str
    status: str
    url: str


def _authorize(request: Request, authorization: str | None) -> None:
    token = request.app.state.settings.opencode_admin_token
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not token or not hmac.compare_digest(supplied, token):
        raise HTTPException(status_code=401, detail="Management credentials required")


@router.post("", response_model=ContainerCreated, status_code=201)
def create_container(request: Request, authorization: str | None = Header(default=None)) -> ContainerCreated:
    _authorize(request, authorization)
    try:
        result = request.app.state.container_manager.create()
    except Exception as error:
        logger.exception("Failed to create OpenCode container")
        raise HTTPException(status_code=503, detail=_SAFE_SERVICE_ERROR) from error
    return ContainerCreated(**result)


@router.get("", response_model=list[ContainerStatus])
def list_containers(request: Request, authorization: str | None = Header(default=None)) -> list[ContainerStatus]:
    _authorize(request, authorization)
    try:
        return [ContainerStatus(**container) for container in request.app.state.container_manager.list()]
    except Exception as error:
        logger.exception("Failed to list OpenCode containers")
        raise HTTPException(status_code=503, detail=_SAFE_SERVICE_ERROR) from error


@router.get("/{container_id}", response_model=ContainerStatus)
def get_container(
    container_id: str, request: Request, authorization: str | None = Header(default=None)
) -> ContainerStatus:
    _authorize(request, authorization)
    try:
        container = request.app.state.container_manager.get(container_id)
    except Exception as error:
        logger.exception("Failed to retrieve OpenCode container %s", container_id)
        raise HTTPException(status_code=503, detail=_SAFE_SERVICE_ERROR) from error
    if container is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    return ContainerStatus(**container)


@router.delete("/{container_id}", status_code=204)
def delete_container(
    container_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    _authorize(request, authorization)
    try:
        request.app.state.container_manager.delete(container_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Managed container not found") from error
    except Exception as error:
        logger.exception("Failed to delete OpenCode container %s", container_id)
        raise HTTPException(status_code=503, detail=_SAFE_SERVICE_ERROR) from error
    return Response(status_code=204)
