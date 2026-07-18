import httpx
import os
from jose import jwt
from jose.utils import base64url_decode
from typing import Dict, Any

# Global JWKS cache – fetched once at startup
_JWKS: Dict[str, Any] = {}

async def fetch_jwks(jwks_url: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        return resp.json()

def get_key(kid: str) -> Dict[str, str]:
    for key in _JWKS.get("keys", []):
        if key.get("kid") == kid:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "alg": key["alg"],
                "n": key["n"],
                "e": key["e"],
            }
    raise Exception("Public key not found for kid")

async def init_jwks():
    # Expected environment variable with Keycloak JWKS endpoint
    jwks_url = os.getenv("KEYCLOAK_JWKS_URL", "http://keycloak:8080/realms/assistant/protocol/openid-connect/certs")
    global _JWKS
    _JWKS = await fetch_jwks(jwks_url)

def verify_jwt(token: str) -> Dict[str, Any]:
    # Decode header to get kid
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    key_dict = get_key(kid)
    public_key = jwt.construct_rsa_key(key_dict)
    # Verify
    decoded = jwt.decode(
        token,
        public_key,
        algorithms=[key_dict["alg"]],
        audience=os.getenv("KEYCLOAK_CLIENT_ID", "backend-service"),
        issuer=os.getenv("KEYCLOAK_ISSUER", "http://keycloak:8080/realms/assistant"),
    )
    return decoded
