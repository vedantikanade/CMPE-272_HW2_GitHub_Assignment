# Authored by Vedanti Kanade
# Written by: [Your Name] - SJSU CMPE-272
import httpx
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from config import settings

BASE_URL = f"https://api.github.com/repos/{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}"

def get_headers(if_none_match: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if if_none_match:
        headers["If-None-Match"] = if_none_match
    return headers

def handle_github_error(response: httpx.Response):
    """Maps GitHub API error responses to client-facing HTTP exceptions."""
    if response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub Authentication failed: Invalid or expired GITHUB_TOKEN."
        )
    elif response.status_code == 403:
        # Check for rate limiting
        if "rate limit exceeded" in response.text.lower():
            retry_after = response.headers.get("Retry-After", "60")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="GitHub API rate limit exceeded.",
                headers={"Retry-After": retry_after}
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"GitHub permission denied: {response.json().get('message', 'Forbidden')}"
        )
    elif response.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub resource or repository not found."
        )
    elif response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream GitHub service error."
        )
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.json().get("message", "GitHub API request failed.")
        )

async def create_github_issue(title: str, body: Optional[str] = None, labels: Optional[list] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}/issues"
    payload = {"title": title}
    if body:
        payload["body"] = body
    if labels:
        payload["labels"] = labels

    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload, headers=get_headers())
        if res.status_code != 201:
            handle_github_error(res)
        return res.json()

async def list_github_issues(
    state: str = "open",
    labels: Optional[str] = None,
    page: int = 1,
    per_page: int = 30,
    if_none_match: Optional[str] = None
) -> Tuple[int, Any, Dict[str, str]]:
    url = f"{BASE_URL}/issues"
    params = {"state": state, "page": page, "per_page": min(per_page, 100)}
    if labels:
        params["labels"] = labels

    async with httpx.AsyncClient() as client:
        res = await client.get(url, params=params, headers=get_headers(if_none_match))
        
        # ETag Extra Credit handling
        if res.status_code == 304:
            return 304, None, {}

        if res.status_code != 200:
            handle_github_error(res)

        out_headers = {}
        if "Link" in res.headers:
            out_headers["Link"] = res.headers["Link"]
        if "ETag" in res.headers:
            out_headers["ETag"] = res.headers["ETag"]

        return 200, res.json(), out_headers

async def get_github_issue(issue_number: int) -> Dict[str, Any]:
    url = f"{BASE_URL}/issues/{issue_number}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=get_headers())
        if res.status_code != 200:
            handle_github_error(res)
        return res.json()

async def update_github_issue(
    issue_number: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    state: Optional[str] = None
) -> Dict[str, Any]:
    url = f"{BASE_URL}/issues/{issue_number}"
    payload = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if state is not None:
        payload["state"] = state

    async with httpx.AsyncClient() as client:
        res = await client.patch(url, json=payload, headers=get_headers())
        if res.status_code != 200:
            handle_github_error(res)
        return res.json()

async def create_github_comment(issue_number: int, body: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/issues/{issue_number}/comments"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json={"body": body}, headers=get_headers())
        if res.status_code != 201:
            handle_github_error(res)
        return res.json()