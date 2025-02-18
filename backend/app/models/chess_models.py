from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi import UploadFile

class Move(BaseModel):
    number: int
    white: Optional[str] = None
    black: Optional[str] = None
    position_after_white: Optional[str] = None
    position_after_black: Optional[str] = None
    white_uci: Optional[str] = None  # UCI format move for white
    black_uci: Optional[str] = None  # UCI format move for black
    full_move: str  # e.g., "1. e4 e5"
    position_fen: str  # FEN after the full move
    captured_piece_white: Optional[str] = None  # Piece captured by white
    captured_piece_black: Optional[str] = None  # Piece captured by black
    is_check_white: bool = False  # Whether white's move gives check
    is_check_black: bool = False  # Whether black's move gives check
    is_checkmate_white: bool = False  # Whether white's move gives checkmate
    is_checkmate_black: bool = False  # Whether black's move gives checkmate

class Analysis(BaseModel):
    move_number: int
    move: str
    analysis: str
    evaluation: Optional[str] = None  # e.g., "+=", "=", "-/+"

class GameAnalysis(BaseModel):
    moves: List[Move]
    summary: str
    key_moments: List[Analysis]
    opening_name: Optional[str] = None
    result: Optional[str] = None
    white_player: Optional[str] = None
    black_player: Optional[str] = None
    date: Optional[str] = None

class HealthCheck(BaseModel):
    status: str
    openai_connection: bool
    message: str

class PGNInput(BaseModel):
    pgn: str

class CoachingRequest(BaseModel):
    message: str
    game_context: Optional[str] = None  # PGN of the current game if available
    conversation_history: Optional[List[Dict[str, str]]] = []  # Previous messages in the conversation

class CoachingResponse(BaseModel):
    response: str
    suggestions: List[str]
    next_steps: Optional[List[str]] = None
    evaluation: Optional[str] = None

class VoiceCoachingRequest(BaseModel):
    audio_file: UploadFile
    game_context: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = []

class VoiceCoachingResponse(BaseModel):
    audio_response: str  # Base64 encoded audio
    text_response: str
    suggestions: List[str]
    next_steps: Optional[List[str]] = None
    evaluation: Optional[str] = None

class AnalysisWithVoiceRequest(BaseModel):
    pgn: str
    audio_file: Optional[UploadFile] = None
    conversation_history: Optional[List[Dict[str, str]]] = []

class AnalysisWithVoiceResponse(BaseModel):
    game_analysis: GameAnalysis
    coaching: Optional[VoiceCoachingResponse] = None 