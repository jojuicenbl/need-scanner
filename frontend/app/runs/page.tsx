"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Run } from "@/types";
import { RunList } from "@/components/RunList";
import { Button } from "@/components/ui/button";

export default function RunsPage() {
    const [runs, setRuns] = useState<Run[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        loadRuns();
    }, []);

    const loadRuns = async () => {
        try {
            const data = await api.getRuns();
            const sorted = data.sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );
            setRuns(sorted);
        } catch (error) {
            console.error("Failed to load runs", error);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">All Runs</h1>
                    <p className="text-slate-500 mt-1">History of your market analysis scans.</p>
                </div>
                <Button asChild>
                    <Link href="/">New Scan</Link>
                </Button>
            </div>

            <RunList runs={runs} isLoading={isLoading} />
        </div>
    );
}
