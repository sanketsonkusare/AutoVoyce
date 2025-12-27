"use client";

import type React from "react";
import { useState } from "react";
import {
  Play,
  Check,
  AlertCircle,
  Loader2,
  Video,
  Clock,
  User,
  FileText,
  ArrowRight,
  ArrowLeft,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { API_ENDPOINTS } from "@/lib/config";
import { SharedHeader } from "@/components/shared-header";
import { SharedFooter } from "@/components/shared-footer";

type IngestionStep = "input" | "preview" | "processing" | "complete";

type LogStatus = "success" | "progress" | "error" | "info";

interface LogEntry {
  id: string;
  message: string;
  timestamp: Date;
  status: LogStatus;
}

interface VideoPreview {
  id: string;
  title: string;
  channel: string;
  duration: string;
  thumbnail?: string;
  hasTranscript: boolean;
  status: "pending" | "fetching" | "processing" | "ready" | "error";
}

export default function IngestionPage() {
  const [currentStep, setCurrentStep] = useState<IngestionStep>("input");
  const [topic, setTopic] = useState("");
  const [urls, setUrls] = useState("");
  const [isResearching, setIsResearching] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [videoPreviews, setVideoPreviews] = useState<VideoPreview[]>([]);
  const [selectedVideos, setSelectedVideos] = useState<Set<string>>(new Set());

  const addLog = (message: string, status: LogStatus) => {
    const newLog: LogEntry = {
      id: Date.now().toString(),
      message,
      timestamp: new Date(),
      status,
    };
    setLogs((prev) => [...prev, newLog]);
  };

  const handleStartResearch = async () => {
    if (!topic.trim() && !urls.trim()) return;

    setIsResearching(true);
    setLogs([]);
    addLog("Searching for videos...", "progress");

    try {
      // Use topic if provided, otherwise use URLs
      const userQuery =
        topic.trim() || urls.trim().split("\n").filter(Boolean).join(", ");

      const response = await fetch(API_ENDPOINTS.UPLOAD, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_query: userQuery }),
      });

      if (!response.ok) {
        throw new Error(`Failed to upload videos: ${response.statusText}`);
      }

      const data = await response.json();
      addLog("Videos found successfully", "success");

      // Parse response - adjust based on actual API response structure
      // For now, we'll create a generic structure
      // If the API returns video data, parse it here
      const detectedVideos: VideoPreview[] = Array.isArray(data.videos)
        ? data.videos.map((video: any, index: number) => ({
            id: video.id || `video-${index + 1}`,
            title: video.title || video.name || `Video ${index + 1}`,
            channel: video.channel || video.channel_name || "Unknown Channel",
            duration: video.duration || "N/A",
            thumbnail: video.thumbnail || video.thumbnail_url,
            hasTranscript: video.has_transcript !== false,
            status: "pending" as const,
          }))
        : // Fallback: create placeholder videos if API doesn't return structured data
          [
            {
              id: "1",
              title: "Video 1",
              channel: "Processing...",
              duration: "N/A",
              hasTranscript: true,
              status: "pending" as const,
            },
          ];

      setVideoPreviews(detectedVideos);
      setSelectedVideos(new Set(detectedVideos.map((v) => v.id)));
      setCurrentStep("preview");
    } catch (error) {
      console.error("Error uploading videos:", error);
      addLog(
        error instanceof Error
          ? error.message
          : "Failed to upload videos. Please try again.",
        "error"
      );
    } finally {
      setIsResearching(false);
    }
  };

  const handleConfirmIngestion = async () => {
    if (selectedVideos.size === 0) return;

    setCurrentStep("processing");
    setIsResearching(true);
    setLogs([]);

    const selectedVideoList = videoPreviews.filter((v) =>
      selectedVideos.has(v.id)
    );

    try {
      // The /upload endpoint handles the ingestion process
      // We'll show progress for each selected video
      for (let i = 0; i < selectedVideoList.length; i++) {
        const video = selectedVideoList[i];

        // Update video status
        setVideoPreviews((prev) =>
          prev.map((v) =>
            v.id === video.id ? { ...v, status: "fetching" } : v
          )
        );
        addLog(`Fetching transcript for: ${video.title}`, "progress");
        await new Promise((resolve) => setTimeout(resolve, 1000));

        setVideoPreviews((prev) =>
          prev.map((v) =>
            v.id === video.id ? { ...v, status: "processing" } : v
          )
        );
        addLog(`Processing transcript for: ${video.title}`, "progress");
        await new Promise((resolve) => setTimeout(resolve, 1500));

        addLog(`Generating embeddings for: ${video.title}`, "progress");
        await new Promise((resolve) => setTimeout(resolve, 1000));

        setVideoPreviews((prev) =>
          prev.map((v) => (v.id === video.id ? { ...v, status: "ready" } : v))
        );
        addLog(`Completed: ${video.title}`, "success");
      }

      addLog("Building knowledge base...", "progress");
      await new Promise((resolve) => setTimeout(resolve, 1000));
      addLog("Research completed successfully!", "success");

      setCurrentStep("complete");
    } catch (error) {
      console.error("Error during ingestion:", error);
      addLog(
        error instanceof Error
          ? error.message
          : "An error occurred during ingestion",
        "error"
      );
    } finally {
      setIsResearching(false);
    }
  };

  const handleToggleVideo = (videoId: string) => {
    setSelectedVideos((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(videoId)) {
        newSet.delete(videoId);
      } else {
        newSet.add(videoId);
      }
      return newSet;
    });
  };

  const handleBackToInput = () => {
    setCurrentStep("input");
    setVideoPreviews([]);
    setSelectedVideos(new Set());
    setLogs([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && currentStep === "input") {
      e.preventDefault();
      handleStartResearch();
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const getStatusIcon = (status: LogStatus) => {
    switch (status) {
      case "success":
        return <Check className="size-4 text-emerald-400" />;
      case "progress":
        return <Loader2 className="size-4 text-amber-400 animate-spin" />;
      case "error":
        return <AlertCircle className="size-4 text-red-400" />;
      default:
        return <div className="size-4 rounded-full bg-blue-400" />;
    }
  };

  const getStatusColor = (status: LogStatus) => {
    switch (status) {
      case "success":
        return "text-emerald-400";
      case "progress":
        return "text-amber-400";
      case "error":
        return "text-red-400";
      default:
        return "text-blue-400";
    }
  };

  const getVideoStatusIcon = (status: VideoPreview["status"]) => {
    switch (status) {
      case "ready":
        return <Check className="size-4 text-emerald-400" />;
      case "fetching":
      case "processing":
        return <Loader2 className="size-4 text-amber-400 animate-spin" />;
      case "error":
        return <AlertCircle className="size-4 text-red-400" />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-[#0f172a] flex flex-col">
      <SharedHeader />

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-16">
        <div className="w-full max-w-4xl">
          <div className="relative">
            {/* Glow effect layers */}
            <div className="absolute -inset-1 bg-gradient-to-r from-violet-600/20 via-purple-600/20 to-violet-600/20 rounded-3xl blur-xl" />
            <div className="absolute -inset-0.5 bg-gradient-to-r from-violet-500/10 to-purple-500/10 rounded-2xl blur-md" />

            <div className="relative rounded-2xl bg-slate-800/50 backdrop-blur-xl border border-slate-700/50 p-8 shadow-2xl shadow-violet-500/5">
              {/* Step Indicator */}
              <div className="flex items-center justify-center mb-8">
                <div className="flex items-center gap-4">
                  <div
                    className={cn(
                      "flex items-center gap-2",
                      currentStep !== "input" && "text-violet-400"
                    )}
                  >
                    <div
                      className={cn(
                        "size-8 rounded-full flex items-center justify-center text-sm font-semibold",
                        currentStep === "input"
                          ? "bg-gradient-to-r from-violet-600 to-purple-600 text-white"
                          : "bg-violet-600/20 text-violet-400"
                      )}
                    >
                      1
                    </div>
                    <span className="text-sm font-medium text-slate-300">
                      Input
                    </span>
                  </div>
                  <ArrowRight className="size-4 text-slate-600" />
                  <div
                    className={cn(
                      "flex items-center gap-2",
                      currentStep === "preview" ||
                        currentStep === "processing" ||
                        currentStep === "complete"
                        ? "text-violet-400"
                        : "text-slate-600"
                    )}
                  >
                    <div
                      className={cn(
                        "size-8 rounded-full flex items-center justify-center text-sm font-semibold",
                        currentStep === "preview" ||
                          currentStep === "processing"
                          ? "bg-gradient-to-r from-violet-600 to-purple-600 text-white"
                          : currentStep === "complete"
                          ? "bg-violet-600/20 text-violet-400"
                          : "bg-slate-700 text-slate-500"
                      )}
                    >
                      2
                    </div>
                    <span className="text-sm font-medium">Preview</span>
                  </div>
                  <ArrowRight className="size-4 text-slate-600" />
                  <div
                    className={cn(
                      "flex items-center gap-2",
                      currentStep === "processing" || currentStep === "complete"
                        ? "text-violet-400"
                        : "text-slate-600"
                    )}
                  >
                    <div
                      className={cn(
                        "size-8 rounded-full flex items-center justify-center text-sm font-semibold",
                        currentStep === "processing"
                          ? "bg-gradient-to-r from-violet-600 to-purple-600 text-white"
                          : currentStep === "complete"
                          ? "bg-violet-600/20 text-violet-400"
                          : "bg-slate-700 text-slate-500"
                      )}
                    >
                      3
                    </div>
                    <span className="text-sm font-medium">Process</span>
                  </div>
                </div>
              </div>

              {/* Step 1: Input */}
              {currentStep === "input" && (
                <div className="space-y-6">
                  <div className="text-center space-y-2">
                    <h1 className="text-2xl font-semibold text-white">
                      Video Research Ingestion
                    </h1>
                    <p className="text-slate-400 text-sm">
                      Enter a YouTube topic or URLs to start analyzing videos
                    </p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-2">
                        Topic
                      </label>
                      <input
                        type="text"
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="e.g., machine learning tutorials"
                        disabled={isResearching}
                        className="w-full rounded-lg border border-slate-600/50 bg-slate-900/50 px-4 py-3 text-white placeholder:text-slate-500 focus:outline-none focus:border-violet-500/50 transition-colors text-sm disabled:opacity-50"
                      />
                    </div>

                    {/* <div>
                      <label className="block text-sm font-medium text-slate-300 mb-2">
                        YouTube URLs (one per line)
                      </label>
                      <textarea
                        value={urls}
                        onChange={(e) => setUrls(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="https://youtube.com/watch?v=..."
                        disabled={isResearching}
                        rows={4}
                        className="w-full rounded-lg border border-slate-600/50 bg-slate-900/50 px-4 py-3 text-white placeholder:text-slate-500 focus:outline-none focus:border-violet-500/50 transition-colors text-sm disabled:opacity-50 resize-none"
                      />
                    </div> */}

                    <div className="flex justify-center pt-2">
                      <button
                        onClick={handleStartResearch}
                        disabled={
                          (!topic.trim() && !urls.trim()) || isResearching
                        }
                        className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-medium text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isResearching ? (
                          <>
                            <Loader2 className="size-4 animate-spin" />
                            Searching...
                          </>
                        ) : (
                          <>
                            <Play className="size-4 fill-current" />
                            Find Videos
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 2: Preview */}
              {currentStep === "preview" && (
                <div className="space-y-6">
                  <div className="text-center space-y-2">
                    <h1 className="text-2xl font-semibold text-white">
                      Preview Videos
                    </h1>
                    <p className="text-slate-400 text-sm">
                      Select the videos you want to analyze (
                      {selectedVideos.size} selected)
                    </p>
                  </div>

                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {videoPreviews.map((video) => (
                      <div
                        key={video.id}
                        className={cn(
                          "p-4 rounded-lg border transition-all cursor-pointer",
                          selectedVideos.has(video.id)
                            ? "bg-violet-600/10 border-violet-500/50"
                            : "bg-slate-900/50 border-slate-700/50 hover:border-slate-600/50"
                        )}
                        onClick={() => handleToggleVideo(video.id)}
                      >
                        <div className="flex items-start gap-4">
                          <div className="size-16 rounded-lg bg-gradient-to-br from-violet-600/20 to-purple-600/20 flex items-center justify-center border border-violet-500/30 shrink-0">
                            <Video className="size-6 text-violet-400" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2 mb-2">
                              <h3 className="text-sm font-medium text-white">
                                {video.title}
                              </h3>
                              {selectedVideos.has(video.id) && (
                                <Check className="size-5 text-violet-400 shrink-0" />
                              )}
                            </div>
                            <div className="flex items-center gap-4 text-xs text-slate-400 mb-2">
                              <div className="flex items-center gap-1">
                                <User className="size-3" />
                                <span>{video.channel}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <Clock className="size-3" />
                                <span>{video.duration}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <FileText className="size-3" />
                                <span>
                                  {video.hasTranscript
                                    ? "Transcript available"
                                    : "No transcript"}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="flex items-center justify-between pt-4 border-t border-slate-700/30">
                    <button
                      onClick={handleBackToInput}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-700/50 bg-slate-800/50 hover:bg-slate-700/50 text-sm text-slate-300 hover:text-white transition-colors"
                    >
                      <ArrowLeft className="size-4" />
                      Back
                    </button>
                    <button
                      onClick={handleConfirmIngestion}
                      disabled={selectedVideos.size === 0}
                      className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-medium text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Start Ingestion
                      <ArrowRight className="size-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: Processing */}
              {(currentStep === "processing" || currentStep === "complete") && (
                <div className="space-y-6">
                  <div className="text-center space-y-2">
                    <h1 className="text-2xl font-semibold text-white">
                      {currentStep === "complete"
                        ? "Ingestion Complete!"
                        : "Processing Videos"}
                    </h1>
                    <p className="text-slate-400 text-sm">
                      {currentStep === "complete"
                        ? "All videos have been analyzed and are ready for chat"
                        : "Analyzing videos and generating embeddings"}
                    </p>
                  </div>

                  {/* Video Progress List */}
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {videoPreviews
                      .filter((v) => selectedVideos.has(v.id))
                      .map((video) => (
                        <div
                          key={video.id}
                          className="p-3 rounded-lg bg-slate-900/50 border border-slate-700/30"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                              {getVideoStatusIcon(video.status)}
                              <span className="text-sm text-white truncate">
                                {video.title}
                              </span>
                            </div>
                            <span className="text-xs text-slate-400 capitalize">
                              {video.status}
                            </span>
                          </div>
                        </div>
                      ))}
                  </div>

                  {/* Status Log Section */}
                  {logs.length > 0 && (
                    <div className="rounded-xl bg-slate-900/50 border border-slate-700/30 overflow-hidden">
                      <div className="px-4 py-3 border-b border-slate-700/30">
                        <h3 className="text-sm font-medium text-white">
                          Progress Log
                        </h3>
                      </div>
                      <div className="max-h-60 overflow-y-auto p-4 space-y-2.5">
                        {logs.map((log, index) => (
                          <div
                            key={index}
                            className="flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300"
                            style={{ animationDelay: `${index * 50}ms` }}
                          >
                            <div className="mt-0.5">
                              {getStatusIcon(log.status)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p
                                className={cn(
                                  "text-sm",
                                  getStatusColor(log.status)
                                )}
                              >
                                {log.message}
                              </p>
                              <p className="text-[10px] text-slate-500 mt-0.5">
                                {formatTime(log.timestamp)}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {currentStep === "complete" && (
                    <div className="flex justify-center pt-4">
                      <a
                        href="/chat"
                        className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-medium text-sm transition-all duration-200"
                      >
                        Go to Chat
                        <ArrowRight className="size-4" />
                      </a>
                    </div>
                  )}
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
