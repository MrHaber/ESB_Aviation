try:
    from pydantic_settings import BaseSettings
except Exception:
    class BaseSettings:
        pass
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
class Settings(BaseSettings):

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://esb_admin:25565@localhost:5432/esb_db").strip()

    JWT_SECRET: str = os.getenv("JWT_SECRET", "RsknBU82E+RifInwJTw4UVh72ooOizgqxX17Ue9jZmQ=").strip()

    PLUGINS_DIR: str = os.getenv("PLUGINS_DIR", "app/plugins").strip()

    LOG_DIR: str = os.getenv("app/logs", "app/logs").strip()

    AVIATION_DB_PATH: str = os.getenv(
        "AVIATION_DB_PATH",
        "resources/synthetic_aviation_messages.db",
    ).strip()

    JWT_EXPIRY_DAYS: int = int(os.getenv("JWT_EXPIRY_DAYS", 3650).strip())

    # раздел для LDAP

    LDAP_ENABLED: bool = bool(os.getenv("LDAP_ENABLED", "False").strip())
    LDAP_SERVER: str = os.getenv("LDAP_SERVER", "ldap://91.132.57.66:389").strip()
    LDAP_BASE_DN: str = os.getenv("LDAP_BASE_DN", "dc=fvds,dc=ru").strip()
    LDAP_USER_DN: str = os.getenv("LDAP_USER_DN", "cn=admin,dc=fvds,dc=ru").strip()
    LDAP_PASSWORD: str = os.getenv("LDAP_PASSWORD", "25565").strip()
    LDAP_AUTH_ROUTE: str = os.getenv("LDAP_AUTH_ROUTE", "/auth/ldap").strip()
    LDAP_CALLBACK_ROUTE: str = os.getenv("LDAP_CALLBACK_ROUTE", "/auth/ldap/callback").strip()

    # раздел для кафки, я не знаю что с ним делать
    # параметры для access management и SASL были взяты отсюда:
    # https://docs.arenadata.io/en/ADStreaming/current/how-to/kafka/access_management/authentication/sasl_plain.html
    KAFKA_ENABLED: bool = bool(os.getenv("KAFKA_ENABLED", "True").strip().lower() == "true")
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").strip()
    KAFKA_SECURITY_PROTOCOL: str = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").strip()
    KAFKA_SASL_MECHANISM: Optional[str] = os.getenv("KAFKA_SASL_MECHANISM", "").strip() or None
    KAFKA_SASL_USERNAME: Optional[str] = os.getenv("KAFKA_SASL_USERNAME", "").strip() or None
    KAFKA_SASL_PASSWORD: Optional[str] = os.getenv("KAFKA_SASL_PASSWORD", "").strip() or None
    KAFKA_TOPIC: str = os.getenv("KAFKA_TOPIC", "app_logs").strip()
    KAFKA_CONSUMER_GROUP: str = os.getenv("KAFKA_CONSUMER_GROUP", "esb_consumer_group").strip()
    KAFKA_AUTO_OFFSET_RESET: str = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest").strip()
    KAFKA_MAX_POLL_RECORDS: int = int(os.getenv("KAFKA_MAX_POLL_RECORDS", "500").strip())
settings = Settings()
