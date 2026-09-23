"use client";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { InventoryNotice, inventorySelectClass } from "@/features/inventory/inventory-shared";
import type { GeographicLocationPayload, GeographicLocationKindValue as LocationKind } from "@/lib/api/generated/model";
import { GeographicLocationKindValue } from "@/lib/api/generated/model";
import {
  useReferenceDataListPSGCBarangays,
  useReferenceDataListPSGCCitiesMunicipalities,
  useReferenceDataListPSGCProvinces,
  useReferenceDataListPSGCRegions,
} from "@/lib/api/generated/reference-data/reference-data";

export function PSGCLocationSelector({
  kind,
  location,
  onChange,
}: {
  kind: LocationKind;
  location?: GeographicLocationPayload;
  onChange: (value: GeographicLocationPayload | undefined) => void;
}) {
  const permanent = kind === GeographicLocationKindValue.PERMANENT;
  const mode = !location
    ? ""
    : location.not_specified
      ? "not_specified"
      : "specified";
  const regions = useReferenceDataListPSGCRegions({ query: { retry: false } });
  const provinces = useReferenceDataListPSGCProvinces(
    { region_code: location?.region_psgc_code ?? "" },
    { query: { enabled: Boolean(location?.region_psgc_code), retry: false } },
  );
  const cities = useReferenceDataListPSGCCitiesMunicipalities(
    {
      region_code: location?.region_psgc_code ?? "",
      ...(location?.province_psgc_code
        ? { province_code: location.province_psgc_code }
        : {}),
    },
    { query: { enabled: Boolean(location?.region_psgc_code), retry: false } },
  );
  const barangays = useReferenceDataListPSGCBarangays(
    { city_municipality_code: location?.city_municipality_psgc_code ?? "" },
    {
      query: {
        enabled: Boolean(location?.city_municipality_psgc_code),
        retry: false,
      },
    },
  );

  const regionItems = regions.data?.data.items ?? [];
  const provinceItems = provinces.data?.data.items ?? [];
  const cityItems = cities.data?.data.items ?? [];
  const barangayItems = barangays.data?.data.items ?? [];

  function chooseMode(nextMode: string) {
    if (nextMode === "") {
      onChange(undefined);
      return;
    }
    if (nextMode === "not_specified") {
      onChange({ kind, not_specified: true });
      return;
    }
    if (nextMode === "specified") {
      onChange({ kind, not_specified: false });
    }
  }

  function chooseRegion(code: string) {
    const selected = regionItems.find((item) => item.code === code);
    if (!selected) return;
    onChange({
      kind,
      not_specified: false,
      region_psgc_code: selected.code,
      region_name_snapshot: selected.name,
    });
  }

  function chooseProvince(code: string) {
    const selected = provinceItems.find((item) => item.code === code);
    if (!selected) {
      onChange({
        ...location,
        kind,
        province_psgc_code: undefined,
        province_name_snapshot: undefined,
        city_municipality_psgc_code: undefined,
        city_municipality_name_snapshot: undefined,
        barangay_psgc_code: undefined,
        barangay_name_snapshot: undefined,
      });
      return;
    }
    onChange({
      ...location,
      kind,
      not_specified: false,
      province_psgc_code: selected.code,
      province_name_snapshot: selected.name,
      city_municipality_psgc_code: undefined,
      city_municipality_name_snapshot: undefined,
      barangay_psgc_code: undefined,
      barangay_name_snapshot: undefined,
    });
  }

  function chooseCity(code: string) {
    const selected = cityItems.find((item) => item.code === code);
    if (!selected) return;
    onChange({
      ...location,
      kind,
      not_specified: false,
      city_municipality_psgc_code: selected.code,
      city_municipality_name_snapshot: selected.name,
      barangay_psgc_code: undefined,
      barangay_name_snapshot: undefined,
    });
  }

  function chooseBarangay(code: string) {
    const selected = barangayItems.find((item) => item.code === code);
    onChange({
      ...location,
      kind,
      not_specified: false,
      barangay_psgc_code: selected?.code,
      barangay_name_snapshot: selected?.name,
    });
  }

  const hasLookupFailure =
    regions.isError || provinces.isError || cities.isError || barangays.isError;
  const savedSnapshot = [
    location?.barangay_name_snapshot,
    location?.city_municipality_name_snapshot,
    location?.province_name_snapshot,
    location?.region_name_snapshot,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <section className="space-y-4" aria-labelledby={`inventory-${kind.toLowerCase()}-location-heading`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id={`inventory-${kind.toLowerCase()}-location-heading`} className="font-semibold text-ink">
            {permanent ? "Permanent structured location" : "Current structured location"}
            {!permanent ? <span className="ml-1 text-danger" aria-hidden="true">*</span> : null}
          </h3>
          <p className="mt-1 text-xs leading-5 text-muted">
            This is separate from the address written above. {!permanent ? "A response is required before submission." : ""}
          </p>
        </div>
        {permanent && location ? (
          <Button variant="quiet" onClick={() => onChange(undefined)}>
            Clear permanent location
          </Button>
        ) : null}
      </div>

      {!permanent || location ? (
        <div className="max-w-xl">
          <Label htmlFor={`inventory-${kind.toLowerCase()}-location-choice`}>
            Location response
          </Label>
          <select
            id={`inventory-${kind.toLowerCase()}-location-choice`}
            className={`mt-2 ${inventorySelectClass}`}
            value={mode}
            onChange={(event) => chooseMode(event.target.value)}
          >
            <option value="">Choose how to provide this location</option>
            <option value="specified">Provide structured location</option>
            <option value="not_specified">Prefer not to specify</option>
          </select>
        </div>
      ) : (
        <Button
          variant="secondary"
          onClick={() => onChange({ kind, not_specified: true })}
        >
          Add permanent structured location
        </Button>
      )}

      {mode === "specified" ? (
        <>
          {hasLookupFailure ? (
            <InventoryNotice tone="warning" role="status">
              Official location choices are temporarily unavailable.
              {savedSnapshot ? (
                <span className="mt-1 block">Saved location: {savedSnapshot}</span>
              ) : null}
              Saved location data is preserved. You can continue editing other sections.
            </InventoryNotice>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor={`inventory-${kind.toLowerCase()}-region`}>Region</Label>
              <select
                id={`inventory-${kind.toLowerCase()}-region`}
                className={`mt-2 ${inventorySelectClass}`}
                value={location?.region_psgc_code ?? ""}
                disabled={regions.isPending || regions.isError}
                onChange={(event) => chooseRegion(event.target.value)}
              >
                <option value="">Select a region</option>
                {location?.region_psgc_code &&
                !regionItems.some((item) => item.code === location.region_psgc_code) ? (
                  <option value={location.region_psgc_code}>
                    {location.region_name_snapshot ?? "Previously saved region"}
                  </option>
                ) : null}
                {regionItems.map((item) => (
                  <option key={item.code} value={item.code}>{item.name}</option>
                ))}
              </select>
              {regions.isPending ? <p role="status" className="mt-1 text-xs text-muted">Loading regions…</p> : null}
            </div>

            <div>
              <Label htmlFor={`inventory-${kind.toLowerCase()}-province`}>
                Province <span className="font-normal text-muted">(where applicable)</span>
              </Label>
              <select
                id={`inventory-${kind.toLowerCase()}-province`}
                className={`mt-2 ${inventorySelectClass}`}
                value={location?.province_psgc_code ?? ""}
                disabled={!location?.region_psgc_code || provinces.isPending || provinces.isError}
                onChange={(event) => chooseProvince(event.target.value)}
              >
                <option value="">No province / not applicable</option>
                {location?.province_psgc_code &&
                !provinceItems.some((item) => item.code === location.province_psgc_code) ? (
                  <option value={location.province_psgc_code}>
                    {location.province_name_snapshot ?? "Previously saved province"}
                  </option>
                ) : null}
                {provinceItems.map((item) => (
                  <option key={item.code} value={item.code}>{item.name}</option>
                ))}
              </select>
            </div>

            <div>
              <Label htmlFor={`inventory-${kind.toLowerCase()}-city`}>City / Municipality</Label>
              <select
                id={`inventory-${kind.toLowerCase()}-city`}
                className={`mt-2 ${inventorySelectClass}`}
                value={location?.city_municipality_psgc_code ?? ""}
                disabled={!location?.region_psgc_code || cities.isPending || cities.isError}
                onChange={(event) => chooseCity(event.target.value)}
              >
                <option value="">Select a city or municipality</option>
                {location?.city_municipality_psgc_code &&
                !cityItems.some((item) => item.code === location.city_municipality_psgc_code) ? (
                  <option value={location.city_municipality_psgc_code}>
                    {location.city_municipality_name_snapshot ?? "Previously saved city / municipality"}
                  </option>
                ) : null}
                {cityItems.map((item) => (
                  <option key={item.code} value={item.code}>{item.name}</option>
                ))}
              </select>
              {cities.isPending ? <p role="status" className="mt-1 text-xs text-muted">Loading cities and municipalities…</p> : null}
            </div>

            <div>
              <Label htmlFor={`inventory-${kind.toLowerCase()}-barangay`}>
                Barangay <span className="font-normal text-muted">(optional)</span>
              </Label>
              <select
                id={`inventory-${kind.toLowerCase()}-barangay`}
                className={`mt-2 ${inventorySelectClass}`}
                value={location?.barangay_psgc_code ?? ""}
                disabled={!location?.city_municipality_psgc_code || barangays.isPending || barangays.isError}
                onChange={(event) => chooseBarangay(event.target.value)}
              >
                <option value="">No barangay selected</option>
                {location?.barangay_psgc_code &&
                !barangayItems.some((item) => item.code === location.barangay_psgc_code) ? (
                  <option value={location.barangay_psgc_code}>
                    {location.barangay_name_snapshot ?? "Previously saved barangay"}
                  </option>
                ) : null}
                {barangayItems.map((item) => (
                  <option key={item.code} value={item.code}>{item.name}</option>
                ))}
              </select>
            </div>
          </div>
          <p aria-live="polite" className="sr-only">
            {regions.isError
              ? "Region choices could not be loaded. Saved location is preserved."
              : provinces.isError
                ? "Province choices could not be loaded. Saved location is preserved."
                : cities.isError
                  ? "City and municipality choices could not be loaded. Saved location is preserved."
                  : barangays.isError
                    ? "Barangay choices could not be loaded. Saved location is preserved."
                    : ""}
          </p>
        </>
      ) : mode === "not_specified" ? (
        <p className="text-sm text-muted">
          Your response will be recorded as “Prefer not to specify.”
        </p>
      ) : null}
    </section>
  );
}
