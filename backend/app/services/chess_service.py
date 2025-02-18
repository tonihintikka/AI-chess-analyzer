import chess.pgn
import io
from typing import List, Dict, Tuple
from fastapi import HTTPException
import logging
from ..models.chess_models import Move

logger = logging.getLogger(__name__)

def extract_moves_from_pgn(pgn_content: str) -> Tuple[List[Move], Dict]:
    """Extract moves from PGN content and return them in a structured format."""
    try:
        logger.info("Attempting to parse PGN content")
        if not pgn_content.strip():
            logger.error("Empty PGN content")
            raise HTTPException(status_code=400, detail="Empty PGN content")

        game = chess.pgn.read_game(io.StringIO(pgn_content))
        if not game:
            logger.error("Invalid PGN format - could not read game")
            raise HTTPException(status_code=400, detail="Invalid PGN format - could not read game")
        
        try:
            # Validate that moves can be parsed
            moves_list = list(game.mainline_moves())
            if not moves_list:
                logger.error("No valid moves found in PGN")
                raise HTTPException(status_code=400, detail="No valid moves found in PGN")
        except ValueError as e:
            logger.error(f"Invalid moves in PGN: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid moves in PGN: {str(e)}")
        
        board = game.board()
        moves = []
        move_number = 1
        current_move = {
            "number": move_number,
            "white": None,
            "black": None,
            "position_after_white": None,
            "position_after_black": None,
            "white_uci": None,
            "black_uci": None,
            "full_move": f"{move_number}.",
            "position_fen": board.fen(),
            "captured_piece_white": None,
            "captured_piece_black": None,
            "is_check_white": False,
            "is_check_black": False,
            "is_checkmate_white": False,
            "is_checkmate_black": False
        }
        
        for node in game.mainline():
            try:
                move = node.move
                if not move:
                    continue
                
                # Get move in both SAN and UCI format
                san_move = board.san(move)
                uci_move = move.uci()
                
                # Check if a piece was captured
                captured_piece = board.piece_at(move.to_square)
                
                # Make the move
                board.push(move)
                
                # Check for check/checkmate
                is_check = board.is_check()
                is_checkmate = board.is_checkmate()
                
                if node.turn():  # Black's move
                    current_move["black"] = san_move
                    current_move["black_uci"] = uci_move
                    current_move["position_after_black"] = board.fen()
                    current_move["captured_piece_black"] = str(captured_piece) if captured_piece else None
                    current_move["is_check_black"] = is_check
                    current_move["is_checkmate_black"] = is_checkmate
                    current_move["full_move"] = f"{move_number}. {current_move['white']} {san_move}"
                    current_move["position_fen"] = board.fen()
                    moves.append(Move(**current_move))
                    move_number += 1
                    current_move = {
                        "number": move_number,
                        "white": None,
                        "black": None,
                        "position_after_white": None,
                        "position_after_black": None,
                        "white_uci": None,
                        "black_uci": None,
                        "full_move": f"{move_number}.",
                        "position_fen": board.fen(),
                        "captured_piece_white": None,
                        "captured_piece_black": None,
                        "is_check_white": False,
                        "is_check_black": False,
                        "is_checkmate_white": False,
                        "is_checkmate_black": False
                    }
                else:  # White's move
                    current_move["white"] = san_move
                    current_move["white_uci"] = uci_move
                    current_move["position_after_white"] = board.fen()
                    current_move["captured_piece_white"] = str(captured_piece) if captured_piece else None
                    current_move["is_check_white"] = is_check
                    current_move["is_checkmate_white"] = is_checkmate
                    current_move["full_move"] = f"{move_number}. {san_move}"
            except Exception as e:
                logger.error(f"Error processing move: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Error processing move: {str(e)}")
        
        # Handle last move if it's only white's move
        if current_move["white"] and not current_move["black"]:
            moves.append(Move(**current_move))
        
        # Extract game metadata
        metadata = {
            "opening_name": game.headers.get("Opening", None),
            "result": game.headers.get("Result", None),
            "white_player": game.headers.get("White", None),
            "black_player": game.headers.get("Black", None),
            "date": game.headers.get("Date", None)
        }
        
        logger.info(f"Successfully extracted {len(moves)} moves from PGN")
        return moves, metadata
    except Exception as e:
        logger.error(f"Error extracting moves from PGN: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error extracting moves from PGN: {str(e)}") 