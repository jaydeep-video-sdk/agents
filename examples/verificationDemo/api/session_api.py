import os
import logging
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class APIResponse:
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    details: Optional[str] = None


class VideoSDKSessionClientError(Exception):
    pass

class VideoSDKSessionClient:
    DEFAULT_BASE_URL = "https://api.videosdk.live/v2"
    DEFAULT_TIMEOUT = 30

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url or os.getenv("VIDEOSDK_BASE_URL", self.DEFAULT_BASE_URL)
        self.token = token or os.getenv("VIDEOSDK_AUTH_TOKEN")
        self.timeout = timeout

        if not self.token:
            raise VideoSDKSessionClientError(
                "Authorization token is required. Provide it via parameter or VIDEOSDK_AUTH_TOKEN environment variable."
            )

        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "User-Agent": "VideoSDK-Session-Client/1.0"
        }

        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     json_data: Optional[Dict] = None) -> APIResponse:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            self.logger.debug(f"Making {method} request to {url}")

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout
            )

            response.raise_for_status()

            try:
                data = response.json()
            except ValueError:
                data = {"message": response.text} if response.text else {}

            return APIResponse(success=True, data=data, status_code=response.status_code)

        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {self.timeout} seconds"
            return APIResponse(success=False, error=error_msg, status_code=408)

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error: {e}"
            return APIResponse(
                success=False,
                error=error_msg,
                status_code=response.status_code,
                details=response.text
            )

        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            return APIResponse(success=False, error=error_msg)

    def fetch_sessions(self, room_id: Optional[str] = None, custom_room_id: Optional[str] = None,
                       page: Optional[int] = None, per_page: Optional[int] = None) -> APIResponse:
        params = {}
        if room_id:
            params["roomId"] = room_id
        if custom_room_id:
            params["customRoomId"] = custom_room_id
        if page:
            params["page"] = page
        if per_page:
            params["perPage"] = per_page

        return self._make_request("GET", "sessions", params=params)

    def fetch_session(self, session_id: str) -> APIResponse:
        if not session_id:
            return APIResponse(success=False, error="session_id is required")
        return self._make_request("GET", f"sessions/{session_id}")

    def fetch_session_participants(self, session_id: str, page: Optional[int] = None, per_page: Optional[int] = None) -> APIResponse:
        if not session_id:
            return APIResponse(success=False, error="session_id is required")
        params = {}
        if page:
            params["page"] = page
        if per_page:
            params["perPage"] = per_page
        return self._make_request("GET", f"sessions/{session_id}/participants", params=params)

    def fetch_active_participants(self, session_id: str, page: Optional[int] = None, per_page: Optional[int] = None) -> APIResponse:
        if not session_id:
            return APIResponse(success=False, error="session_id is required")
        params = {}
        if page:
            params["page"] = page
        if per_page:
            params["perPage"] = per_page
        return self._make_request("GET", f"sessions/{session_id}/participants/active", params=params)

    def end_session(self, room_id: str, session_id: Optional[str] = None) -> APIResponse:
        if not room_id:
            return APIResponse(success=False, error="room_id is required")
        payload = {"roomId": room_id}
        if session_id:
            payload["sessionId"] = session_id
        return self._make_request("POST", "sessions/end", json_data=payload)

    def remove_participant(self, participant_id: str, room_id: str, session_id: Optional[str] = None) -> APIResponse:
        if not participant_id:
            return APIResponse(success=False, error="participant_id is required")
        if not room_id:
            return APIResponse(success=False, error="room_id is required")
        payload = {"participantId": participant_id, "roomId": room_id}
        if session_id:
            payload["sessionId"] = session_id
        return self._make_request("POST", "sessions/participants/remove", json_data=payload)

