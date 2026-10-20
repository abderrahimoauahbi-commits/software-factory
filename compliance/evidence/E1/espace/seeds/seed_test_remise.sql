BEGIN;
INSERT INTO public.fournisseur (code_fournisseur, nom, remise_pct) VALUES ('TEST-F1', 'Fournisseur test 1', 5), ('TEST-F2', 'Fournisseur test 2', 15);
COMMIT;
