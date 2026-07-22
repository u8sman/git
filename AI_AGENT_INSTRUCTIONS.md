# Instructions for an AI coding agent

This repository runs a gateway that accepts completed code changes and commits them directly to GitHub.

1. Obtain the gateway base URL and a revocable agent token from the user.
2. Call `GET <base-url>/projects` with `Authorization: Bearer <token>`.
3. Complete and verify the requested code before delivery.
4. Call `POST <base-url>/push` with the project slug, branch, commit message, and every changed/deleted file.
5. Use `content` for UTF-8 files, `content_base64` for binary files, and `delete: true` for deletions.
6. Include `expected_head` when you know the original branch commit.
7. Never expose the token in output, files, logs, or commits.
8. Return the API's `commit_url` to the user.
9. Remind the user to revoke the agent token when the work is finished.

The live server also exposes public machine-readable instructions at `/api/v1/instructions`.
