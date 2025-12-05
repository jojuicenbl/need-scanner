export interface Run {
    id: string;
    created_at: string;
    mode: "light" | "deep";
    nb_insights: number;
    status?: string;
    notes?: string;
}

// Solution types for productizability classification
export type SolutionType =
    | "saas_b2b"
    | "saas_b2c"
    | "tooling_dev"
    | "api_product"
    | "service_only"
    | "content_only"
    | "hardware_required"
    | "regulation_policy"
    | "impractical_unclear";

// Product angle types for ideation
export type ProductAngleType =
    | "indie_saas"
    | "b2b_saas"
    | "plugin"
    | "extension"
    | "api"
    | "template"
    | "marketplace";

export interface Insight {
    id: string;
    run_id?: string;
    cluster_id: number;
    rank: number;
    priority_score: number;
    priority_score_adjusted?: number;
    pain_score_final?: number;
    founder_fit_score?: number;
    trend_score?: number;
    novelty_score?: number;
    title: string;
    sector?: string;

    // Flattened fields from API
    problem?: string;
    persona?: string;
    jtbd?: string;
    mvp?: string;
    monetizable?: boolean;
    pain_score_llm?: number;

    // Step 5.1: Inter-day deduplication
    max_similarity_with_history?: number;
    duplicate_of_insight_id?: string;
    is_historical_duplicate?: boolean;

    // Step 5.2: SaaS-ability / Productizability
    solution_type?: SolutionType;
    recurring_revenue_potential?: number;
    saas_viable?: boolean;

    // Step 5.3: Product Ideation
    product_angle_title?: string;
    product_angle_summary?: string;
    product_angle_type?: ProductAngleType;
    product_pricing_hint?: string;
    product_complexity?: number; // 1-3

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
    run_mode?: "discover" | "track";
}

export interface GetInsightsParams {
    limit?: number;
    sector?: string;
    min_priority?: number;
    saas_viable_only?: boolean;
    include_duplicates?: boolean;
    solution_type?: SolutionType;
}
