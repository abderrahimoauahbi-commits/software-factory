DO $$ BEGIN
 IF (SELECT count(*) FROM public.fournisseur WHERE code_fournisseur LIKE 'TEST-F%') <> 2 THEN
   RAISE EXCEPTION 'seeder : 2 fournisseurs de test attendus'; END IF;
 BEGIN INSERT INTO public.fournisseur (code_fournisseur, nom, remise_pct) VALUES ('TEST-X','x',101);
   RAISE EXCEPTION 'contrainte de remise absente';
 EXCEPTION WHEN check_violation THEN NULL; END;
END $$;
