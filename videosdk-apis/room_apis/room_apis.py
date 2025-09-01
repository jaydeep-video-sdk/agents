import requests
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
import os

load_dotenv()
VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")
TOKEN: str = VIDEOSDK_AUTH_TOKEN

@dataclass(frozen=True)
class RoomUser:
    email: Optional[str]
    name: Optional[str]
    discontinuedReason: Optional[str]
    id: Optional[str]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RoomUser":
        return RoomUser(
            email=str(data["email"]) if data.get("email") is not None else None,
            name=str(data["name"]) if data.get("name") is not None else None,
            discontinuedReason=str(data["discontinuedReason"]) if data.get("discontinuedReason") is not None else None,
            id=str(data["id"]) if data.get("id") is not None else None,
        )


@dataclass(frozen=True)
class RoomLinks:
    get_room: str
    get_session: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RoomLinks":
        return RoomLinks(
            get_room=str(data.get("get_room", "")),
            get_session=str(data.get("get_session", "")),
        )


@dataclass(frozen=True)
class RoomData:
    roomId: str
    customRoomId: Optional[str]
    disabled: Optional[bool]
    createdAt: Optional[str]
    updatedAt: Optional[str]
    user: Optional[RoomUser]
    id: Optional[str]
    links: Optional[RoomLinks]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RoomData":
        return RoomData(
            roomId=str(data.get("roomId", "")),
            customRoomId=str(data["customRoomId"]) if data.get("customRoomId") is not None else None,
            disabled=bool(data["disabled"]) if "disabled" in data else None,
            createdAt=str(data["createdAt"]) if data.get("createdAt") is not None else None,
            updatedAt=str(data["updatedAt"]) if data.get("updatedAt") is not None else None,
            user=RoomUser.from_dict(data["user"]) if "user" in data and data["user"] is not None else None,
            id=str(data["id"]) if data.get("id") is not None else None,
            links=RoomLinks.from_dict(data["links"]) if "links" in data and data["links"] is not None else None,
        )


@dataclass(frozen=True)
class PageInfo:
    currentPage: int
    perPage: int
    lastPage: int
    total: int

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PageInfo":
        return PageInfo(
            currentPage=int(data.get("currentPage", 0)),
            perPage=int(data.get("perPage", 0)),
            lastPage=int(data.get("lastPage", 0)),
            total=int(data.get("total", 0)),
        )


@dataclass(frozen=True)
class FetchRoomsResponse:
    pageInfo: PageInfo
    data: List[RoomData]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FetchRoomsResponse":
        return FetchRoomsResponse(
            pageInfo=PageInfo.from_dict(dict(data.get("pageInfo", {}))),
            data=[RoomData.from_dict(x) for x in data.get("data", [])],
        )


@dataclass(frozen=True)
class RoomResponse:
    roomId: str
    customRoomId: Optional[str]
    userId: Optional[str]
    disabled: Optional[bool]
    createdAt: Optional[str]
    updatedAt: Optional[str]
    id: Optional[str]
    links: Optional[Dict[str, str]]


@dataclass(frozen=True)
class ValidateRoomResponse:
    roomId: str
    customRoomId: Optional[str]
    userId: Optional[str]
    disabled: Optional[bool]
    createdAt: Optional[str]
    updatedAt: Optional[str]
    id: Optional[str]
    links: Optional[Dict[str, str]]


@dataclass(frozen=True)
class FetchRoomUser:
    email: Optional[str]
    name: Optional[str]
    discontinuedReason: Optional[str]
    id: Optional[str]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FetchRoomUser":
        return FetchRoomUser(
            email=str(data["email"]) if data.get("email") is not None else None,
            name=str(data["name"]) if data.get("name") is not None else None,
            discontinuedReason=str(data["discontinuedReason"]) if data.get("discontinuedReason") is not None else None,
            id=str(data["id"]) if data.get("id") is not None else None,
        )


@dataclass(frozen=True)
class FetchRoomLinks:
    get_room: str
    get_session: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FetchRoomLinks":
        return FetchRoomLinks(
            get_room=str(data.get("get_room", "")),
            get_session=str(data.get("get_session", "")),
        )


@dataclass(frozen=True)
class FetchRoomResponse:
    roomId: str
    customRoomId: Optional[str]
    disabled: Optional[bool]
    createdAt: Optional[str]
    updatedAt: Optional[str]
    user: Optional[FetchRoomUser]
    id: Optional[str]
    links: Optional[FetchRoomLinks]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FetchRoomResponse":
        return FetchRoomResponse(
            roomId=str(data.get("roomId", "")),
            customRoomId=str(data["customRoomId"]) if data.get("customRoomId") is not None else None,
            disabled=bool(data["disabled"]) if "disabled" in data else None,
            createdAt=str(data["createdAt"]) if data.get("createdAt") is not None else None,
            updatedAt=str(data["updatedAt"]) if data.get("updatedAt") is not None else None,
            user=FetchRoomUser.from_dict(data["user"]) if "user" in data and data["user"] is not None else None,
            id=str(data["id"]) if data.get("id") is not None else None,
            links=FetchRoomLinks.from_dict(data["links"]) if "links" in data and data["links"] is not None else None,
        )


@dataclass(frozen=True)
class DeactivateRoomWebhook:
    events: List[str]
    endPoint: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "DeactivateRoomWebhook":
        return DeactivateRoomWebhook(
            events=[str(e) for e in data.get("events", [])],
            endPoint=str(data.get("endPoint", "")),
        )


@dataclass(frozen=True)
class DeactivateRoomUser:
    email: Optional[str]
    name: Optional[str]
    discontinuedReason: Optional[str]
    id: Optional[str]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "DeactivateRoomUser":
        return DeactivateRoomUser(
            email=str(data["email"]) if data.get("email") is not None else None,
            name=str(data["name"]) if data.get("name") is not None else None,
            discontinuedReason=str(data["discontinuedReason"]) if data.get("discontinuedReason") is not None else None,
            id=str(data["id"]) if data.get("id") is not None else None,
        )


@dataclass(frozen=True)
class DeactivateRoomResponse:
    webhook: Optional[DeactivateRoomWebhook]
    disabled: Optional[bool]
    meetingId: Optional[str]
    userMeetingId: Optional[str]
    userId: Optional[str]
    createdAt: Optional[str]
    updatedAt: Optional[str]
    user: Optional[DeactivateRoomUser]
    id: Optional[str]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "DeactivateRoomResponse":
        return DeactivateRoomResponse(
            webhook=DeactivateRoomWebhook.from_dict(data["webhook"]) if "webhook" in data and data["webhook"] else None,
            disabled=bool(data["disabled"]) if "disabled" in data else None,
            meetingId=str(data["meetingId"]) if data.get("meetingId") is not None else None,
            userMeetingId=str(data["userMeetingId"]) if data.get("userMeetingId") is not None else None,
            userId=str(data["userId"]) if data.get("userId") is not None else None,
            createdAt=str(data["createdAt"]) if data.get("createdAt") is not None else None,
            updatedAt=str(data["updatedAt"]) if data.get("updatedAt") is not None else None,
            user=DeactivateRoomUser.from_dict(data["user"]) if "user" in data and data["user"] else None,
            id=str(data["id"]) if data.get("id") is not None else None,
        )


class VideoSDKRoomApis:
    def __init__(self, token: str) -> None:
        self.token: str = token
        self.base_url: str = "https://api.videosdk.live/v2"

    def _request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers: Dict[str, str] = {"Authorization": self.token, "Content-Type": "application/json"}
        try:
            r = requests.request(method=method, url=f"{self.base_url}{endpoint}", headers=headers, json=data, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Request failed: {e}") from e
        except ValueError as e:
            raise RuntimeError(f"Invalid JSON response: {e}") from e

    def create_room(
        self,
        customRoomId: Optional[str] = None,
        webhook: Optional[Dict[str, Any]] = None,
        autoCloseConfig: Optional[Dict[str, Any]] = None,
        autoStartConfig: Optional[Dict[str, Any]] = None,
    ) -> RoomResponse:
        payload: Dict[str, Any] = {}
        if customRoomId is not None:
            payload["customRoomId"] = str(customRoomId)
        if webhook is not None:
            payload["webhook"] = dict(webhook)
        if autoCloseConfig is not None:
            payload["autoCloseConfig"] = dict(autoCloseConfig)
        if autoStartConfig is not None:
            payload["autoStartConfig"] = dict(autoStartConfig)
        j: Dict[str, Any] = self._request("POST", "/rooms", data=payload)
        return RoomResponse(
            roomId=str(j.get("roomId", "")),
            customRoomId=str(j["customRoomId"]) if j.get("customRoomId") is not None else None,
            userId=str(j["userId"]) if j.get("userId") is not None else None,
            disabled=bool(j["disabled"]) if "disabled" in j else None,
            createdAt=str(j["createdAt"]) if j.get("createdAt") is not None else None,
            updatedAt=str(j["updatedAt"]) if j.get("updatedAt") is not None else None,
            id=str(j["id"]) if j.get("id") is not None else None,
            links={str(k): str(v) for k, v in j["links"].items()} if "links" in j and j["links"] is not None else None,
        )

    def validate_room(self, roomId: str) -> ValidateRoomResponse:
        j: Dict[str, Any] = self._request("GET", f"/rooms/validate/{roomId}")
        return ValidateRoomResponse(
            roomId=str(j.get("roomId", "")),
            customRoomId=str(j["customRoomId"]) if j.get("customRoomId") is not None else None,
            userId=str(j["userId"]) if j.get("userId") is not None else None,
            disabled=bool(j["disabled"]) if "disabled" in j else None,
            createdAt=str(j["createdAt"]) if j.get("createdAt") is not None else None,
            updatedAt=str(j["updatedAt"]) if j.get("updatedAt") is not None else None,
            id=str(j["id"]) if j.get("id") is not None else None,
            links={str(k): str(v) for k, v in j["links"].items()} if "links" in j and j["links"] is not None else None,
        )

    def fetch_rooms(self, page: Optional[int] = None, perPage: Optional[int] = None) -> FetchRoomsResponse:
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = int(page)
        if perPage is not None:
            params["perPage"] = int(perPage)
        j: Dict[str, Any] = self._request("GET", "/rooms", params=params)
        return FetchRoomsResponse.from_dict(j)

    def fetch_room(self, roomId: str) -> FetchRoomResponse:
        j: Dict[str, Any] = self._request("GET", f"/rooms/{roomId}")
        return FetchRoomResponse.from_dict(j)

    def deactivate_room(self, roomId: str) -> DeactivateRoomResponse:
        payload: Dict[str, Any] = {"roomId": str(roomId)}
        j: Dict[str, Any] = self._request("POST", "/rooms/deactivate", data=payload)
        return DeactivateRoomResponse.from_dict(j)


if __name__ == "__main__":
    client: VideoSDKRoomApis = VideoSDKRoomApis(TOKEN)
    try:
        created: RoomResponse = client.create_room()
        print(created)
    except Exception as e:
        print(e)

    try:
        validated: ValidateRoomResponse = client.validate_room(created.roomId if created.roomId else "")
        print(validated)
    except Exception as e:
        print(e)

    try:
        fetched: FetchRoomsResponse = client.fetch_rooms(page=1, perPage=2)
        print(fetched)
    except Exception as e:
        print(e)

    try:
        room: FetchRoomResponse = client.fetch_room(created.roomId if created.roomId else "")
        print(room)
    except Exception as e:
        print(e)

    try:
        deactivated: DeactivateRoomResponse = client.deactivate_room(created.roomId if created.roomId else "")
        print(deactivated)
    except Exception as e:
        print(e)
