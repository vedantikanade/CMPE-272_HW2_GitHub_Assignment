# Authored by Vedanti Kanade
# Written by: [Your Name] - SJSU CMPE-272
import json
import logging
import sqlite3
from typing import Optional, List, Literal
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Header, Query, Response, status
from pydantic import BaseModel, Field

from config import settings
from database import init_db, is_duplicate_delivery, save_webhook_event, get_recent_events, DB_FILE
from security import verify_github_signature
import github_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("issues-gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("SQLite Webhook DB Initialized successfully.")
    yield

app = FastAPI(
    title="GitHub Issues Gateway API",
    version="1.0.0",
    description="API Gateway proxying GitHub Issues CRUD and processing Webhooks",
    lifespan=lifespan
)

# Request Models
class IssueCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, description="Issue title is required")
    body: Optional[str] = None
    labels: Optional[List[str]] = None

class IssueUpdateSchema(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    body: Optional[str] = None
    state: Optional[Literal["open", "closed"]] = None

class CommentCreateSchema(BaseModel):
    body: str = Field(..., min_length=1, description="Comment body is required")


# Health Check Endpoint
@app.get("/healthz", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint evaluating DB connectivity and service readiness."""
    db_status = "ok"
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("SELECT 1")
    except Exception as e:
        logger.error(f"Health check DB failure: {str(e)}")
        db_status = "unhealthy"
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connectivity degraded")

    return {
        "status": "ok",
        "database": db_status,
        "service": "GitHub Issues Gateway API"
    }


# Webhook Audit Trail Endpoint
@app.get("/events")
async def list_events(limit: int = Query(20, ge=1, le=100)):
    """Retrieves audit history of processed webhook events from SQLite."""
    events = get_recent_events(limit)
    return {"events": events}


# 1. POST /issues
@app.post("/issues", status_code=status.HTTP_201_CREATED)
async def create_issue(payload: IssueCreateSchema, response: Response):
    issue_data = await github_client.create_github_issue(
        title=payload.title,
        body=payload.body,
        labels=payload.labels
    )
    issue_number = issue_data["number"]
    response.headers["Location"] = f"/issues/{issue_number}"
    
    return {
        "number": issue_data["number"],
        "html_url": issue_data["html_url"],
        "state": issue_data["state"],
        "title": issue_data["title"],
        "body": issue_data.get("body"),
        "labels": [label["name"] for label in issue_data.get("labels", [])],
        "created_at": issue_data["created_at"],
        "updated_at": issue_data["updated_at"]
    }


# 2. GET /issues (with Pagination and Conditional ETag Extra Credit)
@app.get("/issues")
async def list_issues(
    response: Response,
    state: Literal["open", "closed", "all"] = "open",
    labels: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    if_none_match: Optional[str] = Header(None, alias="If-None-Match")
):
    status_code, data, headers = await github_client.list_github_issues(
        state=state,
        labels=labels,
        page=page,
        per_page=per_page,
        if_none_match=if_none_match
    )

    if status_code == 304:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    for key, value in headers.items():
        response.headers[key] = value

    return [
        {
            "number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "labels": [lbl["name"] for lbl in item.get("labels", [])],
            "html_url": item["html_url"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"]
        }
        for item in data
    ]


# 3. GET /issues/{number}
@app.get("/issues/{number}")
async def get_issue(number: int):
    issue_data = await github_client.get_github_issue(number)
    return {
        "number": issue_data["number"],
        "html_url": issue_data["html_url"],
        "state": issue_data["state"],
        "title": issue_data["title"],
        "body": issue_data.get("body"),
        "labels": [label["name"] for label in issue_data.get("labels", [])],
        "created_at": issue_data["created_at"],
        "updated_at": issue_data["updated_at"]
    }


# 4. PATCH /issues/{number}
@app.patch("/issues/{number}")
async def update_issue(number: int, payload: IssueUpdateSchema):
    if payload.title is None and payload.body is None and payload.state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (title, body, or state) must be provided for update."
        )

    issue_data = await github_client.update_github_issue(
        issue_number=number,
        title=payload.title,
        body=payload.body,
        state=payload.state
    )
    return {
        "number": issue_data["number"],
        "html_url": issue_data["html_url"],
        "state": issue_data["state"],
        "title": issue_data["title"],
        "body": issue_data.get("body"),
        "labels": [label["name"] for label in issue_data.get("labels", [])],
        "created_at": issue_data["created_at"],
        "updated_at": issue_data["updated_at"]
    }


# 5. POST /issues/{number}/comments
@app.post("/issues/{number}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(number: int, payload: CommentCreateSchema):
    comment_data = await github_client.create_github_comment(
        issue_number=number,
        body=payload.body
    )
    return {
        "id": comment_data["id"],
        "body": comment_data["body"],
        "user": comment_data["user"]["login"],
        "created_at": comment_data["created_at"],
        "html_url": comment_data["html_url"]
    }


# 6. POST /webhook
@app.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def handle_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: str = Header(None, alias="X-GitHub-Delivery")
):
    body = await request.body()

    if not x_hub_signature_256 or not verify_github_signature(body, settings.WEBHOOK_SECRET, x_hub_signature_256):
        logger.warning("Webhook rejected: Invalid signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature")

    if x_github_event not in ["issues", "issue_comment", "ping"]:
        logger.warning(f"Webhook rejected: Unsupported event '{x_github_event}'")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported event: {x_github_event}")

    if x_github_event == "ping":
        logger.info("GitHub ping event verified successfully.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if x_github_delivery and is_duplicate_delivery(x_github_delivery):
        logger.info(f"Duplicate delivery ignored: {x_github_delivery}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    payload = json.loads(body.decode("utf-8"))
    action = payload.get("action")
    issue_number = payload.get("issue", {}).get("number") if "issue" in payload else None

    save_webhook_event(
        delivery_id=x_github_delivery or "unknown",
        event=x_github_event,
        action=action,
        issue_number=issue_number,
        payload=json.dumps(payload)
    )

    logger.info(f"Saved Webhook Event: {x_github_event} | Action: {action} | Issue: #{issue_number}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)