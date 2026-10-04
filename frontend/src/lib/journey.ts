/**
 * The 10× case on the people in the hackathon brief. Each person has a milestone and the steps the typical way takes.
 * Manual times are working days; with-the-product times are working hours, because the product answers in under a
 * second and what is left is a person checking the sources. Both are editable on the page and tagged by where they come
 * from. Nothing here is measured on real people.
 */

export type Basis = "brief" | "assumption";
export type Step = {
  id: string;
  question: string;
  /** the typical way, in working days */
  manualDays: number;
  /** with TFOTB, working hours spent checking what it returned */
  assistedHours: number;
  basis: Basis;
  manualHow: string;
  siteHow: string;
};
export type Persona = {
  key: "maria" | "devon" | "priya" | "osei";
  name: string;
  role: string;
  /** a sentence copied from the challenge brief */
  pain: string;
  milestone: string;
  built: "built" | "partial";
  builtNote: string;
  steps: Step[];
};

export const HOURS_PER_DAY = 8;

export const PERSONAS: Persona[] = [
  {
    key: "maria",
    name: "Maria",
    role: "Patient organisation leader",
    pain: "She cannot tell whether a related group has already built an asset she could reuse or whether a seemingly similar disease follows a different mechanism.",
    milestone:
      "Approach a partner with a sourced proposal for shared research (the brief's “What good looks like”).",
    built: "built",
    builtNote:
      "Runs end to end on CLN3 disease, the seed disease. Outside the seed cluster the evidence is thinner and the brief says so.",
    steps: [
      {
        id: "m1",
        question: "Who shares our disease characteristics?",
        manualDays: 10,
        assistedHours: 3,
        basis: "assumption",
        manualHow:
          "Search disease databases and papers by hand, reconcile names and synonyms, note why each disease is related.",
        siteHow:
          "Related diseases with the reason for each (shared gene, mechanism read from papers, symptoms). Check the sources.",
      },
      {
        id: "m2",
        question: "What useful work already exists?",
        manualDays: 10,
        assistedHours: 3,
        basis: "assumption",
        manualHow:
          "Look through patient-group sites, ClinicalTrials.gov and papers for registries, studies and models.",
        siteHow:
          "Patient groups with their registry link, and studies matched to the disease. Check each one.",
      },
      {
        id: "m3",
        question: "Who could we approach?",
        manualDays: 5,
        assistedHours: 1,
        basis: "assumption",
        manualHow:
          "Read author lists, find who works on the shared mechanism, look up affiliations.",
        siteHow:
          "Researchers from the papers behind the stored claims, matched by ORCID where there is one.",
      },
      {
        id: "m4",
        question: "What do we do together next?",
        manualDays: 5,
        assistedHours: 4,
        basis: "assumption",
        manualHow: "Write the proposal and attach a source for every statement.",
        siteHow:
          "An exportable evidence brief with the source behind each statement, to edit and check.",
      },
    ],
  },
  {
    key: "devon",
    name: "Devon",
    role: "Newly diagnosed patient or caregiver",
    pain: "Search engines return either nothing useful or dense journal abstracts written for specialists.",
    milestone: "Find the exact community, or an evidence-qualified connection to related ones.",
    built: "built",
    builtNote:
      "Search and patient-group listings (from GARD) work. If there is no group, the page says so.",
    steps: [
      {
        id: "d1",
        question: "Is there a group for our exact diagnosis, or the closest one?",
        manualDays: 3,
        assistedHours: 0.5,
        basis: "assumption",
        manualHow: "Night-time searches, then days of reading before any group is found.",
        siteHow: "One search, then the groups listed for the disease and for related ones.",
      },
    ],
  },
  {
    key: "priya",
    name: "Priya",
    role: "Biotech or pharma scout",
    pain: "Evaluating candidates one disease at a time, scattered across papers, conference talks, and cold outreach, takes months per mechanism.",
    milestone:
      "A ranked list of diseases a mechanism could plausibly treat, each with its evidence.",
    built: "partial",
    builtNote:
      "Only part of this is built: the Clusters page groups diseases around one searched disease by a shared mechanism, gene or symptoms. It cannot yet start from a mechanism and rank every disease.",
    steps: [
      {
        id: "p1",
        question: "Which diseases could this mechanism plausibly treat?",
        manualDays: 40,
        assistedHours: 8,
        basis: "brief",
        manualHow:
          "The brief says months per mechanism. 40 working days is the low end of “months”.",
        siteHow:
          "Clusters around a searched disease with the claims behind each group, for the diseases we hold.",
      },
    ],
  },
  {
    key: "osei",
    name: "Dr. Osei",
    role: "Academic researcher",
    pain: "He has no way of knowing a colleague three universities away is chasing an “unrelated” disease that is, mechanistically, nearly the same problem.",
    milestone: "Who else works on my mechanism, and a way to reach them.",
    built: "partial",
    builtNote:
      "The collaborator view finds authors of papers behind stored claims. It covers only the papers we have read, and it is not a contact route.",
    steps: [
      {
        id: "o1",
        question: "Who else works on this mechanism, under any disease name?",
        manualDays: 10,
        assistedHours: 2,
        basis: "assumption",
        manualHow:
          "Keyword searches under every gene and disease name the mechanism could hide behind.",
        siteHow: "Related diseases that share the mechanism, and the researchers on those papers.",
      },
    ],
  },
];

export type Overrides = Record<string, { manualDays?: number; assistedHours?: number }>;

const pos = (x: number | undefined, fallback: number) =>
  typeof x === "number" && Number.isFinite(x) && x >= 0 ? x : fallback;

export type PersonaResult = {
  manualDays: number;
  assistedDays: number;
  assistedHours: number;
  speedup: number;
  /** how many times longer than assumed the checking could take before the speedup drops below 10 */
  headroom: number;
  /** the speedup if checking took `stress` times as long */
  stressed: number;
};

export function compareJourney(p: Persona, o: Overrides = {}, stress = 3): PersonaResult {
  const manualDays = p.steps.reduce((a, s) => a + pos(o[s.id]?.manualDays, s.manualDays), 0);
  const assistedHours = p.steps.reduce(
    (a, s) => a + pos(o[s.id]?.assistedHours, s.assistedHours),
    0,
  );
  const assistedDays = assistedHours / HOURS_PER_DAY;
  const speedup = assistedDays > 0 ? manualDays / assistedDays : 0;
  return {
    manualDays,
    assistedDays,
    assistedHours,
    speedup,
    headroom: speedup / 10,
    stressed: speedup / stress,
  };
}

export const fmtX = (x: number) => `${x >= 10 ? x.toFixed(0) : x.toFixed(1)}×`;
