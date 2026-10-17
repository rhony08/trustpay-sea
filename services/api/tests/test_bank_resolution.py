"""Country-optional bank resolution."""

import httpx


async def test_account_lookup_without_country(client: httpx.AsyncClient) -> None:
    # "014" (BCA) is unique across the directory → resolves without a country.
    resp = await client.get(
        "/api/v1/entities/account", params={"bank": "014", "account": "8830192831"}
    )
    assert resp.status_code == 200, resp.text


async def test_ambiguous_bank_requires_country(client: httpx.AsyncClient) -> None:
    # "MB" exists in both PH and VN → must be disambiguated.
    resp = await client.get(
        "/api/v1/entities/account", params={"bank": "MB", "account": "1234567890"}
    )
    assert resp.status_code == 400
    assert "multiple countries" in resp.json()["detail"]


async def test_unknown_bank_without_country(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/entities/account", params={"bank": "NOPE", "account": "1234567890"}
    )
    assert resp.status_code == 400
