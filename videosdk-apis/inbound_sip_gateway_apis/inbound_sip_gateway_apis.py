import requests
from dataclasses import dataclass
from typing import List, Optional, Dict

TOKEN: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiI0ZjU1MWI1Yy1mYmEyLTQ0OWQtYjU5NC02MjNhYzgyMGIwZWYiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc1NjY0NTQzMywiZXhwIjoxNzU3MjUwMjMzfQ.C8vlHUQPdFNo5hbx617xm3aBUDyJQYjFnJdcnuD25u8"


@dataclass(frozen=True)
class Auth:
    username: str
    password: str


@dataclass(frozen=True)
class InboundGatewayResponse:
    id: str
    name: str
    numbers: List[str]
    allowedAddresses: List[str]
    allowedNumbers: List[str]
    mediaEncryption: str
    transport: str
    record: bool
    tags: List[str]
    auth: Optional[Auth]
    geoRegion: Optional[str]
    metadata: Optional[Dict[str, str]]
    noiseCancellation: bool


@dataclass(frozen=True)
class InboundGateway:
    id: str
    name: str
    numbers: List[str]
    allowedAddresses: List[str]
    allowedNumbers: List[str]
    mediaEncryption: str
    transport: str
    record: bool
    tags: List[str]
    auth: Optional[Auth]
    geoRegion: Optional[str]
    metadata: Optional[Dict[str, str]]
    noiseCancellation: bool
    address: Optional[str] = None


@dataclass(frozen=True)
class PageInfo:
    currentPage: int
    perPage: int
    lastPage: int
    total: int


@dataclass(frozen=True)
class InboundGatewaysResponse:
    pageInfo: PageInfo
    data: List[InboundGateway]


@dataclass(frozen=True)
class InboundGatewayDetail:
    id: str
    name: str
    numbers: List[str]
    allowedAddresses: List[str]
    allowedNumbers: List[str]
    mediaEncryption: str
    transport: str
    record: bool
    tags: List[str]
    auth: Optional[Auth]
    geoRegion: Optional[str]
    metadata: Optional[Dict[str, str]]
    noiseCancellation: bool
    address: Optional[str] = None

@dataclass(frozen=True)
class DeleteGatewayResponse:
    message: str

class VideoSDKClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.videosdk.live/v2"

    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        try:
            response = requests.request(
                method,
                f"{self.base_url}{endpoint}",
                headers={"Authorization": self.token, "Content-Type": "application/json"},
                json=json,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"API request failed: {e}")

    def create_inbound_gateway(
        self,
        name: str,
        numbers: List[str],
        auth: Optional[Dict[str, str]] = None,
        allowedAddresses: Optional[List[str]] = None,
        allowedNumbers: Optional[List[str]] = None,
        mediaEncryption: Optional[str] = None,
        record: Optional[bool] = None,
        noiseCancellation: Optional[bool] = None,
        metadata: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
    ) -> InboundGatewayResponse:
        payload = {
            "name": name,
            "numbers": numbers,
        }
        if auth is not None:
            payload["auth"] = auth
        if allowedAddresses is not None:
            payload["allowedAddresses"] = allowedAddresses
        if allowedNumbers is not None:
            payload["allowedNumbers"] = allowedNumbers
        if mediaEncryption is not None:
            payload["mediaEncryption"] = mediaEncryption
        if record is not None:
            payload["record"] = record
        if noiseCancellation is not None:
            payload["noiseCancellation"] = noiseCancellation
        if metadata is not None:
            payload["metadata"] = metadata
        if tags is not None:
            payload["tags"] = tags

        data = self._request("POST", "/sip/inbound-gateways", json=payload)
        return InboundGatewayResponse(
            id=str(data["id"]),
            name=str(data["name"]),
            numbers=[str(x) for x in data.get("numbers", [])],
            allowedAddresses=[str(x) for x in data.get("allowedAddresses", [])],
            allowedNumbers=[str(x) for x in data.get("allowedNumbers", [])],
            mediaEncryption=str(data["mediaEncryption"]),
            transport=str(data["transport"]),
            record=bool(data["record"]),
            tags=[str(x) for x in data.get("tags", [])],
            auth=Auth(
                username=str(data["auth"]["username"]),
                password=str(data["auth"]["password"]),
            )
            if "auth" in data and data["auth"] is not None
            else None,
            geoRegion=str(data["geoRegion"]) if "geoRegion" in data else None,
            metadata=data.get("metadata"),
            noiseCancellation=bool(data["noiseCancellation"]),
        )

    def fetch_inbound_gateways(
        self,
        id: Optional[str] = None,
        search: Optional[str] = None,
        page: Optional[int] = None,
        perPage: Optional[int] = None,
    ) -> InboundGatewaysResponse:
        params = {}
        if id is not None:
            params["id"] = id
        if search is not None:
            params["search"] = search
        if page is not None:
            params["page"] = str(page)
        if perPage is not None:
            params["perPage"] = str(perPage)

        data = self._request("GET", "/sip/inbound-gateways", params=params)
        page_info = data["pageInfo"]
        pageInfo = PageInfo(
            currentPage=int(page_info["currentPage"]),
            perPage=int(page_info["perPage"]),
            lastPage=int(page_info["lastPage"]),
            total=int(page_info["total"]),
        )

        gateways: List[InboundGateway] = []
        for g in data.get("data", []):
            gateways.append(
                InboundGateway(
                    id=str(g["id"]),
                    name=str(g["name"]),
                    numbers=[str(x) for x in g.get("numbers", [])],
                    allowedAddresses=[str(x) for x in g.get("allowedAddresses", [])],
                    allowedNumbers=[str(x) for x in g.get("allowedNumbers", [])],
                    mediaEncryption=str(g["mediaEncryption"]),
                    transport=str(g["transport"]),
                    record=bool(g["record"]),
                    tags=[str(x) for x in g.get("tags", [])],
                    auth=Auth(
                        username=str(g["auth"]["username"]),
                        password=str(g["auth"]["password"]),
                    )
                    if "auth" in g and g["auth"] is not None
                    else None,
                    geoRegion=str(g["geoRegion"]) if "geoRegion" in g else None,
                    metadata={str(k): str(v) for k, v in g.get("metadata", {}).items()}
                    if "metadata" in g
                    else None,
                    noiseCancellation=bool(g["noiseCancellation"]),
                    address=str(g["address"]) if "address" in g else None,
                )
            )

        return InboundGatewaysResponse(pageInfo=pageInfo, data=gateways)

    def fetch_inbound_gateway_by_id(self, gatewayId: str) -> InboundGatewayDetail:
        data = self._request("GET", f"/sip/inbound-gateways/{gatewayId}")
        return InboundGatewayDetail(
            id=str(data["id"]),
            name=str(data["name"]),
            numbers=[str(x) for x in data.get("numbers", [])],
            allowedAddresses=[str(x) for x in data.get("allowedAddresses", [])],
            allowedNumbers=[str(x) for x in data.get("allowedNumbers", [])],
            mediaEncryption=str(data["mediaEncryption"]),
            transport=str(data["transport"]),
            record=bool(data["record"]),
            tags=[str(x) for x in data.get("tags", [])],
            auth=Auth(
                username=str(data["auth"]["username"]),
                password=str(data["auth"]["password"])
            ) if "auth" in data and data["auth"] is not None else None,
            geoRegion=str(data["geoRegion"]) if "geoRegion" in data else None,
            metadata={str(k): str(v) for k, v in data.get("metadata", {}).items()} if "metadata" in data else None,
            noiseCancellation=bool(data["noiseCancellation"]),
            address=str(data["address"]) if "address" in data else None,
        )

    def delete_inbound_gateway(self, gatewayId: str) -> DeleteGatewayResponse:
        data = self._request("DELETE", f"/sip/inbound-gateways/{gatewayId}")
        return DeleteGatewayResponse(message=str(data["message"]))


if __name__ == "__main__":
    client = VideoSDKClient(TOKEN)
    response = client.create_inbound_gateway(
        name="Twilio Inbound Gateway",
        numbers=["+11234567890", "+19876543210"],
        auth={"username": "sip_user", "password": "testpass"},
        allowedAddresses=["sip:trusted.example.com"],
        allowedNumbers=["+14150001111"],
        mediaEncryption="disable",
        record=False,
        noiseCancellation=True,
        metadata={"env": "production"},
        tags=["production", "twilio"],
    )
    print(response)
    response = client.fetch_inbound_gateways(page=1, perPage=5)
    print(response)
    gateway = client.fetch_inbound_gateway_by_id(response.data[0].id)
    print(gateway)
    response = client.delete_inbound_gateway(response.data[0].id)
    print(response)