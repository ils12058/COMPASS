"""Frozen final PostgreSQL database guards; see ADR-117."""

from django.db import migrations


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION public.referrals_submission_origin_immutable()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
 IF ROW(NEW.submission_channel, NEW.submitted_by_id, NEW.submitted_at,
        NEW.faculty_home_college_id, NEW.student_college_at_submission_id,
        NEW.submission_policy_digest, NEW.submission_policy_event_id)
    IS DISTINCT FROM
    ROW(OLD.submission_channel, OLD.submitted_by_id, OLD.submitted_at,
        OLD.faculty_home_college_id, OLD.student_college_at_submission_id,
        OLD.submission_policy_digest, OLD.submission_policy_event_id)
 OR (OLD.submission_channel = 'FACULTY_PORTAL' AND
     ROW(NEW.student_id, NEW.student_name_snapshot, NEW.course_year_block_snapshot,
         NEW.form_revision_id, NEW.referred_on, NEW.reference_code,
         NEW.creation_key_digest, NEW.creation_request_fingerprint)
     IS DISTINCT FROM
     ROW(OLD.student_id, OLD.student_name_snapshot, OLD.course_year_block_snapshot,
         OLD.form_revision_id, OLD.referred_on, OLD.reference_code,
         OLD.creation_key_digest, OLD.creation_request_fingerprint)) THEN
   RAISE EXCEPTION USING ERRCODE='23514', CONSTRAINT='referral_origin_immutable',
     MESSAGE='Referral submission provenance is immutable';
 END IF;
 RETURN NEW;
END $function$;
CREATE OR REPLACE FUNCTION public.referrals_administration_immutable()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
 IF TG_OP = 'DELETE' THEN
  IF OLD.acknowledged_by_id IS NOT NULL THEN
   RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Referral administrative history is immutable';
  END IF;
  RETURN OLD;
 ELSIF TG_OP = 'INSERT' THEN
  IF NEW.acknowledged_by_id IS NOT NULL OR NEW.administratively_closed_at IS NOT NULL THEN
   RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Faculty Referrals start unacknowledged';
  END IF;
  RETURN NEW;
 END IF;
 IF OLD.acknowledged_by_id IS NOT NULL AND
    ROW(OLD.acknowledged_by_id, OLD.received_at, OLD.acknowledgment_policy_digest,
        OLD.acknowledgment_policy_event_id) IS DISTINCT FROM
    ROW(NEW.acknowledged_by_id, NEW.received_at, NEW.acknowledgment_policy_digest,
        NEW.acknowledgment_policy_event_id) THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Referral acknowledgment is immutable';
 END IF;
 IF OLD.administratively_closed_at IS NOT NULL AND
    ROW(OLD.administratively_closed_at, OLD.administratively_closed_by_id,
        OLD.closure_policy_digest, OLD.closure_policy_event_id) IS DISTINCT FROM
    ROW(NEW.administratively_closed_at, NEW.administratively_closed_by_id,
        NEW.closure_policy_digest, NEW.closure_policy_event_id) THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Referral administrative closure is immutable';
 END IF;
 IF (OLD.voided_at IS NOT NULL OR NEW.voided_at IS NOT NULL) AND
    ROW(OLD.acknowledged_by_id, OLD.administratively_closed_at) IS DISTINCT FROM
    ROW(NEW.acknowledged_by_id, NEW.administratively_closed_at) THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Voided Referrals cannot transition';
 END IF;
 IF OLD.acknowledged_by_id IS NULL AND NEW.administratively_closed_at IS NOT NULL THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Closure requires prior acknowledgment';
 END IF;
 RETURN NEW;
END $function$;
CREATE TRIGGER referrals_submission_origin_guard BEFORE UPDATE ON public.referrals_referral FOR EACH ROW EXECUTE FUNCTION referrals_submission_origin_immutable();
CREATE TRIGGER referrals_administration_guard BEFORE INSERT OR DELETE OR UPDATE ON public.referrals_referral FOR EACH ROW EXECUTE FUNCTION referrals_administration_immutable();
"""

REVERSE_SQL = r"""
DROP TRIGGER referrals_submission_origin_guard ON public.referrals_referral;
DROP TRIGGER referrals_administration_guard ON public.referrals_referral;
DROP FUNCTION public.referrals_administration_immutable();
DROP FUNCTION public.referrals_submission_origin_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('referrals', '0001_release_baseline'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
