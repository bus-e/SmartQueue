"""Начальная схема: 7 таблиц MVP.

Схема описана в документе «Схема базы данных». Ограничения в базе дублируют правила
доменной модели: одна активная запись на человека, код уникален среди открытых очередей.
"""

from alembic import op

revision = "0001_init"
down_revision = None

UPGRADE = """
CREATE TABLE users (
    id               bigserial PRIMARY KEY,
    telegram_id      bigint UNIQUE,
    email            text UNIQUE,
    password_hash    text,
    guest_token_hash text UNIQUE,
    full_name        text NOT NULL CHECK (length(full_name) BETWEEN 1 AND 50),
    created_at       timestamptz NOT NULL DEFAULT now(),
    last_active_at   timestamptz NOT NULL DEFAULT now(),
    is_blocked       boolean NOT NULL DEFAULT false
);

CREATE TABLE queues (
    id            bigserial PRIMARY KEY,
    code          char(6) NOT NULL CHECK (code ~ '^[A-HJ-NP-Z2-9]{6}$'),
    title         text NOT NULL CHECK (length(title) BETWEEN 1 AND 50),
    type          text NOT NULL CHECK (type IN ('regular', 'business')),
    status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    creator_id    bigint NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    notify_before smallint NOT NULL DEFAULT 2 CHECK (notify_before BETWEEN 1 AND 10),
    created_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    expires_at    timestamptz NOT NULL DEFAULT now() + interval '24 hours'
);
CREATE UNIQUE INDEX queues_code_open_uq ON queues (code) WHERE status = 'open';

CREATE TABLE queue_staff (
    queue_id bigint NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    user_id  bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role     text NOT NULL CHECK (role IN ('owner', 'operator')),
    PRIMARY KEY (queue_id, user_id)
);

CREATE TABLE queue_members (
    id         bigserial PRIMARY KEY,
    queue_id   bigint NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    user_id    bigint REFERENCES users(id) ON DELETE SET NULL,
    guest_name text,
    number     int NOT NULL,
    source     text NOT NULL CHECK (source IN ('app', 'site', 'bot', 'operator')),
    status     text NOT NULL DEFAULT 'waiting'
               CHECK (status IN ('waiting', 'called', 'served', 'left', 'removed', 'closed')),
    joined_at  timestamptz NOT NULL DEFAULT now(),
    called_at  timestamptz,
    served_at  timestamptz,
    left_at    timestamptz,
    CHECK (user_id IS NOT NULL OR guest_name IS NOT NULL),
    UNIQUE (queue_id, number)
);
CREATE UNIQUE INDEX queue_members_active_uq ON queue_members (queue_id, user_id)
    WHERE status IN ('waiting', 'called');
CREATE INDEX queue_members_order_ix ON queue_members (queue_id, status, joined_at);

CREATE TABLE notifications (
    id         bigserial PRIMARY KEY,
    member_id  bigint NOT NULL REFERENCES queue_members(id) ON DELETE CASCADE,
    type       text NOT NULL CHECK (type IN ('n_ahead', 'next', 'first', 'called', 'removed', 'closed')),
    channel    text NOT NULL CHECK (channel IN ('telegram', 'push', 'site')),
    status     text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    attempts   smallint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at    timestamptz,
    UNIQUE (member_id, type)
);
CREATE INDEX notifications_pending_ix ON notifications (created_at) WHERE status = 'pending';

CREATE TABLE devices (
    id         bigserial PRIMARY KEY,
    user_id    bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform   text NOT NULL CHECK (platform IN ('android', 'ios', 'web')),
    push_token text NOT NULL UNIQUE,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE queue_events (
    id         bigserial PRIMARY KEY,
    queue_id   bigint NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    member_id  bigint REFERENCES queue_members(id) ON DELETE SET NULL,
    actor_id   bigint REFERENCES users(id) ON DELETE SET NULL,
    event_type text NOT NULL,
    payload    jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
"""

DOWNGRADE = "DROP TABLE queue_events, devices, notifications, queue_members, queue_staff, queues, users;"


def upgrade():
    op.execute(UPGRADE)


def downgrade():
    op.execute(DOWNGRADE)
