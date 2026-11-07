"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import type { GuidancePerson } from "@/lib/api/generated/model";

export function GuidanceCounselorPeerPicker({
  label,
  search,
  onSearchChange,
  onSearch,
  items,
  selectedPeer,
  selectedId,
  onSelect,
  page,
  hasNext,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  onPageChange,
}: {
  label: string;
  search: string;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  items: GuidancePerson[];
  selectedPeer: GuidancePerson | null;
  selectedId: string | null;
  onSelect: (peer: GuidancePerson) => void;
  page: number;
  hasNext: boolean;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string;
  onRetry: () => void;
  onPageChange: (page: number) => void;
}) {
  return (
    <fieldset className="min-w-0" aria-busy={isLoading}>
      <legend className="text-sm font-semibold text-ink">{label}</legend>
      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          onSearch();
        }}
      >
        <div className="min-w-0 flex-1">
          <Label htmlFor="guidance-counselor-peer-search">Search Counselors</Label>
          <Input
            id="guidance-counselor-peer-search"
            type="search"
            autoComplete="off"
            maxLength={160}
            placeholder="Search name"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
        <Button className="self-end" variant="secondary" type="submit">
          Search
        </Button>
      </form>
      {selectedPeer ? (
        <div className="mt-3 flex items-center gap-2 rounded-sm bg-brand-wash px-3 py-2 text-sm text-ink">
          <PersonAvatar displayName={selectedPeer.display_name} size="compact" />
          <p>
            Selected: <span className="font-semibold">{selectedPeer.display_name}</span>
          </p>
        </div>
      ) : null}
      {isError ? (
        <div role="alert" className="mt-4">
          <p className="text-sm text-danger">{errorMessage}</p>
          <Button className="mt-3" variant="secondary" onClick={onRetry}>
            Retry Counselor search
          </Button>
        </div>
      ) : isLoading ? (
        <p role="status" className="mt-4 text-sm text-muted">Loading Counselors…</p>
      ) : items.length === 0 ? (
        <p className="mt-4 rounded-sm bg-surface-subtle px-4 py-3 text-sm text-muted">
          No Counselors match this search.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-border rounded-sm border border-border">
          {items.map((peer) => (
            <li key={peer.id}>
              <label className="flex min-h-11 cursor-pointer items-start gap-3 px-3 py-3 text-sm text-ink transition-colors hover:bg-surface-subtle has-[:checked]:bg-brand-wash">
                <input
                  className="mt-1 h-4 w-4 shrink-0 accent-brand"
                  type="radio"
                  name="guidance-counselor-peer"
                  value={peer.id}
                  checked={selectedId === peer.id}
                  onChange={() => onSelect(peer)}
                />
                <PersonAvatar displayName={peer.display_name} size="compact" />
                <span className="min-w-0">
                  <span className="block font-semibold">{peer.display_name}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
      {!isError && !isLoading ? (
        <CanonicalPagination
          className="mt-3 border-t-0 pb-0"
          page={page}
          hasNext={hasNext}
          label="Counselor results"
          onPageChange={onPageChange}
        />
      ) : null}
    </fieldset>
  );
}
