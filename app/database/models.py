from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RequestLog(Base):
    __tablename__ = "request_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime)
    user_id = Column(String)
    plugin_name = Column(String)
    request_payload = Column(JSON)
    response_payload = Column(JSON)
    status = Column(String)
    duration_ms = Column(Integer)