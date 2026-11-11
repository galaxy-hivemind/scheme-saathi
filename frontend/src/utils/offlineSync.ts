import { api } from '../api/client';

const OFFLINE_DRAFTS_KEY = 'scheme_saathi_offline_drafts';

export interface OfflineDraftItem {
  local_id: string;
  scheme_id: string;
  beneficiary_id?: string | null;
  notes?: string;
  created_at: string;
  pending_sync: boolean;
}

/**
 * Saves an application draft locally when the citizen is disconnected.
 */
export function saveOfflineDraft(
  schemeId: string,
  beneficiaryId?: string | null,
  notes?: string
): OfflineDraftItem {
  const existing = getOfflineDrafts();
  const newItem: OfflineDraftItem = {
    local_id: `offline-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
    scheme_id: schemeId,
    beneficiary_id: beneficiaryId || null,
    notes: notes || undefined,
    created_at: new Date().toISOString(),
    pending_sync: true,
  };

  existing.push(newItem);
  try {
    localStorage.setItem(OFFLINE_DRAFTS_KEY, JSON.stringify(existing));
  } catch (err) {
    console.error('Failed to store offline draft:', err);
  }

  return newItem;
}

/**
 * Retrieves all pending offline application drafts.
 */
export function getOfflineDrafts(): OfflineDraftItem[] {
  try {
    const raw = localStorage.getItem(OFFLINE_DRAFTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

/**
 * Clears synced items from the offline queue.
 */
export function removeOfflineDraft(localId: string): void {
  const existing = getOfflineDrafts().filter((d) => d.local_id !== localId);
  try {
    localStorage.setItem(OFFLINE_DRAFTS_KEY, JSON.stringify(existing));
  } catch (err) {
    console.error('Failed to update offline drafts storage:', err);
  }
}

/**
 * Automatically syncs all pending offline drafts to the backend API when online.
 * Returns the number of successfully synced drafts.
 */
export async function syncPendingDrafts(): Promise<number> {
  const pending = getOfflineDrafts().filter((d) => d.pending_sync);
  if (pending.length === 0) return 0;

  let syncedCount = 0;
  for (const item of pending) {
    try {
      await api.applications.createDraft(item.scheme_id, item.beneficiary_id, item.notes);
      removeOfflineDraft(item.local_id);
      syncedCount++;
    } catch (err) {
      console.warn(`[PWA Sync] Failed to sync draft for scheme ${item.scheme_id}:`, err);
    }
  }

  return syncedCount;
}
