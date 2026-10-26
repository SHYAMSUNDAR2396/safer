"""Selectors for explicitly labelled, local synthetic test-owned credentials."""


def owned_test_credentials(rows: list[dict]) -> list[str]:
    return [
        row["id"]
        for row in rows
        if row.get("type") == "otp"
        and row.get("userLabel") == "Synthetic test authenticator"
        and isinstance(row.get("id"), str)
    ]
