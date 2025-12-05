import Link from "next/link";
import { Insight, SolutionType } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Lightbulb, Repeat, AlertTriangle } from "lucide-react";

interface InsightCardProps {
    insight: Insight;
}

// Human-readable labels for solution types
const SOLUTION_TYPE_LABELS: Record<SolutionType, string> = {
    saas_b2b: "SaaS B2B",
    saas_b2c: "SaaS B2C",
    tooling_dev: "Dev Tools",
    api_product: "API",
    service_only: "Service",
    content_only: "Content",
    hardware_required: "Hardware",
    regulation_policy: "Regulation",
    impractical_unclear: "Unclear",
};

// Complexity labels
const COMPLEXITY_LABELS: Record<number, string> = {
    1: "Weekend project",
    2: "1-3 months",
    3: "3+ months",
};

export function InsightCard({ insight }: InsightCardProps) {
    const getSectorColor = (sector?: string) => {
        if (!sector) return "secondary";
        const s = sector.toLowerCase();
        if (s.includes("dev") || s.includes("tech")) return "blue";
        if (s.includes("business") || s.includes("b2b")) return "purple";
        if (s.includes("consumer") || s.includes("b2c")) return "green";
        if (s.includes("health") || s.includes("med")) return "pink";
        return "secondary";
    };

    const isDuplicate = insight.is_historical_duplicate;
    const isSaasViable = insight.saas_viable;
    const hasProductAngle = Boolean(insight.product_angle_title);

    return (
        <Link href={`/insights/${insight.id}`}>
            <Card className={cn(
                "h-full hover:border-slate-400 transition-all hover:shadow-md cursor-pointer flex flex-col",
                isDuplicate && "opacity-60 border-dashed",
                isSaasViable && "ring-1 ring-emerald-200"
            )}>
                <CardContent className="p-5 flex flex-col h-full">
                    {/* Top row: Sector + Status badges */}
                    <div className="flex items-start justify-between mb-3 gap-2">
                        <div className="flex flex-wrap gap-1.5">
                            <Badge variant={getSectorColor(insight.sector)} className="capitalize">
                                {insight.sector?.replace(/_/g, " ") || "Unknown"}
                            </Badge>
                            {isSaasViable && (
                                <Badge variant="green" className="text-[10px]">
                                    SaaS Viable
                                </Badge>
                            )}
                            {isDuplicate && (
                                <Badge variant="secondary" className="text-[10px]">
                                    <Repeat className="w-3 h-3 mr-0.5" />
                                    Seen
                                </Badge>
                            )}
                        </div>
                        <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 shrink-0">
                            <span className={cn(
                                "px-1.5 py-0.5 rounded",
                                (insight.pain_score_final || 0) >= 7 ? "bg-red-50 text-red-700" : "bg-slate-100"
                            )}>
                                {insight.pain_score_final || "?"}
                            </span>
                            <span className={cn(
                                "px-1.5 py-0.5 rounded",
                                (insight.founder_fit_score || 0) >= 7 ? "bg-emerald-50 text-emerald-700" : "bg-slate-100"
                            )}>
                                {insight.founder_fit_score?.toFixed(0) || "?"}
                            </span>
                        </div>
                    </div>

                    {/* Title */}
                    <h3 className="font-semibold text-slate-900 mb-2 line-clamp-2 leading-tight">
                        {insight.title}
                    </h3>

                    {/* Product Angle (if available) */}
                    {hasProductAngle && (
                        <div className="flex items-start gap-2 mb-3 p-2 bg-amber-50 rounded-md border border-amber-100">
                            <Lightbulb className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                            <div className="min-w-0">
                                <p className="text-xs font-medium text-amber-800 truncate">
                                    {insight.product_angle_title}
                                </p>
                                {insight.product_pricing_hint && (
                                    <p className="text-[10px] text-amber-600">
                                        {insight.product_pricing_hint}
                                        {insight.product_complexity && (
                                            <span className="ml-1.5 opacity-75">
                                                ({COMPLEXITY_LABELS[insight.product_complexity] || "?"})
                                            </span>
                                        )}
                                    </p>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Problem description */}
                    <p className="text-sm text-slate-500 line-clamp-2 mb-4 flex-grow">
                        {insight.problem}
                    </p>

                    {/* Footer */}
                    <div className="pt-3 border-t border-slate-100 mt-auto">
                        <div className="flex items-center justify-between text-xs text-slate-400">
                            <div className="flex items-center gap-2">
                                <span>#{insight.rank}</span>
                                {insight.solution_type && (
                                    <span className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-500">
                                        {SOLUTION_TYPE_LABELS[insight.solution_type] || insight.solution_type}
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center gap-2">
                                {insight.recurring_revenue_potential && (
                                    <span className={cn(
                                        "px-1.5 py-0.5 rounded",
                                        insight.recurring_revenue_potential >= 7
                                            ? "bg-emerald-50 text-emerald-700"
                                            : insight.recurring_revenue_potential >= 5
                                            ? "bg-blue-50 text-blue-700"
                                            : "bg-slate-100 text-slate-500"
                                    )}>
                                        ${insight.recurring_revenue_potential.toFixed(0)}
                                    </span>
                                )}
                                <span className="font-medium">
                                    {(insight.priority_score_adjusted ?? insight.priority_score).toFixed(1)}
                                </span>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </Link>
    );
}
