"""Synthetic in-process 50-rps application capacity drill; no cloud/production benchmark."""

import argparse
import json
import math
import os
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, insert
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from safer.config import Settings
from safer.main import create_app
from safer.models import Institution, Instrument, Obligation, User
from safer.security import issue_session

ROOT = Path(__file__).resolve().parents[3]


def summarize(samples: list[dict], target_rps: int) -> dict:
    if not samples:
        return {"latency_gate": "incomplete", "server_errors": 0, "reads": {}, "writes": {}}
    groups = {}
    for name, method in [("reads", "GET"), ("writes", "POST")]:
        data = [
            s["server_ms"] for s in samples if s["method"] == method and s["server_ms"] is not None
        ]
        groups[name] = {
            "samples": len(data),
            "p95_ms": sorted(data)[math.ceil(len(data) * 0.95) - 1] if data else None,
        }
    errors = sum(s["status"] >= 500 or s["status"] == 0 for s in samples)
    invalid = sum(s["status"] not in {200, 201} for s in samples)
    complete = all(groups[g]["samples"] for g in groups) and all(
        s["server_ms"] is not None for s in samples
    )
    good = (
        complete
        and groups["reads"]["p95_ms"] <= 500
        and groups["writes"]["p95_ms"] <= 1000
        and errors / len(samples) < 0.01
        and invalid == 0
    )
    first, last = min(s["started"] for s in samples), max(s["started"] for s in samples)
    return {
        "latency_gate": "pass" if good else "fail" if complete else "incomplete",
        "scheduled_rps": target_rps,
        "arrival_rps": (len(samples) - 1) / (last - first) if last > first else None,
        "server_errors": errors,
        "unexpected_statuses": invalid,
        "requests": len(samples),
        **groups,
    }


def run(seconds: int) -> dict:
    if not 10 <= seconds <= 120:
        raise ValueError("Local benchmark duration must be 10 to 120 seconds")
    source = make_url(dotenv_values(ROOT / ".env")["DATABASE_URL"])
    target = "safer_capacity_synthetic_" + uuid.uuid4().hex[:12]
    with psycopg.connect(
        source.set(drivername="postgresql", database="postgres").render_as_string(
            hide_password=False
        ),
        autocommit=True,
    ) as db:
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    url = source.set(database=target)
    env = os.environ | {"DATABASE_URL": url.render_as_string(hide_password=False)}
    with (ROOT / ".local/saf030-migration.log").open("w") as log:
        subprocess.run(
            [str(ROOT / ".venv/bin/alembic"), "upgrade", "head"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=60,
        )
    engine = create_engine(url, hide_parameters=True)
    institution_ids = [uuid.uuid4() for _ in range(10000)]
    obligation_ids = [uuid.uuid4() for _ in institution_ids]
    ids = [uuid.uuid4() for _ in range(100000)]
    user_ids = [uuid.uuid4() for _ in institution_ids]
    with Session(engine) as db:
        db.execute(
            insert(Institution),
            [
                {"id": id, "name": f"Synthetic Capacity Institute {i:05d}"}
                for i, id in enumerate(institution_ids)
            ],
        )
        db.execute(
            insert(Obligation),
            [
                {
                    "id": id,
                    "institution_id": institution_ids[i],
                    "title": "Synthetic capacity obligation",
                    "required_amount": Decimal("1000000.00"),
                    "required_documents": [],
                }
                for i, id in enumerate(obligation_ids)
            ],
        )
        db.execute(
            insert(User),
            [
                {
                    "id": user_ids[i],
                    "issuer": "http://localhost:8090/realms/safer",
                    "subject": f"synthetic-capacity-{i}",
                    "display_name": f"Synthetic capacity actor {i}",
                    "email": f"synthetic-{i}@example.invalid",
                    "institution_id": institution_ids[i],
                    "role": "institution_user",
                }
                for i in range(10000)
            ],
        )
        for start in range(0, 100000, 1000):
            db.execute(
                insert(Instrument),
                [
                    {
                        "id": ids[i],
                        "created_by": user_ids[i // 10],
                        "institution_id": institution_ids[i // 10],
                        "obligation_id": obligation_ids[i // 10],
                        "bank_name": "Synthetic Capacity Bank",
                        "bank_reference": f"SYNTHETIC-{i:09d}",
                        "principal_amount": Decimal("1234.56"),
                        "issue_date": date(2026, 1, 1),
                        "maturity_date": date(2028, 1, 1),
                        "status": "draft",
                    }
                    for i in range(start, start + 1000)
                ],
            )
        user = db.get(User, user_ids[0])
        token, csrf = issue_session(db, user)
        db.commit()
    settings = Settings(database_url=url.render_as_string(hide_password=False))
    app = create_app(settings)
    samples = []
    with TestClient(app) as client:
        client.cookies.set("safer_session", token)
        client.headers.update({"Origin": settings.app_origin, "X-CSRF-Token": csrf})
        assert client.get("/api/v1/instruments").status_code == 200

        def request(index):
            started = time.monotonic()
            method = "POST" if index % 5 == 0 else "GET"
            before = time.perf_counter()
            try:
                if method == "POST":
                    response = client.post(
                        "/api/v1/instruments",
                        json={
                            "obligation_id": str(obligation_ids[0]),
                            "bank_name": "Synthetic Capacity Bank",
                            "bank_reference": f"SYNTHETIC-WRITE-{index}-{target[-12:]}",
                            "principal_amount": "1234.56",
                            "currency": "INR",
                            "issue_date": "2026-01-01",
                            "maturity_date": "2028-01-01",
                        },
                    )
                else:
                    response = client.get(
                        "/api/v1/instruments"
                        if index % 2
                        else f"/api/v1/instruments/{ids[index % 10]}"
                    )
                header = response.headers.get("server-timing", "")
                duration = float(header.split("=", 1)[1]) if header.startswith("app;dur=") else None
                return {
                    "method": method,
                    "status": response.status_code,
                    "server_ms": duration,
                    "client_ms": (time.perf_counter() - before) * 1000,
                    "started": started,
                }
            except (OSError, ValueError):
                return {
                    "method": method,
                    "status": 0,
                    "server_ms": None,
                    "client_ms": (time.perf_counter() - before) * 1000,
                    "started": started,
                }

        begin = time.monotonic()
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = []
            for index in range(seconds * 50):
                wait = begin + index / 50 - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                futures.append(pool.submit(request, index))
            samples = [future.result() for future in futures]
        elapsed = time.monotonic() - begin
    engine.dispose()
    result = summarize(samples, 50)
    return {
        "phase": "SAF-030",
        "classification": "synthetic_only",
        "status": result["latency_gate"],
        "database": target,
        "workload": {
            "institutions": 10000,
            "initial_instruments": 100000,
            "duration_seconds": seconds,
            "read_percent": 80,
            "write_percent": 20,
            "scope": "one institution with 10 preloaded instruments; all 100k rows/indexes present",
        },
        "elapsed_seconds": elapsed,
        "completion_rps": len(samples) / elapsed,
        "metrics": result,
        "transport": "in-process ASGI, real PostgreSQL; header duration excludes network and body transfer",
        "pilot_status": "blocked",
        "limitations": [
            "Not a whole-portfolio dashboard/reviewer workload or infrastructure capacity certification.",
            "OIDC login, TLS/network, file transfer, scanning, background queues and bank/model providers excluded.",
            "Upstream DDoS/origin controls require final hosting platform.",
            "No real institution data; scratch database preserved for inspection.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=20)
    args = parser.parse_args()
    result = run(args.seconds)
    (ROOT / ".local/saf030-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Local capacity latency gate: {result['status']}; pilot remains blocked.")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
