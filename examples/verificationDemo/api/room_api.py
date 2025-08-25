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

class VideoSDKRoomClientError(Exception):
    pass

class VideoSDKRoomClient:
    DEFAULT_BASE_URL = "https://api.videosdk.live/v2"
    DEFAULT_TIMEOUT = 30
    
    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url or os.getenv("VIDEOSDK_BASE_URL", self.DEFAULT_BASE_URL)
        self.token = token or os.getenv("VIDEOSDK_AUTH_TOKEN")
        self.timeout = timeout
        
        if not self.token:
            raise VideoSDKSIPClientError("Authorization token is required. Provide it via parameter or VIDEOSDK_AUTH_TOKEN environment variable.")
        
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "User-Agent": "VideoSDK-SIP-Client/1.0"
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
            
            return APIResponse(
                success=True,
                data=data,
                status_code=response.status_code
            )
            
        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {self.timeout} seconds"
            self.logger.error(error_msg)
            return APIResponse(
                success=False,
                error=error_msg,
                status_code=408
            )
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error: {e}"
            self.logger.error(f"{error_msg} - Response: {response.text}")
            return APIResponse(
                success=False,
                error=error_msg,
                status_code=response.status_code,
                details=response.text
            )
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            self.logger.error(error_msg)
            return APIResponse(
                success=False,
                error=error_msg
            )
    
    def _build_payload(self, **kwargs) -> Dict[str, Any]:
        payload = {}
        bool_fields = {"record_audio", "wait_until_answered", "hide_phone_number", 
                      "record", "noise_cancellation", "include_headers"}
        
        for key, value in kwargs.items():
            if value is not None:
                if key in bool_fields and isinstance(value, bool):
                    payload[self._snake_to_camel(key)] = str(value).lower()
                else:
                    payload[self._snake_to_camel(key)] = value
        
        return payload
    
    def _snake_to_camel(self, snake_str: str) -> str:
        components = snake_str.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])
    
    def create_room(self, custom_room_id: Optional[str] = None, webhook: Optional[Dict] = None, 
                   auto_close_config: Optional[Dict] = None, auto_start_config: Optional[Dict] = None) -> APIResponse:
        payload = {}
        if custom_room_id is not None:
            payload["customRoomId"] = custom_room_id
        if webhook is not None:
            payload["webhook"] = webhook
        if auto_close_config is not None:
            payload["autoCloseConfig"] = auto_close_config
        if auto_start_config is not None:
            payload["autoStartConfig"] = auto_start_config
        
        return self._make_request("POST", "rooms", json_data=payload)
    
    def validate_room(self, room_id: str) -> APIResponse:
        if not room_id:
            return APIResponse(success=False, error="room_id is required")
        
        return self._make_request("GET", f"rooms/validate/{room_id}")
    
    def fetch_rooms(self, page: Optional[int] = None, per_page: Optional[int] = None) -> APIResponse:
        params = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        
        return self._make_request("GET", "rooms", params=params)
    
    def get_room_details(self, room_id: str) -> APIResponse:
        if not room_id:
            return APIResponse(success=False, error="room_id is required")
        
        return self._make_request("GET", f"rooms/{room_id}")
    
    def deactivate_room(self, room_id: str) -> APIResponse:
        if not room_id:
            return APIResponse(success=False, error="room_id is required")
        
        payload = {"roomId": room_id}
        return self._make_request("POST", "rooms/deactivate", json_data=payload)
    
    def close(self):
        self.session.close()
