// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const API_ENDPOINTS = {
  UPLOAD: `${API_BASE_URL}/upload`,
  UPLOAD_PROCESS: `${API_BASE_URL}/upload/process`,
  UPLOAD_STATUS: `${API_BASE_URL}/upload/status`, // SSE endpoint for processing status
  QUERY: `${API_BASE_URL}/query`,
  SCRIBE_TOKEN: `${API_BASE_URL}/scribe-token`, // ElevenLabs realtime STT token endpoint
  TTS: `${API_BASE_URL}/tts`, // ElevenLabs text-to-speech endpoint
} as const;

