import asyncio
import websockets
import json
import httpx
import sys

async def get_token(username, password):
    url = "http://keycloak:8080/realms/assistant/protocol/openid-connect/token"
    data = {
        "client_id": "frontend-spa",
        "grant_type": "password",
        "username": username,
        "password": password
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, data=data)
            if resp.status_code == 200:
                return resp.json()["access_token"]
            else:
                print(f"Failed to get token for {username}: {resp.status_code} {resp.text}", file=sys.stderr)
                return None
        except Exception as e:
            print(f"Error fetching token: {e}", file=sys.stderr)
            return None

async def test_valid():
    token = await get_token("alice", "12345")
    if not token:
        print("Skipping valid WebSocket test due to missing token.", file=sys.stderr)
        return
        
    uri = f"ws://localhost:8000/ws/chat?token={token}"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            payload = {"message": "Hello! Who are you?"}
            print(f"Sending: {payload}")
            await websocket.send(json.dumps(payload))
            
            response = await websocket.recv()
            print(f"Received: {response}")
    except Exception as e:
        print(f"Error connecting: {e}", file=sys.stderr)

async def test_invalid():
    uri = "ws://localhost:8000/ws/chat?token=invalid_token"
    print(f"Connecting with invalid token to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected (unexpectedly)!")
            await websocket.recv()
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed as expected. Code: {e.code}, Reason: {e.reason}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

async def main():
    print("--- Running WebSocket Tests ---")
    await test_invalid()
    print()
    await test_valid()

if __name__ == "__main__":
    asyncio.run(main())
