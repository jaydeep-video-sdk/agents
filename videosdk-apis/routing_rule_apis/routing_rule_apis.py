import requests
from dataclasses import dataclass
from typing import List, Optional, Dict


from dotenv import load_dotenv
import os

load_dotenv()
VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")
TOKEN: str = VIDEOSDK_AUTH_TOKEN
@dataclass(frozen=True)
class RoomDispatch:
    type: str
    prefix: Optional[str] = None
    id: Optional[str] = None
    pin: Optional[str] = None

@dataclass(frozen=True)
class AgentDispatch:
    type: str
    id: str

@dataclass(frozen=True)
class Dispatch:
    room: Optional[RoomDispatch] = None
    agent: Optional[AgentDispatch] = None

@dataclass(frozen=True)
class RoutingRule:
    id: str
    name: str
    type: str
    numbers: List[str]
    gatewayId: str
    dispatch: Dispatch

@dataclass(frozen=True)
class PageInfo:
    currentPage: int
    perPage: int
    lastPage: int
    total: int

@dataclass(frozen=True)
class RoutingRulesResponse:
    pageInfo: PageInfo
    data: List[RoutingRule]

@dataclass(frozen=True)
class DeleteRuleResponse:
    message: str

class VideoSDKRoutingApis:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.videosdk.live/v2"

    def _request(self, method: str, endpoint: str, json: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        resp = requests.request(
            method,
            f"{self.base_url}{endpoint}",
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            json=json,
            params=params,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def create_routing_rule(self, gatewayId: str, name: str, numbers: List[str], dispatch: Dict) -> RoutingRule:
        payload = {"gatewayId": gatewayId, "name": name, "numbers": numbers, "dispatch": dispatch}
        data = self._request("POST", "/sip/routing-rules", json=payload)
        room = data.get("dispatch", {}).get("room")
        agent = data.get("dispatch", {}).get("agent")
        return RoutingRule(
            id=str(data["id"]),
            name=str(data["name"]),
            type=str(data["type"]),
            numbers=[str(n) for n in data["numbers"]],
            gatewayId=str(data["gatewayId"]),
            dispatch=Dispatch(
                room=RoomDispatch(**room) if room else None,
                agent=AgentDispatch(**agent) if agent else None
            )
        )

    def fetch_routing_rules(self, gatewayId: Optional[str] = None) -> RoutingRulesResponse:
        params = {"gatewayId": gatewayId} if gatewayId else None
        data = self._request("GET", "/sip/routing-rules", params=params)
        page_info = PageInfo(**data["pageInfo"])
        rules = []
        for r in data.get("data", []):
            room = r.get("dispatch", {}).get("room")
            agent = r.get("dispatch", {}).get("agent")
            rules.append(RoutingRule(
                id=str(r["id"]),
                name=str(r["name"]),
                type=str(r["type"]),
                numbers=[str(n) for n in r["numbers"]],
                gatewayId=str(r["gatewayId"]),
                dispatch=Dispatch(
                    room=RoomDispatch(**room) if room else None,
                    agent=AgentDispatch(**agent) if agent else None
                )
            ))
        return RoutingRulesResponse(pageInfo=page_info, data=rules)

    def fetch_routing_rule(self, ruleId: str) -> RoutingRule:
        data = self._request("GET", f"/sip/routing-rules/{ruleId}")
        room = data.get("dispatch", {}).get("room")
        agent = data.get("dispatch", {}).get("agent")
        return RoutingRule(
            id=str(data["id"]),
            name=str(data["name"]),
            type=str(data["type"]),
            numbers=[str(n) for n in data["numbers"]],
            gatewayId=str(data["gatewayId"]),
            dispatch=Dispatch(
                room=RoomDispatch(**room) if room else None,
                agent=AgentDispatch(**agent) if agent else None
            )
        )

    def delete_routing_rule(self, ruleId: str) -> DeleteRuleResponse:
        data = self._request("DELETE", f"/sip/routing-rules/{ruleId}")
        return DeleteRuleResponse(message=str(data["message"]))

