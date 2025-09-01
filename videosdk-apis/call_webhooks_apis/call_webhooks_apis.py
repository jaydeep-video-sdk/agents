import requests
from dataclasses import dataclass
from typing import List, Optional, Dict

<<<<<<< HEAD
from dotenv import load_dotenv
import os

load_dotenv()
VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")
TOKEN: str = VIDEOSDK_AUTH_TOKEN
=======
TOKEN: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiI0ZjU1MWI1Yy1mYmEyLTQ0OWQtYjU5NC02MjNhYzgyMGIwZWYiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc1NjY0NTQzMywiZXhwIjoxNzU3MjUwMjMzfQ.C8vlHUQPdFNo5hbx617xm3aBUDyJQYjFnJdcnuD25u8"
>>>>>>> e03b930 (- call webhook apis is added)

@dataclass(frozen=True)
class Webhook:
    id: str
    url: str
    events: List[str]
    createdAt: str
    updatedAt: str

@dataclass(frozen=True)
class PageInfo:
    currentPage: int
    perPage: int
    lastPage: int
    total: int

@dataclass(frozen=True)
class WebhooksResponse:
    pageInfo: PageInfo
    data: List[Webhook]

@dataclass(frozen=True)
class DeleteWebhookResponse:
    message: str

<<<<<<< HEAD
class VideoSDKWebhookApis:
=======
class VideoSDKWebhookClient:
>>>>>>> e03b930 (- call webhook apis is added)
    def __init__(self, token: str):
        self.base_url = "https://api.videosdk.live/v2"
        self.headers = {"Authorization": token, "Content-Type": "application/json"}

    def _request(self, method: str, endpoint: str = "", params: Optional[Dict] = None, json: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.request(method, url, headers=self.headers, params=params, json=json, timeout=30)
        except requests.RequestException as e:
            raise RuntimeError(f"API request error: {e}")
        if not resp.ok:
            raise RuntimeError(f"API request failed [{resp.status_code}]: {resp.text}")
        try:
            return resp.json()
        except ValueError:
            raise RuntimeError("API response is not valid JSON")

    def _normalize_webhook(self, raw: Dict) -> Dict:
        out = {}
        out["id"] = str(raw.get("id") or raw.get("_id") or raw.get("webhookId") or "")
        out["url"] = str(raw.get("url") or "")
        out["events"] = [str(e) for e in (raw.get("events") or [])]
        out["createdAt"] = str(raw.get("createdAt") or raw.get("created_at") or "")
        out["updatedAt"] = str(raw.get("updatedAt") or raw.get("updated_at") or "")
        return out

    def create_webhook(self, url: str, events: List[str]) -> Webhook:
        payload = {"url": str(url), "events": [str(e) for e in events]}
        data = self._request("POST", "/sip/webhooks", json=payload)
        norm = self._normalize_webhook(data)
        return Webhook(id=norm["id"], url=norm["url"], events=norm["events"], createdAt=norm["createdAt"], updatedAt=norm["updatedAt"])

    def fetch_all_webhooks(self, search: Optional[str] = None, page: Optional[int] = None, perPage: Optional[int] = None, webhookId: Optional[str] = None) -> WebhooksResponse:
        params: Dict = {}
        if search is not None:
            params["search"] = str(search)
        if page is not None:
            params["page"] = int(page)
        if perPage is not None:
            params["perPage"] = int(perPage)
        if webhookId is not None:
            params["webhookId"] = str(webhookId)
        data = self._request("GET", "/sip/webhooks", params=params if params else None)
        page_info = data.get("pageInfo", {})
        pi = PageInfo(
            currentPage=int(page_info.get("currentPage", 0)),
            perPage=int(page_info.get("perPage", 0)),
            lastPage=int(page_info.get("lastPage", 0)),
            total=int(page_info.get("total", 0)),
        )
        webhooks = []
        for item in data.get("data", []):
            norm = self._normalize_webhook(item if isinstance(item, dict) else {})
            webhooks.append(Webhook(id=norm["id"], url=norm["url"], events=norm["events"], createdAt=norm["createdAt"], updatedAt=norm["updatedAt"]))
        return WebhooksResponse(pageInfo=pi, data=webhooks)

    def fetch_webhook_by_id(self, webhookId: str) -> Webhook:
        data = self._request("GET", f"/sip/webhooks/{str(webhookId)}")
        norm = self._normalize_webhook(data)
        return Webhook(id=norm["id"], url=norm["url"], events=norm["events"], createdAt=norm["createdAt"], updatedAt=norm["updatedAt"])

    def update_webhook(self, webhookId: str, url: str, events: List[str]) -> Webhook:
        payload = {"url": str(url), "events": [str(e) for e in events]}
        data = self._request("PUT", f"/sip/webhooks/{str(webhookId)}", json=payload)
        norm = self._normalize_webhook(data)
        return Webhook(id=norm["id"], url=norm["url"], events=norm["events"], createdAt=norm["createdAt"], updatedAt=norm["updatedAt"])

    def delete_webhook(self, webhookId: str) -> DeleteWebhookResponse:
        data = self._request("DELETE", f"/sip/webhooks/{str(webhookId)}")
        return DeleteWebhookResponse(message=str(data.get("message", "")))


if __name__ == "__main__":
<<<<<<< HEAD
    client = VideoSDKWebhookApis(TOKEN)
=======
    client = VideoSDKWebhookClient(TOKEN)
>>>>>>> e03b930 (- call webhook apis is added)

    created = client.create_webhook("https://example.com/webhook", ["call-started", "call-answered"])
    print(created)

    all_webhooks = client.fetch_all_webhooks()
    print(all_webhooks)

    single = client.fetch_webhook_by_id(created.id)
    print(single)

    deleted = client.delete_webhook(created.id)
    print(deleted)
