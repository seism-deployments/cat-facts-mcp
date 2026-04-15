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
    """Retrieve cat facts from the Cat Facts API. Use this to fetch random facts, browse available facts, or get a specific fact by ID. This is the primary way to access the cat facts database."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        if fact_id:
            url = f"{BASE_URL}/facts/{fact_id}"
            response = await client.get(url)
            if response.status_code == 200:
                return {"success": True, "fact": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}
        else:
            url = f"{BASE_URL}/facts"
            params = {}
            if animal_type:
                params["animal_type"] = animal_type
            if amount:
                params["amount"] = amount
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "facts": data}
            else:
                # Try the /facts/random endpoint as fallback
                url_random = f"{BASE_URL}/facts/random"
                params_random = {}
                if animal_type:
                    params_random["animal_type"] = animal_type
                if amount:
                    params_random["amount"] = amount
                response2 = await client.get(url_random, params=params_random)
                if response2.status_code == 200:
                    return {"success": True, "facts": response2.json()}
                return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def submit_fact(
    text: str,
    animal_type: Optional[str] = "cat",
    source: Optional[str] = None
) -> dict:
    """Submit a new cat fact to the database for review and inclusion. Use this when a user wants to contribute their own interesting animal fact to the Cat Facts collection."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{BASE_URL}/facts"
        payload = {
            "text": text,
            "type": animal_type or "cat"
        }
        if source:
            payload["source"] = source
        response = await client.post(url, json=payload)
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
    """Add, view, update, or remove recipients who will receive daily cat fact text messages. Use this to manage the list of phone numbers subscribed to receive cat facts. Actions: 'list', 'add', 'remove'."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        if action == "list":
            url = f"{BASE_URL}/users/me/recipients"
            response = await client.get(url)
            if response.status_code == 200:
                return {"success": True, "recipients": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "add":
            if not phone_number:
                return {"success": False, "error": "phone_number is required to add a recipient."}
            url = f"{BASE_URL}/users/me/recipients"
            # Clean phone number: remove non-digits and leading 1
            cleaned = "".join(c for c in phone_number if c.isdigit())
            if cleaned.startswith("1") and len(cleaned) == 11:
                cleaned = cleaned[1:]
            payload = {"phoneNumber": cleaned}
            if name:
                payload["name"] = name
            response = await client.post(url, json=payload)
            if response.status_code in (200, 201):
                return {"success": True, "message": "Recipient added successfully.", "data": response.json()}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "remove":
            if not recipient_id:
                return {"success": False, "error": "recipient_id is required to remove a recipient."}
            url = f"{BASE_URL}/users/me/recipients/{recipient_id}"
            response = await client.delete(url)
            if response.status_code in (200, 204):
                return {"success": True, "message": f"Recipient {recipient_id} removed successfully."}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        else:
            return {"success": False, "error": f"Unknown action '{action}'. Supported actions are: 'list', 'add', 'remove'."}


@mcp.tool()
async def send_fact(
    recipient_id: Optional[str] = None,
    fact_id: Optional[str] = None
) -> dict:
    """Manually trigger sending a cat fact via text message to one or all recipients. Use this when a user wants to immediately send a fact rather than waiting for the scheduled daily send."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{BASE_URL}/users/me/recipients/send"
        payload = {}
        if recipient_id:
            payload["recipientId"] = recipient_id
        if fact_id:
            payload["factId"] = fact_id
        response = await client.post(url, json=payload)
        if response.status_code in (200, 201):
            return {"success": True, "message": "Cat fact sent successfully.", "data": response.json()}
        else:
            return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def get_messages(
    recipient_id: Optional[str] = None,
    limit: Optional[int] = 20,
    page: Optional[int] = 1
) -> dict:
    """Retrieve the conversation history (catversation) between the Catbot and a recipient. Use this to view messages exchanged, including auto-replies from the Catbot when recipients text back."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        if recipient_id:
            url = f"{BASE_URL}/users/me/recipients/{recipient_id}/messages"
        else:
            url = f"{BASE_URL}/users/me/messages"
        params = {}
        if limit:
            params["limit"] = limit
        if page:
            params["page"] = page
        response = await client.get(url, params=params)
        if response.status_code == 200:
            return {"success": True, "messages": response.json()}
        else:
            return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def authenticate_user(
    action: str,
    token: Optional[str] = None
) -> dict:
    """Handle user authentication including login via Google OAuth, session management, and logout. Use this to authenticate the user before performing protected operations like managing recipients or accessing the admin console. Actions: 'login', 'logout', 'status'."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        if action == "login":
            login_url = f"{BASE_URL}/auth/google"
            return {
                "success": True,
                "message": "To log in with Google OAuth, please visit the following URL in your browser.",
                "login_url": login_url,
                "instructions": "Navigate to the login_url to initiate the Google OAuth flow. After authenticating, you will receive a session token."
            }

        elif action == "logout":
            url = f"{BASE_URL}/auth/logout"
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            response = await client.get(url, headers=headers)
            if response.status_code in (200, 302):
                return {"success": True, "message": "Logged out successfully."}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        elif action == "status":
            url = f"{BASE_URL}/users/me"
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return {"success": True, "authenticated": True, "user": response.json()}
            elif response.status_code == 401:
                return {"success": True, "authenticated": False, "message": "Not authenticated."}
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text}

        else:
            return {"success": False, "error": f"Unknown action '{action}'. Supported actions are: 'login', 'logout', 'status'."}


@mcp.tool()
async def import_google_contacts(
    filter: Optional[str] = None,
    dry_run: Optional[bool] = False
) -> dict:
    """Import phone numbers from the authenticated user's Google Contacts to bulk-add recipients. Use this when a user wants to add multiple recipients at once from their existing Google address book."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{BASE_URL}/users/me/recipients/import"
        params = {}
        if filter:
            params["filter"] = filter
        if dry_run:
            params["dryRun"] = "true"
        response = await client.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            result = {"success": True, "data": data}
            if dry_run:
                result["message"] = "Dry run completed. No contacts were actually imported."
            else:
                result["message"] = "Google contacts import initiated."
            return result
        elif response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication required. Please use authenticate_user with action='login' first.",
                "status_code": 401
            }
        else:
            return {"success": False, "status_code": response.status_code, "error": response.text}


@mcp.tool()
async def get_api_logs(
    limit: Optional[int] = 50,
    page: Optional[int] = 1,
    endpoint: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict:
    """Retrieve API usage logs for monitoring and debugging. Use this in an admin context to view request history, track usage patterns, or investigate errors in the Cat Facts API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{BASE_URL}/admin/logs"
        params = {}
        if limit:
            params["limit"] = limit
        if page:
            params["page"] = page
        if endpoint:
            params["endpoint"] = endpoint
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        response = await client.get(url, params=params)
        if response.status_code == 200:
            return {"success": True, "logs": response.json()}
        elif response.status_code == 401:
            return {
                "success": False,
                "error": "Admin authentication required to access API logs.",
                "status_code": 401
            }
        elif response.status_code == 403:
            return {
                "success": False,
                "error": "Forbidden. Admin privileges required to access API logs.",
                "status_code": 403
            }
        else:
            return {"success": False, "status_code": response.status_code, "error": response.text}




async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http")

app = Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", mcp_app),
    ],
    lifespan=mcp_app.lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
