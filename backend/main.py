import os
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth import init_jwks, verify_jwt
from db import create_pool
from models import User
from services import UserService
from agent import respond

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
security = HTTPBearer()

@app.on_event("startup")
async def startup_event():
    # Pre‑load JWKS from Keycloak so we can verify tokens quickly
    await init_jwks()
    app.state.db_pool = await create_pool()

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "db_pool") and app.state.db_pool:
        await app.state.db_pool.close()

@app.get("/health")
async def health():
    return {"status": "ok"}

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        claims = verify_jwt(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    return claims

@app.get("/me")
async def me(claims: dict = Depends(get_current_user)):
    """Return the decoded JWT claims for the caller."""
    return claims

async def get_current_valid_user(
    request: Request,
    claims: dict = Depends(get_current_user)
) -> User:
    keycloak_id = claims.get("sub")
    if not keycloak_id:
        raise HTTPException(status_code=403, detail="Access denied: Missing subject claim")
    
    pool = request.app.state.db_pool
    user = await UserService.validate_user(pool, keycloak_id)
    if not user:
        raise HTTPException(status_code=403, detail="Access denied: Invalid or unregistered user")
    return user

@app.get("/agent/ping", response_model=User)
async def agent_ping(current_user: User = Depends(get_current_valid_user)):
    """Return the validated User from Postgres database."""
    return current_user

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket chat endpoint with JWT authentication and agent response loop."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    try:
        claims = verify_jwt(token)
        keycloak_id = claims.get("sub")
        if not keycloak_id:
            await websocket.close(code=1008, reason="Invalid token: Missing subject claim")
            return
            
        pool = websocket.app.state.db_pool
        user = await UserService.validate_user(pool, keycloak_id)
        if not user:
            await websocket.close(code=1008, reason="Access denied: Invalid or unregistered user")
            return
    except Exception as e:
        await websocket.close(code=1008, reason=f"Authentication failed: {str(e)}")
        return

    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            message_text = data.get("message")
            if not message_text:
                await websocket.send_json({"error": "Missing message content"})
                continue
            
            reply_text = await respond(message_text, user)
            await websocket.send_json({"reply": reply_text})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": f"Error: {str(e)}"})
        except Exception:
            pass

if __name__ == "__main__":
    # Use env vars for host/port with sensible defaults
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

