// The API contract (spec Section 6) has no "list my submissions across
// hackathons" endpoint — GET /hackathons/{id}/submissions is admin-only, and
// GET /submissions/{id} needs an id the client already has. So the frontend
// remembers { hackathonId -> submissionId } locally, populated the moment a
// participant successfully submits, so they can navigate back to their own
// status/evaluation page without the backend needing to expose a new route.
//
// Scoped per userId (not one global key): localStorage is shared across the
// whole browser origin regardless of who's logged in, so without per-user
// namespacing, logging out and back in as a different participant on the
// same machine would show the PREVIOUS user's "already joined" / "already
// submitted" state — a real cross-account data leak, not just a cosmetic bug.

function readAll(storageKey: string): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(storageKey) || "{}");
  } catch {
    return {};
  }
}

function submissionsKey(userId: string): string {
  return `evalon-my-submissions:${userId}`;
}

export function rememberSubmission(userId: string, hackathonId: string, submissionId: string): void {
  if (typeof window === "undefined") return;
  const key = submissionsKey(userId);
  const all = readAll(key);
  all[hackathonId] = submissionId;
  localStorage.setItem(key, JSON.stringify(all));
}

export function getMySubmissionId(userId: string | undefined, hackathonId: string): string | null {
  if (!userId) return null;
  return readAll(submissionsKey(userId))[hackathonId] || null;
}

export function getAllMySubmissions(userId: string | undefined): Record<string, string> {
  if (!userId) return {};
  return readAll(submissionsKey(userId));
}

// Same rationale as above: there's no "my joined hackathons" endpoint
// (GET /hackathons/{id}/participants is admin-only), so the "Joined" badge
// on the hackathon list is backed by a local, per-user set updated on join.

function joinedKey(userId: string): string {
  return `evalon-joined-hackathons:${userId}`;
}

function readJoined(userId: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(joinedKey(userId)) || "[]");
  } catch {
    return [];
  }
}

export function rememberJoined(userId: string, hackathonId: string): void {
  if (typeof window === "undefined") return;
  const joined = new Set(readJoined(userId));
  joined.add(hackathonId);
  localStorage.setItem(joinedKey(userId), JSON.stringify([...joined]));
}

export function hasJoined(userId: string | undefined, hackathonId: string): boolean {
  if (!userId) return false;
  return readJoined(userId).includes(hackathonId);
}
