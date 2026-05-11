from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from ..core.config import settings
from ..auth.roles import Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# убрал shit код отседа
def create_jwt_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.JWT_EXPIRY_DAYS)

    username = data.get("username") or data.get("sub")
    requested_role = data.get("role")
    valid_roles = {role.value for role in Role}
    user_role = Role.ADMIN.value if username == "admin" else requested_role
    if user_role not in valid_roles:
        user_role = Role.USER.value

    to_encode.update({
        "exp": expire,
        "role": user_role
    })
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")

        # Проверяем через try/except
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        try:
            Role(role)  # Пробуем создать Enum из строки
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid role"
            )
        return {"sub": user_id, "role": role}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
