CREATE TABLE public.remise_historique (code_fournisseur text NOT NULL, remise_pct numeric(5,2) NOT NULL, date_effet text NOT NULL);
ALTER TABLE public.fournisseur ADD COLUMN remise_pct numeric(5,2) NOT NULL DEFAULT 0 CONSTRAINT ck_fournisseur_remise_pct CHECK (remise_pct BETWEEN 0 AND 100);
