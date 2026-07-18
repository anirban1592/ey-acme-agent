import os
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth import init_jwks, verify_jwt

app = FastAPI()
security = HTTPBearer()

@app.on_event("startup")
async def startup_event():
    # Pre‑load JWKS from Keycloak so we can verify tokens quickly
    await init_jwks()

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

if __name__ == "__main__":
    # Use env vars for host/port with sensible defaults
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
