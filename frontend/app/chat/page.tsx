"use client";

import type React from "react";
import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import {
  Send,
  Mic,
  ChevronRight,
  Video,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useScribe } from "@elevenlabs/react";
import { cn } from "@/lib/utils";
import { API_ENDPOINTS } from "@/lib/config";
import { SharedHeader } from "@/components/shared-header";
import { SharedFooter } from "@/components/shared-footer";
import { VoiceWaveform } from "@/components/voice-waveform";
import { VideoCard, type VideoStatus } from "@/components/video-card";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  sources?: SourceReference[];
  contextUsed?: string[];
}

interface SourceReference {
  videoId: string;
  videoTitle: string;
  timestamp?: string;
  relevance: string;
}

interface Topic {
  id: string;
  name: string;
  videos: Video[];
}

interface Video {
  id: string;
  title: string;
  channel?: string;
  duration?: string;
  status: VideoStatus;
}

const exampleQuestions = [
  "What are the main topics covered?",
  "Summarize the key points",
  "What are the best practices mentioned?",
  "Compare different approaches",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content:
        "Hello! I'm AutoVoyce, your AI-powered video research assistant. Ask me anything about the videos I've analyzed!",
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [showContext, setShowContext] = useState<Record<string, boolean>>({});
  const [transcribedText, setTranscribedText] = useState("");
  const [usedVoiceInput, setUsedVoiceInput] = useState(false); // Track if user used voice input
  const usedVoiceInputRef = useRef(false); // Ref to track voice input (for closure issues)
  const pendingRequestRef = useRef(false); // Track if there's a pending request to prevent duplicates
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [hasSession, setHasSession] = useState<boolean | null>(null);

  // References for silence detection
  const silenceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const stopRecordingRef = useRef<((text: string) => Promise<void>) | null>(
    null
  );

  // Function to stop recording (defined early so it can be called by other functions)
  const stopRecording = async () => {
    if (!isRecording) return;

    setIsRecording(false);

    // Clear silence detection timeout
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current);
      silenceTimeoutRef.current = null;
    }

    // Cancel animation frame if active
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    // Stop the media stream if it exists
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      try {
        await audioContextRef.current.close();
      } catch (error) {
        console.error("Error closing audio context:", error);
      }
      audioContextRef.current = null;
      analyserRef.current = null;
    }

    // Disconnect from ElevenLabs
    try {
      await scribe.disconnect();
    } catch (error) {
      console.error("Error disconnecting from scribe:", error);
    }

    // Automatically send the transcribed text after recording stops
    if (transcribedText.trim() || inputValue.trim()) {
      const queryText = transcribedText.trim() || inputValue.trim();
      setTranscribedText(""); // Reset transcribed text
      setInputValue(queryText); // Set input value

      // Mark that voice input was used (both state and ref)
      setUsedVoiceInput(true);
      usedVoiceInputRef.current = true;

      // Automatically send the transcribed query using the ref
      if (stopRecordingRef.current) {
        await stopRecordingRef.current(queryText);
      }
    }
  };

  // Function to reset the silence detection timer
  const resetSilenceDetection = () => {
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current);
    }

    if (isRecording) {
      silenceTimeoutRef.current = setTimeout(() => {
        console.log("Silence detected for 1 second, stopping recording");
        stopRecording();
      }, 1000); // 1 second of silence
    }
  };

  // ElevenLabs Scribe hook for realtime transcription (Speech-to-Text)
  const scribe = useScribe({
    modelId: "scribe_v2_realtime",
    onPartialTranscript: (data) => {
      // Update input field with partial transcript for real-time feedback
      setInputValue(data.text);
      // Reset silence timer when we get partial transcripts
      resetSilenceDetection();
    },
    onCommittedTranscript: (data) => {
      // Append committed transcript to accumulated text
      setTranscribedText((prev) => {
        const newText = prev ? `${prev} ${data.text}` : data.text;
        setInputValue(newText);
        return newText;
      });
      // Reset silence timer when we get committed transcripts
      resetSilenceDetection();
    },
  });

  // Text-to-Speech state
  const [isSpeaking, setIsSpeaking] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Function to convert text to speech using ElevenLabs API
  const speak = async (text: string) => {
    try {
      console.log("🎤 Starting TTS for text:", text.substring(0, 50) + "...");

      // Stop any currently playing audio
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      setIsSpeaking(true);
      abortControllerRef.current = new AbortController();

      // Get voice ID from environment or use default
      const voiceId = process.env.NEXT_PUBLIC_ELEVENLABS_VOICE_ID;

      console.log("📞 Calling TTS endpoint:", API_ENDPOINTS.TTS);

      // Call backend TTS endpoint
      const response = await fetch(API_ENDPOINTS.TTS, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: text,
          voice_id: voiceId,
        }),
        signal: abortControllerRef.current.signal,
      });

      console.log("📡 TTS response status:", response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("❌ TTS API error:", errorText);
        throw new Error(
          `Failed to generate speech: ${response.status} ${errorText}`
        );
      }

      // Get audio blob
      const audioBlob = await response.blob();
      console.log("🎵 Audio blob received, size:", audioBlob.size);

      const audioUrl = URL.createObjectURL(audioBlob);

      // Create and play audio
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onended = () => {
        console.log("✅ Audio playback completed");
        setIsSpeaking(false);
        URL.revokeObjectURL(audioUrl);
        audioRef.current = null;
      };

      audio.onerror = (e) => {
        console.error("❌ Error playing audio:", e);
        setIsSpeaking(false);
        URL.revokeObjectURL(audioUrl);
        audioRef.current = null;
      };

      console.log("▶️ Starting audio playback...");
      await audio.play();
      console.log("✅ Audio playback started");
    } catch (error: any) {
      if (error.name !== "AbortError") {
        console.error("❌ Error in speak function:", error);
      }
      setIsSpeaking(false);
    }
  };

  // Function to stop speaking
  const stopSpeaking = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsSpeaking(false);
  };

  // Function to check audio levels
  const checkAudioLevel = () => {
    // Use a ref to track recording state to avoid stale closures
    if (!analyserRef.current) {
      animationFrameRef.current = null;
      return;
    }

    // Check if still recording using the current state
    // We'll check this at the end and continue only if recording
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);

    // Calculate average volume level
    const average =
      dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;

    console.log(`🔊 Audio level: ${average.toFixed(2)} (threshold: 10)`);

    // If volume is below threshold, consider it silence
    if (average < 100) {
      // Silence detected - start or continue the timeout
      if (!silenceTimeoutRef.current) {
        console.log("🔇 Silence detected, starting 1 second timer...");
        silenceTimeoutRef.current = setTimeout(() => {
          console.log("⏱️ Silence detected for 1 second, stopping recording");
          stopRecording();
        }, 1000);
      }
      // If timeout already exists, let it continue
    } else {
      // Sound detected - clear any existing timeout
      if (silenceTimeoutRef.current) {
        console.log("🔊 Sound detected, clearing silence timer");
        clearTimeout(silenceTimeoutRef.current);
        silenceTimeoutRef.current = null;
      }
    }

    // Continue checking audio levels only if still recording
    if (isRecording) {
      animationFrameRef.current = requestAnimationFrame(checkAudioLevel);
    } else {
      animationFrameRef.current = null;
      // Clear timeout if recording stopped
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
        silenceTimeoutRef.current = null;
      }
    }
  };

  // Helper function to get session_id from localStorage or cookies
  const getSessionId = (): string | null => {
    if (typeof window === "undefined") return null;

    // First try localStorage (more reliable for localhost)
    const localStorageId = localStorage.getItem("autovoyce_session_id");
    if (localStorageId) {
      return localStorageId;
    }

    // Fallback to cookies
    const cookies = document.cookie.split(";");
    for (const cookie of cookies) {
      const [name, value] = cookie.trim().split("=");
      if (name === "session_id") {
        return decodeURIComponent(value);
      }
    }

    return null;
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Check for session on mount
  useEffect(() => {
    const sessionId = getSessionId();
    console.log("Chat page loaded - Session ID:", sessionId); // Debug
    console.log("LocalStorage:", localStorage.getItem("autovoyce_session_id")); // Debug
    setHasSession(!!sessionId);

    if (!sessionId) {
      // Update welcome message if no session
      setMessages([
        {
          id: "1",
          role: "assistant",
          content:
            "Hello! I'm AutoVoyce, your AI-powered video research assistant. It looks like you haven't uploaded any videos yet. Please go to the Ingestion page to search and process videos first, then come back here to ask questions!",
          timestamp: new Date(),
        },
      ]);
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        120
      )}px`;
    }
  }, [inputValue]);

  // Cleanup effect for recording resources
  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current);
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(console.error);
      }
      // Cleanup audio playback
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleSendMessage = async () => {
    // If recording is active, stop it first
    if (isRecording) {
      await stopRecording();
      // stopRecording already calls handleSendMessageWithText automatically
      // So we should return here to prevent duplicate calls
      return;
    } else {
      // Text input was used, not voice
      setUsedVoiceInput(false);
      usedVoiceInputRef.current = false;
    }

    // Get the final text
    const textToSend = inputValue.trim();
    if (!textToSend) return;

    // Reset transcribed text after sending
    setTranscribedText("");

    // Send the message
    await handleSendMessageWithText(textToSend);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleMicClick = async () => {
    if (isRecording) {
      // Stop recording manually
      await stopRecording();
    } else {
      // Start recording
      try {
        setIsRecording(true);
        setTranscribedText("");
        setInputValue("");

        // Fetch token from backend
        const response = await fetch(API_ENDPOINTS.SCRIBE_TOKEN);
        if (!response.ok) {
          throw new Error("Failed to get scribe token");
        }

        const { token } = await response.json();

        // Set up audio context and analyzer for silence detection
        const AudioContextClass =
          window.AudioContext || (window as any).webkitAudioContext;
        audioContextRef.current = new AudioContextClass();
        analyserRef.current = audioContextRef.current.createAnalyser();
        analyserRef.current.fftSize = 256;

        // Get microphone access
        mediaStreamRef.current = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

        // Connect microphone to analyzer
        const source = audioContextRef.current.createMediaStreamSource(
          mediaStreamRef.current
        );
        source.connect(analyserRef.current);

        // Connect to ElevenLabs with microphone access
        await scribe.connect({
          token,
          microphone: {
            echoCancellation: true,
            noiseSuppression: true,
          },
        });

        // Start checking audio levels
        checkAudioLevel();

        // Initial silence detection timer
        resetSilenceDetection();
      } catch (error) {
        console.error("Error starting recording:", error);
        setIsRecording(false);

        // Clean up on error
        if (mediaStreamRef.current) {
          mediaStreamRef.current.getTracks().forEach((track) => track.stop());
          mediaStreamRef.current = null;
        }
        if (audioContextRef.current) {
          try {
            await audioContextRef.current.close();
          } catch (e) {
            // Ignore errors during cleanup
          }
          audioContextRef.current = null;
          analyserRef.current = null;
        }

        // Show error message to user
        const errorMessage: Message = {
          id: Date.now().toString(),
          role: "assistant",
          content: `Sorry, I couldn't start the voice recording. Please make sure your microphone is enabled and try again. Error: ${
            error instanceof Error ? error.message : "Unknown error"
          }`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    }
  };

  const handleSendMessageWithText = async (text: string) => {
    if (!text.trim()) return;

    // Prevent duplicate requests - check BEFORE adding user message
    if (pendingRequestRef.current) {
      console.log("⚠️ Request already pending, ignoring duplicate");
      return;
    }

    pendingRequestRef.current = true;

    // Generate unique ID for this message to prevent duplicates
    const messageId = `${Date.now()}-${Math.random()
      .toString(36)
      .substr(2, 9)}`;

    const userMessage: Message = {
      id: messageId,
      role: "user",
      content: text.trim(),
      timestamp: new Date(),
    };

    const queryText = text.trim();

    // Check if this exact message already exists to prevent duplicate display
    setMessages((prev) => {
      // Check if this message content already exists in recent messages
      const recentMessages = prev.slice(-5); // Check last 5 messages
      const isDuplicate = recentMessages.some(
        (msg) => msg.role === "user" && msg.content === text.trim()
      );

      if (isDuplicate) {
        console.log("⚠️ Duplicate user message detected, not adding");
        return prev;
      }

      return [...prev, userMessage];
    });

    setInputValue("");
    setIsTyping(true);

    try {
      // Get session_id from localStorage or cookies
      const sessionId = getSessionId();

      if (!sessionId) {
        throw new Error(
          "No active session found. Please upload videos first from the Ingestion page."
        );
      }

      console.log("Using session_id:", sessionId); // Debug log

      const response = await fetch(API_ENDPOINTS.QUERY, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionId, // Send session_id as header
        },
        body: JSON.stringify({
          user_query: queryText,
        }),
        credentials: "include", // Include cookies in the request
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage =
          errorData.detail || `Failed to query: ${response.statusText}`;

        // If session error, show helpful message
        if (response.status === 401 || response.status === 404) {
          throw new Error(
            errorMessage +
              " Please upload videos first from the Ingestion page."
          );
        }

        throw new Error(errorMessage);
      }

      const data = await response.json();

      // Parse the response - the API returns a string response
      const responseText =
        typeof data === "string"
          ? data
          : data.response || data.answer || JSON.stringify(data);

      // Generate unique ID for AI message
      const aiMessageId = `${Date.now() + 1}-${Math.random()
        .toString(36)
        .substr(2, 9)}`;

      const aiMessage: Message = {
        id: aiMessageId,
        role: "assistant",
        content: responseText,
        timestamp: new Date(),
        // If the API returns source information, parse it here
        sources: data.sources
          ? data.sources.map((source: any) => ({
              videoId: source.video_id || source.id || "",
              videoTitle: source.video_title || source.title || "Video",
              timestamp: source.timestamp,
              relevance: source.relevance || "Relevant",
            }))
          : undefined,
        contextUsed: data.context
          ? Array.isArray(data.context)
            ? data.context
            : [data.context]
          : undefined,
      };

      // Check if this AI response already exists to prevent duplicate display
      setMessages((prev) => {
        // Check if this exact response already exists in recent messages
        const recentMessages = prev.slice(-5); // Check last 5 messages
        const isDuplicate = recentMessages.some(
          (msg) => msg.role === "assistant" && msg.content === responseText
        );

        if (isDuplicate) {
          console.log("⚠️ Duplicate AI message detected, not adding");
          return prev;
        }

        return [...prev, aiMessage];
      });

      // If user used voice input, speak the response
      // Use ref to avoid closure issues with state
      // IMPORTANT: Check and capture the flag value BEFORE any async operations
      const shouldSpeak = usedVoiceInputRef.current && responseText.trim();

      if (shouldSpeak) {
        console.log("🔊 Speaking response (voice input was used)");
        // Don't reset the flag yet - wait until after speaking completes
        try {
          await speak(responseText);
          console.log("✅ Speech completed, resetting voice input flag");
        } catch (error) {
          console.error("Error speaking response:", error);
        } finally {
          // Only reset after speaking completes (or fails)
          setUsedVoiceInput(false);
          usedVoiceInputRef.current = false;
        }
      } else {
        console.log(
          "🔇 Not speaking (text input was used or no response text). Voice flag:",
          usedVoiceInputRef.current
        );
        // Only reset if we're not speaking (to avoid race conditions)
        // But be careful - if there's another request pending, don't reset yet
        // Actually, let's only reset if we're sure this is a text input
        if (!usedVoiceInputRef.current) {
          // This was definitely text input, safe to reset
          setUsedVoiceInput(false);
        }
      }
    } catch (error) {
      console.error("Error querying:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Sorry, I encountered an error while processing your question: ${
          error instanceof Error ? error.message : "Unknown error"
        }. Please try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
      pendingRequestRef.current = false; // Reset pending flag
    }
  };

  // Update the ref so stopRecording can call handleSendMessageWithText
  useEffect(() => {
    stopRecordingRef.current = handleSendMessageWithText;
  }, []);

  const handleExampleQuestion = (question: string) => {
    setInputValue(question);
    textareaRef.current?.focus();
  };

  const toggleContext = (messageId: string) => {
    setShowContext((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }));
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const showSendButton = inputValue.trim().length > 0;

  return (
    <div className="min-h-screen bg-[#0f172a] flex flex-col">
      <SharedHeader />

      {/* Main Chat Area */}
      <main className="flex-1 flex overflow-hidden">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          <div className="relative flex-1 flex flex-col overflow-hidden">
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "flex",
                    message.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  <div className="max-w-[80%] space-y-2">
                    <div
                      className={cn(
                        "rounded-2xl px-4 py-3 animate-in fade-in slide-in-from-bottom-2 duration-300",
                        message.role === "user"
                          ? "bg-gradient-to-r from-violet-600 to-purple-600 text-white"
                          : "bg-slate-800/50 border border-slate-700/50 text-slate-100"
                      )}
                    >
                      <div className="text-sm leading-relaxed">
                        <ReactMarkdown
                          components={{
                            // Headings
                            h1: ({ node, ...props }) => (
                              <h1
                                className="text-lg font-bold mb-2 mt-3 first:mt-0"
                                {...props}
                              />
                            ),
                            h2: ({ node, ...props }) => (
                              <h2
                                className="text-base font-semibold mb-2 mt-3 first:mt-0"
                                {...props}
                              />
                            ),
                            h3: ({ node, ...props }) => (
                              <h3
                                className="text-sm font-semibold mb-1.5 mt-2 first:mt-0"
                                {...props}
                              />
                            ),
                            // Paragraphs
                            p: ({ node, ...props }) => (
                              <p className="mb-2 last:mb-0" {...props} />
                            ),
                            // Lists
                            ul: ({ node, ...props }) => (
                              <ul
                                className="list-disc list-inside mb-2 space-y-1"
                                {...props}
                              />
                            ),
                            ol: ({ node, ...props }) => (
                              <ol
                                className="list-decimal list-inside mb-2 space-y-1"
                                {...props}
                              />
                            ),
                            li: ({ node, ...props }) => (
                              <li className="ml-4" {...props} />
                            ),
                            // Code blocks
                            code: ({ node, inline, ...props }: any) => {
                              if (inline) {
                                return (
                                  <code
                                    className={cn(
                                      "px-1.5 py-0.5 rounded text-xs font-mono",
                                      message.role === "user"
                                        ? "bg-white/20 text-white"
                                        : "bg-slate-700/50 text-violet-300"
                                    )}
                                    {...props}
                                  />
                                );
                              }
                              return (
                                <code
                                  className={cn(
                                    "block p-3 rounded-lg text-xs font-mono overflow-x-auto mb-2",
                                    message.role === "user"
                                      ? "bg-white/10 text-white"
                                      : "bg-slate-900/50 text-slate-200 border border-slate-700/50"
                                  )}
                                  {...props}
                                />
                              );
                            },
                            pre: ({ node, ...props }) => (
                              <pre className="mb-2" {...props} />
                            ),
                            // Links
                            a: ({ node, ...props }) => (
                              <a
                                className={cn(
                                  "underline hover:no-underline",
                                  message.role === "user"
                                    ? "text-white/90 hover:text-white"
                                    : "text-violet-400 hover:text-violet-300"
                                )}
                                target="_blank"
                                rel="noopener noreferrer"
                                {...props}
                              />
                            ),
                            // Strong/Bold
                            strong: ({ node, ...props }) => (
                              <strong className="font-semibold" {...props} />
                            ),
                            // Emphasis/Italic
                            em: ({ node, ...props }) => (
                              <em className="italic" {...props} />
                            ),
                            // Blockquotes
                            blockquote: ({ node, ...props }) => (
                              <blockquote
                                className={cn(
                                  "border-l-4 pl-3 py-1 my-2 italic",
                                  message.role === "user"
                                    ? "border-white/30 text-white/80"
                                    : "border-slate-600 text-slate-300"
                                )}
                                {...props}
                              />
                            ),
                            // Horizontal rule
                            hr: ({ node, ...props }) => (
                              <hr
                                className={cn(
                                  "my-3 border-0 border-t",
                                  message.role === "user"
                                    ? "border-white/20"
                                    : "border-slate-700"
                                )}
                                {...props}
                              />
                            ),
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      </div>
                      <p
                        className={cn(
                          "text-[10px] mt-1.5",
                          message.role === "user"
                            ? "text-white/60"
                            : "text-slate-500"
                        )}
                      >
                        {formatTime(message.timestamp)}
                      </p>
                    </div>

                    {/* Source References */}
                    {message.sources && message.sources.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs text-slate-400 font-medium px-1">
                          Sources:
                        </div>
                        {message.sources.map((source, idx) => (
                          <a
                            key={idx}
                            href={`#video-${source.videoId}`}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:border-violet-500/50 text-xs text-slate-300 hover:text-white transition-colors group"
                          >
                            <Video className="size-3 text-violet-400" />
                            <span className="flex-1 truncate">
                              {source.videoTitle}
                            </span>
                            {source.timestamp && (
                              <span className="text-slate-500 group-hover:text-slate-400">
                                {source.timestamp}
                              </span>
                            )}
                            <ExternalLink className="size-3 text-slate-500 group-hover:text-violet-400" />
                          </a>
                        ))}
                      </div>
                    )}

                    {/* Context Used Section */}
                    {message.contextUsed && message.contextUsed.length > 0 && (
                      <div className="mt-2">
                        <button
                          onClick={() => toggleContext(message.id)}
                          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:border-violet-500/50 text-xs text-slate-400 hover:text-slate-300 transition-colors w-full"
                        >
                          <span>Context Used</span>
                          {showContext[message.id] ? (
                            <ChevronUp className="size-3 ml-auto" />
                          ) : (
                            <ChevronDown className="size-3 ml-auto" />
                          )}
                        </button>
                        {showContext[message.id] && (
                          <div className="mt-2 space-y-1 pl-3">
                            {message.contextUsed.map((context, idx) => (
                              <div
                                key={idx}
                                className="text-xs text-slate-500 flex items-start gap-2"
                              >
                                <ChevronRight className="size-3 mt-0.5 shrink-0" />
                                <span>{context}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex gap-1.5">
                        <span className="size-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0ms]" />
                        <span className="size-2 bg-slate-400 rounded-full animate-bounce [animation-delay:150ms]" />
                        <span className="size-2 bg-slate-400 rounded-full animate-bounce [animation-delay:300ms]" />
                      </div>
                      <span className="text-xs text-slate-400 ml-2">
                        Thinking...
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Example Questions */}
            {messages.length === 1 && !isTyping && (
              <div className="px-6 pb-4">
                <div className="text-xs text-slate-400 mb-2">Try asking:</div>
                <div className="flex flex-wrap gap-2">
                  {exampleQuestions.map((question, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleExampleQuestion(question)}
                      className="px-3 py-1.5 rounded-full border border-slate-700/50 bg-slate-800/30 hover:bg-slate-700/50 text-xs text-slate-300 hover:text-white transition-colors"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Input Area */}
            <div className="p-4 border-t border-slate-700/30 bg-slate-900/30">
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <textarea
                    ref={textareaRef}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask a question about the videos..."
                    rows={1}
                    className="w-full resize-none rounded-full border border-slate-600/50 bg-slate-800/50 backdrop-blur-sm px-5 py-3 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-violet-500/50 transition-colors"
                  />
                </div>

                <button
                  onClick={showSendButton ? handleSendMessage : handleMicClick}
                  className={cn(
                    "shrink-0 size-11 rounded-full flex items-center justify-center transition-all duration-200",
                    showSendButton
                      ? "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400"
                      : isRecording
                      ? "bg-red-500 hover:bg-red-400 animate-pulse"
                      : "bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500"
                  )}
                >
                  {showSendButton ? (
                    <Send className="size-4 text-white" />
                  ) : isRecording ? (
                    <VoiceWaveform isActive={true} className="scale-150" />
                  ) : (
                    <Mic className="size-4 text-white" />
                  )}
                </button>
              </div>

              {/* Voice Recording Indicator */}
              {isRecording && (
                <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
                  <VoiceWaveform isActive={true} />
                  <span>
                    Recording... Will stop and send automatically after 1 second
                    of silence
                  </span>
                </div>
              )}

              {/* Text-to-Speech Indicator */}
              {isSpeaking && (
                <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
                  <VoiceWaveform isActive={true} />
                  <span>AI is speaking...</span>
                  <button
                    onClick={stopSpeaking}
                    className="ml-2 px-2 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs transition-colors"
                  >
                    Stop
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      <SharedFooter />
    </div>
  );
}
