import hmac

from fastapi import APIRouter, Header, HTTPException, Response, Request
from pydantic import BaseModel

router = APIRouter(prefix="/opencode/containers", tags=["OpenCode containers"])


class ContainerCreated(BaseModel):
    id: str
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
        raise HTTPException(status_code=503, detail=str(error)) from error
    return ContainerCreated(**result)


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
        raise HTTPException(status_code=503, detail=str(error)) from error
    return Response(status_code=204)
