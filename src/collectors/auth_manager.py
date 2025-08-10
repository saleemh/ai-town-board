"""Authentication Manager for Board Portal

Handles OAuth2 authentication flow with CivicPlus platform.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class AuthManager:
    """Manages authentication with the CivicPlus board portal system."""
    
    def __init__(self, config: Dict):
        """Initialize authentication manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.base_url = config['board_portal']['base_url']
        self.login_url = config['board_portal']['login_url'] 
        self.credentials_file = config['board_portal']['credentials_file']
        self.credentials: Optional[Dict] = None
        
    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Perform full authentication flow.
        
        Args:
            client: HTTP client to use for requests
            
        Returns:
            True if authentication successful
        """
        logger.info("Starting authentication flow")
        
        try:
            # Load credentials
            self.credentials = self._load_credentials()
            
            # Step 1: Get initial login page to capture state/nonce
            auth_params = await self._get_auth_parameters(client)
            
            # Step 2: Perform OAuth2 authorization
            auth_code = await self._perform_oauth_login(client, auth_params)
            
            # Step 3: Exchange code for tokens (handled automatically by redirect)
            success = await self._verify_authentication(client)
            
            if success:
                logger.info("Authentication successful")
                return True
            else:
                raise Exception("Authentication verification failed")
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
            
    def _load_credentials(self) -> Dict:
        """Load encrypted credentials from file.
        
        Returns:
            Credentials dictionary
            
        Raises:
            FileNotFoundError: If credentials file doesn't exist
        """
        creds_path = Path(self.credentials_file)
        
        if not creds_path.exists():
            # Create template credentials file
            template = {
                "username": "your-email@example.com",
                "password": "your-password",
                "note": "Replace with actual credentials. This file should be encrypted in production."
            }
            
            creds_path.parent.mkdir(parents=True, exist_ok=True)
            with open(creds_path, 'w') as f:
                json.dump(template, f, indent=2)
                
            raise FileNotFoundError(
                f"Credentials file created at {creds_path}. "
                "Please update with actual credentials."
            )
            
        with open(creds_path, 'r') as f:
            credentials = json.load(f)
            
        # Validate required fields
        required_fields = ['username', 'password']
        missing_fields = [field for field in required_fields if field not in credentials]
        
        if missing_fields:
            raise ValueError(f"Missing required credential fields: {missing_fields}")
            
        return credentials
        
    async def _get_auth_parameters(self, client: httpx.AsyncClient) -> Dict:
        """Get authentication parameters from initial request.
        
        Args:
            client: HTTP client to use
            
        Returns:
            Dictionary with auth parameters (state, nonce, etc.)
        """
        logger.debug("Getting authentication parameters")
        
        # Navigate to board portal - this should trigger redirect to auth
        response = await client.get(self.base_url)
        
        # Check if we're redirected to CivicPlus auth
        if 'cpauthentication.civicplus.com' in str(response.url):
            # Parse auth parameters from URL
            parsed_url = urlparse(str(response.url))
            query_params = parse_qs(parsed_url.query)
            
            auth_params = {}
            for key in ['client_id', 'redirect_uri', 'response_type', 'scope', 
                       'response_mode', 'nonce', 'state']:
                if key in query_params:
                    auth_params[key] = query_params[key][0]
                    
            logger.debug(f"Extracted auth parameters: {list(auth_params.keys())}")
            return auth_params
        else:
            raise Exception("Expected redirect to CivicPlus authentication not found")
            
    async def _perform_oauth_login(
        self, 
        client: httpx.AsyncClient, 
        auth_params: Dict
    ) -> str:
        """Perform OAuth2 login with credentials.
        
        Args:
            client: HTTP client to use
            auth_params: Authentication parameters from initial request
            
        Returns:
            Authorization code
        """
        logger.debug("Performing OAuth2 login")
        
        # Get the login form
        login_response = await client.get(client.url)
        soup = BeautifulSoup(login_response.text, 'html.parser')
        
        # Find the login form
        login_form = soup.find('form', {'method': 'post'})
        if not login_form:
            raise Exception("Login form not found on authentication page")
            
        # Extract form action and hidden fields
        form_action = login_form.get('action')
        form_data = {}
        
        # Get all hidden input fields
        for input_field in login_form.find_all('input', type='hidden'):
            name = input_field.get('name')
            value = input_field.get('value', '')
            if name:
                form_data[name] = value
                
        # Add credentials
        form_data['Username'] = self.credentials['username']  # May need adjustment
        form_data['Password'] = self.credentials['password']  # May need adjustment
        
        # Submit login form
        login_url = urljoin(str(client.url), form_action) if form_action else str(client.url)
        
        response = await client.post(
            login_url,
            data=form_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': str(client.url)
            }
        )
        
        # Check for successful authentication
        if response.status_code == 200 and 'error' not in response.text.lower():
            # Extract authorization code if present
            if 'code=' in str(response.url):
                parsed = urlparse(str(response.url))
                code_params = parse_qs(parsed.query)
                if 'code' in code_params:
                    return code_params['code'][0]
                    
        # If we get here, login likely failed
        self._check_for_login_errors(response.text)
        raise Exception("OAuth2 login failed - no authorization code received")
        
    def _check_for_login_errors(self, response_text: str):
        """Check response for common login error messages.
        
        Args:
            response_text: HTML response text to analyze
        """
        error_patterns = [
            r'invalid.*username.*password',
            r'login.*failed',
            r'authentication.*error',
            r'invalid.*credentials'
        ]
        
        text_lower = response_text.lower()
        for pattern in error_patterns:
            if re.search(pattern, text_lower):
                raise Exception(f"Login failed - check credentials: {pattern}")
                
    async def _verify_authentication(self, client: httpx.AsyncClient) -> bool:
        """Verify that authentication was successful.
        
        Args:
            client: HTTP client to check
            
        Returns:
            True if authenticated
        """
        logger.debug("Verifying authentication status")
        
        try:
            # Try to access a protected page
            response = await client.get(self.base_url + '/Agendas')
            
            # Check for signs of successful authentication
            if response.status_code == 200:
                # Look for user-specific content or lack of login prompts
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check for user name or logout link (adjust selectors as needed)
                user_indicators = [
                    soup.find(string=re.compile(self.credentials['username'], re.I)),
                    soup.find('a', href=re.compile('logout', re.I)),
                    soup.find('span', class_=re.compile('user', re.I))
                ]
                
                if any(user_indicators):
                    return True
                    
                # Check that we're not being redirected to login
                if 'cpauthentication.civicplus.com' not in str(response.url):
                    return True
                    
            return False
            
        except Exception as e:
            logger.warning(f"Authentication verification failed: {e}")
            return False