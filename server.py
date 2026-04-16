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
    fact_id: Optional[str] = None
) -> dict:
    """Retrieve cat facts from the Cat Facts API. Use this to fetch random cat facts, browse available facts, or get a specific fact by ID. Supports filtering by animal type and pagination."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        if fact_id:
            response = await client.get(f"{BASE_URL}/facts/{fact_id}")
            if response.status_code == 200:
                return {"success": True, "fact": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}
        else:
            params = {
                "animal_type": animal_type or "cat",
                "amount": max(1, min(500, amount or 1))
            }
            response = await client.get(f"{BASE_URL}/facts/random", params=params)
            if response.status_code == 200:
                data = response.json()
                # API returns single object when amount=1, list when amount>1
                if isinstance(data, list):
                    return {"success": True, "facts": data, "count": len(data)}
                else:
                    return {"success": True, "facts": [data], "count": 1}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def submit_fact(
    text: str,
    animal_type: Optional[str] = "cat",
    source: Optional[str] = None
) -> dict:
    """Submit a new cat (or other animal) fact to the Cat Facts database for review. Use this when a user wants to contribute their own interesting animal fact to the community."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "text": text,
            "type": animal_type or "cat"
        }
        if source:
            payload["source"] = source

        response = await client.post(f"{BASE_URL}/facts", json=payload)
        if response.status_code in (200, 201):
            return {"success": True, "message": "Fact submitted successfully for review.", "data": response.json()}
        else:
            return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def manage_recipients(
    action: str,
    phone_number: Optional[str] = None,
    name: Optional[str] = None,
    recipient_id: Optional[str] = None
) -> dict:
    """Add, view, update, or remove recipients who will receive daily cat facts via SMS. Use this when a user wants to manage their list of prank targets or friends to send cat facts to. Actions: 'list', 'add', 'update', 'delete'."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        action = action.lower().strip()

        if action == "list":
            response = await client.get(f"{BASE_URL}/users/me/recipients")
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "recipients": data}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "add":
            if not phone_number:
                return {"success": False, "error": "phone_number is required for 'add' action."}
            # Clean the phone number
            cleaned = "".join(filter(str.isdigit, phone_number)).lstrip("1")
            if len(cleaned) not in (10, 11):
                return {"success": False, "error": f"Invalid phone number length after cleaning: '{cleaned}'. Must be 10 or 11 digits."}
            payload = {"phoneNumber": cleaned}
            if name:
                payload["name"] = name
            response = await client.post(f"{BASE_URL}/users/me/recipients", json=payload)
            if response.status_code in (200, 201):
                return {"success": True, "message": "Recipient added successfully.", "data": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "update":
            if not recipient_id:
                return {"success": False, "error": "recipient_id is required for 'update' action."}
            payload = {}
            if phone_number:
                cleaned = "".join(filter(str.isdigit, phone_number)).lstrip("1")
                payload["phoneNumber"] = cleaned
            if name:
                payload["name"] = name
            if not payload:
                return {"success": False, "error": "At least one of phone_number or name must be provided for update."}
            response = await client.put(f"{BASE_URL}/users/me/recipients/{recipient_id}", json=payload)
            if response.status_code == 200:
                return {"success": True, "message": "Recipient updated successfully.", "data": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "delete":
            if not recipient_id:
                return {"success": False, "error": "recipient_id is required for 'delete' action."}
            response = await client.delete(f"{BASE_URL}/users/me/recipients/{recipient_id}")
            if response.status_code in (200, 204):
                return {"success": True, "message": f"Recipient '{recipient_id}' deleted successfully."}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        else:
            return {"success": False, "error": f"Unknown action '{action}'. Valid actions: 'list', 'add', 'update', 'delete'."}


@mcp.tool()
async def send_fact(
    recipient_id: Optional[str] = None,
    fact_id: Optional[str] = None
) -> dict:
    """Manually trigger sending a cat fact via SMS to one or all recipients. Use this when a user wants to send a fact immediately rather than waiting for the daily scheduled message."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {}
        if fact_id:
            payload["factId"] = fact_id

        if recipient_id:
            url = f"{BASE_URL}/users/me/recipients/{recipient_id}/send"
        else:
            url = f"{BASE_URL}/users/me/recipients/send"

        response = await client.post(url, json=payload)
        if response.status_code in (200, 201):
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text}
            return {"success": True, "message": "Fact sent successfully.", "data": data}
        else:
            return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def get_conversation(
    recipient_id: str,
    limit: Optional[int] = 20,
    page: Optional[int] = 1
) -> dict:
    """Retrieve the SMS conversation history (catversation) between the Catbot and a specific recipient. Use this to review what messages have been exchanged with a recipient."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {
            "limit": limit or 20,
            "page": page or 1
        }
        response = await client.get(
            f"{BASE_URL}/users/me/recipients/{recipient_id}/catversation",
            params=params
        )
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "conversation": data, "recipient_id": recipient_id}
        else:
            return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def authenticate_user(
    action: str,
    email: Optional[str] = None,
    password: Optional[str] = None
) -> dict:
    """Handle user authentication including login, logout, and Google OAuth. Use this when a user needs to sign in, sign out, or connect their Google account to import contacts. Actions: 'login', 'logout', 'google_oauth', 'get_current_user'."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        action = action.lower().strip()

        if action == "login":
            if not email or not password:
                return {"success": False, "error": "Both email and password are required for login."}
            payload = {"email": email, "password": password}
            response = await client.post(f"{BASE_URL}/auth/local", json=payload)
            if response.status_code == 200:
                return {"success": True, "message": "Login successful.", "data": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "logout":
            response = await client.get(f"{BASE_URL}/auth/logout")
            if response.status_code == 200:
                return {"success": True, "message": "Logout successful."}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "google_oauth":
            oauth_url = f"{BASE_URL}/auth/google"
            return {
                "success": True,
                "message": "To authenticate with Google, please visit the following URL in your browser.",
                "oauth_url": oauth_url
            }

        elif action == "get_current_user":
            response = await client.get(f"{BASE_URL}/users/me")
            if response.status_code == 200:
                return {"success": True, "user": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        else:
            return {"success": False, "error": f"Unknown action '{action}'. Valid actions: 'login', 'logout', 'google_oauth', 'get_current_user'."}


@mcp.tool()
async def import_google_contacts(
    oauth_token: str,
    filter_has_phone: Optional[bool] = True
) -> dict:
    """Import contacts from a user's Google account to bulk-add recipients for cat facts. Use this when a user wants to add multiple recipients at once from their Google Contacts."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {oauth_token}"}
        params = {}
        if filter_has_phone is not None:
            params["filterHasPhone"] = str(filter_has_phone).lower()

        response = await client.get(
            f"{BASE_URL}/users/me/contacts/google",
            headers=headers,
            params=params
        )
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "message": "Google contacts imported successfully.", "data": data}
        else:
            return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def manage_unsubscribe(
    action: str,
    phone_number: str
) -> dict:
    """Check, add, or remove unsubscribe records for recipients who have opted out of receiving cat facts. Use this to respect opt-out requests or re-enable a recipient who wants to re-subscribe. Actions: 'check', 'unsubscribe', 'resubscribe'."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        action = action.lower().strip()
        # Clean the phone number
        cleaned = "".join(filter(str.isdigit, phone_number)).lstrip("1")

        if not cleaned or len(cleaned) not in (10, 11):
            return {"success": False, "error": f"Invalid phone number '{phone_number}'. Must be 10 or 11 digits after cleaning."}

        if action == "check":
            response = await client.get(f"{BASE_URL}/unsubscribe/{cleaned}")
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "phone_number": cleaned, "unsubscribed": data.get("unsubscribed", False), "data": data}
            elif response.status_code == 404:
                return {"success": True, "phone_number": cleaned, "unsubscribed": False, "message": "Phone number is not on the unsubscribe list."}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "unsubscribe":
            payload = {"phoneNumber": cleaned}
            response = await client.post(f"{BASE_URL}/unsubscribe", json=payload)
            if response.status_code in (200, 201):
                return {"success": True, "message": f"Phone number {cleaned} has been unsubscribed from cat facts.", "data": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "resubscribe":
            response = await client.delete(f"{BASE_URL}/unsubscribe/{cleaned}")
            if response.status_code in (200, 204):
                return {"success": True, "message": f"Phone number {cleaned} has been resubscribed and will receive cat facts again."}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        else:
            return {"success": False, "error": f"Unknown action '{action}'. Valid actions: 'check', 'unsubscribe', 'resubscribe'."}




async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http", stateless_http=True)

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
