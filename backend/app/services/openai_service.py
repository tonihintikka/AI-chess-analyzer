import json
import logging
from typing import Dict, List
from fastapi import HTTPException
from openai import OpenAI
import os
from dotenv import load_dotenv
import base64
from ..models.chess_models import Analysis

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not client.api_key:
    logger.error("OpenAI API key not found in environment variables!")

async def analyze_game_with_gpt(moves: List) -> Dict:
    """Analyze the chess game using GPT-4."""
    try:
        # Prepare the moves for GPT analysis
        moves_text = "\n".join([move.full_move for move in moves])
        logger.info("Prepared moves for GPT analysis")
        
        # Create the prompt for GPT-4
        prompt = f"""You are a chess analysis engine. Analyze the following chess game and provide your analysis in JSON format.
IMPORTANT: Respond with ONLY valid JSON - no markdown, no code blocks, no additional text.

Required JSON structure:
{{
    "summary": "Brief overall game summary",
    "key_moments": [
        {{
            "move_number": number,
            "move": "move in algebraic notation",
            "analysis": "Analysis of the move",
            "evaluation": "Evaluation symbol (e.g., +=, =, -/+)"
        }}
    ]
}}

Game moves to analyze:
{moves_text}

Remember: Return ONLY the JSON object, nothing else."""

        logger.info("Sending request to OpenAI")
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a chess grandmaster. You must respond with valid JSON only, no other text or formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={ "type": "json_object" }  # Enforce JSON response
        )
        logger.info("Received response from OpenAI")

        # Extract the content and ensure it's valid JSON
        content = response.choices[0].message.content.strip()
        try:
            # Try to parse the response as JSON
            logger.info("Attempting to parse GPT response as JSON")
            analysis_dict = json.loads(content)
            # Ensure required fields are present
            if not isinstance(analysis_dict, dict):
                raise ValueError("Response is not a dictionary")
            if "summary" not in analysis_dict or "key_moments" not in analysis_dict:
                raise ValueError("Missing required fields in response")
            logger.info("Successfully parsed GPT response")
            return analysis_dict
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response as JSON: {str(e)}")
            logger.error(f"Raw response: {content}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse GPT response as JSON. Response: {content[:100]}..."
            )
        except ValueError as e:
            logger.error(f"Invalid response format: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response format: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )

async def get_coaching_response(messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    """Get coaching response from OpenAI."""
    try:
        # Add formatting instructions to the system message
        system_message = """You are an experienced chess coach and grandmaster. 
        Provide clear, constructive advice and explain concepts in an easy-to-understand way. 
        Format your responses using markdown:

        1. Use '### Analysis' for position or question analysis
        2. Use '### Key Points' for main takeaways
        3. Use '### Strategy' for long-term plans
        4. Use '### Tactics' for immediate opportunities
        5. Use '### Suggestions' for concrete moves or ideas
        6. Use '### Evaluation' for position assessment
        
        Use numbered lists (1., 2., etc.) for sequential points
        Use **bold** for emphasis on important terms
        Keep paragraphs focused and well-structured
        """

        # Update the system message in the messages list
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] = system_message
        else:
            messages.insert(0, {"role": "system", "content": system_message})

        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            temperature=temperature,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error getting coaching response: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def structure_coaching_response(coaching_text: str) -> Dict:
    """Structure the coaching response into a consistent format."""
    try:
        analysis_prompt = """Convert the following coaching advice into a JSON object with this exact structure:
{
    "text_response": "Main coaching response with markdown formatting",
    "suggestions": ["Suggestion 1", "Suggestion 2", "Suggestion 3"],
    "next_steps": ["Action 1", "Action 2"],
    "evaluation": "Brief evaluation"
}

Original coaching content:
"""
        
        analysis_prompt += coaching_text
        
        structured_response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a JSON formatter. Format the chess coaching advice into a valid JSON object with the exact structure specified. Ensure all strings are properly escaped."
                },
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            max_tokens=1000,
            response_format={ "type": "json_object" }
        )
        
        try:
            content = structured_response.choices[0].message.content.strip()
            parsed_response = json.loads(content)
            
            # Validate the response structure
            required_fields = ["text_response", "suggestions"]
            for field in required_fields:
                if field not in parsed_response:
                    raise ValueError(f"Missing required field: {field}")
                    
            # Ensure suggestions is a list
            if not isinstance(parsed_response["suggestions"], list):
                parsed_response["suggestions"] = [parsed_response["suggestions"]]
                
            # Ensure next_steps is a list if present
            if "next_steps" in parsed_response and not isinstance(parsed_response["next_steps"], list):
                parsed_response["next_steps"] = [parsed_response["next_steps"]]
                
            return parsed_response
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Raw response content: {content}")
            # Provide a fallback response
            return {
                "text_response": coaching_text,
                "suggestions": ["Please review the advice above"],
                "next_steps": ["Consider the main points mentioned"],
                "evaluation": "Unable to structure the response"
            }
            
    except Exception as e:
        logger.error(f"Error structuring coaching response: {str(e)}")
        # Return a simplified response rather than raising an exception
        return {
            "text_response": coaching_text,
            "suggestions": ["Please review the advice provided"],
            "next_steps": ["Consider the key points mentioned"],
            "evaluation": "Error structuring the response"
        }

async def text_to_speech(text: str, voice: str = "alloy") -> str:
    """Convert text to speech using OpenAI's TTS API."""
    try:
        speech_response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        
        audio_data = speech_response.content
        return base64.b64encode(audio_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Error in text-to-speech conversion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def speech_to_text(audio_content: bytes) -> str:
    """Convert speech to text using OpenAI's Whisper API."""
    try:
        transcript_response = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", audio_content, "audio/wav")
        )
        return transcript_response.text
    except Exception as e:
        logger.error(f"Error in speech-to-text conversion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def check_openai_connection() -> bool:
    """Test the OpenAI connection."""
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a chess analyzer."},
                {"role": "user", "content": "Say 'OK' if you can hear me."}
            ],
            max_tokens=5
        )
        return bool(response and response.choices)
    except Exception as e:
        logger.error(f"OpenAI connection test failed: {str(e)}")
        return False 