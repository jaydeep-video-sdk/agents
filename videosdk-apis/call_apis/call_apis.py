import requests
from dataclasses import dataclass
from typing import List, Optional, Dict

TOKEN: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiI0ZjU1MWI1Yy1mYmEyLTQ0OWQtYjU5NC02MjNhYzgyMGIwZWYiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc1NjY0NTQzMywiZXhwIjoxNzU3MjUwMjMzfQ.C8vlHUQPdFNo5hbx617xm3aBUDyJQYjFnJdcnuD25u8"

@dataclass(frozen=True)
class TimeLog:
    status: str
    timestamp: str

@dataclass(frozen=True)
class CallData:
    callId: str
    type: str
    gatewayId: str
    gatewayName: str
    ruleId: Optional[str]
    ruleName: Optional[str]
    roomId: str
    to: str
    from_: str
    status: str
    timelog: List[TimeLog]
    start: Optional[str]
    end: Optional[str]
    sessionId: Optional[str]
    userId: Optional[str]
    deleted: bool

@dataclass(frozen=True)
class PageInfo:
    currentPage: int
    perPage: int
    lastPage: int
    total: int

@dataclass(frozen=True)
class CallsResponse:
    pageInfo: PageInfo
    data: List[CallData]

@dataclass(frozen=True)
class OutboundCallData:
    callId: str
    status: str
    roomId: Optional[str]
    sipCallTo: str
    sipCallFrom: Optional[str]
    gatewayId: str
    metadata: Optional[Dict[str, str]]
    timelog: List[TimeLog]

@dataclass(frozen=True)
class OutboundCallResponse:
    message: str
    data: OutboundCallData

class VideoSDKCallClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.videosdk.live/v2"

    def _get(self, params: Optional[dict] = None) -> dict:
        resp = requests.get(
            f"{self.base_url}/sip/call",
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            params=params,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, payload: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}/sip/call",
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_calls(
        self,
        roomId: Optional[str] = None,
        sessionId: Optional[str] = None,
        id: Optional[str] = None,
        gatewayId: Optional[str] = None,
        ruleId: Optional[str] = None,
        type: Optional[str] = None,
        search: Optional[str] = None,
        startDate: Optional[int] = None,
        endDate: Optional[int] = None,
        page: Optional[int] = None,
        perPage: Optional[int] = None
    ) -> CallsResponse:
        params = {k: v for k, v in locals().items() if k != "self" and v is not None}
        data = self._get(params=params)
        calls = []
        for c in data.get("data", []):
            timelog = [TimeLog(status=t.get("status",""), timestamp=t.get("timestamp","")) for t in c.get("timelog",[])]
            calls.append(CallData(
                callId=c.get("callId",""),
                type=c.get("type",""),
                gatewayId=c.get("gatewayId",""),
                gatewayName=c.get("gatewayName",""),
                ruleId=c.get("ruleId"),
                ruleName=c.get("ruleName"),
                roomId=c.get("roomId",""),
                to=c.get("to",""),
                from_=c.get("from",""),
                status=c.get("status",""),
                timelog=timelog,
                start=c.get("start"),
                end=c.get("end"),
                sessionId=c.get("sessionId"),
                userId=c.get("userId"),
                deleted=c.get("deleted",False)
            ))
        page_info = PageInfo(**data["pageInfo"])
        return CallsResponse(pageInfo=page_info, data=calls)

    def make_outbound_call(
            self,
            gatewayId: str,
            sipCallTo: str,
            sipCallFrom: Optional[str] = None,
            destinationRoomId: Optional[str] = None,
            participant: Optional[Dict[str, str]] = None,
            recordAudio: Optional[bool] = None,
            waitUntilAnswered: Optional[bool] = None,
            ringingTimeout: Optional[int] = None,
            dtmf: Optional[str] = None,
            maxCallDuration: Optional[int] = None,
            mediaEncryption: Optional[str] = None,
            hidePhoneNumber: Optional[bool] = None,
            headers: Optional[Dict[str, str]] = None,
            includeHeaders: Optional[List[str]] = None,
            metadata: Optional[Dict[str, str]] = None
    ) -> OutboundCallResponse:
        payload = {k: v for k, v in locals().items() if k != "self" and v is not None}
        data = self._post(payload)
        call_dict = data["data"]
        timelog = [TimeLog(status=t.get("status", ""), timestamp=t.get("timestamp", "")) for t in
                   call_dict.get("timelog", [])]
        call_data = OutboundCallData(
            callId=call_dict.get("callId", ""),
            status=call_dict.get("status", ""),
            roomId=call_dict.get("roomId"),
            sipCallTo=call_dict.get("sipCallTo", ""),
            sipCallFrom=call_dict.get("sipCallFrom"),
            gatewayId=call_dict.get("gatewayId", ""),
            metadata=call_dict.get("metadata"),
            timelog=timelog
        )

        return OutboundCallResponse(message=str(data.get("message", "")), data=call_data)

if __name__ == "__main__":
    client = VideoSDKCallClient(TOKEN)
    calls_resp = client.fetch_calls()
    print(calls_resp)

    call_resp = client.make_outbound_call(
        gatewayId="9908f984-fd53-433d-b192-3895e6a2d3e0",
        sipCallTo="+919664920749",
        destinationRoomId="sn1h-7yca-uypo"
    )
    print(call_resp)
