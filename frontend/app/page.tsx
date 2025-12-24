"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Play,
  MessageSquare,
  Mic,
  Video,
  Brain,
  Search,
  Zap,
  Lock,
  Sparkles,
} from "lucide-react";
import { SharedHeader } from "@/components/shared-header";
import { SharedFooter } from "@/components/shared-footer";
import { cn } from "@/lib/utils";

interface WaveformBar {
  height: number;
  animationDelay: number;
  animationDuration: number;
}

export default function LandingPage() {
  const [waveformBars, setWaveformBars] = useState<WaveformBar[]>([]);

  // Generate random values only on client to avoid hydration mismatch
  useEffect(() => {
    setWaveformBars(
      Array.from({ length: 7 }, (_, i) => ({
        height: 20 + Math.random() * 30,
        animationDelay: i * 100,
        animationDuration: 800 + Math.random() * 400,
      }))
    );
  }, []);
  return (
    <div className="min-h-screen bg-[#0f172a] flex flex-col">
      <SharedHeader />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative px-4 py-20 md:py-32 overflow-hidden">
          {/* Background Effects */}
          <div className="absolute inset-0 bg-gradient-to-b from-violet-900/20 via-transparent to-transparent" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(139,92,246,0.1),transparent_50%)]" />

          <div className="relative max-w-7xl mx-auto">
            <div className="text-center space-y-8">
              {/* Headline */}
              <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold text-white leading-tight">
                Talk to YouTube.
                <br />
                <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-violet-400 bg-clip-text text-transparent">
                  Not just watch it.
                </span>
              </h1>

              {/* Subheading */}
              <p className="text-lg md:text-xl text-slate-300 max-w-2xl mx-auto leading-relaxed">
                Autovoyce analyzes videos, remembers context, and lets you ask
                questions via chat or voice.
              </p>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
                <Link
                  href="/ingestion"
                  className="inline-flex items-center gap-2 px-8 py-4 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-semibold text-base transition-all duration-200 shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/30 hover:scale-105"
                >
                  Start Researching
                  <ArrowRight className="size-5" />
                </Link>
                <Link
                  href="#how-it-works"
                  className="inline-flex items-center gap-2 px-8 py-4 rounded-full border border-slate-600/50 bg-slate-800/50 backdrop-blur-sm hover:bg-slate-700/50 text-white font-semibold text-base transition-all duration-200"
                >
                  See How It Works
                  <Play className="size-5" />
                </Link>
              </div>

              {/* Visual: Chat bubbles and video cards */}
              <div className="relative mt-16 h-64 md:h-80 flex items-center justify-center">
                <div className="absolute inset-0 flex items-center justify-center">
                  {/* Video Card */}
                  <div className="relative w-48 md:w-64 h-32 md:h-40 rounded-xl bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700/50 shadow-2xl overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-violet-600/20 to-purple-600/20" />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Video className="size-12 md:size-16 text-violet-400/50" />
                    </div>
                    <div className="absolute bottom-0 left-0 right-0 p-3 bg-slate-900/80 backdrop-blur-sm">
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full animate-pulse"
                          style={{ width: "60%" }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Chat Bubbles */}
                <div className="absolute top-8 left-8 md:left-16 animate-in fade-in slide-in-from-bottom-4 duration-700">
                  <div className="bg-slate-800/90 backdrop-blur-sm border border-slate-700/50 rounded-2xl px-4 py-3 shadow-xl">
                    <p className="text-sm text-white">
                      What are the key points?
                    </p>
                  </div>
                </div>
                <div className="absolute top-24 right-8 md:right-16 animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-300">
                  <div className="bg-gradient-to-r from-violet-600 to-purple-600 rounded-2xl px-4 py-3 shadow-xl">
                    <p className="text-sm text-white">
                      Based on the analysis...
                    </p>
                  </div>
                </div>
                <div className="absolute bottom-8 left-12 md:left-24 animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-500">
                  <div className="bg-slate-800/90 backdrop-blur-sm border border-slate-700/50 rounded-2xl px-4 py-3 shadow-xl">
                    <p className="text-sm text-white">Can you explain this?</p>
                  </div>
                </div>

                {/* Voice Waveform */}
                <div className="absolute bottom-4 right-12 md:right-24 flex items-center gap-1">
                  {waveformBars.length > 0
                    ? waveformBars.map((bar, i) => (
                        <div
                          key={i}
                          className="w-1 bg-gradient-to-t from-violet-500 to-purple-500 rounded-full animate-pulse"
                          style={{
                            height: `${bar.height}px`,
                            animationDelay: `${bar.animationDelay}ms`,
                            animationDuration: `${bar.animationDuration}ms`,
                          }}
                        />
                      ))
                    : // Fallback during SSR/hydration
                      Array.from({ length: 7 }, (_, i) => (
                        <div
                          key={i}
                          className="w-1 bg-gradient-to-t from-violet-500 to-purple-500 rounded-full animate-pulse"
                          style={{
                            height: "25px",
                            animationDelay: `${i * 100}ms`,
                            animationDuration: "1000ms",
                          }}
                        />
                      ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section
          id="how-it-works"
          className="relative px-4 py-20 md:py-32 bg-slate-900/30"
        >
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
                How It Works
              </h2>
              <p className="text-slate-400 text-lg max-w-2xl mx-auto">
                Three simple steps to turn any YouTube topic into a research
                conversation
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8 md:gap-12">
              {/* Step 1 */}
              <div className="relative group">
                <div className="relative p-8 rounded-2xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 hover:border-violet-500/50 transition-all duration-300 h-full">
                  <div className="absolute -top-4 -left-4 size-12 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                    1
                  </div>
                  <div className="mt-4 space-y-4">
                    <div className="size-16 rounded-xl bg-gradient-to-br from-violet-600/20 to-purple-600/20 flex items-center justify-center border border-violet-500/30">
                      <Video className="size-8 text-violet-400" />
                    </div>
                    <h3 className="text-xl font-semibold text-white">
                      Enter a Topic or Video
                    </h3>
                    <p className="text-slate-400 leading-relaxed">
                      Provide YouTube URLs or search for a topic. Autovoyce will
                      find and analyze relevant videos.
                    </p>
                  </div>
                </div>
              </div>

              {/* Step 2 */}
              <div className="relative group">
                <div className="relative p-8 rounded-2xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 hover:border-violet-500/50 transition-all duration-300 h-full">
                  <div className="absolute -top-4 -left-4 size-12 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                    2
                  </div>
                  <div className="mt-4 space-y-4">
                    <div className="size-16 rounded-xl bg-gradient-to-br from-violet-600/20 to-purple-600/20 flex items-center justify-center border border-violet-500/30">
                      <Brain className="size-8 text-violet-400" />
                    </div>
                    <h3 className="text-xl font-semibold text-white">
                      AI Analyzes Everything
                    </h3>
                    <p className="text-slate-400 leading-relaxed">
                      Transcripts, context, embeddings, and summaries are
                      extracted and stored for deep understanding.
                    </p>
                  </div>
                </div>
              </div>

              {/* Step 3 */}
              <div className="relative group">
                <div className="relative p-8 rounded-2xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 hover:border-violet-500/50 transition-all duration-300 h-full">
                  <div className="absolute -top-4 -left-4 size-12 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                    3
                  </div>
                  <div className="mt-4 space-y-4">
                    <div className="size-16 rounded-xl bg-gradient-to-br from-violet-600/20 to-purple-600/20 flex items-center justify-center border border-violet-500/30">
                      <MessageSquare className="size-8 text-violet-400" />
                    </div>
                    <h3 className="text-xl font-semibold text-white">
                      Ask Anything
                    </h3>
                    <p className="text-slate-400 leading-relaxed">
                      Use text chat or voice chat to ask contextual questions
                      across all analyzed videos.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Key Features Grid */}
        <section className="relative px-4 py-20 md:py-32">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
                Key Features
              </h2>
              <p className="text-slate-400 text-lg max-w-2xl mx-auto">
                Everything you need for deep video research
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[
                {
                  icon: Video,
                  title: "Multi-video context understanding",
                  desc: "Analyze multiple videos simultaneously with cross-video reasoning",
                },
                {
                  icon: Brain,
                  title: "Persistent memory per topic",
                  desc: "Your research context is saved and accessible anytime",
                },
                {
                  icon: Mic,
                  title: "Voice-based AI conversation",
                  desc: "Natural voice interactions for hands-free research",
                },
                {
                  icon: Search,
                  title: "Cross-video reasoning",
                  desc: "Ask questions that span across all analyzed content",
                },
                {
                  icon: Zap,
                  title: "Fast ingestion & retrieval",
                  desc: "Quick processing and instant access to insights",
                },
                {
                  icon: Lock,
                  title: "Privacy-friendly",
                  desc: "No public sharing - your research stays private",
                },
              ].map((feature, index) => (
                <div
                  key={index}
                  className="p-6 rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 hover:border-violet-500/50 transition-all duration-300 group"
                >
                  <div className="size-12 rounded-lg bg-gradient-to-br from-violet-600/20 to-purple-600/20 flex items-center justify-center border border-violet-500/30 mb-4 group-hover:scale-110 transition-transform">
                    <feature.icon className="size-6 text-violet-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {feature.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Example Use Cases */}
        <section className="relative px-4 py-20 md:py-32 bg-slate-900/30">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
                Perfect For
              </h2>
              <p className="text-slate-400 text-lg max-w-2xl mx-auto">
                Whether you're researching, learning, or creating content
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[
                {
                  title: "Researchers",
                  desc: "Deep dive into academic and technical video content",
                  color: "from-blue-600/20 to-cyan-600/20",
                },
                {
                  title: "Students",
                  desc: "Study complex topics across multiple educational videos",
                  color: "from-emerald-600/20 to-teal-600/20",
                },
                {
                  title: "Founders",
                  desc: "Research market trends, competitors, and industry insights",
                  color: "from-amber-600/20 to-orange-600/20",
                },
                {
                  title: "Content Creators",
                  desc: "Analyze successful content strategies and techniques",
                  color: "from-rose-600/20 to-pink-600/20",
                },
                {
                  title: "Journalists",
                  desc: "Fact-check and gather information from video sources",
                  color: "from-indigo-600/20 to-purple-600/20",
                },
              ].map((useCase, index) => (
                <div
                  key={index}
                  className="p-6 rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 hover:border-violet-500/50 transition-all duration-300"
                >
                  <div
                    className={cn(
                      "size-12 rounded-lg bg-gradient-to-br",
                      useCase.color,
                      "flex items-center justify-center mb-4"
                    )}
                  >
                    <Sparkles className="size-6 text-violet-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">
                    {useCase.title}
                  </h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {useCase.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="relative px-4 py-20 md:py-32">
          <div className="max-w-4xl mx-auto text-center">
            <div className="relative p-12 md:p-16 rounded-3xl bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-xl border border-slate-700/50 shadow-2xl">
              {/* Glow effect */}
              <div className="absolute -inset-1 bg-gradient-to-r from-violet-600/20 via-purple-600/20 to-violet-600/20 rounded-3xl blur-xl" />

              <div className="relative space-y-6">
                <h2 className="text-3xl md:text-5xl font-bold text-white">
                  Turn videos into conversations.
                </h2>
                <p className="text-lg text-slate-300 max-w-2xl mx-auto">
                  Start your research journey today. Ask questions, get
                  insights, and unlock the knowledge hidden in video content.
                </p>
                <Link
                  href="/chat"
                  className="inline-flex items-center gap-2 px-8 py-4 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-semibold text-base transition-all duration-200 shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/30 hover:scale-105"
                >
                  Start Chatting
                  <ArrowRight className="size-5" />
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <SharedFooter />
    </div>
  );
}
