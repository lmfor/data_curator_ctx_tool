import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from contextlib import contextmanager
from typing import List, Optional, Dict
from datetime import datetime
import logging

from models import Base, ValidatedURL, ScrapingRun, ValidationLog

# Load environment variables
load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
    
    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(bind=self.engine)
        self.logger.info("Database tables created successfully")
    
    def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        Base.metadata.drop_all(bind=self.engine)
        self.logger.info("All database tables dropped")
    
    @contextmanager
    def get_db_session(self):
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone()[0] == 1
        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            return False
    
    # ValidatedURL operations
    def add_validated_url(self, url: str, title: str = None, content_hash: str = None, 
                         last_modified: datetime = None, ctx_relevance_score: float = None,
                         ctx_currency_score: float = None, page_metadata: Dict = None) -> Optional[Dict]:
        """Add a new validated URL to the database"""
        try:
            with self.get_db_session() as session:
                validated_url = ValidatedURL(
                    url=url,
                    title=title,
                    content_hash=content_hash,
                    last_modified=last_modified,
                    ctx_relevance_score=ctx_relevance_score,
                    ctx_currency_score=ctx_currency_score,
                    page_metadata=page_metadata
                )
                session.add(validated_url)
                session.flush()  # Get the ID
                session.refresh(validated_url)  # Refresh to get all attributes
                
                # Return a dictionary with the data instead of the SQLAlchemy object
                return {
                    'id': validated_url.id,
                    'url': validated_url.url,
                    'title': validated_url.title,
                    'content_hash': validated_url.content_hash,
                    'last_modified': validated_url.last_modified,
                    'validation_timestamp': validated_url.validation_timestamp,
                    'ctx_relevance_score': validated_url.ctx_relevance_score,
                    'ctx_currency_score': validated_url.ctx_currency_score,
                    'is_current': validated_url.is_current,
                    'page_metadata': validated_url.page_metadata
                }
        except IntegrityError:
            self.logger.warning(f"URL already exists: {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error adding validated URL: {e}")
            return None
    
    def get_validated_url(self, url: str) -> Optional[ValidatedURL]:
        """Get a validated URL by URL"""
        try:
            with self.get_db_session() as session:
                return session.query(ValidatedURL).filter(ValidatedURL.url == url).first()
        except Exception as e:
            self.logger.error(f"Error getting validated URL: {e}")
            return None
    
    def get_all_validated_urls(self) -> List[ValidatedURL]:
        """Get all validated URLs"""
        try:
            with self.get_db_session() as session:
                return session.query(ValidatedURL).all()
        except Exception as e:
            self.logger.error(f"Error getting all validated URLs: {e}")
            return []
    
    def update_url_currency_status(self, url: str, is_current: bool) -> bool:
        """Update the currency status of a URL"""
        try:
            with self.get_db_session() as session:
                validated_url = session.query(ValidatedURL).filter(ValidatedURL.url == url).first()
                if validated_url:
                    validated_url.is_current = is_current
                    return True
                return False
        except Exception as e:
            self.logger.error(f"Error updating URL currency status: {e}")
            return False
    
    # ScrapingRun operations
    def start_scraping_run(self) -> Optional[ScrapingRun]:
        """Start a new scraping run"""
        try:
            with self.get_db_session() as session:
                run = ScrapingRun(status='running')
                session.add(run)
                session.flush()
                return run
        except Exception as e:
            self.logger.error(f"Error starting scraping run: {e}")
            return None
    
    def finish_scraping_run(self, run_id: int, status: str = 'completed', 
                           pages_processed: int = 0, pages_validated: int = 0,
                           error_message: str = None) -> bool:
        """Finish a scraping run with results"""
        try:
            with self.get_db_session() as session:
                run = session.query(ScrapingRun).filter(ScrapingRun.id == run_id).first()
                if run:
                    run.end_time = datetime.now()
                    run.status = status
                    run.pages_processed = pages_processed
                    run.pages_validated = pages_validated
                    run.error_message = error_message
                    return True
                return False
        except Exception as e:
            self.logger.error(f"Error finishing scraping run: {e}")
            return False
    
    def get_latest_scraping_run(self) -> Optional[ScrapingRun]:
        """Get the most recent scraping run"""
        try:
            with self.get_db_session() as session:
                return session.query(ScrapingRun).order_by(ScrapingRun.start_time.desc()).first()
        except Exception as e:
            self.logger.error(f"Error getting latest scraping run: {e}")
            return None
    
    # ValidationLog operations
    def log_validation(self, url: str, validation_type: str, result: str,
                      ctx_response: str = None, confidence_score: float = None,
                      reasoning: str = None) -> Optional[ValidationLog]:
        """Log a validation attempt"""
        try:
            with self.get_db_session() as session:
                log = ValidationLog(
                    url=url,
                    validation_type=validation_type,
                    result=result,
                    ctx_response=ctx_response,
                    confidence_score=confidence_score,
                    reasoning=reasoning
                )
                session.add(log)
                session.flush()
                return log
        except Exception as e:
            self.logger.error(f"Error logging validation: {e}")
            return None
    
    def get_validation_history(self, url: str) -> List[ValidationLog]:
        """Get validation history for a URL"""
        try:
            with self.get_db_session() as session:
                return session.query(ValidationLog).filter(ValidationLog.url == url).order_by(ValidationLog.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting validation history: {e}")
            return []

# Global database manager instance
db_manager = DatabaseManager()