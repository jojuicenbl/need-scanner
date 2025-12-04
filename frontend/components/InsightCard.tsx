import Link from "next/link";
import { Insight } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface InsightCardProps {
    insight: Insight;
}

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

    return (
        <Link href={`/insights/${insight.id}`}>
            <Card className="h-full hover:border-slate-400 transition-all hover:shadow-md cursor-pointer flex flex-col">
                <CardContent className="p-5 flex flex-col h-full">
                    <div className="flex items-start justify-between mb-3">
                        <Badge variant={getSectorColor(insight.sector)} className="capitalize">
                            {insight.sector?.replace(/_/g, " ") || "Unknown"}
                        </Badge>
                        <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                            <span className={cn(
                                "px-1.5 py-0.5 rounded",
                                (insight.pain_score_final || 0) > 7 ? "bg-red-50 text-red-700" : "bg-slate-100"
                            )}>
                                Pain {insight.pain_score_final || "?"}
                            </span>
                            <span className={cn(
                                "px-1.5 py-0.5 rounded",
                                (insight.founder_fit_score || 0) > 7 ? "bg-emerald-50 text-emerald-700" : "bg-slate-100"
                            )}>
                                Fit {insight.founder_fit_score || "?"}
                            </span>
                        </div>
                    </div>

                    <h3 className="font-semibold text-slate-900 mb-2 line-clamp-2 leading-tight">
                        {insight.title}
                    </h3>

                    <p className="text-sm text-slate-500 line-clamp-3 mb-4 flex-grow">
                        {insight.problem}
                    </p>

                    <div className="pt-4 border-t border-slate-100 mt-auto flex items-center justify-between text-xs text-slate-400">
                        <span>Rank #{insight.rank}</span>
                        <span>Priority {insight.priority_score_adjusted?.toFixed(1) || insight.priority_score.toFixed(1)}</span>
                    </div>
                </CardContent>
            </Card>
        </Link>
    );
}
