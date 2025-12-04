export interface Run {
    id: string;
    created_at: string;
    mode: "light" | "deep";
    nb_insights: number;
    status?: string;
}

export interface Insight {
    id: string;
    run_id?: string;
    cluster_id: number;
    rank: number;
    priority_score: number;
    priority_score_adjusted?: number;
    pain_score_final?: number;
    founder_fit_score?: number;
    title: string;
    sector?: string;

    // Flattened fields from API
    problem?: string;
    persona?: string;
    jtbd?: string;
    mvp?: string;
    monetizable?: boolean;
    pain_score_llm?: number;

    examples: Array<{
        id: string;
        url?: string;
        score?: number;
        comments_count?: number;
        source?: string;
        title?: string;
    }>;
}

export interface Exploration {
    exploration_id?: string;
    insight_id: string;
    created_at?: string;
    content: string; // Markdown content
    // Structured fields if available
    monetization?: string;
    variants?: string;
    next_steps?: string;
}

export interface CreateRunPayload {
    mode: "light" | "deep";
    max_insights?: number;
}
