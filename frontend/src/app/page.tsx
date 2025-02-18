'use client';

import { useState } from 'react';
import {
  Container,
  Grid,
  Box,
  Typography,
  CircularProgress,
  Button,
  Collapse,
} from '@mui/material';
import ChessBoard from '@/components/ChessBoard';
import GameAnalysis from '@/components/GameAnalysis';
import PGNInput from '@/components/PGNInput';
import ChessCoaching from '@/components/ChessCoaching';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface GameAnalysisData {
  moves: Array<{
    number: number;
    white: string;
    black: string;
    position_fen: string;
    full_move: string;
    analysis?: string;
    evaluation?: string;
  }>;
  summary: string;
  key_moments: Array<{
    move_number: number;
    move: string;
    analysis: string;
    evaluation?: string;
  }>;
}

export default function Home() {
  const [isLoading, setIsLoading] = useState(false);
  const [currentMove, setCurrentMove] = useState(0);
  const [gameAnalysis, setGameAnalysis] = useState<GameAnalysisData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCoaching, setShowCoaching] = useState(false);

  const handlePGNSubmit = async (pgn: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/analyze`, { pgn });
      setGameAnalysis(response.data);
      setCurrentMove(0);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Error analyzing game'
      );
      setGameAnalysis(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMoveSelect = (moveNumber: number) => {
    setCurrentMove(moveNumber);
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom align="center">
        Chess Game Analyzer
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Box sx={{ mb: 3 }}>
            <PGNInput onPGNSubmit={handlePGNSubmit} isLoading={isLoading} />
          </Box>

          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              minHeight: '600px',
            }}
          >
            {isLoading ? (
              <CircularProgress />
            ) : (
              <ChessBoard
                fen={
                  gameAnalysis?.moves[currentMove]?.position_fen ||
                  'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
                }
                disabled
              />
            )}
          </Box>
        </Grid>

        <Grid item xs={12} md={6}>
          {gameAnalysis && (
            <>
              <GameAnalysis
                moves={gameAnalysis.moves}
                currentMove={currentMove}
                onMoveSelect={handleMoveSelect}
                summary={gameAnalysis.summary}
                keyMoments={gameAnalysis.key_moments}
              />

              <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
                <Button
                  variant="contained"
                  onClick={() => setShowCoaching(!showCoaching)}
                >
                  {showCoaching ? 'Hide Coach' : 'Start Coaching'}
                </Button>
              </Box>

              <Collapse in={showCoaching}>
                <Box sx={{ mt: 2 }}>
                  <ChessCoaching
                    gameContext={gameAnalysis.moves
                      .map((m) => m.full_move)
                      .join(' ')}
                  />
                </Box>
              </Collapse>
            </>
          )}
        </Grid>
      </Grid>
    </Container>
  );
}
