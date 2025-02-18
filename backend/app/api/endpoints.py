from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import Optional
import json
import logging
from ..models.chess_models import (
    GameAnalysis, PGNInput, CoachingRequest, CoachingResponse,
    VoiceCoachingResponse, AnalysisWithVoiceResponse, HealthCheck,
    Analysis
)
from ..services.chess_service import extract_moves_from_pgn
from ..services.openai_service import (
    analyze_game_with_gpt, get_coaching_response, structure_coaching_response,
    text_to_speech, speech_to_text, check_openai_connection
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get("/health", response_model=HealthCheck)
async def check_health():
    """
    Check the health of the service and OpenAI connection.
    Returns status of the API and OpenAI connection.
    """
    try:
        openai_connection = await check_openai_connection()
        return HealthCheck(
            status="healthy" if openai_connection else "unhealthy",
            openai_connection=openai_connection,
            message="Service is healthy and OpenAI connection is working" if openai_connection else "OpenAI connection failed"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthCheck(
            status="unhealthy",
            openai_connection=False,
            message=f"Service health check failed: {str(e)}"
        )

@router.post("/analyze", response_model=GameAnalysis)
async def analyze_game(pgn_input: PGNInput):
    """
    Analyze a chess game from PGN text.
    Returns structured analysis including move-by-move commentary and game summary.
    """
    try:
        logger.info("Starting game analysis")
        # Extract moves and metadata from PGN
        moves, metadata = extract_moves_from_pgn(pgn_input.pgn)
        
        # Get AI analysis
        analysis = await analyze_game_with_gpt(moves)
        
        # Log the analysis response
        logger.info("Analysis response:")
        logger.info(json.dumps(analysis, indent=2))
        
        # Create the response
        response = GameAnalysis(
            moves=moves,
            summary=analysis["summary"],
            key_moments=[Analysis(**moment) for moment in analysis["key_moments"]],
            **metadata
        )
        
        # Log the final response
        logger.info("Final response:")
        logger.info(json.dumps(response.model_dump(), indent=2))
        
        logger.info("Analysis completed successfully")
        return response
        
    except Exception as e:
        logger.error(f"Error in analyze_game endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/coach", response_model=CoachingResponse)
async def get_chess_coaching(request: CoachingRequest):
    """
    Interactive chess coaching endpoint that provides personalized advice and feedback.
    """
    try:
        logger.info("Starting chess coaching interaction")
        
        # Prepare the conversation context
        messages = [
            {"role": "system", "content": """You are an experienced chess coach and grandmaster. 
            Provide clear, constructive advice and explain concepts in an easy-to-understand way. 
            Focus on helping players improve their game through strategic understanding and tactical awareness."""}
        ]
        
        # Add conversation history if it exists
        if request.conversation_history:
            messages.extend(request.conversation_history)
        
        # Add game context if provided
        if request.game_context:
            messages.append({
                "role": "user", 
                "content": f"Here's the game we're discussing:\n{request.game_context}"
            })
        
        # Add the current user message
        messages.append({"role": "user", "content": request.message})
        
        # Get coaching response
        coaching_content = await get_coaching_response(messages)
        
        # Structure the response
        try:
            structured_content = await structure_coaching_response(coaching_content)
            logger.info("Successfully structured coaching response")
            return CoachingResponse(**structured_content)
        except:
            # Fallback to a simpler response if structuring fails
            return CoachingResponse(
                response=coaching_content,
                suggestions=["Focus on the key points mentioned above"],
                next_steps=["Review the advice and apply it in your next game"],
                evaluation="Please see the main response for evaluation"
            )
            
    except Exception as e:
        logger.error(f"Error in chess coaching endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-with-voice", response_model=AnalysisWithVoiceResponse)
async def analyze_and_coach(
    pgn: str = Form(...),
    audio_file: Optional[UploadFile] = None,
    conversation_history: Optional[str] = None
):
    """
    Combined endpoint that first analyzes the game and then provides voice coaching.
    The initial analysis is required, voice coaching is optional.
    """
    try:
        logger.info("Starting combined analysis and coaching")
        
        # First, analyze the game
        moves, metadata = extract_moves_from_pgn(pgn)
        analysis = await analyze_game_with_gpt(moves)
        
        game_analysis = GameAnalysis(
            moves=moves,
            summary=analysis["summary"],
            key_moments=[Analysis(**moment) for moment in analysis["key_moments"]],
            **metadata
        )
        
        # If there's no audio file, return just the analysis
        if not audio_file:
            return AnalysisWithVoiceResponse(game_analysis=game_analysis)
        
        # Process voice coaching if audio file is provided
        audio_content = await audio_file.read()
        
        # Convert speech to text
        user_message = await speech_to_text(audio_content)
        logger.info(f"Transcribed text: {user_message}")
        
        # Prepare coaching context with game analysis
        messages = [
            {"role": "system", "content": """You are an experienced chess coach and grandmaster. 
            You have just analyzed a game, and now you're providing voice coaching.
            Keep your responses clear, concise, and focused on the most important points.
            Reference specific moves and positions from the game analysis when relevant."""},
            {"role": "user", "content": f"""Game Summary: {analysis['summary']}
            
Key Moments:
{json.dumps(analysis['key_moments'], indent=2)}

Player Question/Comment: {user_message}"""}
        ]
        
        # Add conversation history if provided
        if conversation_history:
            try:
                conv_history = json.loads(conversation_history)
                messages.extend(conv_history)
            except json.JSONDecodeError:
                logger.warning("Invalid conversation history format")
        
        # Get coaching response
        coaching_text = await get_coaching_response(messages)
        
        # Structure the response
        structured_content = await structure_coaching_response(coaching_text)
        
        # Convert response to speech
        audio_base64 = await text_to_speech(structured_content["text_response"])
        
        coaching_response = VoiceCoachingResponse(
            audio_response=audio_base64,
            **structured_content
        )
        
        return AnalysisWithVoiceResponse(
            game_analysis=game_analysis,
            coaching=coaching_response
        )
        
    except Exception as e:
        logger.error(f"Error in combined analysis and coaching endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 