"use client";

import { useEffect, useState, use } from "react";
import { api } from "@/lib/api";
import { Insight } from "@/types";
import { InsightCard } from "@/components/InsightCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Filter, SlidersHorizontal } from "lucide-react";
import Link from "next/link";

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const [insights, setInsights] = useState<Insight[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Filters
    const [minPain, setMinPain] = useState(0);
    const [minFit, setMinFit] = useState(0);
    const [selectedSector, setSelectedSector] = useState("all");

    useEffect(() => {
        loadInsights();
    }, [id]);

    const loadInsights = async () => {
        try {
            const data = await api.getRunInsights(id);
            setInsights(data);
        } catch (error) {
            console.error("Failed to load insights", error);
        } finally {
            setIsLoading(false);
        }
    };

    const sectors = Array.from(new Set(insights.map(i => i.sector).filter(Boolean))) as string[];

    const filteredInsights = insights.filter(insight => {
        if (selectedSector !== "all" && insight.sector !== selectedSector) return false;
        if ((insight.pain_score_final || 0) < minPain) return false;
        if ((insight.founder_fit_score || 0) < minFit) return false;
        return true;
    });

    return (
        <div className="space-y-8">
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" asChild>
                    <Link href="/runs">
                        <ArrowLeft className="h-4 w-4" />
                    </Link>
                </Button>
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900">Run Analysis</h1>
                    <p className="text-slate-500 text-sm">ID: {id}</p>
                </div>
            </div>

            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm space-y-4">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-900 mb-2">
                    <Filter className="h-4 w-4" />
                    Filters
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                        <label className="text-xs text-slate-500">Sector</label>
                        <Select
                            value={selectedSector}
                            onChange={(e) => setSelectedSector(e.target.value)}
                        >
                            <option value="all">All Sectors</option>
                            {sectors.map(s => (
                                <option key={s} value={s}>{s?.replace(/_/g, " ")}</option>
                            ))}
                        </Select>
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs text-slate-500 flex justify-between">
                            <span>Min Pain Score</span>
                            <span>{minPain}</span>
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="10"
                            step="1"
                            value={minPain}
                            onChange={(e) => setMinPain(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-slate-900"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs text-slate-500 flex justify-between">
                            <span>Min Founder Fit</span>
                            <span>{minFit}</span>
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="10"
                            step="1"
                            value={minFit}
                            onChange={(e) => setMinFit(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-slate-900"
                        />
                    </div>
                </div>
            </div>

            {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="h-64 bg-slate-100 rounded-lg animate-pulse" />
                    ))}
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredInsights.map(insight => (
                        <InsightCard key={insight.id} insight={insight} />
                    ))}
                    {filteredInsights.length === 0 && (
                        <div className="col-span-full text-center py-12 text-slate-500">
                            No insights match your filters.
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
