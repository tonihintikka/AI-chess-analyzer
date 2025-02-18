# Chess Game Analyzer API Documentation

## Overview
The Chess Game Analyzer is an AI-powered chess analysis tool that provides game analysis, coaching, and voice interaction capabilities using GPT-4 and other OpenAI services.

## Base URL
```
http://localhost:8000/api
```

## Authentication
The API requires an OpenAI API key to be set in the `.env` file:
```
OPENAI_API_KEY=your_api_key_here
```

## Endpoints

### Health Check
```http
GET /health
```
Check the health of the service and OpenAI connection.

#### Response
```json
{
  "status": "healthy",
  "openai_connection": true,
  "message": "Service is healthy and OpenAI connection is working"
}
```

### Analyze Game
```http
POST /analyze
```
Analyze a chess game from PGN notation.

#### Request Body
```json
{
  "pgn": "string (PGN format chess game)"
}
```

#### Response
```json
{
  "moves": [
    {
      "number": 1,
      "white": "e4",
      "black": "e5",
      "position_after_white": "fen_string",
      "position_after_black": "fen_string",
      "white_uci": "e2e4",
      "black_uci": "e7e5",
      "full_move": "1. e4 e5",
      "position_fen": "fen_string",
      "captured_piece_white": null,
      "captured_piece_black": null,
      "is_check_white": false,
      "is_check_black": false,
      "is_checkmate_white": false,
      "is_checkmate_black": false
    }
  ],
  "summary": "Game analysis summary",
  "key_moments": [
    {
      "move_number": 1,
      "move": "e4",
      "analysis": "Analysis of the move",
      "evaluation": "+="
    }
  ],
  "opening_name": "String",
  "result": "1-0",
  "white_player": "Player Name",
  "black_player": "Player Name",
  "date": "YYYY.MM.DD"
}
```

### Chess Coaching
```http
POST /coach
```
Get interactive chess coaching and personalized advice.

#### Request Body
```json
{
  "message": "string",
  "game_context": "string (optional PGN)",
  "conversation_history": [
    {
      "role": "user/assistant",
      "content": "string"
    }
  ]
}
```

#### Response
```json
{
  "response": "Coaching advice",
  "suggestions": ["Suggestion 1", "Suggestion 2"],
  "next_steps": ["Step 1", "Step 2"],
  "evaluation": "Position evaluation"
}
```

### Analyze with Voice
```http
POST /analyze-with-voice
```
Combined endpoint for game analysis and voice coaching.

#### Request Body
- Form Data:
  - `pgn`: string (required)
  - `audio_file`: file (optional)
  - `conversation_history`: string (optional JSON)

#### Response
```json
{
  "game_analysis": {
    // Same as /analyze response
  },
  "coaching": {
    "audio_response": "base64_encoded_audio",
    "text_response": "Coaching advice",
    "suggestions": ["Suggestion 1", "Suggestion 2"],
    "next_steps": ["Step 1", "Step 2"],
    "evaluation": "Position evaluation"
  }
}
```

## Error Responses
The API uses standard HTTP status codes:
- `200`: Success
- `400`: Bad Request (invalid input)
- `500`: Internal Server Error

Error response format:
```json
{
  "detail": "Error message"
}
```

## Setup and Running
1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

4. Run the server:
```bash
uvicorn app.main:app --reload
```

## Interactive Documentation
Access the Swagger UI documentation at:
```
http://localhost:8000/docs
```

## Testing
Example test commands are available in `test_commands.txt`. Basic test using curl:
```bash
curl http://localhost:8000/api/health
```

## Dependencies
- FastAPI
- python-chess
- openai
- python-dotenv
- uvicorn
- pydantic

## Notes
- The API uses GPT-4-turbo-preview for analysis and coaching
- Voice features use OpenAI's Whisper for speech-to-text and TTS for text-to-speech
- CORS is enabled for all origins in development (customize for production) 