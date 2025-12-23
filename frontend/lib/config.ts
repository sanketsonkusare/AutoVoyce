// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const API_ENDPOINTS = {
  UPLOAD: `${API_BASE_URL}/upload`,
  QUERY: `${API_BASE_URL}/query`,
} as const;

