-- LeadHunter runtime compatibility for existing Supabase databases.
-- Safe to run repeatedly. Repairs columns used by the current app.

alter table if exists research
    add column if not exists created_at timestamptz default now();

alter table if exists jobs
    add column if not exists created_at timestamptz default now();

alter table if exists search_results
    add column if not exists result_rank integer;

alter table if exists businesses
    add column if not exists source text;
alter table if exists businesses
    add column if not exists source_id text;
alter table if exists businesses
    add column if not exists requested_industry text;
alter table if exists businesses
    add column if not exists requested_city text;
alter table if exists businesses
    add column if not exists verified_industry text;
alter table if exists businesses
    add column if not exists verified_city text;
alter table if exists businesses
    add column if not exists google_types text[] default '{}';
alter table if exists businesses
    add column if not exists google_match_confidence numeric;
alter table if exists businesses
    add column if not exists google_rating numeric;
alter table if exists businesses
    add column if not exists google_review_count integer;
alter table if exists businesses
    add column if not exists google_maps_url text;
alter table if exists businesses
    add column if not exists problems text[] default '{}';
alter table if exists businesses
    add column if not exists recommended_services text[] default '{}';

create index if not exists idx_research_business_id_id
    on research (business_id, id desc);

create index if not exists idx_search_results_search_rank
    on search_results (search_id, result_rank);

create index if not exists idx_jobs_discovery_created
    on jobs (job_type, created_at desc);
