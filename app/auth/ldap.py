from ldap3 import Server, Connection, ALL, SUBTREE
from loguru import logger
from ..core.config import settings
from fastapi import HTTPException


async def authenticate_ldap(username: str, password: str):
    if not settings.LDAP_ENABLED:
        raise HTTPException(status_code=400, detail="LDAP authentication is disabled")

    server = Server(settings.LDAP_SERVER, get_info=ALL)
    try:
        user_dn = f"uid={username},ou=people,{settings.LDAP_BASE_DN}"

        user_conn = Connection(server, user_dn, password, auto_bind=True)

        admin_conn = Connection(
            server,
            settings.LDAP_USER_DN,
            settings.LDAP_PASSWORD,
            auto_bind=True
        )

        admin_conn.search(
            f"ou=people,{settings.LDAP_BASE_DN}",
            f"(uid={username})",
            SUBTREE,
            attributes=["cn", "mail", "uid"]
        )

        if not admin_conn.entries:
            raise HTTPException(status_code=401, detail="User not found")

        entry = admin_conn.entries[0]
        user_data = {
            "uid": entry.uid.value,
            "cn": entry.cn.value,
            "email": entry.mail.value if "mail" in entry else None
        }

        return user_data

    except Exception as e:
        logger.error(f"LDAP authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    finally:
        if 'admin_conn' in locals():
            admin_conn.unbind()
        if 'user_conn' in locals():
            user_conn.unbind()