-- LeadHunter 004: businesses schema parity.
-- The live database drifted from the canonical schema: upsert_business wrote
-- address/website_domain/normalized_phone/normalized_name/normalized_address,
-- every insert failed with PGRST204, and every discovery job saved 0 leads.
-- Safe to run repeatedly.

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

create index if not exists idx_businesses_website_domain
    on businesses (website_domain);
create index if not exists idx_businesses_normalized_phone
    on businesses (normalized_phone);
create index if not exists idx_businesses_normalized_name
    on businesses (normalized_name);
