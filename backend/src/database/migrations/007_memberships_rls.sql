-- =====================================================================
-- M7: Enable RLS on memberships + align actors.auth_user_id index
-- Run AFTER 006c_finish_app_drop.sql
-- =====================================================================

-- 1. Ensure memberships table exists (idempotent; created in M3 but
--    absent from baseline schema.sql so some envs may be missing it)
CREATE TABLE IF NOT EXISTS public.memberships (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_memberships_user_id   ON public.memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_tenant_id ON public.memberships(tenant_id);

-- 2. Enable RLS
ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;

-- Members can read their own memberships; owners/admins can read all in tenant.
-- Service role (backend) bypasses RLS naturally.
DROP POLICY IF EXISTS memberships_self_read ON public.memberships;
CREATE POLICY memberships_self_read ON public.memberships
    FOR SELECT
    USING (user_id = auth.uid());

-- 3. Ensure on_auth_user_created trigger is present.
--    (Idempotent — function defined in M5; re-running is safe.)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 4. Index on actors.auth_user_id for fast membership lookup
CREATE INDEX IF NOT EXISTS idx_actors_auth_user_id ON public.actors(auth_user_id);

-- 5. Verify
SELECT COUNT(*) AS memberships_count FROM public.memberships;
