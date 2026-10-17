import type {
  CriticalHabitatArea,
  SiteSpeciesContext,
  SpeciesEntry,
} from '../../types/api'

/**
 * How directly a listed animal bears on work at the site, from sourced fields only.
 *
 * - `crew_hazard`: the cited encounter source describes a way it can hurt workers.
 * - `work_impact`: critical habitat at or near the site, or cited guidance that
 *   requires crews to act (for example stopping work near it).
 * - `background`: listed for the area, with nothing on record that changes the work.
 *
 * Never inferred from protection status alone, and never a sighting.
 */
export type Relevance = 'crew_hazard' | 'work_impact' | 'background'

export interface WildlifeRow {
  species: SpeciesEntry
  /** Critical habitat areas from the map service for this species. */
  habitat: CriticalHabitatArea[]
  relevance: Relevance
  /** Plain reasons for the relevance, shown with the label. */
  reasons: string[]
}

const rank: Record<Relevance, number> = {
  crew_hazard: 0,
  work_impact: 1,
  background: 2,
}

export const isPlant = (s: SpeciesEntry) =>
  /plant|fern|lichen|conifer|cycad/i.test(s.group ?? '')

const key = (v: string | null) => (v ?? '').trim().toLowerCase()

/** Map areas belong to a species when the scientific (or common) name matches. */
export function habitatFor(s: SpeciesEntry, areas: CriticalHabitatArea[]) {
  return areas.filter(
    (a) =>
      (key(a.scientific_name) &&
        key(a.scientific_name) === key(s.scientific_name)) ||
      (key(a.common_name) && key(a.common_name) === key(s.common_name)),
  )
}

export function relevanceOf(
  s: SpeciesEntry,
  habitat: CriticalHabitatArea[],
): Pick<WildlifeRow, 'relevance' | 'reasons'> {
  const reasons: string[] = []
  if (s.encounter?.hazard)
    reasons.push('Cited source describes a worker hazard')
  if (s.protection?.critical_habitat_here)
    reasons.push('Critical habitat at this location (IPaC)')
  if (habitat.length) reasons.push('Critical habitat within about 3 km')
  if (s.encounter && !s.encounter.hazard && s.encounter.actions.length)
    reasons.push('Cited guidance requires crews to act')
  const relevance: Relevance = s.encounter?.hazard
    ? 'crew_hazard'
    : reasons.length
      ? 'work_impact'
      : 'background'
  return { relevance, reasons }
}

/** Animals ordered by relevance to the job site, plants, and unmatched habitat. */
export function arrangeWildlife(context: SiteSpeciesContext) {
  const areas = context.critical_habitat
  const animals: WildlifeRow[] = context.species
    .filter((s) => !isPlant(s))
    .map((species) => {
      const habitat = habitatFor(species, areas)
      return { species, habitat, ...relevanceOf(species, habitat) }
    })
    .sort(
      (a, b) =>
        rank[a.relevance] - rank[b.relevance] ||
        b.reasons.length - a.reasons.length ||
        key(a.species.common_name ?? a.species.scientific_name).localeCompare(
          key(b.species.common_name ?? b.species.scientific_name),
        ),
    )
  const matched = new Set(animals.flatMap((r) => r.habitat.map((a) => a.id)))
  return {
    animals,
    plants: context.species.filter(isPlant),
    otherHabitat: areas.filter((a) => !matched.has(a.id)),
  }
}
