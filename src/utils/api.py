import logging
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class APIRequester:
    """API Requester class for making HTTP requests."""

    DEFAULT_HEADERS = {"accept": "application/json", "Content-Type": "application/json"}

    def __init__(self, endpoint: str):
        """
        Initialize API Requester.

        Args:
            endpoint: Base endpoint URL (e.g., 'http://localhost:8000')
        """
        self.endpoint = endpoint.rstrip("/")

    def _build_url(self, api_path: str) -> str:
        """
        Build full URL from endpoint and API path.

        Args:
            api_path: API path to append to endpoint

        Returns:
            Full URL string
        """
        return f"{self.endpoint}{api_path}"

    def _get_headers(
        self,
        headers: Optional[dict[str, str]] = None,
        include_content_type: bool = True,
    ) -> dict[str, str]:
        """
        Get request headers with defaults.

        Args:
            headers: Custom headers to merge with defaults
            include_content_type: Whether to include Content-Type header

        Returns:
            Merged headers dictionary
        """
        default_headers = {"accept": self.DEFAULT_HEADERS["accept"]}
        if include_content_type:
            default_headers["Content-Type"] = self.DEFAULT_HEADERS["Content-Type"]

        if headers:
            default_headers.update(headers)

        return default_headers

    def get(
        self,
        api_path: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> requests.Response:
        """
        Make a GET request.

        Args:
            api_path: API path to append to endpoint (e.g., '/rec/user/similar')
            params: Query parameters
            headers: Request headers

        Returns:
            Response object
        """
        url = self._build_url(api_path)
        request_headers = self._get_headers(headers, include_content_type=False)

        try:
            response = requests.get(url, params=params, headers=request_headers)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"GET request failed: {e}")
            raise

    def post(
        self,
        api_path: str,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> requests.Response:
        """
        Make a POST request.

        Args:
            api_path: API path to append to endpoint (e.g., '/rec/user/similar')
            data: JSON data to send in request body
            headers: Request headers

        Returns:
            Response object
        """
        url = self._build_url(api_path)
        request_headers = self._get_headers(headers)

        try:
            response = requests.post(url, json=data, headers=request_headers)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"POST request failed: {e}")
            raise

    def put(
        self,
        api_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> requests.Response:
        """
        Make a PUT request.

        Args:
            api_path: API path to append to endpoint (e.g., '/rec/user/similar')
            data: JSON data to send in request body
            params: Query parameters
            headers: Request headers

        Returns:
            Response object
        """
        url = self._build_url(api_path)
        request_headers = self._get_headers(headers)

        try:
            response = requests.put(
                url, json=data, params=params, headers=request_headers
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"PUT request failed: {e}")
            raise
