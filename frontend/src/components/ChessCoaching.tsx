import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Box,
  List,
  ListItem,
  ListItemText,
  Chip,
  Divider,
  IconButton,
  Paper,
  Avatar,
  CircularProgress,
} from '@mui/material';
import {
  Send,
  Mic,
  Stop,
  Psychology,
  SportsEsports,
  LightbulbOutlined,
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface CoachingResponse {
  response: string;
  suggestions: string[];
  next_steps?: string[];
  evaluation?: string;
}

interface ChessCoachingProps {
  gameContext?: string;
}

export default function ChessCoaching({ gameContext }: ChessCoachingProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = inputMessage.trim();
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post<CoachingResponse>(`${API_BASE_URL}/coach`, {
        message: userMessage,
        game_context: gameContext,
        conversation_history: messages,
      });

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.data.response },
      ]);

      // Add suggestions as separate messages if they exist
      if (response.data.suggestions?.length > 0) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: '### Suggestions:\n' + response.data.suggestions.join('\n'),
          },
        ]);
      }

      // Add next steps as separate messages if they exist
      const nextSteps = response.data.next_steps;
      if (nextSteps && nextSteps.length > 0) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: '### Next Steps:\n' + nextSteps.join('\n'),
          },
        ]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          sampleRate: 16000
        }
      });
      
      const recorder = new MediaRecorder(stream, {
        mimeType: 'audio/wav'
      });
      
      setMediaRecorder(recorder);
      setAudioChunks([]);

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          setAudioChunks((chunks) => [...chunks, event.data]);
        }
      };

      // Request data every second to ensure we get all audio
      recorder.start(1000);
      setIsRecording(true);
    } catch (error: any) {
      // If WAV is not supported, try WebM
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
          audio: {
            channelCount: 1,
            sampleRate: 16000
          }
        });
        
        const recorder = new MediaRecorder(stream, {
          mimeType: 'audio/webm'
        });
        
        setMediaRecorder(recorder);
        setAudioChunks([]);

        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            setAudioChunks((chunks) => [...chunks, event.data]);
          }
        };

        recorder.start(1000);
        setIsRecording(true);
      } catch (fallbackError: any) {
        console.error('Error starting recording:', fallbackError);
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `Sorry, I couldn't start recording: ${fallbackError.message}`,
          },
        ]);
      }
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
      
      mediaRecorder.onstop = async () => {
        // Create blob with proper MIME type
        const mimeType = mediaRecorder.mimeType || 'audio/wav';
        const audioBlob = new Blob(audioChunks, { 
          type: mimeType
        });

        // Create file with proper name and type
        const extension = mimeType.includes('webm') ? 'webm' : 'wav';
        const audioFile = new File([audioBlob], `recording.${extension}`, {
          type: mimeType
        });

        const formData = new FormData();
        formData.append('audio_file', audioFile);
        // Add empty PGN if no game context
        formData.append('pgn', gameContext || '');
        if (gameContext) {
          formData.append('conversation_history', JSON.stringify(messages));
        }
        
        setIsLoading(true);
        try {
          const response = await axios.post(
            `${API_BASE_URL}/analyze-with-voice`,
            formData,
            {
              headers: {
                'Content-Type': 'multipart/form-data',
              },
            }
          );

          // Handle the structured response
          if (response.data.coaching) {
            // Convert base64 audio to audio element
            const audio = new Audio(
              `data:audio/mp3;base64,${response.data.coaching.audio_response}`
            );
            await audio.play();

            setMessages((prev) => [
              ...prev,
              { role: 'assistant', content: response.data.coaching.text_response },
            ]);
          }
        } catch (error: any) {
          console.error('Error sending voice message:', error);
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: `Sorry, I encountered an error processing your voice message: ${error.message}`,
            },
          ]);
        } finally {
          setIsLoading(false);
        }
      };
    }
  };

  const formatMessage = (content: string) => {
    // Split content into sections based on markdown headers and lists
    const sections = content.split(/(?=###)/);
    
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {sections.map((section, index) => {
          const trimmedSection = section.trim();
          if (!trimmedSection) return null;

          // Check if this is a header section (###)
          if (trimmedSection.startsWith('###')) {
            const [header, ...content] = trimmedSection.split('\n');
            return (
              <Box key={index}>
                <Typography 
                  variant="subtitle1" 
                  sx={{ 
                    fontWeight: 600,
                    color: 'primary.main',
                    mt: index > 0 ? 2 : 0,
                    mb: 1
                  }}
                >
                  {header.replace('###', '').trim()}
                </Typography>
                {content.length > 0 && (
                  <Box sx={{ pl: 0 }}>
                    {content.map((line, lineIndex) => {
                      const trimmedLine = line.trim();
                      if (!trimmedLine) return null;

                      // Check for numbered list items
                      const numberMatch = trimmedLine.match(/^(\d+)\.\s+(.+)/);
                      if (numberMatch) {
                        const [, number, text] = numberMatch;
                        return (
                          <Box 
                            key={lineIndex}
                            sx={{ 
                              display: 'flex',
                              gap: 1,
                              pl: 2,
                              mb: 1
                            }}
                          >
                            <Typography 
                              component="span" 
                              sx={{ 
                                color: 'primary.main',
                                fontWeight: 500,
                                minWidth: '24px'
                              }}
                            >
                              {number}.
                            </Typography>
                            <Typography
                              sx={{
                                flex: 1,
                                '& strong': {
                                  fontWeight: 600,
                                  color: 'primary.main'
                                }
                              }}
                              dangerouslySetInnerHTML={{
                                __html: text.replace(
                                  /\*\*(.*?)\*\*/g,
                                  '<strong>$1</strong>'
                                )
                              }}
                            />
                          </Box>
                        );
                      }

                      // Check for sub-bullet points
                      const indentLevel = (trimmedLine.match(/^\s+/) || [''])[0].length;
                      const bulletMatch = trimmedLine.match(/^[\s-]*\s*(.+)/);
                      if (bulletMatch) {
                        return (
                          <Box 
                            key={lineIndex}
                            sx={{ 
                              display: 'flex',
                              gap: 1,
                              pl: 2 + indentLevel,
                              mb: 0.5
                            }}
                          >
                            <Typography 
                              component="span" 
                              sx={{ 
                                color: 'primary.main',
                                minWidth: '20px'
                              }}
                            >
                              •
                            </Typography>
                            <Typography
                              sx={{
                                flex: 1,
                                '& strong': {
                                  fontWeight: 600,
                                  color: 'primary.main'
                                }
                              }}
                              dangerouslySetInnerHTML={{
                                __html: bulletMatch[1].replace(
                                  /\*\*(.*?)\*\*/g,
                                  '<strong>$1</strong>'
                                )
                              }}
                            />
                          </Box>
                        );
                      }

                      // Regular paragraph
                      return (
                        <Typography 
                          key={lineIndex}
                          sx={{ 
                            mb: 1,
                            lineHeight: 1.6,
                            '& strong': {
                              fontWeight: 600,
                              color: 'primary.main'
                            }
                          }}
                          dangerouslySetInnerHTML={{
                            __html: trimmedLine.replace(
                              /\*\*(.*?)\*\*/g,
                              '<strong>$1</strong>'
                            )
                          }}
                        />
                      );
                    })}
                  </Box>
                )}
              </Box>
            );
          }

          // Regular paragraph with bold text support
          return (
            <Typography 
              key={index} 
              sx={{ 
                lineHeight: 1.6,
                '& strong': {
                  fontWeight: 600,
                  color: 'primary.main'
                }
              }}
              dangerouslySetInnerHTML={{
                __html: trimmedSection.replace(
                  /\*\*(.*?)\*\*/g,
                  '<strong>$1</strong>'
                )
              }}
            />
          );
        })}
      </Box>
    );
  };

  return (
    <Card elevation={3}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Psychology sx={{ mr: 1, color: 'primary.main' }} />
          <Typography variant="h6">Chess Coach</Typography>
        </Box>

        <Paper 
          sx={{ 
            height: '400px',
            display: 'flex',
            flexDirection: 'column',
            bgcolor: '#f5f5f5',
            p: 2,
          }}
        >
          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            {messages.map((message, index) => (
              <Box
                key={index}
                sx={{
                  display: 'flex',
                  justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                  alignItems: 'flex-start',
                  gap: 1,
                }}
              >
                {message.role === 'assistant' && (
                  <Avatar sx={{ bgcolor: 'primary.main' }}>
                    <SportsEsports />
                  </Avatar>
                )}
                <Paper
                  elevation={1}
                  sx={{
                    p: 2,
                    maxWidth: '80%',
                    bgcolor: message.role === 'user' ? 'primary.main' : 'white',
                    color: message.role === 'user' ? 'white' : 'text.primary',
                    borderRadius: 2,
                    '& .MuiTypography-root': {
                      color: message.role === 'user' ? 'inherit' : 'text.primary',
                    },
                  }}
                >
                  {formatMessage(message.content)}
                </Paper>
                {message.role === 'user' && (
                  <Avatar sx={{ bgcolor: 'secondary.main' }}>
                    {message.role.charAt(0).toUpperCase()}
                  </Avatar>
                )}
              </Box>
            ))}
            {isLoading && (
              <Box sx={{ display: 'flex', justifyContent: 'center' }}>
                <CircularProgress size={24} />
              </Box>
            )}
          </Box>

          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: 'flex', gap: 1 }}>
            <IconButton
              color={isRecording ? 'secondary' : 'primary'}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isLoading}
            >
              {isRecording ? <Stop /> : <Mic />}
            </IconButton>

            <TextField
              fullWidth
              placeholder="Ask your chess coach..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              disabled={isLoading}
              multiline
              maxRows={3}
              size="small"
              sx={{
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'white',
                },
              }}
            />

            <Button
              variant="contained"
              onClick={handleSendMessage}
              disabled={!inputMessage.trim() || isLoading}
              startIcon={<Send />}
            >
              Send
            </Button>
          </Box>
        </Paper>
      </CardContent>
    </Card>
  );
} 