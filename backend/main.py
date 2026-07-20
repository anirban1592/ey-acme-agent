import os
import uuid
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth import init_jwks, verify_jwt
from db import create_pool
from models import User
from services import UserService
from agent import respond, close_checkpointer
from agent.response_types import ErrorResponse, resolve_role_context

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
    await close_checkpointer()

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

    def _error_envelope() -> dict:
        return dict(
            request_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            role_context=resolve_role_context(user.roles),
        )

    try:
        while True:
            data = await websocket.receive_json()
            message_text = data.get("message")
            thread_id = data.get("thread_id") or str(uuid.uuid4())
            if not message_text:
                error = ErrorResponse(message="Missing message content", code="missing_message", **_error_envelope())
                await websocket.send_json({"reply": error.model_dump(mode="json"), "thread_id": thread_id})
                continue

            responses = await respond(message_text, user, thread_id)
            for response in responses:
                await websocket.send_json({"reply": response.model_dump(mode="json"), "thread_id": thread_id})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            fallback_thread_id = locals().get("thread_id") or str(uuid.uuid4())
            error = ErrorResponse(message=str(e), code="websocket_error", **_error_envelope())
            await websocket.send_json({"reply": error.model_dump(mode="json"), "thread_id": fallback_thread_id})
        except Exception:
            pass

if __name__ == "__main__":
    # Use env vars for host/port with sensible defaults
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

