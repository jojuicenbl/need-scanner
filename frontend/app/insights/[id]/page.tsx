"use client";

import { useEffect, useState, use } from "react";
import { api } from "@/lib/api";
import { Insight, Exploration } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, ExternalLink, Sparkles, Loader2 } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

export default function InsightDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const [insight, setInsight] = useState<Insight | null>(null);
    const [explorations, setExplorations] = useState<Exploration[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isExploring, setIsExploring] = useState(false);

    useEffect(() => {
        loadData();
    }, [id]);

    const loadData = async () => {
        try {
            const [insightData, explorationsData] = await Promise.all([
                api.getInsight(id),
                api.getInsightExplorations(id).catch(() => []) // Handle 404 or empty list gracefully
            ]);
            setInsight(insightData);
            setExplorations(explorationsData);
        } catch (error) {
            console.error("Failed to load insight data", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleExplore = async () => {
        setIsExploring(true);
        try {
            const newExploration = await api.exploreInsight(id);
            setExplorations([newExploration, ...explorations]);
        } catch (error) {
            console.error("Failed to explore insight", error);
        } finally {
            setIsExploring(false);
        }
    };

    if (isLoading) {
        return (
            <div className="space-y-8 animate-pulse">
                <div className="h-8 w-1/3 bg-slate-200 rounded" />
                <div className="h-64 bg-slate-100 rounded" />
            </div>
        );
    }

    if (!insight) return <div>Insight not found</div>;

    return (
        <div className="space-y-8 max-w-4xl mx-auto">
            {/* Header */}
            <div className="space-y-4">
                <Button variant="ghost" size="sm" asChild className="-ml-2">
                    <Link href={insight.run_id ? `/runs/${insight.run_id}` : "/runs"}>
                        <ArrowLeft className="mr-2 h-4 w-4" /> Back
                    </Link>
                </Button>

                <div className="flex items-start justify-between gap-4">
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <Badge variant="outline" className="capitalize">{insight.sector?.replace(/_/g, " ")}</Badge>
                            <Badge variant="secondary">Rank #{insight.rank}</Badge>
                        </div>
                        <h1 className="text-3xl font-bold text-slate-900 leading-tight">
                            {insight.title}
                        </h1>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                        <div className="text-sm font-medium text-slate-500">Priority Score</div>
                        <div className="text-3xl font-bold text-slate-900">
                            {insight.priority_score_adjusted?.toFixed(1) || insight.priority_score.toFixed(1)}
                        </div>
                    </div>
                </div>
            </div>

            {/* Core Insight */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="md:col-span-2">
                    <CardHeader>
                        <CardTitle>The Problem</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <p className="text-lg text-slate-700 leading-relaxed">
                            {insight.problem}
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-slate-100">
                            <div>
                                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Persona</div>
                                <div className="font-medium">{insight.persona}</div>
                            </div>
                            <div className="md:col-span-2">
                                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Job To Be Done</div>
                                <div className="font-medium">{insight.jtbd}</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>MVP Concept</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-slate-700">{insight.mvp}</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Scores</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            <div>
                                <div className="flex justify-between text-sm mb-1">
                                    <span>Pain Level</span>
                                    <span className="font-medium">{insight.pain_score_final}/10</span>
                                </div>
                                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-slate-900"
                                        style={{ width: `${(insight.pain_score_final || 0) * 10}%` }}
                                    />
                                </div>
                            </div>
                            <div>
                                <div className="flex justify-between text-sm mb-1">
                                    <span>Founder Fit</span>
                                    <span className="font-medium">{insight.founder_fit_score}/10</span>
                                </div>
                                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-slate-900"
                                        style={{ width: `${(insight.founder_fit_score || 0) * 10}%` }}
                                    />
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Exploration Section */}
            <section className="space-y-6 pt-8 border-t border-slate-200">
                <div className="flex items-center justify-between">
                    <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <Sparkles className="h-6 w-6 text-purple-600" />
                        Deep Exploration
                    </h2>
                    <Button
                        onClick={handleExplore}
                        disabled={isExploring}
                        className="bg-purple-600 hover:bg-purple-700 text-white"
                    >
                        {isExploring ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Analyzing...
                            </>
                        ) : (
                            <>
                                <Sparkles className="mr-2 h-4 w-4" />
                                Explore Idea
                            </>
                        )}
                    </Button>
                </div>

                {explorations.length > 0 ? (
                    <div className="space-y-8">
                        {explorations.map((exp, i) => (
                            <Card key={exp.exploration_id || i} className="border-purple-100 bg-purple-50/30">
                                <CardContent className="p-8 prose prose-slate max-w-none">
                                    <ReactMarkdown>{exp.content}</ReactMarkdown>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-12 bg-slate-50 rounded-lg border border-dashed border-slate-200">
                        <Sparkles className="h-12 w-12 mx-auto text-slate-300 mb-4" />
                        <p className="text-slate-500">
                            No explorations yet. Click "Explore Idea" to generate a deep analysis including monetization, variants, and next steps.
                        </p>
                    </div>
                )}
            </section>

            {/* Sources */}
            {insight.examples && insight.examples.length > 0 && (
                <section className="pt-8 border-t border-slate-200">
                    <h3 className="text-lg font-semibold mb-4">Sources</h3>
                    <div className="grid gap-4">
                        {insight.examples.map((ex, i) => (
                            <a
                                key={i}
                                href={ex.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block p-4 bg-white border border-slate-200 rounded-lg hover:border-slate-400 transition-colors"
                            >
                                <div className="flex items-center justify-between">
                                    <span className="font-medium text-slate-900 truncate pr-4">{ex.title || "Untitled Source"}</span>
                                    <ExternalLink className="h-4 w-4 text-slate-400 flex-shrink-0" />
                                </div>
                                <div className="flex gap-4 mt-2 text-xs text-slate-500">
                                    <span className="capitalize">{ex.source}</span>
                                    {ex.score && <span>Score: {ex.score}</span>}
                                    {ex.comments_count && <span>Comments: {ex.comments_count}</span>}
                                </div>
                            </a>
                        ))}
                    </div>
                </section>
            )}
        </div>
    );
}
