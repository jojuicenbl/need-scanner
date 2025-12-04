import { Run, Insight, CreateRunPayload, Exploration } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function fetchAPI<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...options.headers,
        },
    });

    if (!res.ok) {
        const error = await res.text();
        throw new Error(`API Error: ${res.status} ${res.statusText} - ${error}`);
    }

    return res.json();
}

export const api = {
    getRuns: () => fetchAPI<Run[]>("/runs"),

    createRun: (payload: CreateRunPayload) =>
        fetchAPI<{ run_id: string; message: string }>("/runs", {
            method: "POST",
            body: JSON.stringify(payload),
        }),

    getRunInsights: (runId: string) => fetchAPI<Insight[]>(`/runs/${runId}/insights`),

    getInsight: (insightId: string) => fetchAPI<Insight>(`/insights/${insightId}`),

    exploreInsight: (insightId: string) =>
        fetchAPI<Exploration>(`/insights/${insightId}/explore`, {
            method: "POST",
        }),

    getInsightExplorations: (insightId: string) =>
        fetchAPI<Exploration[]>(`/insights/${insightId}/explorations`),
};
