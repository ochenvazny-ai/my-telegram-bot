-- ============================================================
-- Migration v4: users + admins tables + schedule_history cleanup
-- Выполнить в Supabase SQL Editor, если таблиц ещё нет
-- ============================================================

-- Пользователи бота
create table if not exists public.users (
  id bigint primary key,
  username text,
  first_name text,
  created_at timestamptz default now()
);
alter table public.users enable row level security;
create policy "Allow anon select" on public.users for select using (true);
create policy "Allow anon insert" on public.users for insert with check (true);
create policy "Allow anon update" on public.users for update using (true) with check (true);

-- Администраторы бота
create table if not exists public.admins (
  id serial primary key,
  user_id bigint unique not null,
  username text,
  name text,
  created_at timestamptz default now()
);
alter table public.admins enable row level security;
create policy "Allow anon select" on public.admins for select using (true);
create policy "Allow anon insert" on public.admins for insert with check (true);
create policy "Allow anon update" on public.admins for update using (true) with check (true);
create policy "Allow anon delete" on public.admins for delete using (true);

-- Колонки username/name для admins (если таблица была создана раньше без них)
alter table public.admins add column if not exists username text;
alter table public.admins add column if not exists name text;

-- Начальный админ (создатель бота) — раскомментировать и подставить свой ID
-- insert into public.admins (user_id, username, name) values (1207797393, 'id1207797393', 'Создатель')
-- on conflict (user_id) do nothing;

-- Индекс для быстрой очистки старого кэша расписания
create index if not exists idx_schedule_history_date on public.schedule_history (date);
