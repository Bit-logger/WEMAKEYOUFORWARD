-- ============================================================================
-- JOBFLEX / NEXORA - Migration 003: Cascade Deletion & Bulk Job Upload Support
-- Run in Supabase Dashboard -> SQL Editor -> New Query -> Run
-- Safe to re-run (idempotent checks included).
-- ============================================================================

-- 1. Ensure foreign key on applications cascades when a job is deleted
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'applications_job_id_fkey' AND table_name = 'applications'
    ) THEN
        ALTER TABLE public.applications 
        ADD CONSTRAINT applications_job_id_fkey 
        FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE CASCADE;
    END IF;
END $$;

-- 2. Ensure foreign key on saved_jobs cascades when a job is deleted
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'saved_jobs_job_id_fkey' AND table_name = 'saved_jobs'
    ) THEN
        ALTER TABLE public.saved_jobs 
        ADD CONSTRAINT saved_jobs_job_id_fkey 
        FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE CASCADE;
    END IF;
END $$;

-- 3. Update status constraint to include 'Deleted' for soft-delete support
ALTER TABLE public.jobs DROP CONSTRAINT IF EXISTS jobs_status_check;
ALTER TABLE public.jobs ADD CONSTRAINT jobs_status_check 
CHECK (status IN ('Draft','Pending','Approved','Rejected','Review','Suspended','Paused','Closed','Deleted'));

-- 4. Add index for fast deletion and filtering
CREATE INDEX IF NOT EXISTS idx_jobs_status_active ON public.jobs(status) WHERE status != 'Deleted';
