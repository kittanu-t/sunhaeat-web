create schema if not exists extensions;
create extension if not exists postgis with schema extensions;
create extension if not exists pg_trgm with schema extensions;
set search_path = extensions, public;

create schema app;
revoke all on schema app from public;

do $$ begin
  create role api_runtime nologin noinherit;
exception when duplicate_object then null; end $$;
alter role api_runtime set search_path = app, extensions, public;
alter role api_runtime set statement_timeout = '3s';
grant usage on schema app, extensions to api_runtime;

create table app.provinces (
  code text primary key check (code ~ '^TH-[0-9]{2}$'),
  name_th text not null
);

create table app.restaurants (
  id uuid primary key,
  slug text not null unique,
  name text not null check (length(name) between 1 and 200),
  name_normalized text not null,
  province_code text not null references app.provinces (code),
  location geography(Point, 4326) not null,
  address text,
  locality text,
  tags text[] not null default '{}',
  description text,
  website text check (website like 'https://%'),
  facebook_url text check (facebook_url like 'https://www.facebook.com/%'),
  price_min integer check (price_min >= 0),
  price_max integer check (price_max >= price_min),
  confidence real check (confidence between 0 and 1),
  is_demo boolean not null default false,
  dataset_release text not null
);
create index restaurants_location on app.restaurants using gist (location);
create index restaurants_name on app.restaurants using gin (name_normalized gin_trgm_ops);
create index restaurants_tags on app.restaurants using gin (tags);
create index restaurants_province on app.restaurants (province_code);

create table app.restaurant_sources (
  restaurant_id uuid not null references app.restaurants (id) on delete cascade,
  dataset text not null,
  record_id text not null,
  license text not null,
  primary key (restaurant_id, dataset, record_id)
);

create table app.menu_items (
  restaurant_id uuid not null references app.restaurants (id) on delete cascade,
  position smallint not null,
  name text not null,
  price_thb integer check (price_thb >= 0),
  primary key (restaurant_id, position)
);

create table app.opening_hours (
  restaurant_id uuid not null references app.restaurants (id) on delete cascade,
  weekday smallint not null check (weekday between 0 and 6), -- 0 = Sunday, Asia/Bangkok
  opens time not null,
  closes time not null,
  primary key (restaurant_id, weekday)
);

do $$ declare t text; begin
  foreach t in array array['provinces', 'restaurants', 'restaurant_sources', 'menu_items', 'opening_hours'] loop
    execute format('alter table app.%I enable row level security', t);
    execute format('grant select on app.%I to api_runtime', t);
    execute format('create policy runtime_read on app.%I for select to api_runtime using (true)', t);
  end loop;
end $$;
