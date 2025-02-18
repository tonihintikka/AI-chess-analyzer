import { useEffect, useState } from 'react';
import { Chessboard } from 'react-chessboard';
import { Chess } from 'chess.js';

interface ChessBoardProps {
  fen?: string;
  onMove?: (move: { from: string; to: string }) => void;
  disabled?: boolean;
}

export default function ChessBoard({ fen, onMove, disabled = false }: ChessBoardProps) {
  const [game, setGame] = useState(new Chess(fen));

  useEffect(() => {
    if (fen) {
      setGame(new Chess(fen));
    }
  }, [fen]);

  function onDrop(sourceSquare: string, targetSquare: string) {
    if (disabled) return false;

    try {
      const move = game.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: 'q', // always promote to queen for simplicity
      });

      if (move === null) return false;
      
      if (onMove) {
        onMove({ from: sourceSquare, to: targetSquare });
      }

      return true;
    } catch (error) {
      return false;
    }
  }

  return (
    <div className="w-full max-w-[600px] aspect-square">
      <Chessboard
        position={game.fen()}
        onPieceDrop={onDrop}
        boardWidth={600}
        areArrowsAllowed={true}
        customBoardStyle={{
          borderRadius: '4px',
          boxShadow: '0 2px 10px rgba(0, 0, 0, 0.5)',
        }}
      />
    </div>
  );
} 