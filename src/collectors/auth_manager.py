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
            
            # Check if already authenticated
            if auth_params.get('already_authenticated'):
                logger.info("User is already authenticated")
                success = True
            else:
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
            Dictionary with auth parameters (state, nonce, etc.) and login_url
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
            
            # Store the login URL for later use        
            auth_params['login_url'] = str(response.url)
                    
            logger.debug(f"Extracted auth parameters: {list(auth_params.keys())}")
            return auth_params
        elif response.status_code == 200:
            # We're already authenticated - no redirect needed
            logger.info("Already authenticated - no redirect to CivicPlus detected")
            return {'already_authenticated': True}
        else:
            raise Exception(f"Unexpected authentication response: {response.status_code} at {response.url}")
            
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
        
        # Get the login page using the URL from auth_params
        login_url = auth_params.get('login_url')
        if not login_url:
            raise Exception("Login URL not found in auth parameters")
            
        login_response = await client.get(login_url)
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
                
        # Add credentials - first let's debug what form fields exist
        logger.debug("Available form fields:")
        for input_field in login_form.find_all('input'):
            field_name = input_field.get('name', 'NO_NAME')
            field_type = input_field.get('type', 'NO_TYPE')
            logger.debug(f"  {field_name} ({field_type})")
            
        # Try common username/password field names
        username_field = None
        password_field = None
        
        # Look for username field
        for input_field in login_form.find_all('input'):
            field_name = input_field.get('name', '').lower()
            field_type = input_field.get('type', '').lower()
            if 'email' in field_name or 'username' in field_name or (field_type == 'email'):
                username_field = input_field.get('name')
                break
        
        # Look for password field  
        for input_field in login_form.find_all('input', type='password'):
            password_field = input_field.get('name')
            break
            
        if not username_field or not password_field:
            raise Exception(f"Could not find username/password fields. Username: {username_field}, Password: {password_field}")
            
        form_data[username_field] = self.credentials['username']
        form_data[password_field] = self.credentials['password']
        
        logger.debug(f"Using fields - Username: {username_field}, Password: {password_field}")
        
        # Submit login form  
        submit_url = urljoin(login_url, form_action) if form_action else login_url
        
        response = await client.post(
            submit_url,
            data=form_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': login_url
            }
        )
        
        logger.debug(f"Login response status: {response.status_code}")
        logger.debug(f"Login response URL: {response.url}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        
        # Check for successful authentication - could be redirect or form post
        if response.status_code in [200, 302]:
            # Check URL for authorization code
            if 'code=' in str(response.url):
                parsed = urlparse(str(response.url))
                code_params = parse_qs(parsed.query)
                if 'code' in code_params:
                    logger.info("Authorization code found in URL")
                    return code_params['code'][0]
            
            # Check for redirect to callback with authorization code
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if 'code=' in location:
                    parsed = urlparse(location)
                    code_params = parse_qs(parsed.query)
                    if 'code' in code_params:
                        logger.info("Authorization code found in redirect location")
                        return code_params['code'][0]
            
            # Check response body for form post with code
            if 'code' in response.text:
                # Look for form post response with authorization code
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find the form that will post to redirect_uri
                oauth_form = soup.find('form')
                if oauth_form:
                    form_action = oauth_form.get('action')
                    form_data = {}
                    
                    # Extract all form fields including code and id_token
                    for input_field in oauth_form.find_all('input'):
                        name = input_field.get('name')
                        value = input_field.get('value', '')
                        if name:
                            form_data[name] = value
                    
                    if 'code' in form_data:
                        logger.info("Found authorization code, completing OAuth flow")
                        
                        # Submit the form to complete the OAuth flow
                        if form_action:
                            oauth_response = await client.post(form_action, data=form_data)
                            logger.debug(f"OAuth completion response: {oauth_response.status_code}")
                            logger.debug(f"OAuth completion URL: {oauth_response.url}")
                        
                        return form_data['code']
                    
        # If we get here, login likely failed
        self._check_for_login_errors(response.text)
        logger.debug(f"Response text sample: {response.text[:500]}...")
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
            # Wait a moment for OAuth flow to complete
            import asyncio
            await asyncio.sleep(1)
            
            # Try to access a protected page
            response = await client.get(self.base_url + '/Agendas')
            
            logger.debug(f"Verification response status: {response.status_code}")
            logger.debug(f"Verification response URL: {response.url}")
            
            # Check for signs of successful authentication
            if response.status_code == 200:
                # Check that we're not being redirected to login
                if 'cpauthentication.civicplus.com' not in str(response.url):
                    logger.info("Authentication verification successful - no redirect to auth")
                    return True
                else:
                    logger.debug("Still being redirected to authentication")
                    return False
                    
            # Check for redirects
            elif response.status_code in [302, 301]:
                location = response.headers.get('Location', '')
                logger.debug(f"Redirect location: {location}")
                if 'cpauthentication.civicplus.com' not in location:
                    logger.info("Authentication verification successful - redirect to internal page")  
                    return True
                else:
                    logger.debug("Being redirected back to authentication")
                    return False
                    
            return False
            
        except Exception as e:
            logger.warning(f"Authentication verification failed: {e}")
            return False