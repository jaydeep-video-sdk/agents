import requests
from dataclasses import dataclass
from typing import List, Optional

TOKEN: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiI0ZjU1MWI1Yy1mYmEyLTQ0OWQtYjU5NC02MjNhYzgyMGIwZWYiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc1NjY0NTQzMywiZXhwIjoxNzU3MjUwMjMzfQ.C8vlHUQPdFNo5hbx617xm3aBUDyJQYjFnJdcnuD25u8"


@dataclass(frozen=True)
class TimeLog:
    start: str
    end: Optional[str]


@dataclass(frozen=True)
class Participant:
    id: str
    participantId: str
    name: str
    timelog: List[TimeLog]


@dataclass(frozen=True)
class Links:
    get_room: str
    get_session: str


@dataclass(frozen=True)
class Session:
    id: str
    roomId: str
    start: str
    end: str
    participants: List[Participant]
    status: str
    links: Links


@dataclass(frozen=True)
class PageInfo:
    currentPage: int
    perPage: int
    lastPage: int
    total: int


@dataclass(frozen=True)
class SessionsResponse:
    pageInfo: PageInfo
    data: List[Session]


@dataclass(frozen=True)
class SessionDetail:
    id: str
    roomId: str
    start: str
    end: str
    participants: List[Participant]
    status: str
    links: Links
    userId: Optional[str]
    customRoomId: Optional[str]
    activeDuration: Optional[int]
    chatLink: Optional[str]


@dataclass(frozen=True)
class EndSessionResponse:
    start: str
    end: Optional[str]
    participants: List[Participant]
    id: str
    roomId: str
    status: str
    links: Links


class VideoSDKClient:
    def __init__(self, token: str):
        self.base_url = "https://api.videosdk.live/v2"
        self.headers = {"Authorization": token, "Content-Type": "application/json"}

    def _request(self, method: str, endpoint: str, params: Optional[dict] = None, json: Optional[dict] = None) -> dict:
        try:
            response = requests.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                json=json,
            )
            if not response.ok:
                raise RuntimeError(f"API request failed [{response.status_code}]: {response.text}")
            return response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"API request error: {e}")

    def fetch_sessions(
        self,
        roomId: Optional[str] = None,
        customRoomId: Optional[str] = None,
        page: Optional[int] = None,
        perPage: Optional[int] = None,
    ) -> SessionsResponse:
        params = {}
        if roomId is not None:
            params["roomId"] = roomId
        if customRoomId is not None:
            params["customRoomId"] = customRoomId
        if page is not None:
            params["page"] = page
        if perPage is not None:
            params["perPage"] = perPage

        data = self._request("GET", "/sessions/", params=params)

        page_info = PageInfo(
            currentPage=int(data["pageInfo"]["currentPage"]),
            perPage=int(data["pageInfo"]["perPage"]),
            lastPage=int(data["pageInfo"]["lastPage"]),
            total=int(data["pageInfo"]["total"]),
        )

        sessions: List[Session] = []
        for s in data.get("data", []):
            participants: List[Participant] = []
            for p in s.get("participants", []):
                timelogs = [TimeLog(start=str(t["start"]), end=str(t["end"]) if "end" in t else None) for t in p.get("timelog", [])]
                participants.append(
                    Participant(
                        id=str(p["_id"]) if "_id" in p else "",
                        participantId=str(p["participantId"]),
                        name=str(p["name"]),
                        timelog=timelogs,
                    )
                )

            links = Links(get_room=str(s["links"]["get_room"]), get_session=str(s["links"]["get_session"]))

            sessions.append(
                Session(
                    id=str(s["id"]),
                    roomId=str(s["roomId"]),
                    start=str(s["start"]),
                    end=str(s["end"]),
                    participants=participants,
                    status=str(s["status"]),
                    links=links,
                )
            )

        return SessionsResponse(pageInfo=page_info, data=sessions)

    def fetch_session(self, sessionId: str) -> SessionDetail:
        data = self._request("GET", f"/sessions/{sessionId}")

        participants: List[Participant] = []
        for p in data.get("participants", []):
            timelogs = [TimeLog(start=str(t["start"]), end=str(t["end"]) if "end" in t else None) for t in p.get("timelog", [])]
            participants.append(
                Participant(
                    id=str(p["_id"]),
                    participantId=str(p["participantId"]),
                    name=str(p["name"]),
                    timelog=timelogs,
                )
            )

        links = Links(
            get_room=str(data["links"]["get_room"]),
            get_session=str(data["links"]["get_session"]),
        )

        return SessionDetail(
            id=str(data["id"]),
            roomId=str(data["roomId"]),
            start=str(data["start"]),
            end=str(data["end"]),
            participants=participants,
            status=str(data["status"]),
            links=links,
            userId=str(data["userId"]) if "userId" in data else None,
            customRoomId=str(data["customRoomId"]) if "customRoomId" in data else None,
            activeDuration=int(data["activeDuration"]) if "activeDuration" in data else None,
            chatLink=str(data["chatLink"]) if "chatLink" in data else None,
        )

    def end_session(self, roomId: str, sessionId: Optional[str] = None) -> EndSessionResponse:
        body = {"roomId": roomId}
        if sessionId is not None:
            body["sessionId"] = sessionId

        data = self._request("POST", "/sessions/end", json=body)

        participants: List[Participant] = []
        for p in data.get("participants", []):
            timelogs = [TimeLog(start=str(t["start"]), end=str(t["end"]) if "end" in t else None) for t in p.get("timelog", [])]
            participants.append(
                Participant(
                    id=str(p["_id"]),
                    participantId=str(p["participantId"]),
                    name=str(p["name"]),
                    timelog=timelogs,
                )
            )

        links = Links(
            get_room=str(data["links"]["get_room"]),
            get_session=str(data["links"]["get_session"]),
        )

        return EndSessionResponse(
            start=str(data["start"]),
            end=str(data["end"]) if "end" in data else None,
            participants=participants,
            id=str(data["id"]),
            roomId=str(data["roomId"]),
            status=str(data["status"]),
            links=links,
        )


if __name__ == "__main__":
    client = VideoSDKClient(TOKEN)
    try:
        print(client.fetch_sessions(roomId="sn1h-7yca-uypo", page=1, perPage=2))
        print(client.fetch_session("68b1a4979b728b68b08e9fba"))
        print(client.end_session(roomId="sn1h-7yca-uypo", sessionId="68b1a4979b728b68b08e9fba"))
    except RuntimeError as e:
        print(e)
