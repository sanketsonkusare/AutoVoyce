"use client"

import type React from "react"
import { useState, useRef, useEffect } from "react"
import { Send, Mic, ChevronRight, Video, ExternalLink, ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@/lib/utils"
import { API_ENDPOINTS } from "@/lib/config"
import { SharedHeader } from "@/components/shared-header"
import { SharedFooter } from "@/components/shared-footer"
import { SparkleDecoration } from "@/components/sparkle-decoration"
import { VoiceWaveform } from "@/components/voice-waveform"
import { VideoCard, type VideoStatus } from "@/components/video-card"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
  sources?: SourceReference[]
  contextUsed?: string[]
}

interface SourceReference {
  videoId: string
  videoTitle: string
  timestamp?: string
  relevance: string
}

interface Topic {
  id: string
  name: string
  videos: Video[]
}

interface Video {
  id: string
  title: string
  channel?: string
  duration?: string
  status: VideoStatus
}

const exampleQuestions = [
  "What are the main topics covered?",
  "Summarize the key points",
  "What are the best practices mentioned?",
  "Compare different approaches",
]

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content:
        "Hello! I'm AutoVoyce, your AI-powered video research assistant. Ask me anything about the videos I've analyzed!",
      timestamp: new Date(),
    },
  ])
  const [inputValue, setInputValue] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [showContext, setShowContext] = useState<Record<string, boolean>>({})
  const [currentTopic, setCurrentTopic] = useState<Topic>({
    id: "1",
    name: "Machine Learning Fundamentals",
    videos: [
      { id: "1", title: "Introduction to Neural Networks", channel: "AI Explained", duration: "15:30", status: "ready" },
      { id: "2", title: "Deep Learning Basics", channel: "Tech Talks", duration: "22:15", status: "ready" },
      { id: "3", title: "ML Algorithms Explained", channel: "Data Science", duration: "18:45", status: "analyzing" },
    ],
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [inputValue])

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputValue.trim(),
      timestamp: new Date(),
    }

    const queryText = inputValue.trim()
    setMessages((prev) => [...prev, userMessage])
    setInputValue("")
    setIsTyping(true)

    try {
      const response = await fetch(API_ENDPOINTS.QUERY, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_query: queryText }),
      })

      if (!response.ok) {
        throw new Error(`Failed to query: ${response.statusText}`)
      }

      const data = await response.json()
      
      // Parse the response - the API returns a string response
      const responseText = typeof data === "string" ? data : data.response || data.answer || JSON.stringify(data)

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
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
      }

      setMessages((prev) => [...prev, aiMessage])
    } catch (error) {
      console.error("Error querying:", error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Sorry, I encountered an error while processing your question: ${
          error instanceof Error ? error.message : "Unknown error"
        }. Please try again.`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsTyping(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleMicClick = () => {
    setIsRecording(!isRecording)
  }

  const handleExampleQuestion = (question: string) => {
    setInputValue(question)
    textareaRef.current?.focus()
  }

  const toggleContext = (messageId: string) => {
    setShowContext((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }))
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }

  const showSendButton = inputValue.trim().length > 0

  return (
    <div className="min-h-screen bg-[#0f172a] flex flex-col">
      <SharedHeader />

      {/* Main Chat Area */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <aside className="hidden md:flex w-80 border-r border-slate-700/30 bg-slate-900/30 flex-col">
          {/* Topic Header */}
          <div className="p-4 border-b border-slate-700/30">
            <h2 className="text-lg font-semibold text-white mb-1">{currentTopic.name}</h2>
            <p className="text-xs text-slate-400">{currentTopic.videos.length} videos analyzed</p>
          </div>

          {/* Video List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Videos</h3>
            {currentTopic.videos.map((video) => (
              <VideoCard
                key={video.id}
                title={video.title}
                channel={video.channel}
                duration={video.duration}
                status={video.status}
                onClick={() => {
                  // Scroll to video reference in chat
                  console.log("Navigate to video:", video.id)
                }}
              />
            ))}
          </div>

          {/* Switch Topic Button */}
          <div className="p-4 border-t border-slate-700/30">
            <button className="w-full px-4 py-2 rounded-lg border border-slate-700/50 bg-slate-800/50 hover:bg-slate-700/50 text-sm text-slate-300 hover:text-white transition-colors">
              Switch Topic
            </button>
          </div>
        </aside>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          <div className="relative flex-1 flex flex-col overflow-hidden">
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
                >
                  <div className="max-w-[80%] space-y-2">
                    <div
                      className={cn(
                        "rounded-2xl px-4 py-3 animate-in fade-in slide-in-from-bottom-2 duration-300",
                        message.role === "user"
                          ? "bg-gradient-to-r from-violet-600 to-purple-600 text-white"
                          : "bg-slate-800/50 border border-slate-700/50 text-slate-100",
                      )}
                    >
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                      <p
                        className={cn(
                          "text-[10px] mt-1.5",
                          message.role === "user" ? "text-white/60" : "text-slate-500",
                        )}
                      >
                        {formatTime(message.timestamp)}
                      </p>
                    </div>

                    {/* Source References */}
                    {message.sources && message.sources.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs text-slate-400 font-medium px-1">Sources:</div>
                        {message.sources.map((source, idx) => (
                          <a
                            key={idx}
                            href={`#video-${source.videoId}`}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:border-violet-500/50 text-xs text-slate-300 hover:text-white transition-colors group"
                          >
                            <Video className="size-3 text-violet-400" />
                            <span className="flex-1 truncate">{source.videoTitle}</span>
                            {source.timestamp && (
                              <span className="text-slate-500 group-hover:text-slate-400">{source.timestamp}</span>
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
                              <div key={idx} className="text-xs text-slate-500 flex items-start gap-2">
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
                      <span className="text-xs text-slate-400 ml-2">Thinking...</span>
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
                        : "bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500",
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
                  <span>Recording... Click again to stop</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      <SharedFooter />
      <SparkleDecoration />
    </div>
  )
}
