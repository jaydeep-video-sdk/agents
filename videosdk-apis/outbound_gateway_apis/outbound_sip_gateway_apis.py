import requests
from dataclasses import dataclass
from typing import List, Optional, Dict

from dotenv import load_dotenv
import os

load_dotenv()
VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")
TOKEN: str = VIDEOSDK_AUTH_TOKEN

@dataclass(frozen=True)
class Auth:
    username: str
    password: Optional[str] = None

@dataclass(frozen=True)
class OutboundGateway:
    id: str
    name: str
    numbers: List[str]
    address: str
    geoRegion: Optional[str]
    transport: str
    auth: Auth
    mediaEncryption: Optional[str]
    record: Optional[bool]
    noiseCancellation: Optional[bool]
    allowedNumbers: Optional[List[str]]
    metadata: Optional[Dict[str, str]]
    tags: Optional[List[str]]

@dataclass(frozen=True)
class PageInfo:
    currentPage: int
    perPage: int
    lastPage: int
    total: int

@dataclass(frozen=True)
class OutboundGatewaysResponse:
    pageInfo: PageInfo
    data: List[OutboundGateway]

@dataclass(frozen=True)
class DeleteGatewayResponse:
    message: str

class OutbondGateWayApis:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.videosdk.live/v2"

    def _request(self, method: str, endpoint: str, json: Optional[dict] = None) -> dict:
        try:
            resp = requests.request(
                method,
                f"{self.base_url}{endpoint}",
                headers={"Authorization": self.token, "Content-Type": "application/json"},
                json=json,
                timeout=30
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"API request failed: {e}")

    def create_outbound_gateway(
        self,
        name: str,
        numbers: List[str],
        address: str,
        transport: str,
        auth: Dict[str, str],
        geoRegion: Optional[str] = None,
        mediaEncryption: Optional[str] = None,
        record: Optional[bool] = None,
        noiseCancellation: Optional[bool] = None,
        allowedNumbers: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        includeHeaders: Optional[bool] = None,
        headers: Optional[Dict[str, str]] = None,
        headersToAttributes: Optional[Dict[str, str]] = None
    ) -> OutboundGateway:
        payload = {
            "name": name,
            "numbers": numbers,
            "address": address,
            "transport": transport,
            "auth": auth
        }
        if geoRegion: payload["geoRegion"] = geoRegion
        if mediaEncryption: payload["mediaEncryption"] = mediaEncryption
        if record is not None: payload["record"] = record
        if noiseCancellation is not None: payload["noiseCancellation"] = noiseCancellation
        if allowedNumbers: payload["allowedNumbers"] = allowedNumbers
        if metadata: payload["metadata"] = metadata
        if tags: payload["tags"] = tags
        if includeHeaders is not None: payload["includeHeaders"] = includeHeaders
        if headers: payload["headers"] = headers
        if headersToAttributes: payload["headersToAttributes"] = headersToAttributes

        data = self._request("POST", "/sip/outbound-gateways", json=payload)
        return self._map_outbound_gateway(data, id_key="gatewayId")

    def fetch_outbound_gateways(
        self,
        id: Optional[str] = None,
        search: Optional[str] = None,
        page: Optional[int] = None,
        perPage: Optional[int] = None
    ) -> OutboundGatewaysResponse:
        params = {}
        if id: params["id"] = id
        if search: params["search"] = search
        if page: params["page"] = page
        if perPage: params["perPage"] = perPage

        resp = requests.get(
            f"{self.base_url}/sip/outbound-gateways",
            headers={"Authorization": self.token},
            params=params,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        pageInfo = PageInfo(**data["pageInfo"])
        gateways = [self._map_outbound_gateway(g) for g in data.get("data", [])]
        return OutboundGatewaysResponse(pageInfo=pageInfo, data=gateways)

    def fetch_outbound_gateway(self, gatewayId: str) -> OutboundGateway:
        data = self._request("GET", f"/sip/outbound-gateways/{gatewayId}")
        return self._map_outbound_gateway(data)

    def update_outbound_gateway(self, gatewayId: str, payload: dict) -> OutboundGateway:
        self._request("PUT", f"/sip/outbound-gateways/{gatewayId}", json=payload)
        return self.fetch_outbound_gateway(gatewayId)

    def delete_outbound_gateway(self, gatewayId: str) -> DeleteGatewayResponse:
        data = self._request("DELETE", f"/sip/outbound-gateways/{gatewayId}")
        return DeleteGatewayResponse(message=str(data["message"]))

    def _map_outbound_gateway(self, data: dict, id_key: str = "id") -> OutboundGateway:
        return OutboundGateway(
            id=str(data.get(id_key)),
            name=str(data.get("name")),
            numbers=[str(n) for n in data.get("numbers", [])],
            address=str(data.get("address")),
            geoRegion=str(data.get("geoRegion")) if data.get("geoRegion") else None,
            transport=str(data.get("transport")),
            auth=Auth(
                username=str(data["auth"]["username"]),
                password=data["auth"].get("password") if data.get("auth") else None
            ),
            mediaEncryption=str(data.get("mediaEncryption")) if data.get("mediaEncryption") else None,
            record=bool(data.get("record")) if data.get("record") is not None else None,
            noiseCancellation=bool(data.get("noiseCancellation")) if data.get("noiseCancellation") is not None else None,
            allowedNumbers=[str(n) for n in data.get("allowedNumbers", [])] if data.get("allowedNumbers") else None,
            metadata=data.get("metadata"),
            tags=data.get("tags")
        )


if __name__ == "__main__":
    client = OutbondGateWayApis(TOKEN)

    gw = client.create_outbound_gateway(
        name="Minimal Gateway",
        numbers=["+12065551234"],
        address="sip.myprovider.com",
        transport="udp",
        auth={"username": "sipuser", "password": "sippass"}
    )
    print(gw)

    all_gws = client.fetch_outbound_gateways(page=1, perPage=10)
    print(all_gws)

    one_gw = client.fetch_outbound_gateway(gw.id)
    print(one_gw)

    updated_gw = client.update_outbound_gateway(gw.id, {"numbers": ["+12065551234", "+12065559876"]})
    print(updated_gw)

    del_resp = client.delete_outbound_gateway(gw.id)
    print(del_resp)
