import requests
import os
from typing import Dict, List, Optional, Union, Any
import logging
from dataclasses import dataclass
from enum import Enum


class Transport(Enum):
    UDP = "udp"
    TCP = "tcp"
    TLS = "tls"


class MediaEncryption(Enum):
    SRTP = "srtp"
    DTLS = "dtls"


class CallType(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass
class APIResponse:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    details: Optional[str] = None


class VideoSDKSIPClientError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class VideoSDKSIPClient:
    DEFAULT_BASE_URL = "https://api.videosdk.live/v2"
    DEFAULT_TIMEOUT = 30
    
    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url or os.getenv("VIDEOSDK_BASE_URL", self.DEFAULT_BASE_URL)
        self.token = token or os.getenv("VIDEOSDK_TOKEN")
        self.timeout = timeout
        
        if not self.token:
            raise VideoSDKSIPClientError("Authorization token is required. Provide it via parameter or VIDEOSDK_TOKEN environment variable.")
        
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "User-Agent": "VideoSDK-SIP-Client/1.0"
        }
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     json_data: Optional[Dict] = None) -> APIResponse:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            self.logger.debug(f"Making {method} request to {url}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
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
    
    def trigger_call(self, gateway_id: str, sip_call_to: str, destination_room_id: str,
                    sip_call_from: Optional[str] = None, participant_name: Optional[str] = None,
                    record_audio: Optional[bool] = None, wait_until_answered: Optional[bool] = None,
                    ringing_timeout: Optional[int] = None, dtmf: Optional[str] = None,
                    max_call_duration: Optional[int] = None, media_encryption: Optional[str] = None,
                    hide_phone_number: Optional[bool] = None, headers: Optional[Dict] = None,
                    include_headers: Optional[List[str]] = None, metadata: Optional[Dict] = None) -> APIResponse:

        if not all([gateway_id, sip_call_to, destination_room_id]):
            return APIResponse(
                success=False,
                error="gateway_id, sip_call_to, and destination_room_id are required"
            )
        
        payload = {
            "gatewayId": gateway_id,
            "sipCallTo": sip_call_to,
            "destinationRoomId": destination_room_id
        }
        
        # Add optional fields
        optional_fields = {
            "sipCallFrom": sip_call_from,
            "dtmf": dtmf,
            "mediaEncryption": media_encryption,
            "headers": headers,
            "includeHeaders": include_headers,
            "metadata": metadata
        }
        
        for key, value in optional_fields.items():
            if value is not None:
                payload[key] = value
        
        # Handle participant name
        if participant_name:
            payload["participant"] = {"name": participant_name}
        
        # Handle boolean fields
        bool_fields = {
            "recordAudio": record_audio,
            "waitUntilAnswered": wait_until_answered,
            "hidePhoneNumber": hide_phone_number
        }
        
        for key, value in bool_fields.items():
            if value is not None:
                payload[key] = str(value).lower()
        
        # Handle numeric fields
        if ringing_timeout is not None:
            payload["ringingTimeout"] = str(ringing_timeout)
        if max_call_duration is not None:
            payload["maxCallDuration"] = str(max_call_duration)
        
        return self._make_request("POST", "sip/call", json_data=payload)
    
    def list_calls(self, room_id: Optional[str] = None, session_id: Optional[str] = None,
                  call_id: Optional[str] = None, gateway_id: Optional[str] = None,
                  rule_id: Optional[str] = None, call_type: Optional[Union[str, CallType]] = None,
                  search: Optional[str] = None, start_date: Optional[int] = None,
                  end_date: Optional[int] = None, page: Optional[int] = None,
                  per_page: Optional[int] = None) -> APIResponse:

        params = {}
        
        if call_type:
            if isinstance(call_type, CallType):
                call_type = call_type.value
        
        param_mapping = {
            "roomId": room_id,
            "sessionId": session_id,
            "id": call_id,
            "gatewayId": gateway_id,
            "ruleId": rule_id,
            "type": call_type,
            "search": search,
            "startDate": start_date,
            "endDate": end_date,
            "page": page,
            "perPage": per_page
        }
        
        for key, value in param_mapping.items():
            if value is not None:
                params[key] = value
        
        return self._make_request("GET", "sip/call", params=params)
  
    def create_outbound_gateway(self, name: str, numbers: List[str], address: str,
                               geo_region: str, transport: Union[str, Transport],
                               media_encryption: Optional[Union[str, MediaEncryption]] = None,
                               record: Optional[bool] = None, noise_cancellation: Optional[bool] = None,
                               auth: Optional[Dict] = None, include_headers: Optional[bool] = None,
                               headers: Optional[Dict] = None, headers_to_attributes: Optional[Dict] = None,
                               metadata: Optional[Dict] = None, tags: Optional[List[str]] = None) -> APIResponse:
       
        if not all([name, numbers, address, geo_region, transport]):
            return APIResponse(
                success=False,
                error="name, numbers, address, geo_region, and transport are required"
            )
        
        # Handle enums
        if isinstance(transport, Transport):
            transport = transport.value
        if isinstance(media_encryption, MediaEncryption):
            media_encryption = media_encryption.value
        
        payload = {
            "name": name,
            "numbers": numbers,
            "address": address,
            "geoRegion": geo_region,
            "transport": transport
        }
        
        # Add optional fields
        optional_fields = {
            "mediaEncryption": media_encryption,
            "auth": auth,
            "headers": headers,
            "headersToAttributes": headers_to_attributes,
            "metadata": metadata,
            "tags": tags
        }
        
        for key, value in optional_fields.items():
            if value is not None:
                payload[key] = value
        
        
        bool_fields = {
            "record": record,
            "noiseCancellation": noise_cancellation,
            "includeHeaders": include_headers
        }
        
        for key, value in bool_fields.items():
            if value is not None:
                payload[key] = str(value).lower()
        
        return self._make_request("POST", "sip/outbound-gateways", json_data=payload)
    
    def list_outbound_gateways(self, gateway_id: Optional[str] = None, search: Optional[str] = None,
                              page: Optional[int] = None, per_page: Optional[int] = None) -> APIResponse:
        params = {}
        param_mapping = {
            "id": gateway_id,
            "search": search,
            "page": page,
            "perPage": per_page
        }
        
        for key, value in param_mapping.items():
            if value is not None:
                params[key] = value
        
        return self._make_request("GET", "sip/outbound-gateways", params=params)
    
    def get_outbound_gateway(self, gateway_id: str) -> APIResponse:
        if not gateway_id:
            return APIResponse(
                success=False,
                error="gateway_id is required"
            )
        
        return self._make_request("GET", f"sip/outbound-gateways/{gateway_id}")
    
    def update_outbound_gateway(self, gateway_id: str, name: Optional[str] = None,
                               numbers: Optional[List[str]] = None, address: Optional[str] = None,
                               geo_region: Optional[str] = None, transport: Optional[Union[str, Transport]] = None,
                               auth: Optional[Dict] = None, media_encryption: Optional[Union[str, MediaEncryption]] = None,
                               record: Optional[bool] = None, noise_cancellation: Optional[bool] = None,
                               allowed_numbers: Optional[List[str]] = None, metadata: Optional[Dict] = None,
                               tags: Optional[List[str]] = None) -> APIResponse:
        
        if not gateway_id:
            return APIResponse(
                success=False,
                error="gateway_id is required"
            )
        
        payload = {}
        
        # Handle enums
        if isinstance(transport, Transport):
            transport = transport.value
        if isinstance(media_encryption, MediaEncryption):
            media_encryption = media_encryption.value
        
        # Add optional fields
        optional_fields = {
            "name": name,
            "numbers": numbers,
            "address": address,
            "geoRegion": geo_region,
            "transport": transport,
            "auth": auth,
            "mediaEncryption": media_encryption,
            "allowedNumbers": allowed_numbers,
            "metadata": metadata,
            "tags": tags
        }
        
        for key, value in optional_fields.items():
            if value is not None:
                payload[key] = value
        
        # Handle boolean fields
        bool_fields = {
            "record": record,
            "noiseCancellation": noise_cancellation
        }
        
        for key, value in bool_fields.items():
            if value is not None:
                payload[key] = value
        
        return self._make_request("PUT", f"sip/outbound-gateways/{gateway_id}", json_data=payload)
    
    def delete_outbound_gateway(self, gateway_id: str) -> APIResponse:
        if not gateway_id:
            return APIResponse(
                success=False,
                error="gateway_id is required"
            )
        
        return self._make_request("DELETE", f"sip/outbound-gateways/{gateway_id}")
    
    def create_routing_rule(self, gateway_id: str, name: str, numbers: List[str], dispatch: Dict,
                           hide_phone_number: Optional[bool] = None, metadata: Optional[Dict] = None,
                           tags: Optional[List[str]] = None) -> APIResponse:
        
        if not all([gateway_id, name, numbers, dispatch]):
            return APIResponse(
                success=False,
                error="gateway_id, name, numbers, and dispatch are required"
            )
        
        payload = {
            "gatewayId": gateway_id,
            "name": name,
            "numbers": numbers,
            "dispatch": dispatch
        }
        
        optional_fields = {
            "metadata": metadata,
            "tags": tags
        }
        
        for key, value in optional_fields.items():
            if value is not None:
                payload[key] = value
        
        if hide_phone_number is not None:
            payload["hidePhoneNumber"] = hide_phone_number
        
        return self._make_request("POST", "sip/routing-rules", json_data=payload)
    
    def list_routing_rules(self, gateway_id: Optional[str] = None, rule_id: Optional[str] = None,
                          search: Optional[str] = None, page: Optional[int] = None,
                          per_page: Optional[int] = None) -> APIResponse:
        params = {}
        param_mapping = {
            "gatewayId": gateway_id,
            "id": rule_id,
            "search": search,
            "page": page,
            "perPage": per_page
        }
        
        for key, value in param_mapping.items():
            if value is not None:
                params[key] = value
        
        return self._make_request("GET", "sip/routing-rules", params=params)
    
    def get_routing_rule(self, rule_id: str) -> APIResponse:
        if not rule_id:
            return APIResponse(
                success=False,
                error="rule_id is required"
            )
        
        return self._make_request("GET", f"sip/routing-rules/{rule_id}")
    
    def update_routing_rule(self, rule_id: str, name: Optional[str] = None,
                           dispatch: Optional[Dict] = None, hide_phone_number: Optional[bool] = None,
                           metadata: Optional[Dict] = None, tags: Optional[List[str]] = None,
                           numbers: Optional[List[str]] = None) -> APIResponse:
       
        if not rule_id:
            return APIResponse(
                success=False,
                error="rule_id is required"
            )
        
        payload = {}
        
        optional_fields = {
            "name": name,
            "dispatch": dispatch,
            "metadata": metadata,
            "tags": tags,
            "numbers": numbers
        }
        
        for key, value in optional_fields.items():
            if value is not None:
                payload[key] = value
        
        if hide_phone_number is not None:
            payload["hidePhoneNumber"] = hide_phone_number
        
        return self._make_request("PUT", f"sip/routing-rules/{rule_id}", json_data=payload)
    
    def delete_routing_rule(self, rule_id: str) -> APIResponse:
        
        if not rule_id:
            return APIResponse(
                success=False,
                error="rule_id is required"
            )
        
        return self._make_request("DELETE", f"sip/routing-rules/{rule_id}")


if __name__ == "__main__":
    client = VideoSDKSIPClient(token="your-token-here")
    
    response = client.list_calls(page=1, per_page=10)
    if response.success:
        print("Calls retrieved successfully:", response.data)
    else:
        print("Error:", response.error)
    
    gateway_response = client.create_outbound_gateway(
        name="My Gateway",
        numbers=["+1234567890"],
        address="sip.example.com",
        geo_region="us-east-1",
        transport=Transport.UDP,
        record=True
    )
    
    if gateway_response.success:
        print("Gateway created:", gateway_response.data)
    else:
        print("Gateway creation failed:", gateway_response.error)