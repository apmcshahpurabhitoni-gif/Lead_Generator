-- LeadHunter canonical existing-database upgrade. Safe to run repeatedly.
alter table if exists research add column if not exists created_at timestamptz default now();
alter table if exists research alter column research_json set default '{}'::jsonb;
alter table if exists jobs add column if not exists created_at timestamptz default now();
alter table if exists businesses add column if not exists address text;
alter table if exists businesses add column if not exists website_domain text;
alter table if exists businesses add column if not exists normalized_phone text;
alter table if exists businesses add column if not exists normalized_name text;
alter table if exists businesses add column if not exists normalized_address text;
alter table if exists businesses add column if not exists source_attribution text;
alter table if exists businesses add column if not exists source_place_id text;
alter table if exists businesses add column if not exists source text;
alter table if exists businesses add column if not exists problems text[] default '{}';
alter table if exists businesses add column if not exists recommended_services text[] default '{}';
create table if not exists search_results (
 search_id bigint not null references jobs(id) on delete cascade,
 business_id bigint not null references businesses(id) on delete cascade,
 result_rank integer,
 created_at timestamptz default now(),
 primary key(search_id,business_id)
);
alter table if exists search_results add column if not exists result_rank integer;
create index if not exists idx_research_business_created on research(business_id, created_at desc);
create index if not exists idx_search_results_search_rank on search_results(search_id, result_rank);
create index if not exists idx_search_results_business on search_results(business_id);
create index if not exists businesses_place_id_idx on businesses(source_place_id) where source_place_id is not null;
create index if not exists businesses_phone_city_idx on businesses(normalized_phone,city) where normalized_phone is not null;
create index if not exists businesses_domain_idx on businesses(website_domain) where website_domain is not null;
