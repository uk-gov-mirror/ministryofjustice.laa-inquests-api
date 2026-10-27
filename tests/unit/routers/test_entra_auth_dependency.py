import asyncio
from unittest.mock import MagicMock

from fastapi.security import HTTPAuthorizationCredentials

from app.contexts.user import (
    get_entra_user_email_address,
    get_entra_user_name,
    get_entra_user_object_id,
)
from app.ports.entra_auth_port import AuthenticatedUser
from app.routers.dependencies.entra_auth import verify_entra_caseworker_token


def test_verified_user_is_recorded_in_the_request_user_context():
    entra_auth = MagicMock()
    entra_auth.verify_token.return_value = AuthenticatedUser(
        firm_code=None,
        scopes=frozenset({"User.Caseworker"}),
        name="Test Name",
        entra_object_id="entra-object-id",
        email_address="caseworker@example.com",
    )

    async def verify_and_read_context():
        await verify_entra_caseworker_token(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            entra_auth,
        )
        return (
            get_entra_user_object_id(),
            get_entra_user_name(),
            get_entra_user_email_address(),
        )

    # Context variables set inside asyncio.run do not leak into this test's context.
    assert asyncio.run(verify_and_read_context()) == (
        "entra-object-id",
        "Test Name",
        "caseworker@example.com",
    )
