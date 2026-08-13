-- Дополнительные занятия
create table if not exists public.extra_classes (
  id serial primary key,
  subject text not null,
  description text,
  photo_id text,
  created_at timestamptz default now(),
  is_active boolean default true
);
alter table public.extra_classes enable row level security;
create policy "Allow anon select" on public.extra_classes for select using (true);
create policy "Allow anon insert" on public.extra_classes for insert with check (true);
create policy "Allow anon update" on public.extra_classes for update using (true) with check (true);

-- Кэш готовых картинок расписания
create table if not exists public.schedule_images (
  kind text primary key,  -- 'num' | 'den' | 'cmp'
  image_bytes bytea not null,
  updated_at timestamptz default now()
);
alter table public.schedule_images enable row level security;
create policy "Allow anon select" on public.schedule_images for select using (true);
create policy "Allow anon upsert" on public.schedule_images for insert with check (true);
create policy "Allow anon update" on public.schedule_images for update using (true) with check (true);
create policy "Allow anon delete" on public.schedule_images for delete using (true);

-- Название группы
insert into public.settings (key, value) values ('group_name', 'ИБ1-31')
on conflict (key) do nothing;