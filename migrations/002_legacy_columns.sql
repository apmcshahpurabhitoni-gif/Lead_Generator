-- Apply to existing deployments that already have the original schema.
alter table businesses add column if not exists address text;
alter table businesses add column if not exists website_domain text;
alter table businesses add column if not exists normalized_phone text;
alter table businesses add column if not exists normalized_name text;
alter table businesses add column if not exists normalized_address text;
alter table businesses add column if not exists source_attribution text;
alter table businesses add column if not exists source_place_id text;
create index if not exists businesses_place_id_idx on businesses(source_place_id) where source_place_id is not null;
create index if not exists businesses_phone_city_idx on businesses(normalized_phone,city) where normalized_phone is not null;
create index if not exists businesses_domain_idx on businesses(website_domain) where website_domain is not null;
alter table search_results add column if not exists result_rank integer;
