#!/usr/bin/env python3
"""Push a local directory's files through AI Git Gateway.

Example:
  AI_GIT_TOKEN=aig_... python cli/ai_push.py \
    --gateway http://localhost:8000/api/v1 \
    --project my-project --branch main --message "Finish feature" \
    src/app.py templates/page.html
"""
import argparse
import base64
import mimetypes
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--message", required=True)
    parser.add_argument("--token", default=os.getenv("AI_GIT_TOKEN"))
    parser.add_argument("--delete", action="append", default=[])
    args = parser.parse_args()
    if not args.token:
        parser.error("Set AI_GIT_TOKEN or pass --token")

    changes = []
    for filename in args.files:
        path = Path(filename)
        data = path.read_bytes()
        mime, _ = mimetypes.guess_type(path.name)
        text_mimes = {"application/json", "application/javascript", "application/xml"}
        if mime and (mime.startswith("text/") or mime in text_mimes):
            changes.append({"path": path.as_posix(), "content": data.decode("utf-8")})
        else:
            try:
                changes.append({"path": path.as_posix(), "content": data.decode("utf-8")})
            except UnicodeDecodeError:
                changes.append(
                    {
                        "path": path.as_posix(),
                        "content_base64": base64.b64encode(data).decode(),
                    }
                )
    changes.extend({"path": item, "delete": True} for item in args.delete)

    response = httpx.post(
        f"{args.gateway.rstrip('/')}/push",
        headers={"Authorization": f"Bearer {args.token}"},
        json={
            "project": args.project,
            "branch": args.branch,
            "commit_message": args.message,
            "files": changes,
        },
        timeout=120,
    )
    if response.is_error:
        raise SystemExit(f"Push failed ({response.status_code}): {response.text}")
    print(response.json()["commit_url"])


if __name__ == "__main__":
    main()
