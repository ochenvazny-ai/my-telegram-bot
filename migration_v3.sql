-- Настройки бота (текущая смена и т.п.)
create table if not exists public.settings (
  id serial primary key,
  key text unique not null,
  value text,
  created_at timestamptz default now()
);
alter table public.settings enable row level security;
create policy "Allow anon select" on public.settings for select using (true);
create policy "Allow anon insert" on public.settings for insert with check (true);
create policy "Allow anon update" on public.settings for update using (true) with check (true);

insert into public.settings (key, value) values ('current_shift', '1')
on conflict (key) do nothing;

-- Подписи к заменам (объявления с флагом is_replacement_note)
alter table public.announcements add column if not exists is_replacement_note boolean default false;
