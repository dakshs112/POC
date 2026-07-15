import json
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


app = FastAPI()

BASE_URL = "https://api.jolpi.ca/ergast/f1"

# Mock users
mock_users = {
    "user1": {
        "name": "Daksh",
        "favorite_drivers": [
            "max_verstappen",
            "hamilton"
        ]
    },
    "user2": {
        "name": "Abhisekh",
        "favorite_drivers": [
            "leclerc",
            "norris"
        ]
    }
}


@app.get("/")
async def home():
    return {"message": "F1 Recommendation API POC"}


# Helper function to fetch drivers from Jolpica API
async def fetch_drivers():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/current/drivers.json",
            timeout=10
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail="Failed to fetch driver data"
        )

    data = response.json()
    return data["MRData"]["DriverTable"]["Drivers"]

@app.get("/drivers",response_class =HTMLResponse)
async def get_drivers():

    drivers = await fetch_drivers()

    result = []

    for driver in drivers:
        result.append({
            "id": driver["driverId"],
            "name": f"{driver['givenName']} {driver['familyName']}"
        })

    with open(f"{DATA_DIR}/drivers.txt", "w", encoding="utf-8") as file:

        for driver in result:
            file.write(f"ID: {driver['id']}\n")
            file.write(f"Name: {driver['name']}\n")
            file.write("-" * 30 + "\n")

    html = "<h1>Drivers</h1><ul>"

    for driver in result:
        html += f"<li>{driver['name']} ({driver['id']})</li>"

    html += "</ul>"

    return html


@app.get("/users/{user_id}",response_class=HTMLResponse)
async def get_user_favorites(user_id: str):

    # Check if user exists
    if user_id not in mock_users:
        raise HTTPException(
            status_code=404,
            detail="User does not exist."
        )

    drivers = await fetch_drivers()


    favorites = mock_users[user_id]["favorite_drivers"]

    favorite_driver_details = []

    for driver in drivers:
        if driver["driverId"] in favorites:
            favorite_driver_details.append({
                "id": driver["driverId"],
                "name": f"{driver['givenName']} {driver['familyName']}"
            })

    user_data = {
        "user": {
            "id": user_id,
            "name": mock_users[user_id]["name"]
        },
        "favorite_drivers": favorite_driver_details
    }
    with open(f"{DATA_DIR}/{user_id}.txt", "w", encoding="utf-8") as file:
        file.write(f"User ID: {user_id}\n")
        file.write(f"Name: {mock_users[user_id]['name']}\n\n")

        file.write("Favorite Drivers:\n")

        for driver in favorite_driver_details:
            file.write(f"- {driver['name']} ({driver['id']})\n")
    html = f"""
    <html>
    <head>
        <title>{mock_users[user_id]['name']}'s Favorite Drivers</title>
    </head>
    <body>
        <h1>{mock_users[user_id]['name']}'s Favorite Drivers</h1>

        <ul>
    """

    for driver in favorite_driver_details:
        html += f"""
            <li>
                <strong>{driver['name']}</strong><br>
                Driver ID: {driver['id']}
            </li>
        """

    html += """
        </ul>
    </body>
    </html>
    """

    return html