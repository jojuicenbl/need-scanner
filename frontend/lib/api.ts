import { Run, Insight, CreateRunPayload, Exploration, GetInsightsParams } from "@/types";

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

/**
 * Build query string from params object, omitting undefined/null values
 */
function buildQueryString(params: Record<string, unknown>): string {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== "") {
            searchParams.append(key, String(value));
        }
    }
    const queryString = searchParams.toString();
    return queryString ? `?${queryString}` : "";
}

export const api = {
    getRuns: () => fetchAPI<Run[]>("/runs"),

    createRun: (payload: CreateRunPayload) =>
        fetchAPI<{ run_id: string; message: string }>("/runs", {
            method: "POST",
            body: JSON.stringify(payload),
        }),

    /**
     * Get insights for a run with optional filters
     *
     * @param runId - The run ID
     * @param params - Optional filter parameters:
     *   - saas_viable_only: Only return SaaS-viable insights
     *   - include_duplicates: Include historical duplicates (default: false)
     *   - solution_type: Filter by solution type
     *   - sector: Filter by sector
     *   - min_priority: Minimum priority score
     *   - limit: Maximum number of results
     */
    getRunInsights: (runId: string, params?: GetInsightsParams) => {
        const queryString = params ? buildQueryString({
            limit: params.limit,
            sector: params.sector,
            min_priority: params.min_priority,
            saas_viable_only: params.saas_viable_only,
            include_duplicates: params.include_duplicates,
            solution_type: params.solution_type,
        }) : "";
        return fetchAPI<Insight[]>(`/runs/${runId}/insights${queryString}`);
    },

    getInsight: (insightId: string) => fetchAPI<Insight>(`/insights/${insightId}`),

    exploreInsight: (insightId: string) =>
        fetchAPI<Exploration>(`/insights/${insightId}/explore`, {
            method: "POST",
        }),

    getInsightExplorations: (insightId: string) =>
        fetchAPI<Exploration[]>(`/insights/${insightId}/explorations`),
};
