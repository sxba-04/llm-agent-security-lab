import { useState } from 'react';
import { ArrowDownToLine, ArrowRight, GitCompareArrows, Info } from 'lucide-react';
import { navigate, useResource } from './api';
import { DownloadButton } from './DownloadButton';
import type { Campaign, Json, Metric, ReviewSet, Summary, SummaryGroup } from './types';
import { Disclosure, Empty, EngineeringNote, ErrorBox, goalNames, isDamagedCampaign, JsonBlock, Loading, metricNames, PageHeader, Panel, Pill, sourceNames, variantNames } from './ui';

interface PairMetric { left_numerator: number; right_numerator: number; denominator: number; pending: number; not_applicable: number; left_rate: number | null; right_rate: number | null; difference_pp: number | null }
interface Pair { comparison: string; left_variant: string; right_variant: string; source: string; goal: string; model: string; engineering_only: boolean; n_candidate_blocks: number; n_common_valid_blocks: number; n_excluded_blocks: number; excluded: Record<string, number>; excluded_blocks: Json; metrics: Record<string, PairMetric> }
interface Profile { model: string; engineering_only: boolean; case_id: string; goal: string; variant: string; source: string; n_runs: number; n_valid: number; n_invalid: number; repetitions: number[]; metrics: Record<string, Metric>; outcomes: Json }
interface Paired { comparisons: Pair[]; case_profiles: Profile[] }
function percentage(rate: number | null) { return rate === null || rate === undefined ? '—' : `${(rate * 100).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`; }
export function ComparePage({ campaigns, selected }: Readonly<{ campaigns: Campaign[]; selected: string | null }>) {
  const validCampaigns = campaigns.filter(c => !isDamagedCampaign(c));
  const unavailable = selected ? campaigns.find(c => c.campaign_id === selected) : undefined;
  const id = selectedCampaignId(validCampaigns, selected);
  const reviews = useResource<{ review_sets: ReviewSet[] }>('/api/reviews');
  const [review, setReview] = useState('');
  const [metric, setMetric] = useState('backend_violation');
  const [source, setSource] = useState(''), [goal, setGoal] = useState('');
  const available = reviews.data?.review_sets.filter(r => r.campaign_id === id) || [];
  const effectiveReview = available.some(r => r.review_set_id === review) ? review : '';
  const campaignState = validCampaigns.find(c => c.campaign_id === id)?.state;
  // A terminal transition changes the interval to zero: fetch once more, then stop.
  const summaryPoll = ['queued', 'running', 'cancelling'].includes(campaignState || '') ? 2500 : 0;
  const summary = useResource<Summary>(summaryPath(id, effectiveReview), summaryPoll);
  return <>
    <PageHeader eyebrow="03 / ANALYSE" title="Unterschiede nachvollziehbar vergleichen." description="Zähler, Nenner und offene Bewertungen bleiben sichtbar. Vergleiche beziehen sich auf denselben Versuch." />
    {!validCampaigns.length ? <Empty title="Keine prüfbaren Versuche zum Vergleich" action={<button className="button primary" onClick={() => navigate('campaigns', { new: '1' })}><ArrowRight size={16} />Versuch vorbereiten</button>}>Starte einen Mock-Versuch mit prüfbaren Laufprotokollen. Beschädigte Versuche werden nicht in Vergleiche einbezogen.</Empty> : <>
      {selected && !id && <ErrorBox error={unavailable?.error || 'Der gewählte Versuch ist nicht verfügbar oder seine Nachweise sind beschädigt. Wähle einen prüfbaren Versuch.'} />}
      <Panel action={id && summary.data && <DownloadButton path={comparisonDownloadPath(id, effectiveReview, metric, source, goal)} filename={`${id}-comparison.csv`} className="button secondary small"><ArrowDownToLine size={16} />Gefilterten Vergleich als CSV</DownloadButton>}><div className="filter-bar"><label className="field grow"><span>Versuch</span><select aria-label="Versuch" value={id} onChange={e => { setReview(''); navigate('compare', { id: e.target.value }); }}>{!id && <option value="">Prüfbaren Versuch auswählen</option>}{validCampaigns.map(c => <option key={c.campaign_id} value={c.campaign_id}>{c.display_name || c.campaign_id} · {c.completed_runs} Läufe</option>)}</select></label><label className="field grow"><span>Menschliche Bewertungen</span><select aria-label="Menschliche Bewertungen" value={effectiveReview} onChange={e => setReview(e.target.value)}><option value="">Ohne angehängte Bewertungen</option>{available.map((r, index) => <option key={r.review_set_id} value={r.review_set_id}>Bewertungssatz {index + 1} · {r.packet_count} Pakete · {r.review_set_id.slice(0, 8)}</option>)}</select></label></div><div className="filter-bar"><label className="field grow"><span>Messgröße</span><select aria-label="Messgröße" value={metric} onChange={e => setMetric(e.target.value)}>{Object.entries(metricNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="field"><span>Quelle</span><select aria-label="Quelle" value={source} onChange={e => setSource(e.target.value)}><option value="">Beide Quellen</option><option value="clean">Saubere Quelle</option><option value="attack">Manipulierte Quelle</option></select></label><label className="field"><span>Angriffsziel</span><select aria-label="Angriffsziel" value={goal} onChange={e => setGoal(e.target.value)}><option value="">Alle Ziele</option>{Object.entries(goalNames).map(([key, label]) => <option key={key} value={key}>{key} · {label}</option>)}</select></label></div></Panel>
      <ErrorBox error={summary.error} retry={summary.refresh} /><ErrorBox error={reviews.error} retry={reviews.refresh} />
      {summary.loading ? <Loading text="Vergleich wird berechnet …" /> : summary.data && <ComparisonResults summary={summary.data} metric={metric} source={source} goal={goal} />}
    </>}
    <EngineeringNote />
  </>;
}

function selectedCampaignId(campaigns: Campaign[], selected: string | null) {
  if (selected) return campaigns.find(c => c.campaign_id === selected)?.campaign_id || '';
  return campaigns[0]?.campaign_id || '';
}
function summaryPath(id: string, review: string) {
  if (!id) return null;
  const path = `/api/campaigns/${encodeURIComponent(id)}/summary`;
  return review ? `${path}?review_set_id=${encodeURIComponent(review)}` : path;
}
function comparisonDownloadPath(id: string, review: string, metric: string, source: string, goal: string) {
  const query = new URLSearchParams({ metric });
  if (review) query.set('review_set_id', review);
  if (source) query.set('source', source);
  if (goal) query.set('goal', goal);
  return `/api/campaigns/${encodeURIComponent(id)}/comparison.csv?${query}`;
}
function formatDifference(value: number | null) {
  if (value === null) return 'Offen';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toLocaleString('de-DE', { maximumFractionDigits: 1 })}`;
}
function GroupTable({ groups, metric }: Readonly<{ groups: SummaryGroup[]; metric: string }>) {
  if (!groups.length) return <Empty title="Keine passenden Ergebnisse">Passe die Filter an oder warte auf protokollierte Läufe.</Empty>;
  return <div className="table-scroll" tabIndex={0} role="region" aria-label="Vergleichstabelle"><table className="metrics-table"><thead><tr><th>Variante</th><th>Quelle / Ziel</th><th>Beobachtet</th><th>Rate</th><th>Offen</th><th>Nicht anwendbar</th><th>Gültig / gesamt</th></tr></thead><tbody>{groups.map(group => { const m = group.metrics[metric]; return <tr key={JSON.stringify([group.variant, group.source, group.goal, group.model, group.engineering_only])}><td><strong>{group.variant}</strong><small>{variantNames[group.variant]} · {group.model} · {group.engineering_only ? 'Mock' : 'LLM'}</small></td><td>{sourceNames[group.source]}<small>{group.goal}</small></td><td><strong>{m.numerator}</strong> / {m.denominator}</td><td><div className="rate-cell"><span>{percentage(m.rate)}</span><span className="rate-bar"><span style={{ width: `${(m.rate || 0) * 100}%` }} /></span></div></td><td>{m.pending ? <Pill tone="amber">{m.pending} offen</Pill> : '0'}</td><td>{m.not_applicable}</td><td>{group.n_valid} / {group.n_runs}<small>{group.n_base_cases} Basisfälle</small></td></tr>; })}</tbody></table></div>;
}
function PairCards({ pairs, metric }: Readonly<{ pairs: Pair[]; metric: string }>) {
  if (!pairs.length) return <Empty title="Noch keine gemeinsamen Vergleichsblöcke">Für einen gepaarten Vergleich werden die passenden Varianten auf demselben Fall und derselben Quelle benötigt.</Empty>;
  return <div className="pair-grid">{pairs.map(pair => { const m = pair.metrics[metric]; return <div className="pair-card" key={JSON.stringify([pair.left_variant, pair.right_variant, pair.source, pair.goal, pair.model, pair.engineering_only])}><div className="pair-heading"><span><strong>{pair.left_variant}</strong><GitCompareArrows size={17} /><strong>{pair.right_variant}</strong></span><Pill>{pair.goal}</Pill></div><p>{sourceNames[pair.source]} · {pair.model} · {pair.engineering_only ? 'Mock' : 'LLM'}</p><div className="pair-difference">{formatDifference(m.difference_pp)}<small>{m.difference_pp === null ? 'Keine auswertbaren Paare' : 'Prozentpunkte · links minus rechts'}</small></div><div className="pair-numbers"><span>{pair.left_variant}: <strong>{m.left_numerator}/{m.denominator}</strong></span><span>{pair.right_variant}: <strong>{m.right_numerator}/{m.denominator}</strong></span></div><div className="pair-foot"><span>{m.pending} offen</span><span>{m.not_applicable} n. a.</span><span>{pair.n_excluded_blocks} ausgeschlossen</span></div><Disclosure title={`${pair.n_common_valid_blocks} gemeinsame / ${pair.n_candidate_blocks} mögliche Blöcke`}><JsonBlock value={{ excluded: pair.excluded, excluded_blocks: pair.excluded_blocks }} /></Disclosure></div>; })}</div>;
}
function ComparisonResults({ summary, metric, source, goal }: Readonly<{ summary: Summary; metric: string; source: string; goal: string }>) {
  const matchesFilter = (row: { source: string; goal: string }) => (!source || row.source === source) && (!goal || row.goal === goal);
  const groups = summary.groups.filter(matchesFilter);
  const paired = summary.paired_comparisons as unknown as Paired | undefined;
  const pairs = paired?.comparisons?.filter(matchesFilter) || [];
      return <div className="stack"><div className="notice info"><Info size={19} /><span>Offene semantische Urteile zählen nicht als Misserfolg. Wiederholungen desselben Falls sind keine unabhängigen Fälle. Alle Unterschiede sind deskriptiv.</span></div>
        <Panel title={metricNames[metric]} subtitle="Alle gültigen Läufe je Variante, Quelle und Angriffsziel. Modell und Ausführungsmodus bleiben getrennt." action={<Pill>{summary.n_runs} protokollierte Läufe</Pill>}>
          <GroupTable groups={groups} metric={metric} />
        </Panel>
        <Panel title="Gepaarter Variantenvergleich" subtitle="Nur gemeinsame gültige Fallblöcke. Ein Block ist ein Fall mit derselben Wiederholung, Quelle, Ziel- und Modellbedingung.">
          <PairCards pairs={pairs} metric={metric} />
        </Panel>
        <Panel title="Stabilität innerhalb der Fälle" subtitle="Wiederholungen werden fallweise ausgewiesen und nicht als neue Basisfälle gezählt.">{paired?.case_profiles?.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label="Vergleichstabelle"><table><thead><tr><th>Fall / Variante</th><th>Quelle</th><th>Wiederholungen</th><th>Beobachtet</th><th>Offen</th><th>Ungültig</th></tr></thead><tbody>{paired.case_profiles.filter(matchesFilter).map(profile => <tr key={JSON.stringify([profile.case_id, profile.variant, profile.source, profile.model, profile.engineering_only])}><td><strong>{profile.case_id}</strong><small>{profile.variant} · {profile.goal}</small></td><td>{sourceNames[profile.source]}</td><td>{profile.repetitions.join(', ')}</td><td>{profile.metrics[metric].numerator} / {profile.metrics[metric].denominator}</td><td>{profile.metrics[metric].pending}</td><td>{profile.n_invalid}</td></tr>)}</tbody></table></div> : <p className="muted">Noch keine Fallprofile vorhanden.</p>}</Panel>
        <Disclosure title="Vollständige Zusammenfassung als JSON"><JsonBlock value={summary} /></Disclosure>
      </div>;
}
