import { useState, useRef, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemText,
  Chip,
  Box,
  IconButton,
  Paper,
} from '@mui/material';
import {
  NavigateBefore,
  NavigateNext,
  SkipPrevious,
  SkipNext,
} from '@mui/icons-material';

interface Move {
  number: number;
  white: string;
  black: string;
  position_fen: string;
  full_move: string;
}

interface KeyMoment {
  move_number: number;
  move: string;
  analysis: string;
  evaluation?: string;
}

interface GameAnalysisProps {
  moves: Move[];
  currentMove: number;
  onMoveSelect: (moveNumber: number) => void;
  summary?: string;
  keyMoments?: KeyMoment[];
}

export default function GameAnalysis({
  moves,
  currentMove,
  onMoveSelect,
  summary,
  keyMoments,
}: GameAnalysisProps) {
  const [selectedMove, setSelectedMove] = useState<number | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const moveRefs = useRef<(HTMLLIElement | null)[]>([]);

  // Update refs array when moves change
  useEffect(() => {
    moveRefs.current = moveRefs.current.slice(0, moves.length);
  }, [moves]);

  // Scroll to current move when it changes
  useEffect(() => {
    if (moveRefs.current[currentMove]) {
      moveRefs.current[currentMove]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [currentMove]);

  const handleMoveClick = (moveNumber: number) => {
    setSelectedMove(moveNumber);
    onMoveSelect(moveNumber);
  };

  const handleNavigation = (direction: 'first' | 'prev' | 'next' | 'last') => {
    let newMove = currentMove;
    switch (direction) {
      case 'first':
        newMove = 0;
        break;
      case 'prev':
        if (currentMove > 0) newMove = currentMove - 1;
        break;
      case 'next':
        if (currentMove < moves.length - 1) newMove = currentMove + 1;
        break;
      case 'last':
        newMove = moves.length - 1;
        break;
    }
    setSelectedMove(newMove);
    onMoveSelect(newMove);
  };

  // Find analysis for current move
  const getCurrentMoveAnalysis = () => {
    if (!keyMoments) return null;
    const currentMoveNumber = Math.floor(currentMove / 2) + 1;
    return keyMoments.find(km => km.move_number === currentMoveNumber);
  };

  return (
    <Card>
      <CardContent>
        {summary && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Game Summary
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {summary}
            </Typography>
          </Box>
        )}

        <Typography variant="h6" gutterBottom>
          Move Analysis
        </Typography>
        
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
          <IconButton
            onClick={() => handleNavigation('first')}
            disabled={currentMove === 0}
          >
            <SkipPrevious />
          </IconButton>
          <IconButton
            onClick={() => handleNavigation('prev')}
            disabled={currentMove === 0}
          >
            <NavigateBefore />
          </IconButton>
          <IconButton
            onClick={() => handleNavigation('next')}
            disabled={currentMove === moves.length - 1}
          >
            <NavigateNext />
          </IconButton>
          <IconButton
            onClick={() => handleNavigation('last')}
            disabled={currentMove === moves.length - 1}
          >
            <SkipNext />
          </IconButton>
        </Box>

        <Paper 
          variant="outlined" 
          sx={{ maxHeight: 400, overflow: 'auto' }}
          ref={listRef}
        >
          <List dense>
            {moves.map((move, index) => {
              const keyMoment = keyMoments?.find(
                km => km.move_number === Math.floor(index / 2) + 1
              );
              return (
                <ListItem
                  key={move.number}
                  ref={(element: HTMLLIElement | null) => {
                    moveRefs.current[index] = element;
                  }}
                  onClick={() => handleMoveClick(index)}
                  sx={{
                    cursor: 'pointer',
                    transition: 'background-color 0.3s',
                    '&:hover': {
                      backgroundColor: 'action.hover',
                    },
                    backgroundColor:
                      index === currentMove
                        ? 'primary.light'
                        : index === selectedMove
                        ? 'action.selected'
                        : keyMoment ? 'rgba(25, 118, 210, 0.08)'
                        : 'inherit',
                    color: index === currentMove ? 'white' : 'inherit',
                  }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography 
                          variant="body2" 
                          color={index === currentMove ? 'inherit' : 'textSecondary'}
                        >
                          {move.number}.
                        </Typography>
                        <Typography color={index === currentMove ? 'inherit' : 'text.primary'}>
                          {move.full_move}
                        </Typography>
                        {keyMoment?.evaluation && (
                          <Chip
                            label={keyMoment.evaluation}
                            size="small"
                            color={
                              keyMoment.evaluation.includes('+')
                                ? 'success'
                                : keyMoment.evaluation.includes('-')
                                ? 'error'
                                : 'default'
                            }
                            sx={{
                              color: index === currentMove ? 'white' : 'inherit',
                              borderColor: index === currentMove ? 'white' : 'inherit',
                            }}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      keyMoment && (
                        <Typography 
                          variant="body2" 
                          color={index === currentMove ? 'inherit' : 'text.secondary'}
                          sx={{ 
                            opacity: index === currentMove ? 0.9 : 0.7,
                            mt: 1,
                            fontStyle: 'italic'
                          }}
                        >
                          {keyMoment.analysis}
                        </Typography>
                      )
                    }
                  />
                </ListItem>
              );
            })}
          </List>
        </Paper>
      </CardContent>
    </Card>
  );
} 