"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Run } from "@/types";
import { RunList } from "@/components/RunList";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Loader2, Search } from "lucide-react";

export default function Home() {
    const router = useRouter();
    const [runs, setRuns] = useState<Run[]>([]);
    const [isLoadingRuns, setIsLoadingRuns] = useState(true);
    const [isCreating, setIsCreating] = useState(false);

    // Form state
    const [mode, setMode] = useState<"light" | "deep">("light");
    const [maxInsights, setMaxInsights] = useState(20);

    useEffect(() => {
        loadRuns();
    }, []);

    const loadRuns = async () => {
        try {
            const data = await api.getRuns();
            // Sort by created_at desc
            const sorted = data.sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setRuns(sorted);
        } catch (error) {
            console.error("Failed to load runs", error);
        } finally {
            setIsLoadingRuns(false);
        }
    };

    const handleCreateRun = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsCreating(true);
        try {
            const res = await api.createRun({ mode, max_insights: maxInsights });
            router.push(`/runs/${res.run_id}`);
        } catch (error) {
            console.error("Failed to create run", error);
            setIsCreating(false);
        }
    };

    return (
        <div className="space-y-12">
            <section className="max-w-2xl mx-auto">
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">
                        Start a new analysis
                    </h1>
                    <p className="text-slate-500">
                        Scan the web for unmet needs and emerging trends.
                    </p>
                </div>

                <Card className="border-slate-200 shadow-lg shadow-slate-200/50">
                    <CardHeader>
                        <CardTitle>New Scan</CardTitle>
                        <CardDescription>Configure your analysis parameters</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleCreateRun} className="space-y-6">
                            <div className="grid grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                        Mode
                                    </label>
                                    <Select
                                        value={mode}
                                        onChange={(e) => setMode(e.target.value as "light" | "deep")}
                                    >
                                        <option value="light">Light (Fast)</option>
                                        <option value="deep">Deep (Comprehensive)</option>
                                    </Select>
                                    <p className="text-xs text-slate-500">
                                        Light scans are faster but less detailed. Deep scans analyze more sources.
                                    </p>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                        Max Insights
                                    </label>
                                    <Input
                                        type="number"
                                        min={1}
                                        max={100}
                                        value={maxInsights}
                                        onChange={(e) => setMaxInsights(parseInt(e.target.value))}
                                    />
                                    <p className="text-xs text-slate-500">
                                        Maximum number of insights to generate.
                                    </p>
                                </div>
                            </div>

                            <Button type="submit" className="w-full" disabled={isCreating}>
                                {isCreating ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Starting Scan...
                                    </>
                                ) : (
                                    <>
                                        <Search className="mr-2 h-4 w-4" />
                                        Run Scan
                                    </>
                                )}
                            </Button>
                        </form>
                    </CardContent>
                </Card>
            </section>

            <section>
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-semibold text-slate-900">Recent Runs</h2>
                    <Button variant="ghost" size="sm" asChild>
                        <Link href="/runs">View all</Link>
                    </Button>
                </div>
                <RunList runs={runs.slice(0, 5)} isLoading={isLoadingRuns} />
            </section>
        </div>
    );
}
