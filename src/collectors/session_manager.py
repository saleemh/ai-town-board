"""Session Manager for Board Portal

Handles session persistence and cookie management.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import httpx


logger = logging.getLogger(__name__)


class SessionManager:
    """Manages persistent sessions for board portal access."""
    
    def __init__(self, config: Dict):
        """Initialize session manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.session_file = Path(config['storage']['data_directory']) / '.session' / 'board_portal_session.json'
        self.session_timeout = timedelta(hours=4)  # Assume sessions expire after 4 hours
        
        # Ensure session directory exists
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        
    async def has_valid_session(self, client: httpx.AsyncClient) -> bool:
        """Check if we have a valid existing session.
        
        Args:
            client: HTTP client to check
            
        Returns:
            True if valid session exists
        """
        if not self.session_file.exists():
            logger.debug("No session file found")
            return False
            
        try:
            # Load session data
            session_data = self._load_session_data()
            
            if not session_data:
                logger.debug("Empty session data")
                return False
                
            # Check if session has expired
            if self._is_session_expired(session_data):
                logger.debug("Session has expired")
                return False
                
            # Restore cookies to client
            if 'cookies' in session_data:
                client.cookies.clear()
                for name, value in session_data['cookies'].items():
                    client.cookies.set(name, value)
                    
            # Test if session is actually valid by making a request
            return await self._test_session_validity(client)
            
        except Exception as e:
            logger.warning(f"Error checking session validity: {e}")
            return False
            
    async def save_session(self, client: httpx.AsyncClient):
        """Save current session state.
        
        Args:
            client: HTTP client with active session
        """
        try:
            session_data = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'cookies': dict(client.cookies),
                'user_agent': client.headers.get('User-Agent', ''),
            }
            
            # Save to file
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
                
            logger.debug("Session saved successfully")
            
        except Exception as e:
            logger.warning(f"Failed to save session: {e}")
            
    async def restore_session(self, client: httpx.AsyncClient) -> bool:
        """Restore session from saved state.
        
        Args:
            client: HTTP client to restore session to
            
        Returns:
            True if session restored successfully
        """
        try:
            if not self.session_file.exists():
                return False
                
            session_data = self._load_session_data()
            if not session_data:
                return False
                
            # Restore cookies
            if 'cookies' in session_data:
                client.cookies.clear()
                for name, value in session_data['cookies'].items():
                    client.cookies.set(name, value)
                    
            # Restore user agent if needed
            if 'user_agent' in session_data and session_data['user_agent']:
                client.headers['User-Agent'] = session_data['user_agent']
                
            logger.debug("Session restored successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to restore session: {e}")
            return False
            
    def clear_session(self):
        """Clear saved session data."""
        try:
            if self.session_file.exists():
                self.session_file.unlink()
                logger.debug("Session cleared")
        except Exception as e:
            logger.warning(f"Failed to clear session: {e}")
            
    def _load_session_data(self) -> Optional[Dict]:
        """Load session data from file.
        
        Returns:
            Session data dictionary or None
        """
        try:
            with open(self.session_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Failed to load session data: {e}")
            return None
            
    def _is_session_expired(self, session_data: Dict) -> bool:
        """Check if session has expired.
        
        Args:
            session_data: Session data dictionary
            
        Returns:
            True if session is expired
        """
        if 'timestamp' not in session_data:
            return True
            
        try:
            session_time = datetime.fromisoformat(session_data['timestamp'].replace('Z', '+00:00'))
            return datetime.utcnow().replace(tzinfo=session_time.tzinfo) - session_time > self.session_timeout
        except Exception as e:
            logger.debug(f"Error parsing session timestamp: {e}")
            return True
            
    async def _test_session_validity(self, client: httpx.AsyncClient) -> bool:
        """Test if current session is actually valid.
        
        Args:
            client: HTTP client to test
            
        Returns:
            True if session is valid
        """
        try:
            # Make a simple request to a protected page
            base_url = self.config['board_portal']['base_url']
            test_url = f"{base_url}/Agendas"
            
            response = await client.get(test_url, follow_redirects=False)
            
            # Check if we're redirected to authentication
            if response.status_code in [302, 301]:
                redirect_location = response.headers.get('Location', '')
                if 'cpauthentication.civicplus.com' in redirect_location:
                    logger.debug("Session invalid - redirected to auth")
                    return False
                    
            # Check if we get a successful response
            if response.status_code == 200:
                # Additional check: look for auth-related content
                if 'login' in response.text.lower() or 'sign in' in response.text.lower():
                    logger.debug("Session invalid - login form present")
                    return False
                    
                logger.debug("Session appears valid")
                return True
                
            logger.debug(f"Unexpected status code: {response.status_code}")
            return False
            
        except Exception as e:
            logger.debug(f"Session validity test failed: {e}")
            return False