"use client";

import { useEffect, useState, use } from "react";
import { api } from "@/lib/api";
import { Insight, SolutionType } from "@/types";
import { InsightCard } from "@/components/InsightCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Filter, SlidersHorizontal, CheckCircle, XCircle, Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

// Solution type labels for dropdown
const SOLUTION_TYPE_OPTIONS: { value: SolutionType | "all"; label: string }[] = [
    { value: "all", label: "All Types" },
    { value: "saas_b2b", label: "SaaS B2B" },
    { value: "saas_b2c", label: "SaaS B2C" },
    { value: "tooling_dev", label: "Dev Tools" },
    { value: "api_product", label: "API Product" },
    { value: "service_only", label: "Service Only" },
    { value: "content_only", label: "Content Only" },
    { value: "hardware_required", label: "Hardware" },
    { value: "regulation_policy", label: "Regulation" },
    { value: "impractical_unclear", label: "Unclear" },
];

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const [insights, setInsights] = useState<Insight[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Filters
    const [minPain, setMinPain] = useState(0);
    const [minFit, setMinFit] = useState(0);
    const [selectedSector, setSelectedSector] = useState("all");

    // New Step 5 filters
    const [saasViableOnly, setSaasViableOnly] = useState(false);
    const [showDuplicates, setShowDuplicates] = useState(false);
    const [selectedSolutionType, setSelectedSolutionType] = useState<SolutionType | "all">("all");
    const [minRevenuePotential, setMinRevenuePotential] = useState(0);

    useEffect(() => {
        loadInsights();
    }, [id]);

    const loadInsights = async () => {
        try {
            // Load all insights (we'll filter client-side for responsiveness)
            const data = await api.getRunInsights(id, { include_duplicates: true });
            setInsights(data);
        } catch (error) {
            console.error("Failed to load insights", error);
        } finally {
            setIsLoading(false);
        }
    };

    const sectors = Array.from(new Set(insights.map(i => i.sector).filter(Boolean))) as string[];
    const solutionTypes = Array.from(new Set(insights.map(i => i.solution_type).filter(Boolean))) as SolutionType[];

    const filteredInsights = insights.filter(insight => {
        // Existing filters
        if (selectedSector !== "all" && insight.sector !== selectedSector) return false;
        if ((insight.pain_score_final || 0) < minPain) return false;
        if ((insight.founder_fit_score || 0) < minFit) return false;

        // New Step 5 filters
        if (saasViableOnly && !insight.saas_viable) return false;
        if (!showDuplicates && insight.is_historical_duplicate) return false;
        if (selectedSolutionType !== "all" && insight.solution_type !== selectedSolutionType) return false;
        if ((insight.recurring_revenue_potential || 0) < minRevenuePotential) return false;

        return true;
    });

    // Stats for filter summary
    const saasViableCount = insights.filter(i => i.saas_viable).length;
    const duplicateCount = insights.filter(i => i.is_historical_duplicate).length;
    const withProductAngleCount = insights.filter(i => i.product_angle_title).length;

    return (
        <div className="space-y-8">
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" asChild>
                    <Link href="/runs">
                        <ArrowLeft className="h-4 w-4" />
                    </Link>
                </Button>
                <div className="flex-1">
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900">Run Analysis</h1>
                    <p className="text-slate-500 text-sm">ID: {id}</p>
                </div>
                {/* Quick stats */}
                <div className="hidden md:flex items-center gap-3 text-xs">
                    <span className="px-2 py-1 bg-slate-100 rounded-full">
                        {insights.length} total
                    </span>
                    <span className="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full">
                        {saasViableCount} SaaS viable
                    </span>
                    <span className="px-2 py-1 bg-amber-50 text-amber-700 rounded-full">
                        {withProductAngleCount} with ideas
                    </span>
                    {duplicateCount > 0 && (
                        <span className="px-2 py-1 bg-slate-50 text-slate-500 rounded-full">
                            {duplicateCount} duplicates
                        </span>
                    )}
                </div>
            </div>

            {/* Filters */}
            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                        <Filter className="h-4 w-4" />
                        Filters
                    </div>
                    <span className="text-xs text-slate-500">
                        {filteredInsights.length} of {insights.length} insights
                    </span>
                </div>

                {/* Quick toggles row */}
                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={() => setSaasViableOnly(!saasViableOnly)}
                        className={cn(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                            saasViableOnly
                                ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                        )}
                    >
                        <CheckCircle className="w-3.5 h-3.5" />
                        SaaS Viable Only
                    </button>
                    <button
                        onClick={() => setShowDuplicates(!showDuplicates)}
                        className={cn(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                            showDuplicates
                                ? "bg-blue-100 text-blue-800 border border-blue-300"
                                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                        )}
                    >
                        {showDuplicates ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                        {showDuplicates ? "Showing Duplicates" : "Hide Duplicates"}
                    </button>
                </div>

                {/* Main filters grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
                        <label className="text-xs text-slate-500">Solution Type</label>
                        <Select
                            value={selectedSolutionType}
                            onChange={(e) => setSelectedSolutionType(e.target.value as SolutionType | "all")}
                        >
                            {SOLUTION_TYPE_OPTIONS.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs text-slate-500 flex justify-between">
                            <span>Min Pain Score</span>
                            <span className="font-medium">{minPain}</span>
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
                            <span className="font-medium">{minFit}</span>
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

                {/* Revenue potential slider */}
                <div className="pt-2 border-t border-slate-100">
                    <div className="max-w-md space-y-2">
                        <label className="text-xs text-slate-500 flex justify-between">
                            <span>Min Recurring Revenue Potential</span>
                            <span className="font-medium">{minRevenuePotential}/10</span>
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="10"
                            step="1"
                            value={minRevenuePotential}
                            onChange={(e) => setMinRevenuePotential(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
                        />
                    </div>
                </div>
            </div>

            {/* Results */}
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
                            <p>No insights match your filters.</p>
                            <p className="text-sm mt-1">Try adjusting your filter criteria.</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
