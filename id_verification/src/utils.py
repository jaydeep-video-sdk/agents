import os
import requests
import json

class VideoSDKClient:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://api.videosdk.live/v2/sip"
        self.headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }

    def create_outbound_gateway(self, name, numbers, address):
        payload = {
            "name": name,
            "numbers": numbers,
            "address": address,
            "geoRegion": "us001",
            "transport": "udp",
            "mediaEncryption": "dtls",
            "record": "true",
            "noiseCancellation": "false",
            "includeHeaders": "true"
        }
        
        response = requests.post(
            f"{self.base_url}/outbound-gateways",
            headers=self.headers,
            json=payload
        )
        return response.json()

    def create_routing_rule(self, gateway_id, name, numbers, room_id):
        payload = {
            "gatewayId": gateway_id,
            "name": name,
            "numbers": numbers,
            "dispatch": {
                "room": {
                    "type": "conference",
                    "id": room_id
                }
            }
        }
        
        response = requests.post(
            f"{self.base_url}/routing-rules",
            headers=self.headers,
            json=payload
        )
        return response.json()

    def trigger_call(self, gateway_id, to_number, from_number, room_id, context=None):
        payload = {
            "gatewayId": gateway_id,
            "sipCallTo": to_number,
            "sipCallFrom": from_number,
            "destinationRoomId": room_id,
            "recordAudio": "true",
            "waitUntilAnswered": "true",
            "ringingTimeout": "60",
            "maxCallDuration": "3600",
            "metadata": context or {}
        }
        
        response = requests.post(
            f"{self.base_url}/calls",
            headers=self.headers,
            json=payload
        )
        return response.json()
