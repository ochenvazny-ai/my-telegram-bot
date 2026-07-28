-- Домашние задания
create table if not exists public.homework (
  id serial primary key,
  task text not null,
  due_date text,
  created_at timestamptz default now()
);
alter table public.homework enable row level security;
create policy "Allow anon select" on public.homework for select using (true);
create policy "Allow anon insert" on public.homework for insert with check (true);
create policy "Allow anon delete" on public.homework for delete using (true);

-- Объявления
create table if not exists public.announcements (
  id serial primary key,
  text text not null,
  created_at timestamptz default now(),
  author_id bigint,
  is_active boolean default true
);
alter table public.announcements enable row level security;
create policy "Allow anon select" on public.announcements for select using (true);
create policy "Allow anon insert" on public.announcements for insert with check (true);
create policy "Allow anon update" on public.announcements for update using (true) with check (true);

-- Предпраздничные дни (дата в формате MM-DD, без года — повторяется ежегодно)
create table if not exists public.pre_holidays (
  id serial primary key,
  date text not null,
  is_active boolean default true,
  created_at timestamptz default now()
);
alter table public.pre_holidays enable row level security;
create policy "Allow anon select" on public.pre_holidays for select using (true);
create policy "Allow anon insert" on public.pre_holidays for insert with check (true);
create policy "Allow anon update" on public.pre_holidays for update using (true) with check (true);

-- Базовое расписание (числитель/знаменатель по дням недели)
create table if not exists public.schedule (
  id serial primary key,
  week_type text not null,
  day_of_week int not null,
  pair_number int not null,
  subject text not null,
  teacher text,
  room text,
  created_at timestamptz default now(),
  unique (week_type, day_of_week, pair_number)
);
alter table public.schedule enable row level security;
create policy "Allow anon select" on public.schedule for select using (true);
create policy "Allow anon insert" on public.schedule for insert with check (true);
create policy "Allow anon update" on public.schedule for update using (true) with check (true);
create policy "Allow anon delete" on public.schedule for delete using (true);

-- Кэш расписания с наложенными заменами по конкретным датам
create table if not exists public.schedule_history (
  id serial primary key,
  date date not null,
  week_type text,
  day text,
  pair_num text,
  subject text,
  teacher text,
  room text,
  is_replaced boolean default false,
  original_subject text,
  original_teacher text,
  original_room text,
  created_at timestamptz default now()
);
create index if not exists idx_schedule_history_date on public.schedule_history (date);
alter table public.schedule_history enable row level security;
create policy "Allow anon select" on public.schedule_history for select using (true);
create policy "Allow anon insert" on public.schedule_history for insert with check (true);
create policy "Allow anon delete" on public.schedule_history for delete using (true);

-- Обновляем admins: добавляем поля username/name, которых не было в изначальной схеме
alter table public.admins add column if not exists username text;
alter table public.admins add column if not exists name text;
