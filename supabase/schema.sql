CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    role TEXT CHECK (role IN ('admin', 'auditor', 'viewer')) DEFAULT 'viewer',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    vendor_name TEXT NOT NULL,
    tax_id TEXT,
    status TEXT CHECK (status IN ('approved', 'pending', 'blocked')) DEFAULT 'pending',
    country TEXT,
    category TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (org_id, vendor_name)
);

CREATE TABLE IF NOT EXISTS public.rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL,
    description TEXT,
    field TEXT NOT NULL,
    check_type TEXT NOT NULL CHECK (check_type IN ('exists', 'in_list', 'lte', 'gte', 'matches', 'not_in_list')),
    value JSONB,
    weight INT NOT NULL DEFAULT 10,
    severity TEXT CHECK (severity IN ('low', 'medium', 'high')) DEFAULT 'medium',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (org_id, rule_id)
);

CREATE TABLE IF NOT EXISTS public.invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_url TEXT,
    uploaded_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMPTZ DEFAULT now(),
    raw_text TEXT
);

CREATE TABLE IF NOT EXISTS public.audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES public.invoices(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    risk_score INT NOT NULL,
    verdict TEXT CHECK (verdict IN ('APPROVE', 'REVIEW', 'REJECT')) NOT NULL,
    confidence NUMERIC(3,2),
    routing_reason TEXT,
    summary TEXT,
    next_action TEXT,
    gate_passed BOOLEAN DEFAULT false,
    gate_warnings JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.audit_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id UUID NOT NULL REFERENCES public.audits(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL,
    status TEXT CHECK (status IN ('pass', 'fail')) NOT NULL,
    reason TEXT,
    weight INT,
    severity TEXT
);

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_org ON public.users(org_id);
CREATE INDEX IF NOT EXISTS idx_vendors_org ON public.vendors(org_id);
CREATE INDEX IF NOT EXISTS idx_vendors_name ON public.vendors(vendor_name);
CREATE INDEX IF NOT EXISTS idx_rules_org ON public.rules(org_id);
CREATE INDEX IF NOT EXISTS idx_rules_rule_id ON public.rules(rule_id);
CREATE INDEX IF NOT EXISTS idx_invoices_org ON public.invoices(org_id);
CREATE INDEX IF NOT EXISTS idx_audits_org ON public.audits(org_id);
CREATE INDEX IF NOT EXISTS idx_audits_invoice ON public.audits(invoice_id);
CREATE INDEX IF NOT EXISTS idx_audit_checks_audit ON public.audit_checks(audit_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org ON public.audit_logs(org_id);

CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_vendors_updated_at
    BEFORE UPDATE ON public.vendors
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

CREATE OR REPLACE TRIGGER trg_rules_updated_at
    BEFORE UPDATE ON public.rules
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

INSERT INTO public.organizations (id, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Org')
ON CONFLICT (id) DO NOTHING;