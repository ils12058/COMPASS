"""Frozen final PostgreSQL database guards; see ADR-117."""

from django.db import migrations


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION public.gm_or_key(value text)
 RETURNS text
 LANGUAGE sql
 IMMUTABLE STRICT
AS $function$
 SELECT CASE WHEN (value COLLATE "C") ~ '^[ -~]*$' AND length(btrim(value, ' ')) BETWEEN 1 AND 96
 THEN translate(btrim(value, ' '), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') END
$function$;
CREATE OR REPLACE FUNCTION public.gm_receipt_closure_successor()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
 IF OLD.is_current AND NOT NEW.is_current AND NOT EXISTS (
   SELECT 1 FROM good_moral_goodmoralreceiptassignment WHERE previous_id=NEW.id
 ) THEN
   RAISE EXCEPTION USING ERRCODE='23514', CONSTRAINT='gm_receipt_closure_successor', MESSAGE='Receipt closure requires an immutable successor';
 END IF;
 RETURN NULL;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_receipt_identity_claim()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
 IF NEW.origin='ORDINARY' AND NOT EXISTS (
   SELECT 1 FROM good_moral_goodmoralreceiptassignment WHERE identity_id=NEW.id
 ) THEN
   RAISE EXCEPTION USING ERRCODE='23514', CONSTRAINT='gm_receipt_identity_claim', MESSAGE='Receipt reservation requires its immutable claim';
 END IF;
 RETURN NULL;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_receipt_identity_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE rstatus text;
BEGIN
 IF TG_OP<>'INSERT' THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_identity_immutable' , MESSAGE
     = 'Receipt reservations cannot be changed or deleted' ;
 END IF;
 IF gm_or_key(NEW.normalized_key) IS DISTINCT FROM NEW.normalized_key THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_canonical_key' , MESSAGE =
     'Receipt identity is not canonical' ;
 END IF;
 IF NEW.origin='ORDINARY' AND NEW.state='BOUND' THEN
   SELECT status INTO rstatus FROM good_moral_goodmoralrequest WHERE id = NEW.bound_request_id FOR
     UPDATE ;
   IF rstatus IN ('REQUESTED','READY_FOR_ISSUANCE') THEN RETURN NEW; END IF;
 END IF;
 RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_reservation_boundary' , MESSAGE
   = 'Receipt reservation source or binding is invalid' ;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_inspection_eligibility_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE rid uuid;
BEGIN
 IF TG_TABLE_NAME='good_moral_goodmoralrequest' THEN rid=NEW.id;
 ELSIF TG_TABLE_NAME='good_moral_goodmoralreceiptassignment' THEN rid=NEW.request_id;
 ELSE SELECT request_id INTO rid FROM good_moral_goodmoralreceiptassignment WHERE id=NEW.assignment_id; END IF;
 IF EXISTS (
   SELECT 1 FROM good_moral_goodmoralreceiptverification v
   JOIN good_moral_goodmoralreceiptassignment a ON a.id=v.assignment_id
   JOIN good_moral_goodmoralrequest r ON r.id=a.request_id
   WHERE a.request_id=rid AND v.invalidated_at IS NOT NULL AND (
     (v.invalidation_reason='CANCELLED' AND r.status<>'CANCELLED')
     OR (v.invalidation_reason='RECEIPT_REVISED' AND a.is_current)
     OR (v.invalidation_reason='POLICY_CHANGED' AND NOT EXISTS (
       SELECT 1 FROM good_moral_goodmoralreceiptverification successor
       WHERE successor.assignment_id=a.id AND successor.verified_at>v.verified_at
     ))
   )
 ) THEN
   RAISE EXCEPTION USING ERRCODE='23514', CONSTRAINT='gm_inspection_invalidation_transition', MESSAGE='Inspection invalidation requires its declared transition';
 END IF;
 IF EXISTS (
   SELECT 1 FROM good_moral_goodmoralreceiptverification v
   JOIN good_moral_goodmoralreceiptassignment a ON a.id=v.assignment_id
   JOIN good_moral_goodmoralrequest r ON r.id=a.request_id
   JOIN good_moral_goodmoralreceiptidentity i ON i.id=a.identity_id
   WHERE a.request_id=rid AND v.invalidated_at IS NULL AND
     (NOT a.is_current OR i.state<>'BOUND' OR i.bound_request_id<>r.id OR r.status='CANCELLED')
 ) THEN
   RAISE EXCEPTION USING ERRCODE='23514', CONSTRAINT='gm_inspection_eligibility', MESSAGE='Changed receipt requires inspection invalidation';
 END IF;
 RETURN NULL;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_receipt_request_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
 IF TG_OP='DELETE' THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_request_preserved' , MESSAGE =
     'Good Moral receipt evidence is preserved' ;
 END IF;
 IF TG_OP = 'UPDATE' AND ROW ( OLD.official_receipt_number , OLD.official_receipt_date ,
   OLD.official_receipt_amount )
    IS DISTINCT FROM ROW ( NEW.official_receipt_number , NEW.official_receipt_date ,
      NEW.official_receipt_amount ) THEN
   IF OLD.status IN ( 'ISSUED' , 'CANCELLED' ) OR ( OLD.status = 'READY_FOR_ISSUANCE' AND NEW.status
     <> 'REQUESTED' ) THEN
     RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_terminal_facts' , MESSAGE =
       'Receipt correction lifecycle is invalid' ;
   END IF;
 END IF;
 RETURN NEW;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_receipt_assignment_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE r good_moral_goodmoralrequest; prior good_moral_goodmoralreceiptassignment;
        ident good_moral_goodmoralreceiptidentity;
BEGIN
 IF TG_OP='DELETE' THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_claim_preserved' , MESSAGE =
     'Receipt claims cannot be deleted' ;
 END IF;
 SELECT * INTO r FROM good_moral_goodmoralrequest WHERE id=NEW.request_id FOR UPDATE;
 IF TG_OP='UPDATE' THEN
   IF OLD.is_current AND NOT NEW.is_current AND NEW.closed_at IS NOT NULL
       AND NEW.closed_by_id IS NOT NULL AND NEW.closure_reason='REVISION'
       AND NEW.closed_at>=OLD.recorded_at AND OLD.closed_at IS NULL
       AND (to_jsonb(NEW)-ARRAY['is_current','closed_at','closed_by_id','closure_reason'])
          = (to_jsonb(OLD)-ARRAY['is_current','closed_at','closed_by_id','closure_reason'])
       AND r.status IN ('REQUESTED','READY_FOR_ISSUANCE') THEN RETURN NEW; END IF;
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_revision_immutable' , MESSAGE
     = 'Receipt facts cannot be rewritten or reactivated' ;
 END IF;
 SELECT * INTO prior FROM good_moral_goodmoralreceiptassignment WHERE request_id = NEW.request_id
   ORDER BY sequence DESC LIMIT 1 ;
 IF NEW.sequence<>coalesce(prior.sequence,0)+1 OR NEW.previous_id IS DISTINCT FROM prior.id
    OR NEW.closed_at IS NOT NULL OR NEW.closed_by_id IS NOT NULL OR NEW.closure_reason<>'' THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_revision_chain' , MESSAGE =
     'Receipt revision predecessor or sequence is invalid' ;
 END IF;
 IF NEW.identity_id IS NOT NULL THEN
   SELECT * INTO ident FROM good_moral_goodmoralreceiptidentity WHERE id=NEW.identity_id FOR UPDATE;
   IF ident.id IS NULL OR gm_or_key(NEW.display_number) IS DISTINCT FROM ident.normalized_key THEN
     RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_claim_key' , MESSAGE =
       'Receipt revision does not match its reserved identifier' ;
   END IF;
 END IF;
 IF NEW.is_current AND ( ident.state IS DISTINCT FROM 'BOUND' OR ident.bound_request_id IS DISTINCT
   FROM NEW.request_id ) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_claim_owner' , MESSAGE =
     'Current receipt owner is invalid' ;
 END IF;
 IF NEW.origin='ORDINARY' AND r.status IN ('REQUESTED','READY_FOR_ISSUANCE') THEN
   IF NEW.identity_id IS NULL THEN
     IF NEW.display_number = '' AND NOT NEW.is_current AND NEW.change_kind = 'REMOVED' THEN RETURN
       NEW ; END IF ;
   ELSIF NEW.is_current AND NEW.display_number=btrim(NEW.display_number,' ')
         AND NEW.change_kind IN ('ASSIGNED','REVISED','REPLACED') THEN
     IF EXISTS ( SELECT 1 FROM good_moral_goodmoralreceiptassignment WHERE identity_id =
       NEW.identity_id )
       AND (prior.identity_id IS DISTINCT FROM NEW.identity_id
         OR NOT (prior.closed_at IS NOT NULL AND prior.closure_reason='REVISION')) THEN
       RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_no_reactivation' , MESSAGE
         = 'Reserved receipt cannot be adopted or reactivated' ;
     END IF;
     RETURN NEW;
   END IF;
 END IF;
 RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_claim_boundary' , MESSAGE =
   'Receipt revision source or lifecycle is invalid' ;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_receipt_projection_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE rid uuid; r good_moral_goodmoralrequest; a good_moral_goodmoralreceiptassignment;
BEGIN
 IF TG_TABLE_NAME='good_moral_goodmoralrequest' THEN rid=NEW.id; ELSE rid=NEW.request_id; END IF;
 SELECT * INTO r FROM good_moral_goodmoralrequest WHERE id=rid;
 SELECT * INTO a FROM good_moral_goodmoralreceiptassignment WHERE request_id = rid ORDER BY sequence
   DESC LIMIT 1 ;
 IF ( a.id IS NULL AND ( r.official_receipt_number <> '' OR r.official_receipt_date IS NOT NULL OR
   r.official_receipt_amount IS NOT NULL ) )
   OR (a.id IS NOT NULL AND ROW(a.display_number,a.receipt_date,a.amount) IS DISTINCT FROM
                          ROW ( r.official_receipt_number , r.official_receipt_date ,
                            r.official_receipt_amount ) )
   OR EXISTS (SELECT 1 FROM good_moral_goodmoralreceiptassignment
              WHERE request_id=rid AND is_current AND id<>a.id) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_projection_match' , MESSAGE =
     'Receipt projection must match its latest immutable revision' ;
 END IF;
 RETURN NULL;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_receipt_mutation_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE r good_moral_goodmoralrequest; latest uuid;
BEGIN
 IF TG_OP<>'INSERT' THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_operation_immutable' , MESSAGE
     = 'Receipt operations are immutable' ;
 END IF;
 SELECT * INTO r FROM good_moral_goodmoralrequest WHERE id=NEW.request_id FOR UPDATE;
 SELECT id INTO latest FROM good_moral_goodmoralreceiptassignment WHERE request_id = NEW.request_id
   ORDER BY sequence DESC LIMIT 1 ;
 IF NEW.result_revision_id IS DISTINCT FROM latest OR r.status NOT IN ( 'REQUESTED' ,
   'READY_FOR_ISSUANCE' )
    OR NEW.result_request_version::timestamptz IS DISTINCT FROM r.updated_at THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_operation_result' , MESSAGE =
     'Receipt operation result does not match the corrected request' ;
 END IF;
 IF NEW.fingerprint !~ '^[a-f0-9]{64}$'
    OR EXISTS (SELECT 1 FROM good_moral_goodmoralreceiptassignment
         WHERE id IN ( NEW.intended_revision_id , NEW.result_revision_id ) AND request_id <>
           NEW.request_id ) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_receipt_operation_shape' , MESSAGE =
     'Receipt operation references are invalid' ;
 END IF;
 RETURN NEW;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_receipt_verification_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE a good_moral_goodmoralreceiptassignment; r good_moral_goodmoralrequest;
        i good_moral_goodmoralreceiptidentity;
BEGIN
 IF TG_OP='DELETE' THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_inspection_preserved' , MESSAGE =
     'Physical inspection history is immutable' ;
 END IF;
 SELECT * INTO a FROM good_moral_goodmoralreceiptassignment WHERE id=NEW.assignment_id;
 SELECT * INTO r FROM good_moral_goodmoralrequest WHERE id=a.request_id FOR UPDATE;
 IF r.status NOT IN ('REQUESTED','READY_FOR_ISSUANCE') THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_inspection_boundary' , MESSAGE =
     'Physical inspection requires pending receipt context' ;
 END IF;
 IF TG_OP='UPDATE' THEN
   IF OLD.invalidated_at IS NULL AND NEW.invalidated_at>=OLD.verified_at
     AND NEW.invalidated_by_id IS NOT NULL AND NEW.invalidation_reason IN ( 'RECEIPT_REVISED' ,
       'CANCELLED' , 'POLICY_CHANGED' )
     AND (to_jsonb(NEW)-ARRAY['invalidated_at','invalidated_by_id','invalidation_reason']) =
         ( to_jsonb ( OLD ) - ARRAY [ 'invalidated_at' , 'invalidated_by_id' , 'invalidation_reason'
           ] ) THEN RETURN NEW ; END IF ;
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_inspection_immutable' , MESSAGE =
     'Physical inspection cannot be rewritten or reactivated' ;
 END IF;
 SELECT * INTO i FROM good_moral_goodmoralreceiptidentity WHERE id=a.identity_id FOR UPDATE;
 SELECT * INTO a FROM good_moral_goodmoralreceiptassignment WHERE id=NEW.assignment_id FOR UPDATE;
 IF NOT a.is_current OR i.state IS DISTINCT FROM 'BOUND' OR i.bound_request_id IS DISTINCT FROM
   a.request_id
    OR a.receipt_date IS NULL OR a.receipt_date>(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Manila')::date
    OR a.amount IS NULL OR a.amount<>NEW.expected_amount OR NEW.invalidated_at IS NOT NULL
    OR NEW.verified_at < transaction_timestamp ( ) OR NEW.verified_at > clock_timestamp ( ) +
      interval '1 second'
    OR NEW.fingerprint !~ '^[a-f0-9]{64}$'
    OR NEW.policy_id='' OR NEW.policy_version=''
    OR coalesce(NEW.fee_decision->>'status','') NOT IN ('APPROVED','PROVISIONAL')
    OR NEW.fee_decision->>'policy_id' IS DISTINCT FROM NEW.policy_id
    OR NEW.fee_decision->>'version' IS DISTINCT FROM NEW.policy_version
    OR NEW.fee_decision->>'currency' IS DISTINCT FROM NEW.currency
    OR (NEW.fee_decision->>'expected_amount')::numeric IS DISTINCT FROM NEW.expected_amount
    OR NEW.fee_decision->>'variant' IS DISTINCT FROM r.variant
    OR NEW.fee_decision->>'reference_date' IS DISTINCT FROM a.receipt_date::text
    OR NEW.fee_decision->>'applicability_rule' IS DISTINCT FROM 'RECEIPT_DATE_IN_APPROVED_RANGE'
    OR coalesce(NEW.fee_decision->>'authority_reference','')=''
    OR NOT coalesce(a.receipt_date BETWEEN (NEW.fee_decision->>'applicable_from')::date
                                      AND ( NEW.fee_decision ->> 'applicable_through' ) :: date ,
                                        false ) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_inspection_revision' , MESSAGE =
     'Physical inspection revision or fee evidence is invalid' ;
 END IF;
 RETURN NEW;
END $function$;
CREATE OR REPLACE FUNCTION public.gm_inspection_request_guard()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE vid uuid ; a good_moral_goodmoralreceiptassignment ; v
  good_moral_goodmoralreceiptverification ;
BEGIN
 IF TG_OP='UPDATE' AND OLD.status IN ('ISSUED','CANCELLED') AND NEW.status<>OLD.status THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_inspection_terminal' , MESSAGE =
     'Terminal receipt lifecycle cannot be reopened' ;
 END IF;
 IF TG_OP='UPDATE' AND OLD.status IN ('ISSUED','CANCELLED') AND
    ROW ( NEW.issued_receipt_assignment_id , NEW.issued_receipt_verification_id ,
      NEW.prepared_receipt_verification_id )
    IS DISTINCT FROM ROW ( OLD.issued_receipt_assignment_id , OLD.issued_receipt_verification_id ,
      OLD.prepared_receipt_verification_id ) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_issuance_receipt_immutable' , MESSAGE
     = 'Historical issuance evidence cannot be rewritten' ;
 END IF;
 IF (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM NEW.status
       OR OLD.prepared_at IS DISTINCT FROM NEW.prepared_at
       OR OLD.prepared_receipt_verification_id IS DISTINCT FROM NEW.prepared_receipt_verification_id
         )
       AND NEW.status IN ('READY_FOR_ISSUANCE','ISSUED') THEN
   vid = CASE WHEN NEW.status = 'ISSUED' THEN NEW.issued_receipt_verification_id ELSE
     NEW.prepared_receipt_verification_id END ;
   SELECT * INTO v FROM good_moral_goodmoralreceiptverification WHERE id=vid;
   SELECT * INTO a FROM good_moral_goodmoralreceiptassignment WHERE id=v.assignment_id;
   IF v.id IS NULL OR v.invalidated_at IS NOT NULL OR a.request_id IS DISTINCT FROM NEW.id OR NOT
     a.is_current
      OR (NEW.status='ISSUED' AND (NEW.issued_receipt_assignment_id IS DISTINCT FROM a.id
          OR NEW.prepared_receipt_verification_id IS DISTINCT FROM v.id)) THEN
     RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_transition_inspection_required' ,
       MESSAGE = 'New transition requires exact physical inspection evidence' ;
   END IF;
 END IF;
 IF NEW.prepared_receipt_verification_id IS NOT NULL AND NOT EXISTS (
   SELECT 1 FROM good_moral_goodmoralreceiptverification av JOIN
     good_moral_goodmoralreceiptassignment aa ON aa.id = av.assignment_id
   WHERE av.id=NEW.prepared_receipt_verification_id AND aa.request_id=NEW.id
 ) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_preparation_receipt_owner' , MESSAGE =
     'Preparation inspection belongs to another request' ;
 END IF;
 IF NEW.status <> 'ISSUED' AND ( NEW.issued_receipt_assignment_id IS NOT NULL OR
   NEW.issued_receipt_verification_id IS NOT NULL ) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_issuance_receipt_shape' , MESSAGE =
     'Issuance evidence requires issued status' ;
 END IF;
 IF (NEW.issued_receipt_assignment_id IS NULL)<>(NEW.issued_receipt_verification_id IS NULL) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_issuance_receipt_pair' , MESSAGE =
     'Issuance evidence must be paired' ;
 END IF;
 IF NEW.issued_receipt_verification_id IS NOT NULL AND NOT EXISTS (
     SELECT 1 FROM good_moral_goodmoralreceiptverification av JOIN
       good_moral_goodmoralreceiptassignment aa ON aa.id = av.assignment_id
     WHERE av.id = NEW.issued_receipt_verification_id AND aa.id = NEW.issued_receipt_assignment_id
       AND aa.request_id = NEW.id ) THEN
   RAISE EXCEPTION USING ERRCODE = '23514' , CONSTRAINT = 'gm_issuance_receipt_owner' , MESSAGE =
     'Issuance evidence must belong to this request' ;
 END IF;
 RETURN NEW;
END $function$;
CREATE TRIGGER gm_receipt_request_guard BEFORE INSERT OR DELETE OR UPDATE ON public.good_moral_goodmoralrequest FOR EACH ROW EXECUTE FUNCTION gm_receipt_request_guard();
CREATE TRIGGER gm_receipt_identity_guard BEFORE INSERT OR DELETE OR UPDATE ON public.good_moral_goodmoralreceiptidentity FOR EACH ROW EXECUTE FUNCTION gm_receipt_identity_guard();
CREATE TRIGGER gm_receipt_assignment_guard BEFORE INSERT OR DELETE OR UPDATE ON public.good_moral_goodmoralreceiptassignment FOR EACH ROW EXECUTE FUNCTION gm_receipt_assignment_guard();
CREATE CONSTRAINT TRIGGER gm_receipt_projection_request AFTER INSERT OR UPDATE ON public.good_moral_goodmoralrequest DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gm_receipt_projection_guard();
CREATE CONSTRAINT TRIGGER gm_receipt_projection_revision AFTER INSERT OR UPDATE ON public.good_moral_goodmoralreceiptassignment DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gm_receipt_projection_guard();
CREATE CONSTRAINT TRIGGER gm_receipt_closure_successor AFTER UPDATE ON public.good_moral_goodmoralreceiptassignment DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gm_receipt_closure_successor();
CREATE TRIGGER gm_receipt_mutation_guard BEFORE INSERT OR DELETE OR UPDATE ON public.good_moral_goodmoralreceiptmutation FOR EACH ROW EXECUTE FUNCTION gm_receipt_mutation_guard();
CREATE CONSTRAINT TRIGGER gm_receipt_identity_claim AFTER INSERT ON public.good_moral_goodmoralreceiptidentity DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gm_receipt_identity_claim();
CREATE TRIGGER gm_receipt_verification_guard BEFORE INSERT OR DELETE OR UPDATE ON public.good_moral_goodmoralreceiptverification FOR EACH ROW EXECUTE FUNCTION gm_receipt_verification_guard();
CREATE CONSTRAINT TRIGGER gm_inspection_request AFTER INSERT OR UPDATE ON public.good_moral_goodmoralrequest DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gm_inspection_eligibility_guard();
CREATE CONSTRAINT TRIGGER gm_inspection_assignment AFTER UPDATE ON public.good_moral_goodmoralreceiptassignment DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gm_inspection_eligibility_guard();
CREATE CONSTRAINT TRIGGER gm_inspection_verification AFTER INSERT OR UPDATE ON public.good_moral_goodmoralreceiptverification DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gm_inspection_eligibility_guard();
CREATE TRIGGER gm_inspection_request_guard BEFORE INSERT OR UPDATE ON public.good_moral_goodmoralrequest FOR EACH ROW EXECUTE FUNCTION gm_inspection_request_guard();
"""

REVERSE_SQL = r"""
DROP TRIGGER gm_receipt_request_guard ON public.good_moral_goodmoralrequest;
DROP TRIGGER gm_receipt_identity_guard ON public.good_moral_goodmoralreceiptidentity;
DROP TRIGGER gm_receipt_assignment_guard ON public.good_moral_goodmoralreceiptassignment;
DROP TRIGGER gm_receipt_projection_request ON public.good_moral_goodmoralrequest;
DROP TRIGGER gm_receipt_projection_revision ON public.good_moral_goodmoralreceiptassignment;
DROP TRIGGER gm_receipt_closure_successor ON public.good_moral_goodmoralreceiptassignment;
DROP TRIGGER gm_receipt_mutation_guard ON public.good_moral_goodmoralreceiptmutation;
DROP TRIGGER gm_receipt_identity_claim ON public.good_moral_goodmoralreceiptidentity;
DROP TRIGGER gm_receipt_verification_guard ON public.good_moral_goodmoralreceiptverification;
DROP TRIGGER gm_inspection_request ON public.good_moral_goodmoralrequest;
DROP TRIGGER gm_inspection_assignment ON public.good_moral_goodmoralreceiptassignment;
DROP TRIGGER gm_inspection_verification ON public.good_moral_goodmoralreceiptverification;
DROP TRIGGER gm_inspection_request_guard ON public.good_moral_goodmoralrequest;
DROP FUNCTION public.gm_inspection_request_guard();
DROP FUNCTION public.gm_receipt_verification_guard();
DROP FUNCTION public.gm_receipt_mutation_guard();
DROP FUNCTION public.gm_receipt_projection_guard();
DROP FUNCTION public.gm_receipt_assignment_guard();
DROP FUNCTION public.gm_receipt_request_guard();
DROP FUNCTION public.gm_inspection_eligibility_guard();
DROP FUNCTION public.gm_receipt_identity_guard();
DROP FUNCTION public.gm_receipt_identity_claim();
DROP FUNCTION public.gm_receipt_closure_successor();
DROP FUNCTION public.gm_or_key(value text);
"""


class Migration(migrations.Migration):
    dependencies = [
        ('good_moral', '0001_release_baseline'),
        ('accounts', '0001_release_baseline'),
        ('audit', '0001_release_baseline'),
        ('institutional_forms', '0001_release_baseline'),
        ('organization', '0001_release_baseline'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
