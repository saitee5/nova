/**
 * frontend/src/utils/assetAliases.ts
 *
 * Centralized reconciliation between frontend 3D scene display tags and
 * backend canonical asset IDs.
 *
 * Examples:
 * F-301A ↔ F-201A
 * TLE-301 ↔ E-201
 * K-301 ↔ K-201
 * C-302 ↔ V-201
 * P-202A ↔ P-201A
 * P-202B ↔ P-201B
 * T-101A ↔ T-201
 */

const DISPLAY_TO_CANONICAL: Record<string, string> = {
  'F-301A': 'F-201A',
  'F-301B': 'F-201A',
  'TLE-301': 'E-201',
  'K-301': 'K-201',
  'C-302': 'V-201',
  'C-201': 'V-201',
  'P-202A': 'P-201A',
  'P-202B': 'P-201B',
  'T-101A': 'T-201',
  'T-101B': 'T-201',
  'T-102': 'T-201',
}

const CANONICAL_TO_DISPLAY: Record<string, string> = {
  'F-201A': 'F-301A',
  'E-201': 'TLE-301',
  'K-201': 'K-301',
  'V-201': 'C-302',
  'P-201A': 'P-202A',
  'P-201B': 'P-202B',
  'T-201': 'T-101A',
  'SYS-FUEL-GAS': 'SYS-FUEL-GAS',
  'SYS-FLARE': 'SYS-FLARE',
  'SYS-FNG': 'SYS-FNG',
}

/**
 * Returns the canonical backend asset ID for a given frontend display tag or ID.
 * If no alias is mapped and it already matches a known canonical pattern or format,
 * returns the identifier as-is.
 */
export function toCanonicalAssetId(displayTagOrId?: string | null): string {
  if (!displayTagOrId) return ''
  const trimmed = displayTagOrId.trim()
  if (DISPLAY_TO_CANONICAL[trimmed]) {
    return DISPLAY_TO_CANONICAL[trimmed]
  }
  return trimmed
}

/**
 * Returns the frontend display tag for a given backend canonical asset ID.
 * If not mapped, returns the canonical ID as-is.
 */
export function toDisplayTag(canonicalAssetId?: string | null): string {
  if (!canonicalAssetId) return ''
  const trimmed = canonicalAssetId.trim()
  if (CANONICAL_TO_DISPLAY[trimmed]) {
    return CANONICAL_TO_DISPLAY[trimmed]
  }
  return trimmed
}

/**
 * Returns true if the given ID or tag corresponds to the same equipment item.
 */
export function isSameAsset(tagA?: string | null, tagB?: string | null): boolean {
  if (!tagA || !tagB) return false
  if (tagA === tagB) return true
  return toCanonicalAssetId(tagA) === toCanonicalAssetId(tagB)
}
