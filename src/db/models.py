from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class ValidatedURL(Base):
    __tablename__ = 'validated_urls'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(500), nullable=False, unique=True)
    title = Column(String(200))
    content_hash = Column(String(64))  # For detecting content changes
    last_modified = Column(DateTime)
    validation_timestamp = Column(DateTime, default=func.now())
    ctx_relevance_score = Column(Float)  # CTX agent relevance confidence
    ctx_currency_score = Column(Float)   # CTX agent currency confidence
    is_current = Column(Boolean, default=True)
    page_metadata = Column(JSON)  # Store additional info like page size, author, etc.
    
    def __repr__(self):
        return f"<ValidatedURL(url='{self.url}', title='{self.title}')>"

class ScrapingRun(Base):
    __tablename__ = 'scraping_runs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime)
    status = Column(String(20), default='running')  # running, completed, failed
    pages_processed = Column(Integer, default=0)
    pages_validated = Column(Integer, default=0)
    error_message = Column(Text)
    
    def __repr__(self):
        return f"<ScrapingRun(id={self.id}, status='{self.status}')>"

class ValidationLog(Base):
    __tablename__ = 'validation_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(500), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    validation_type = Column(String(20))  # 'relevance' or 'currency'
    result = Column(String(20))  # 'pass', 'fail'
    ctx_response = Column(Text)  # Full CTX agent response
    confidence_score = Column(Float)
    reasoning = Column(Text)  # Why it passed/failed
    
    def __repr__(self):
        return f"<ValidationLog(url='{self.url}', type='{self.validation_type}', result='{self.result}')>"