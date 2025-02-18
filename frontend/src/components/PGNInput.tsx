import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Box,
  Alert,
} from '@mui/material';
import { Upload } from '@mui/icons-material';

interface PGNInputProps {
  onPGNSubmit: (pgn: string) => void;
  isLoading?: boolean;
}

export default function PGNInput({ onPGNSubmit, isLoading = false }: PGNInputProps) {
  const [pgnText, setPgnText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handlePGNChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setPgnText(event.target.value);
    setError(null);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pgn')) {
      setError('Please upload a .pgn file');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      setPgnText(content);
      setError(null);
    };
    reader.onerror = () => {
      setError('Error reading file');
    };
    reader.readAsText(file);
  };

  const handleSubmit = () => {
    if (!pgnText.trim()) {
      setError('Please enter PGN data');
      return;
    }
    onPGNSubmit(pgnText.trim());
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Upload Game
        </Typography>

        <Box sx={{ mb: 2 }}>
          <TextField
            multiline
            rows={4}
            fullWidth
            placeholder="Paste your PGN here..."
            value={pgnText}
            onChange={handlePGNChange}
            variant="outlined"
            error={!!error}
            helperText={error}
          />
        </Box>

        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            component="label"
            startIcon={<Upload />}
            disabled={isLoading}
          >
            Upload PGN
            <input
              type="file"
              accept=".pgn"
              hidden
              onChange={handleFileUpload}
            />
          </Button>

          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!pgnText.trim() || isLoading}
          >
            Analyze Game
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
} 