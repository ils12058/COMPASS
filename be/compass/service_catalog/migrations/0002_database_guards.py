"""Frozen final PostgreSQL database guards; see ADR-117."""

from django.db import migrations


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION public.compass_service_slot_record_booking_history()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
            IF NEW.current_appointment_id IS NOT NULL
                AND NEW.current_appointment_id IS DISTINCT FROM OLD.current_appointment_id THEN
                INSERT INTO service_catalog_serviceappointmentslotbooking
                    (id, created_at, appointment_id, slot_id)
                VALUES (
                    md5(NEW.id::text || ':' || NEW.current_appointment_id::text)::uuid,
                    CURRENT_TIMESTAMP,
                    NEW.current_appointment_id,
                    NEW.id
                )
                ON CONFLICT (slot_id, appointment_id) DO NOTHING;
            END IF;
            RETURN NEW;
        END;
        $function$;
CREATE OR REPLACE FUNCTION public.compass_service_slot_prevent_delete()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
            RAISE EXCEPTION 'Service Appointment Slots are operational records and cannot be deleted';
        END;
        $function$;
CREATE OR REPLACE FUNCTION public.compass_service_slot_booking_prevent_delete()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
            RAISE EXCEPTION 'Fixed Slot booking history is append-only';
        END;
        $function$;
CREATE TRIGGER compass_service_slot_record_booking_history AFTER UPDATE OF current_appointment_id ON public.service_catalog_serviceappointmentslot FOR EACH ROW EXECUTE FUNCTION compass_service_slot_record_booking_history();
CREATE TRIGGER compass_service_slot_prevent_delete BEFORE DELETE ON public.service_catalog_serviceappointmentslot FOR EACH ROW EXECUTE FUNCTION compass_service_slot_prevent_delete();
CREATE TRIGGER compass_service_slot_booking_prevent_delete BEFORE DELETE ON public.service_catalog_serviceappointmentslotbooking FOR EACH ROW EXECUTE FUNCTION compass_service_slot_booking_prevent_delete();
"""

REVERSE_SQL = r"""
DROP TRIGGER compass_service_slot_record_booking_history ON public.service_catalog_serviceappointmentslot;
DROP TRIGGER compass_service_slot_prevent_delete ON public.service_catalog_serviceappointmentslot;
DROP TRIGGER compass_service_slot_booking_prevent_delete ON public.service_catalog_serviceappointmentslotbooking;
DROP FUNCTION public.compass_service_slot_booking_prevent_delete();
DROP FUNCTION public.compass_service_slot_prevent_delete();
DROP FUNCTION public.compass_service_slot_record_booking_history();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('service_catalog', '0001_release_baseline'),
        ('appointments', '0002_release_baseline_links'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
