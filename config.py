"""
config.py — Central configuration for AspectLens.
------------------------------------------------
All app-wide constants live here (app name, file paths, chart colours,
platform badge colours) so every other file imports from ONE place.
"""
import os

APP_NAME = "AspectLens"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "absa.db")   # SQLite file (auto-created)

# ---- Sentiment colours (used by charts + badges) ----
POS_COLOR = "#10b981"   # emerald  = Positive
NEG_COLOR = "#f43f5e"   # rose/red = Negative
NEU_COLOR = "#8b5cf6"   # violet   = Neutral
ACCENT = "#9333ea"      # brand purple
