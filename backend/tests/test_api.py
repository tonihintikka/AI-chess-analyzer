import requests
import json
from typing import Dict, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

def test_health_check() -> bool:
    """Test the health check endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/health")
        data = response.json()
        logger.info(f"Health check response: {data}")
        return data.get("status") == "healthy"
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return False

def test_analyze_game(pgn: str) -> Dict:
    """Test the game analysis endpoint with a given PGN."""
    try:
        response = requests.post(
            f"{BASE_URL}/analyze",
            headers=HEADERS,
            json={"pgn": pgn}
        )
        if response.status_code == 400:
            logger.info(f"Expected error response for invalid PGN: {response.json()}")
            return response.json()
        data = response.json()
        return data
    except Exception as e:
        logger.error(f"Game analysis failed: {str(e)}")
        return None

def validate_move_data(move: Dict) -> List[str]:
    """Validate that a move contains all required fields."""
    errors = []
    required_fields = [
        "number", "full_move", "position_fen",
        "is_check_white", "is_check_black",
        "is_checkmate_white", "is_checkmate_black"
    ]
    
    for field in required_fields:
        if field not in move:
            errors.append(f"Missing required field: {field}")
    
    return errors

def validate_analysis(analysis: Dict) -> List[str]:
    """Validate the analysis response structure."""
    errors = []
    
    # Check required top-level fields
    required_fields = ["moves", "summary", "key_moments"]
    for field in required_fields:
        if field not in analysis:
            errors.append(f"Missing required field: {field}")
            return errors
    
    # Validate moves
    for move in analysis["moves"]:
        move_errors = validate_move_data(move)
        if move_errors:
            errors.extend([f"Move {move.get('number', '?')}: {error}" 
                         for error in move_errors])
    
    # Validate key moments
    for moment in analysis["key_moments"]:
        if not all(k in moment for k in ["move_number", "move", "analysis"]):
            errors.append(f"Invalid key moment structure: {moment}")
    
    return errors

def run_tests():
    """Run all tests and print results."""
    # Test 1: Health Check
    logger.info("Testing health check endpoint...")
    if test_health_check():
        logger.info("✅ Health check passed")
    else:
        logger.error("❌ Health check failed")
    
    # Test 2: Simple game analysis
    simple_pgn = """
[Event "Test Game"]
[Site "Chess Game Analyzer"]
[Date "2024.03.20"]
[Round "1"]
[White "Player 1"]
[Black "Player 2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O 1-0
"""
    
    logger.info("Testing game analysis with simple game...")
    analysis = test_analyze_game(simple_pgn)
    if analysis:
        errors = validate_analysis(analysis)
        if errors:
            logger.error("❌ Analysis validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
        else:
            logger.info("✅ Analysis validation passed")
            logger.info(f"Game summary: {analysis['summary']}")
            logger.info(f"Number of moves: {len(analysis['moves'])}")
            logger.info(f"Number of key moments: {len(analysis['key_moments'])}")
    
    # Test 3: Complex game with checks and captures
    complex_pgn = """
[Event "Test Game"]
[Site "Chess Game Analyzer"]
[Date "2024.03.20"]
[Round "1"]
[White "Player 1"]
[Black "Player 2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 O-O 
8. O-O d6 9. Bg5 Bxc3 10. bxc3 Nxe4 11. Bxd8 Nxc3 12. Qd3 Nxd1 13. Raxd1 Rxd8 1-0
"""
    
    logger.info("Testing game analysis with complex game...")
    analysis = test_analyze_game(complex_pgn)
    if analysis:
        errors = validate_analysis(analysis)
        if errors:
            logger.error("❌ Analysis validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
        else:
            logger.info("✅ Analysis validation passed")
            logger.info(f"Game summary: {analysis['summary']}")
            logger.info(f"Number of moves: {len(analysis['moves'])}")
            logger.info(f"Number of key moments: {len(analysis['key_moments'])}")
    
    # Test 4: Invalid PGN
    logger.info("Testing error handling with invalid PGN...")
    invalid_pgn = "1. e4 e5 invalid moves"
    error_response = test_analyze_game(invalid_pgn)
    if error_response and "detail" in error_response:
        logger.info("✅ Invalid PGN handling passed")
    else:
        logger.error("❌ Invalid PGN handling failed")

def save_analysis_to_file(analysis: Dict, filename: str = "analysis_result.json"):
    """Save the analysis result to a JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(analysis, f, indent=2)
        logger.info(f"Analysis saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to save analysis: {str(e)}")

if __name__ == "__main__":
    run_tests() 