create table app.rate_limits (
  key text not null,
  window_start timestamptz not null,
  hits integer not null check (hits > 0),
  primary key (key, window_start)
);
create index rate_limits_window on app.rate_limits (window_start);

create table app.ai_usage (
  day date not null, -- Asia/Bangkok
  scope text not null, -- 'global', 's:<session hash>' or 'ip:<ip hash>'
  requests integer not null default 0,
  tokens bigint not null default 0,
  blocked boolean not null default false,
  primary key (day, scope)
);

do $$ declare t text; begin
  foreach t in array array['rate_limits', 'ai_usage'] loop
    execute format('alter table app.%I enable row level security', t);
    execute format('grant select, insert, update, delete on app.%I to api_runtime', t);
    execute format('create policy runtime_all on app.%I for all to api_runtime using (true) with check (true)', t);
  end loop;
end $$;
