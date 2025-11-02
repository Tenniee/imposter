from fastapi import FastAPI
from app.routes import game

import random, string# reset_room_table.py

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://192.168.1.6"] for more control
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include game routes

app.include_router(game.router)
