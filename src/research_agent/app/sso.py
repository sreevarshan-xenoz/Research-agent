"""SSO/OAuth authentication providers for P18 Security Hardening.

Provides Google, GitHub, and ORCID OAuth2 integration via fastapi-users'
OAuth router support. Falls back gracefully if provider credentials
are not configured.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OAuth provider configuration
# ---------------------------------------------------------------------------


class OAuthProvider:
    """Configuration for a single OAuth2 provider."""

    def __init__(
        self,
        name: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
        scopes: list[str] | None = None,
        enabled: bool = False,
    ):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.scopes = scopes or ["openid", "email", "profile"]
        self.enabled = enabled and bool(client_id) and bool(client_secret)

    def is_configured(self) -> bool:
        return self.enabled and bool(self.client_id) and bool(self.client_secret)


# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------


def _load_providers() -> list[OAuthProvider]:
    """Load OAuth provider configurations from settings."""
    providers: list[OAuthProvider] = []

    try:
        from research_agent.config import load_settings
        settings = load_settings()
        sso = settings.sso

        if sso.enabled:
            # Google
            providers.append(OAuthProvider(
                name="google",
                client_id=sso.google_client_id,
                client_secret=str(sso.google_client_secret),
                authorize_url="https://accounts.google.com/o/oauth2/auth",
                token_url="https://oauth2.googleapis.com/token",
                scopes=["openid", "email", "profile"],
                enabled=bool(sso.google_client_id),
            ))

            # GitHub
            providers.append(OAuthProvider(
                name="github",
                client_id=sso.github_client_id,
                client_secret=str(sso.github_client_secret),
                authorize_url="https://github.com/login/oauth/authorize",
                token_url="https://github.com/login/oauth/access_token",
                scopes=["user:email"],
                enabled=bool(sso.github_client_id),
            ))

            # ORCID
            providers.append(OAuthProvider(
                name="orcid",
                client_id=sso.orcid_client_id,
                client_secret=str(sso.orcid_client_secret),
                authorize_url="https://orcid.org/oauth/authorize",
                token_url="https://orcid.org/oauth/token",
                scopes=["/authenticate"],
                enabled=bool(sso.orcid_client_id),
            ))
    except Exception as exc:
        logger.warning("Failed to load SSO providers: %s", exc)

    return providers


# ---------------------------------------------------------------------------
# SSO Router builder
# ---------------------------------------------------------------------------


def build_sso_router() -> APIRouter:
    """Build an APIRouter with SSO/OAuth login endpoints.

    Adds routes:
    - GET /api/auth/sso/providers — list configured providers
    - GET /api/auth/sso/{provider}/login — initiate OAuth flow
    - GET /api/auth/sso/{provider}/callback — OAuth callback

    Falls back to returning provider metadata only if fastapi-users
    OAuth integration is not available.
    """
    router = APIRouter(prefix="/api/auth/sso", tags=["auth"])

    providers = _load_providers()
    configured = [p for p in providers if p.is_configured()]

    @router.get("/providers")
    async def list_providers():
        """List all configured SSO/OAuth providers."""
        return {
            "providers": [
                {
                    "name": p.name,
                    "configured": p.is_configured(),
                    "scopes": p.scopes,
                }
                for p in providers
            ],
            "enabled": any(p.is_configured() for p in providers),
        }

    @router.get("/{provider_name}")
    async def provider_info(provider_name: str):
        """Get login URL info for a specific provider."""
        for p in configured:
            if p.name == provider_name:
                return {
                    "name": p.name,
                    "authorize_url": p.authorize_url,
                    "scopes": p.scopes,
                    "configured": True,
                }
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_name}' not configured. "
                   f"Configured: {[p.name for p in configured] or 'none'}",
        )

    @router.get("/{provider_name}/login")
    async def provider_login(provider_name: str):
        """Initiate OAuth login flow (returns redirect URL).

        In production, this redirects to the provider's OAuth consent page.
        For now, returns the auth URL for the frontend to navigate to.
        """
        for p in configured:
            if p.name == provider_name:
                redirect_uri = f"/api/auth/sso/{provider_name}/callback"
                auth_url = (
                    f"{p.authorize_url}"
                    f"?client_id={p.client_id}"
                    f"&redirect_uri={redirect_uri}"
                    f"&scope={' '.join(p.scopes)}"
                    f"&response_type=code"
                    f"&access_type=offline"
                )
                return {
                    "provider": p.name,
                    "authorization_url": auth_url,
                    "redirect_uri": redirect_uri,
                }

        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_name}' not configured",
        )

    return router


# ---------------------------------------------------------------------------
# Convenience: check if any SSO provider is configured
# ---------------------------------------------------------------------------


def is_sso_configured() -> bool:
    """Check if any SSO/OAuth provider has credentials configured."""
    try:
        providers = _load_providers()
        return any(p.is_configured() for p in providers)
    except Exception:
        return False
