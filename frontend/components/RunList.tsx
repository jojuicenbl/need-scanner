import Link from "next/link";
import { Run } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, Layers } from "lucide-react";

interface RunListProps {
    runs: Run[];
    isLoading?: boolean;
}

export function RunList({ runs, isLoading }: RunListProps) {
    if (isLoading) {
        return (
            <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-24 bg-slate-100 rounded-lg animate-pulse" />
                ))}
            </div>
        );
    }

    if (runs.length === 0) {
        return (
            <Card className="bg-slate-50 border-dashed">
                <CardContent className="flex flex-col items-center justify-center py-12 text-slate-500">
                    <Layers className="h-12 w-12 mb-4 opacity-20" />
                    <p>No runs found. Start a new scan!</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-4">
            {runs.map((run) => (
                <Link key={run.id} href={`/runs/${run.id}`}>
                    <Card className="hover:border-slate-400 transition-colors cursor-pointer group">
                        <CardContent className="p-4 flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="h-10 w-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 group-hover:bg-slate-200 transition-colors">
                                    <Layers className="h-5 w-5" />
                                </div>
                                <div>
                                    <div className="font-medium text-slate-900 flex items-center gap-2">
                                        Run {run.id.slice(0, 8)}
                                        {run.mode === "deep" && (
                                            <Badge variant="secondary" className="text-[10px] h-5 px-1.5">Deep</Badge>
                                        )}
                                    </div>
                                    <div className="text-sm text-slate-500 flex items-center gap-2 mt-0.5">
                                        <Calendar className="h-3 w-3" />
                                        {new Date(run.created_at).toLocaleDateString()}
                                        <span className="text-slate-300">•</span>
                                        {run.nb_insights} insights
                                    </div>
                                </div>
                            </div>
                            <div className="text-slate-400 group-hover:text-slate-600">
                                →
                            </div>
                        </CardContent>
                    </Card>
                </Link>
            ))}
        </div>
    );
}
