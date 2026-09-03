-- LeadHunter dashboard/runtime compatibility hardening.
-- Safe to run against existing databases. These ALTER statements are idempotent.

alter table if exists research
  add column if not exists created_at timestamptz default now();

alter table if exists research
  alter column research_json set default '{}'::jsonb;

alter table if exists businesses
  add column if not exists address text;

alter table if exists businesses
  add column if not exists website_domain text;

alter table if exists businesses
  add column if not exists normalized_phone text;

alter table if exists businesses
  add column if not exists normalized_name text;

alter table if exists businesses
  add column if not exists normalized_address text;

alter table if exists businesses
  add column if not exists source_attribution text;

alter table if exists businesses
  add column if not exists source_place_id text;

alter table if exists search_results
  add column if not exists result_rank integer;

create index if not exists research_business_idx
  on research(business_id, created_at desc);

create index if not exists search_results_business_idx
  on search_results(business_id, created_at desc);
