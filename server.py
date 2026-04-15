from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
from fastmcp import FastMCP
import httpx
import os
from typing import Optional

mcp = FastMCP("Cat Facts API")

BASE_URL = "https://cat-fact.herokuapp.com"


@mcp.tool()
async def get_facts(
    animal_type: Optional[str] = "cat",
    amount: Optional[int] = 1,
    status: Optional[str] = "verified"
) -> dict:
    """Retrieve cat facts from the Cat Facts API. Use this when the user wants to browse, search, or get a random cat fact. Supports filtering by animal type, status, and pagination."""
    params = {}
    if animal_type:
        params["animal_type"] = animal_type
    if amount is not None:
        params["amount"] = amount
    if status and status != "all":
        params["status"] = status

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/facts", params=params)
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "facts": data,
                "count": len(data) if isinstance(data, list) else 1
            }
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool()
async def submit_fact(
    text: str,
    animal_type: Optional[str] = "cat",
    source: Optional[str] = None
) -> dict:
    """Submit a new cat (or other animal) fact to the Cat Facts database for review. Use this when a user wants to contribute their own interesting animal fact."""
    payload = {
        "text": text,
        "type": animal_type or "cat"
    }
    if source:
        payload["source"] = source

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(f"{BASE_URL}/facts", json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "message": "Fact submitted successfully for review.",
                "fact": data
            }
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool()
async def manage_recipients(
    action: str,
    phone_number: Optional[str] = None,
    name: Optional[str] = None
) -> dict:
    """Add, list, or remove phone number recipients who will receive daily cat facts via SMS. Use this when the user wants to manage who gets cat facts sent to them. Actions: 'list', 'add', 'remove'."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            if action == "list":
                response = await client.get(f"{BASE_URL}/users")
                response.raise_for_status()
                data = response.json()
                return {"success": True, "recipients": data}

            elif action == "add":
                if not phone_number:
                    return {"success": False, "error": "phone_number is required for 'add' action."}
                # Clean phone number
                cleaned = "".join(filter(str.isdigit, phone_number)).lstrip("1")
                if len(cleaned) not in (10, 11):
                    return {"success": False, "error": "Invalid phone number. Must be 10 or 11 digits."}
                payload = {"phoneNumber": cleaned}
                if name:
                    payload["name"] = name
                response = await client.post(f"{BASE_URL}/users", json=payload)
                response.raise_for_status()
                data = response.json()
                return {"success": True, "message": "Recipient added successfully.", "recipient": data}

            elif action == "remove":
                if not phone_number:
                    return {"success": False, "error": "phone_number is required for 'remove' action."}
                cleaned = "".join(filter(str.isdigit, phone_number)).lstrip("1")
                response = await client.delete(f"{BASE_URL}/users/{cleaned}")
                response.raise_for_status()
                return {"success": True, "message": f"Recipient with phone number {cleaned} removed successfully."}

            else:
                return {"success": False, "error": f"Unknown action '{action}'. Use 'list', 'add', or 'remove'."}

        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool()
async def send_fact(
    recipient_id: Optional[str] = None,
    fact_id: Optional[str] = None
) -> dict:
    """Manually send a cat fact via SMS to one or all recipients immediately, outside of the daily scheduled send. Use this when the user wants to send a fact right now."""
    payload = {}
    if recipient_id:
        payload["recipient"] = recipient_id
    if fact_id:
        payload["factId"] = fact_id

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(f"{BASE_URL}/facts/send", json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "message": "Cat fact sent successfully.",
                "details": data
            }
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool()
async def get_conversation(
    recipient_id: Optional[str] = None,
    limit: Optional[int] = 20,
    page: Optional[int] = 1
) -> dict:
    """Retrieve the catversation (SMS conversation history) between Catbot and a specific recipient. Use this to review what messages have been exchanged."""
    params = {}
    if limit:
        params["limit"] = limit
    if page:
        params["page"] = page

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            if recipient_id:
                url = f"{BASE_URL}/users/{recipient_id}/conversation"
            else:
                url = f"{BASE_URL}/conversation"

            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "conversation": data,
                "recipient_id": recipient_id
            }
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool()
async def auth_google(
    action: str
) -> dict:
    """Initiate Google OAuth authentication or handle Google Contacts import. Use this when the user wants to log in via Google or import their Google contacts as cat facts recipients. Actions: 'login', 'import_contacts'."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            if action == "login":
                response = await client.get(f"{BASE_URL}/auth/google")
                # This endpoint likely returns a redirect; capture the URL
                return {
                    "success": True,
                    "message": "Google OAuth login initiated. Please visit the URL to authenticate.",
                    "auth_url": f"{BASE_URL}/auth/google",
                    "status_code": response.status_code
                }
            elif action == "import_contacts":
                response = await client.get(f"{BASE_URL}/auth/google/contacts")
                return {
                    "success": True,
                    "message": "Google Contacts import initiated. Please visit the URL to authorize contact access.",
                    "auth_url": f"{BASE_URL}/auth/google/contacts",
                    "status_code": response.status_code
                }
            else:
                return {"success": False, "error": f"Unknown action '{action}'. Use 'login' or 'import_contacts'."}
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            # Redirects may raise exceptions; provide helpful info
            return {
                "success": True,
                "message": f"Auth endpoint reached. Action: {action}. Note: This endpoint may require browser-based interaction.",
                "auth_url": f"{BASE_URL}/auth/google" if action == "login" else f"{BASE_URL}/auth/google/contacts"
            }


@mcp.tool()
async def get_api_logs(
    limit: Optional[int] = 50,
    page: Optional[int] = 1,
    endpoint: Optional[str] = None
) -> dict:
    """Retrieve API usage logs for monitoring and admin purposes. Use this when an admin wants to inspect recent API activity, diagnose issues, or audit usage."""
    params = {}
    if limit:
        params["limit"] = limit
    if page:
        params["page"] = page
    if endpoint:
        params["endpoint"] = endpoint

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/admin/logs", params=params)
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "logs": data,
                "page": page,
                "limit": limit
            }
        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


@mcp.tool()
async def manage_unsubscribe(
    action: str,
    phone_number: Optional[str] = None
) -> dict:
    """Handle unsubscribe requests from recipients who no longer want to receive cat facts. Use this when a recipient wants to opt out or when checking unsubscribe history. Actions: 'unsubscribe', 'list'."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            if action == "list":
                response = await client.get(f"{BASE_URL}/unsubscribe")
                response.raise_for_status()
                data = response.json()
                return {"success": True, "unsubscribed": data}

            elif action == "unsubscribe":
                if not phone_number:
                    return {"success": False, "error": "phone_number is required for 'unsubscribe' action."}
                cleaned = "".join(filter(str.isdigit, phone_number)).lstrip("1")
                if len(cleaned) not in (10, 11):
                    return {"success": False, "error": "Invalid phone number. Must be 10 or 11 digits."}
                response = await client.post(f"{BASE_URL}/unsubscribe", json={"phoneNumber": cleaned})
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "message": f"Phone number {cleaned} has been unsubscribed from cat facts.",
                    "details": data
                }
            else:
                return {"success": False, "error": f"Unknown action '{action}'. Use 'unsubscribe' or 'list'."}

        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}




async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http")

class _FixAcceptHeader:
    """Ensure Accept header includes both types FastMCP requires."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            accept = headers.get(b"accept", b"").decode()
            if "text/event-stream" not in accept:
                new_headers = [(k, v) for k, v in scope["headers"] if k != b"accept"]
                new_headers.append((b"accept", b"application/json, text/event-stream"))
                scope = dict(scope, headers=new_headers)
        await self.app(scope, receive, send)

app = _FixAcceptHeader(Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", mcp_app),
    ],
    lifespan=mcp_app.lifespan,
))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
