from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Literal
import structlog

from core.config import settings
from core.exceptions import InvalidTokenError, InsufficientPermissionsError

logger = structlog.get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    sub: str                                    
    role: Literal["caregiver", "doctor", "admin"]
    patient_id: str                             
    patient_name: str
    patient_age: int
    patient_stage: int                         
    iat: int | None = None
    exp: int | None = None


def _decode_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(**payload)
    except JWTError as e:
        logger.warning("jwt_decode_failed", error=str(e))
        raise InvalidTokenError(internal=str(e))
    except Exception as e:
        logger.error("jwt_unexpected_error", error=str(e))
        raise InvalidTokenError(internal=str(e))


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    if not settings.is_production and request.headers.get("X-Dev-Bypass") == "true":
        logger.warning("auth_bypassed_dev_mode")
        user = TokenPayload(
            sub="dev-user-001",
            role="caregiver",
            patient_id="dev-patient-001",
            patient_name="Ahmed Ben Ali",
            patient_age=75,
            patient_stage=1,
        )
        request.state.user_id = user.sub
        return user

    if not credentials:
        raise InvalidTokenError(internal="No Authorization header")

    user = _decode_token(credentials.credentials)
    request.state.user_id = user.sub

    structlog.contextvars.bind_contextvars(
        user_id=user.sub,
        user_role=user.role,
        patient_id=user.patient_id,
    )

    return user


def require_role(*allowed_roles: str):
   
    async def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if user.role not in allowed_roles:
            logger.warning(
                "access_denied",
                user_role=user.role,
                required_roles=allowed_roles,
            )
            raise InsufficientPermissionsError(
                internal=f"Role {user.role} not in {allowed_roles}"
            )
        return user
    return _check


async def verify_internal_key(request: Request) -> None:
    if settings.is_production:
        if not settings.internal_api_key:
            raise InsufficientPermissionsError(
                internal="FASTAPI_INTERNAL_API_KEY not configured in production"
            )
        key = request.headers.get("X-Internal-Key")
        if key != settings.internal_api_key:
            logger.warning("invalid_internal_key", path=request.url.path)
            raise InvalidTokenError(internal="Missing or invalid X-Internal-Key")
    else:
        if not settings.internal_api_key:
            return
        key = request.headers.get("X-Internal-Key")
        if key != settings.internal_api_key:
            logger.warning("invalid_internal_key", path=request.url.path)
            raise InvalidTokenError(internal="Missing or invalid X-Internal-Key")