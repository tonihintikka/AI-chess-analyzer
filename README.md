# Chess Game Analyzer

An AI-powered chess game analysis tool that provides detailed move-by-move analysis, game summaries, and interactive coaching using GPT-4.

## Features

- **Game Analysis**: Upload PGN files or paste PGN text for instant AI analysis
- **Interactive Board**: Visual representation of the game with move navigation
- **Move-by-Move Analysis**: Detailed analysis of key moments and critical positions
- **AI Coaching**: Interactive chess coach powered by GPT-4
- **Voice Interaction**: Voice-based coaching with speech-to-text and text-to-speech capabilities
- **Real-time Evaluation**: Position evaluation with standard chess notation (e.g., +=, -/+)

## Tech Stack

### Frontend
- Next.js 14
- React
- Material-UI (MUI)
- TypeScript
- Axios for API calls
- react-chessboard for chess visualization

### Backend
- FastAPI
- Python 3.10+
- OpenAI GPT-4 API
- python-chess for game processing
- Pydantic for data validation

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- Conda or other Python virtual environment manager
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd chess-game-analyzer
```

2. Backend Setup:
```bash
cd backend
conda create -n chess-analyzer python=3.10
conda activate chess-analyzer
pip install -r requirements.txt
```

3. Create a `.env` file in the backend directory:
```
OPENAI_API_KEY=your_api_key_here
```

4. Frontend Setup:
```bash
cd frontend
npm install
```

5. Create a `.env.local` file in the frontend directory:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### Running the Application

1. Start the backend server:
```bash
cd backend
conda activate chess-analyzer
uvicorn app.main:app --reload
```

2. Start the frontend development server:
```bash
cd frontend
npm run dev
```

The application will be available at `http://localhost:3000`

## Usage

1. **Analyzing a Game**:
   - Upload a PGN file or paste PGN text in the input area
   - Click "Analyze Game" to start the analysis
   - View the interactive board and move list with analysis

2. **Navigating Moves**:
   - Use the navigation buttons (First, Previous, Next, Last)
   - Click on any move in the move list
   - View key moments highlighted in light blue

3. **Using the AI Coach**:
   - Click "Start Coaching" to open the coaching interface
   - Type questions or use voice input for coaching
   - Receive personalized advice and analysis

## API Documentation

### Backend Endpoints

#### Game Analysis
```http
POST /api/analyze
Content-Type: application/json

{
  "pgn": "string (PGN format chess game)"
}
```

#### Interactive Coaching
```http
POST /api/coach
Content-Type: application/json

{
  "message": "string",
  "game_context": "string (optional PGN)",
  "conversation_history": []
}
```

#### Voice Coaching
```http
POST /api/voice-coach
Content-Type: multipart/form-data

audio_file: binary
game_context: string (optional)
conversation_history: string (optional)
```

## Component Structure

### Frontend
- `ChessBoard`: Interactive chess board component
- `GameAnalysis`: Move list and analysis display
- `PGNInput`: Game input component
- `ChessCoaching`: Interactive coaching interface
- `ThemeRegistry`: Material-UI theme configuration

### Backend
- `main.py`: Application entry point and FastAPI setup
- `endpoints.py`: API route handlers
- `chess_service.py`: Chess game processing logic
- `openai_service.py`: GPT-4 integration and analysis
- `chess_models.py`: Pydantic data models

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for GPT-4 API
- python-chess library
- react-chessboard component
- Material-UI team

## Support

For support, please open an issue in the repository or contact the maintainers. 