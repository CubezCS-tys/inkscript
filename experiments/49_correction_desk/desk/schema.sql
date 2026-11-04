-- The Desk: the people's sheet (experiment 49, P1, 2026-10-21). DESIGN.md §3.
--
-- Everything here lives in one PostgreSQL schema chosen by search_path: `desk` for the real Desk, `test_<pid>` for a
-- test run (appuser may not CREATE DATABASE on this server, so tests get a throwaway schema inside `inkdesk`).
-- The extensions are created once per database, in `public`, by desk/db.py (pg_trgm, unaccent, btree_gist).
--
-- Stable keys only (DESIGN §2). A subject key is one of:
--   work:C…                      a cited-work card (platform v2 id_registry, hash of the card's natural key)
--   person:A…                    a person (hash of 'auth:<authority id>', or 'mention:<byline anchor>' for a provisional one)
--   mention:<mention_id>         a citation mention, '<stem>|p<page>|w<first>-<last>|<n>' on Azure word numbers
--   byline:<anchor_key>          a byline mention, by its ink anchor '<stem>|p<page>|w<first>-<last>'
--                                (or '<stem>|<block_id>|<byline_pos>|<script>' for the 95 bylines with no anchor)
--   authority:<id>               a Mandumah authority id
--   pubfield:W<999$c>|<field>    a publication's metadata field (metadata ops: P2+)
--   line:<stem>|p<page>|l<n>     an Azure line (page ops: P2+, written as platform v2 `patches`)
-- Never a row number.

-- ------------------------------------------------------------------ who
CREATE TABLE actors (
  actor_id    text PRIMARY KEY,                     -- person:<login> | agent:<name> | model:<name> | rule:<name>
  kind        text NOT NULL CHECK (kind IN ('person', 'agent', 'model', 'rule')),
  name        text NOT NULL,
  role        text CHECK (role IN ('corrector', 'admin')),   -- all correctors are equal (owner, 2026-10-21)
  skills      text[] NOT NULL DEFAULT '{}',         -- languages ar | en | fr (fields later: law, education, turath …)
  ui_lang     text NOT NULL DEFAULT 'ar' CHECK (ui_lang IN ('ar', 'en', 'fr')),
  active      boolean NOT NULL DEFAULT true,
  is_demo     boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (kind <> 'person' OR role IS NOT NULL),
  CHECK (skills <@ ARRAY['ar', 'en', 'fr']::text[])
);

-- P1 only: one local token per actor, sent as the X-Desk-Token header. Only its sha256 is stored.
-- TODO(P4): real accounts — an admin invites by e-mail, password (argon2) + a second factor (TOTP), expiring
-- sessions, rate limits and login alerts (DESIGN §11). This table is then dropped.
CREATE TABLE tokens (
  token_sha   text PRIMARY KEY,
  actor_id    text NOT NULL REFERENCES actors(actor_id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  revoked     boolean NOT NULL DEFAULT false
);

-- The review rule per decision kind: a setting, not code (DESIGN §7). Since the owner's change of 2026-10-21 every
-- kind is `single` (one key: accepted when its corrector makes it). `sample` / `two_keys` are kept as values only,
-- in case they are wanted later; P1 builds no flow for them.
CREATE TABLE review_rules (
  op                   text PRIMARY KEY,
  rule                 text NOT NULL DEFAULT 'single' CHECK (rule IN ('single', 'sample', 'two_keys')),
  sample_pct           integer NOT NULL DEFAULT 0 CHECK (sample_pct BETWEEN 0 AND 100),
  two_keys_min_impact  integer,                     -- above this impact the decision needs two keys whatever the rule
  note                 text
);

-- ------------------------------------------------------------------ what can be corrected
CREATE TABLE subjects (
  subject_key         text PRIMARY KEY,
  kind                text NOT NULL,                -- work | person | mention | byline | authority | pubfield | line
  label               text,                         -- for screens
  first_seen_release  text,
  last_seen_release   text,
  status              text NOT NULL DEFAULT 'live' CHECK (status IN ('live', 'orphaned', 'contested')),
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX subjects_label_trgm ON subjects USING gin (label public.gin_trgm_ops);
CREATE INDEX subjects_kind ON subjects (kind, status);

-- ------------------------------------------------------------------ questions waiting for a person
CREATE TABLE tasks (
  task_id          bigserial PRIMARY KEY,
  task_key         text NOT NULL,                   -- kind|subject keys: one live task per question
  kind             text NOT NULL,                   -- work_joined_without_author | possible_same_work | byline_twin |
                                                    -- orphaned_decision | conflict
  subject_keys     text[] NOT NULL,
  question         text,
  candidates       jsonb NOT NULL DEFAULT '[]',
  machine_guess    jsonb,
  impact           real NOT NULL DEFAULT 1,
  uncertainty      real NOT NULL DEFAULT 0.5,
  priority         real NOT NULL DEFAULT 0.5,       -- impact × uncertainty (DESIGN §6)
  source           jsonb NOT NULL DEFAULT '{}',     -- detector, reading / release it ran on
  skills           text[] NOT NULL DEFAULT '{}',    -- each element one requirement: 'ar', or 'en|fr' = either
  state            text NOT NULL DEFAULT 'open'
                   CHECK (state IN ('open', 'claimed', 'answered', 'closed', 'stale', 'contested')),
  claimed_by       text REFERENCES actors(actor_id),
  lease_until      timestamptz,
  answered_by      uuid,                            -- the decision that answered it
  about_decision   uuid,                            -- orphaned_decision / conflict: the decision it is about
  reserved_for     text REFERENCES actors(actor_id), -- only this corrector (the decision's owner) or an admin takes it
  excluded_actors  text[] NOT NULL DEFAULT '{}',    -- may not take it (said "unsure" on it)
  skipped_by       text[] NOT NULL DEFAULT '{}',
  created_release  text,
  is_demo          boolean NOT NULL DEFAULT false,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX tasks_one_live ON tasks (task_key) WHERE state IN ('open', 'claimed');
CREATE INDEX tasks_queue ON tasks (state, priority DESC, task_id);
CREATE INDEX tasks_subjects ON tasks USING gin (subject_keys);
CREATE INDEX tasks_about ON tasks (about_decision);

CREATE TABLE task_events (                          -- claim / skip / unsure / answer / stale: for minutes per task
  event_id   bigserial PRIMARY KEY,
  task_id    bigint NOT NULL REFERENCES tasks(task_id),
  actor_id   text REFERENCES actors(actor_id),
  event      text NOT NULL,
  note       text,
  at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX task_events_task ON task_events (task_id, at);

-- ------------------------------------------------------------------ the decisions (append-only)
CREATE TABLE decisions (
  decision_id            uuid PRIMARY KEY,
  seq                    bigserial UNIQUE,         -- the order decisions are applied in, within a phase
  domain                 text NOT NULL CHECK (domain IN ('page', 'metadata', 'identity')),
  op                     text NOT NULL,
  subject_keys           text[] NOT NULL CHECK (cardinality(subject_keys) >= 1),
  payload                jsonb NOT NULL DEFAULT '{}',
  reason_code            text,
  note                   text,
  evidence               jsonb NOT NULL DEFAULT '{}',   -- what the person saw: members, names, crops
  actor_id               text NOT NULL REFERENCES actors(actor_id),
  role_at_time           text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  task_id                bigint REFERENCES tasks(task_id),
  confidence             text NOT NULL DEFAULT 'sure' CHECK (confidence IN ('sure', 'likely', 'unsure')),
  status                 text NOT NULL CHECK (status IN ('proposed', 'accepted', 'rejected', 'superseded')),
  supersedes             uuid REFERENCES decisions(decision_id),
  superseded_by          uuid REFERENCES decisions(decision_id),
  review_policy_at_time  text NOT NULL,
  is_demo                boolean NOT NULL DEFAULT false
);
CREATE INDEX decisions_subjects ON decisions USING gin (subject_keys);
CREATE INDEX decisions_status ON decisions (status, seq);
CREATE INDEX decisions_actor ON decisions (actor_id, created_at);
CREATE INDEX decisions_note_trgm ON decisions USING gin (note public.gin_trgm_ops);

-- Every decision has an owner: its actor. Only the owner, or an admin, may supersede or revert it (owner,
-- 2026-10-21); ops.py enforces that, the database keeps the record unchangeable:
-- a decision never changes after it is written: only its status moves (proposed -> accepted | rejected |
-- superseded; accepted -> superseded | rejected) and superseded_by is set once. No DELETE, no TRUNCATE.
CREATE FUNCTION decisions_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'decisions are append-only: DELETE of % refused', OLD.decision_id
      USING ERRCODE = 'restrict_violation';
  END IF;
  IF (to_jsonb(NEW) - 'status' - 'superseded_by') IS DISTINCT FROM (to_jsonb(OLD) - 'status' - 'superseded_by') THEN
    RAISE EXCEPTION 'decisions are append-only: only status and superseded_by may change (decision %)', OLD.decision_id
      USING ERRCODE = 'restrict_violation';
  END IF;
  IF OLD.superseded_by IS NOT NULL AND NEW.superseded_by IS DISTINCT FROM OLD.superseded_by THEN
    RAISE EXCEPTION 'superseded_by is set once (decision %)', OLD.decision_id USING ERRCODE = 'restrict_violation';
  END IF;
  IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
       (OLD.status = 'proposed' AND NEW.status IN ('accepted', 'rejected', 'superseded')) OR
       (OLD.status = 'accepted' AND NEW.status IN ('superseded', 'rejected'))) THEN
    RAISE EXCEPTION 'decision % cannot go from % to %', OLD.decision_id, OLD.status, NEW.status
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER decisions_append_only BEFORE UPDATE OR DELETE ON decisions
  FOR EACH ROW EXECUTE FUNCTION decisions_append_only();

CREATE FUNCTION refuse_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only: TRUNCATE refused', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
END $$;
CREATE TRIGGER decisions_no_truncate BEFORE TRUNCATE ON decisions
  FOR EACH STATEMENT EXECUTE FUNCTION refuse_truncate();

-- every status change, with who and why (the decision row itself keeps only the current status)
CREATE TABLE decision_events (
  event_id     bigserial PRIMARY KEY,
  decision_id  uuid NOT NULL REFERENCES decisions(decision_id),
  status       text NOT NULL,
  why          text,
  actor_id     text REFERENCES actors(actor_id),
  at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX decision_events_decision ON decision_events (decision_id, at);

ALTER TABLE tasks ADD FOREIGN KEY (answered_by) REFERENCES decisions(decision_id);
ALTER TABLE tasks ADD FOREIGN KEY (about_decision) REFERENCES decisions(decision_id);

-- ------------------------------------------------------------------ notes (instead of second keys)
-- A corrector who disagrees with a decision leaves a note; the decision's owner sees it under /me/notes and acts
-- (supersedes or reverts their own decision) or resolves the note. The release step also leaves notes on conflicts.
CREATE TABLE notes (
  note_id      bigserial PRIMARY KEY,
  subject_key  text NOT NULL,
  decision_id  uuid REFERENCES decisions(decision_id),
  author       text NOT NULL REFERENCES actors(actor_id),
  text         text NOT NULL CHECK (length(text) > 0),
  created_at   timestamptz NOT NULL DEFAULT now(),
  resolved_at  timestamptz,
  resolved_by  text REFERENCES actors(actor_id),
  is_demo      boolean NOT NULL DEFAULT false
);
CREATE INDEX notes_subject ON notes (subject_key, created_at);
CREATE INDEX notes_decision ON notes (decision_id) WHERE decision_id IS NOT NULL;
CREATE INDEX notes_text_trgm ON notes USING gin (text public.gin_trgm_ops);

-- ------------------------------------------------------------------ known answers, mixed into queues
-- A quiet accuracy gauge, shown to admins only. Not a gate: it never changes what happens to a decision.
CREATE TABLE gold (
  task_id     bigint PRIMARY KEY REFERENCES tasks(task_id),
  answer      jsonb NOT NULL,                       -- {op, subject_keys, payload}
  set_by      text NOT NULL REFERENCES actors(actor_id),
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------ builds
CREATE TABLE releases (
  release_id       text PRIMARY KEY,                -- R<yyyymmdd>T<hhmmss>
  reading_path     text NOT NULL,                   -- the machine reading it was built from
  reading_sig      jsonb,                           -- size/mtime of the reading and its WAL, last load event
  path             text,                            -- the release copy
  status           text NOT NULL CHECK (status IN ('building', 'built', 'failed')),
  n_decisions      integer, n_applied integer, n_superseded integer, n_orphaned integer, n_conflict integer,
  counts_before    jsonb, counts_after jsonb,
  checks           jsonb,
  fingerprint      text,                            -- sha256 of every table a decision can touch (no clocks)
  timings          jsonb,
  built_by         text REFERENCES actors(actor_id),
  started_at       timestamptz NOT NULL DEFAULT now(),
  finished_at      timestamptz,
  copy_deleted_at  timestamptz,                     -- older copies are deleted: at most 2 on disk
  note             text,
  is_demo          boolean NOT NULL DEFAULT false
);

CREATE TABLE applications (                         -- what a build did with each decision
  release_id   text NOT NULL REFERENCES releases(release_id),
  decision_id  uuid NOT NULL REFERENCES decisions(decision_id),
  ord          integer NOT NULL,                    -- the order it was applied in
  status       text NOT NULL CHECK (status IN ('applied', 'superseded', 'orphaned', 'conflict')),
  detail       jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY (release_id, decision_id)
);
CREATE INDEX applications_decision ON applications (decision_id);

-- ==== idempotent upgrades (db.init_schema runs everything below this line again on an existing schema) ====
-- ------------------------------------------------------------------ the field guide's reviews (2026-10-23)
-- /how-we-collect: a person reads how a field is collected and says whether its label is right. One row per review,
-- never changed (the latest per field is the one shown); field_key is '<explore tab>.<column>', e.g.
-- 'articles.n_institutions'.
CREATE TABLE IF NOT EXISTS field_reviews (
  review_id       bigserial PRIMARY KEY,
  field_key       text NOT NULL CHECK (field_key ~ '^[a-z]+\.[a-z][a-z0-9_]*$'),
  verdict         text NOT NULL CHECK (verdict IN ('agree', 'wrong_label', 'question')),
  comment         text CHECK (comment IS NULL OR length(comment) <= 4000),
  proposed_label  text CHECK (proposed_label IS NULL OR length(proposed_label) <= 200),
  author          text NOT NULL REFERENCES actors(actor_id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  is_demo         boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS field_reviews_field ON field_reviews (field_key, created_at);
CREATE OR REPLACE FUNCTION field_reviews_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'field_reviews is append-only: write a new review instead' USING ERRCODE = 'restrict_violation';
END $$;
DROP TRIGGER IF EXISTS field_reviews_append_only ON field_reviews;
CREATE TRIGGER field_reviews_append_only BEFORE UPDATE OR DELETE ON field_reviews
  FOR EACH ROW EXECUTE FUNCTION field_reviews_append_only();
DROP TRIGGER IF EXISTS field_reviews_no_truncate ON field_reviews;
CREATE TRIGGER field_reviews_no_truncate BEFORE TRUNCATE ON field_reviews
  FOR EACH STATEMENT EXECUTE FUNCTION refuse_truncate();

-- ------------------------------------------------------------------ the librarian's review sample (2026-10-23)
-- /librarian (experiment 56): the owner checks a sample of the AI librarian's institution decisions (proposals in
-- experiments/56_librarian_institutions/out/decisions56.jsonl, never applied) and says yes / no / unsure. One row per
-- verdict, never changed (the latest per decision is the one shown); decision_id is the librarian's 'D56-<12 hex>'.
CREATE TABLE IF NOT EXISTS librarian_verdicts (
  verdict_id      bigserial PRIMARY KEY,
  decision_id     text NOT NULL CHECK (decision_id ~ '^D56-[0-9a-f]{12}$'),
  verdict         text NOT NULL CHECK (verdict IN ('yes', 'no', 'unsure')),
  comment         text CHECK (comment IS NULL OR length(comment) <= 4000),
  in_sample       boolean NOT NULL DEFAULT false,
  author          text NOT NULL REFERENCES actors(actor_id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  is_demo         boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS librarian_verdicts_decision ON librarian_verdicts (decision_id, created_at);
CREATE OR REPLACE FUNCTION librarian_verdicts_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'librarian_verdicts is append-only: write a new verdict instead' USING ERRCODE = 'restrict_violation';
END $$;
DROP TRIGGER IF EXISTS librarian_verdicts_append_only ON librarian_verdicts;
CREATE TRIGGER librarian_verdicts_append_only BEFORE UPDATE OR DELETE ON librarian_verdicts
  FOR EACH ROW EXECUTE FUNCTION librarian_verdicts_append_only();
DROP TRIGGER IF EXISTS librarian_verdicts_no_truncate ON librarian_verdicts;
CREATE TRIGGER librarian_verdicts_no_truncate BEFORE TRUNCATE ON librarian_verdicts
  FOR EACH STATEMENT EXECUTE FUNCTION refuse_truncate();

-- ------------------------------------------------------------------ institution decisions (experiment 64, 2026-11-02)
-- Institutions and printed affiliations are decided with the ordinary `decisions` rows (keys.OPS: define_institution,
-- same_institution, not_same_institution, not_an_institution_row, set_inst_country, set_inst_parent, set_inst_type,
-- link_affiliation, not_an_institution, unit_kept_apart; subject keys 'inst:I…' and 'aff:<stem>|b<n>|<script>|a<n>').
-- No new table is needed; the review rule of each new kind is listed here so an existing Desk shows it (one key).
INSERT INTO review_rules (op, rule, sample_pct, two_keys_min_impact, note)
SELECT op, 'single', 0, NULL, '' FROM unnest(ARRAY['define_institution', 'same_institution', 'not_same_institution',
  'not_an_institution_row', 'set_inst_country', 'set_inst_parent', 'set_inst_type', 'link_affiliation',
  'not_an_institution', 'unit_kept_apart']) AS op
ON CONFLICT (op) DO NOTHING;

-- ------------------------------------------------------------------ cited-work decisions (experiment 67, 2026-11-02)
-- The librarian's cited-work operations (keys.OPS: edition_of, not_a_work, define_work, link_publication,
-- relate_works, relate_publication; the new subject key 'pub:W…' is a Mandumah publication). No new table; the
-- review rule of each new kind is listed so an existing Desk shows it (one key).
INSERT INTO review_rules (op, rule, sample_pct, two_keys_min_impact, note)
SELECT op, 'single', 0, NULL, '' FROM unnest(ARRAY['edition_of', 'not_a_work', 'define_work', 'link_publication',
  'relate_works', 'relate_publication']) AS op
ON CONFLICT (op) DO NOTHING;
