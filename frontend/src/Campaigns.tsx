import { useEffect, useId, useState } from 'react';
import { ArrowDownToLine, CheckCheck, ChevronRight, ClipboardCheck, GitCompareArrows, Play, Plus, RefreshCw, Square, X } from 'lucide-react';
import { DownloadButton } from './DownloadButton';
import { api, confirmDiscardChanges, downloadFile, message, navigate, post, useResource, useUnsavedChanges } from './api';
import type { Campaign, CampaignMetadata, Data, Document, DocumentEntry, LabCase, Manifest, RunRecord, Source, Summary, Variant } from './types';
import { DataFields, Disclosure, Empty, EngineeringNote, ErrorBox, formatDate, hasActiveWorker, isDamagedCampaign, JsonBlock, Loading, metricNames, PageHeader, Panel, Pill, sourceNames, Status, Tabs, TextBlock, TicketDiff, variantNames } from './ui';

const activeStates = new Set(['queued', 'running', 'cancelling']);
export function CampaignsPage({ cases, campaigns, selected, showNew, onChange, loading = false }: Readonly<{ cases: LabCase[]; campaigns: Campaign[]; selected: string | null; showNew: boolean; onChange: () => void; loading?: boolean }>) {
  return <>
    <PageHeader eyebrow="02 / VERSUCHSDURCHFÜHRUNG" title="Kontrolliert starten. Genau hinsehen." description="Jeder Versuch protokolliert seine Konfiguration, die einzelnen Läufe und alle beobachteten Effekte." action={!showNew && <button className="button primary" onClick={() => navigate('campaigns', { new: '1' })}><Plus size={17} />Neuer Mock-Versuch</button>} />
    {showNew || (!campaigns.length && !selected) ? <LaunchForm cases={cases} active={campaigns.some(hasActiveWorker)} onChange={onChange} /> : null}
    <CampaignSelection campaigns={campaigns} selected={selected} showNew={showNew} loading={loading} onChange={onChange} />
    <Panel><Disclosure title="Gesamten Forschungsbestand sichern"><p>Die Sicherung umfasst alle gespeicherten Versuche, auch nicht zugeordnete PDF-Quellen, Bewertungshistorien und verfügbare Codeversionen. Bewahre die Datei zusätzlich außerhalb des Dienstes auf. Unvollständige Versuche und fehlende historische Codeversionen bleiben im Sicherungsbericht gekennzeichnet.</p>{campaigns.some(hasActiveWorker) ? <p className="muted">Bitte den aktiven Versuch vor der Sicherung abschließen oder abbrechen.</p> : <DownloadButton path="/api/workspace/backup" filename="security-lab-workspace.zip" className="button secondary"><ArrowDownToLine size={16} />Forschungsbestand herunterladen</DownloadButton>}<p className="muted">Eine heruntergeladene Datei ersetzt noch keine überprüfte Wiederherstellung in einen getrennten Arbeitsbereich.</p></Disclosure></Panel>
    <EngineeringNote />
  </>;
}
function CampaignSelection({ campaigns, selected, showNew, loading, onChange }: Readonly<{ campaigns: Campaign[]; selected: string | null; showNew: boolean; loading: boolean; onChange: () => void }>) {
  if (!selected) {
    if (showNew || campaigns.length === 0) return null;
    return <CampaignHistory campaigns={campaigns} />;
  }
  const campaign = campaigns.find(item => item.campaign_id === selected);
  if (loading && !campaign) return <Loading text="Versuch wird geprüft …" />;
  if (!campaign) return <Empty title="Versuch nicht verfügbar">Wähle einen vorhandenen Versuch aus dem Versuchsverlauf.</Empty>;
  if (isDamagedCampaign(campaign)) return <Panel title={<span className="title-with-pill"><span className="mono">{selected}</span><Status value="damaged" /></span>}><ErrorBox error={campaign.error || 'Die Integritätsprüfung dieses Versuchs ist fehlgeschlagen.'} /><p className="muted">Dieser Versuch wird nicht in Auswertungen einbezogen. Laufdaten, Vergleich, Bewertung und Archivexport sind gesperrt, solange die gespeicherten Nachweise nicht geprüft werden können.</p><button className="button secondary" onClick={() => navigate('campaigns')}>Zum Versuchsverlauf</button></Panel>;
  return <CampaignDetail key={selected} id={selected} brief={campaign} onChange={onChange} />;
}
function CampaignHistory({ campaigns }: Readonly<{ campaigns: Campaign[] }>) {
  return <Panel title="Versuchsverlauf" subtitle={`${campaigns.length} gespeicherte Versuche`}><div className="table-scroll" tabIndex={0} role="region" aria-label="Versuchsverlauf"><table><thead><tr><th>Versuch</th><th>Erstellt</th><th>Status</th><th>Läufe</th><th><span className="sr-only">Öffnen</span></th></tr></thead><tbody>{campaigns.map(c => <tr key={c.campaign_id}><td><button className="text-button mono" onClick={() => navigate('campaigns', { id: c.campaign_id })}>{c.display_name || c.campaign_id}</button>{c.display_name && <small className="mono">{c.campaign_id}</small>}{Boolean(c.tags?.length) && <small>{c.tags!.join(" · ")}</small>}{isDamagedCampaign(c) && <small className="text-danger">{c.error || 'Integritätsprüfung fehlgeschlagen'}</small>}</td><td>{formatDate(c.created_at)}</td><td><Status value={isDamagedCampaign(c) ? 'damaged' : c.state} /> <Pill>{c.engineering_only ? 'Mock' : 'CLI-Import'}</Pill></td><td>{isDamagedCampaign(c) ? 'Nicht prüfbar' : `${c.completed_runs} / ${c.planned_runs}`}</td><td><button className="icon-button" aria-label={`Versuch ${c.campaign_id} öffnen`} onClick={() => navigate('campaigns', { id: c.campaign_id })}><ChevronRight size={18} /></button></td></tr>)}</tbody></table></div></Panel>;
}
function initialCases(cases: LabCase[], preferred: string | null): string[] {
  if (preferred && cases.some(item => item.case_id === preferred)) return [preferred];
  const first = cases[0];
  return first ? [first.case_id] : [];
}
function toggle<T>(value: T, items: T[], setter: (items: T[]) => void) {
  setter(items.includes(value) ? items.filter(item => item !== value) : [...items, value]);
}
export function LaunchForm({ cases, active, onChange }: Readonly<{ cases: LabCase[]; active: boolean; onChange: () => void }>) {
  const caseControlPrefix = useId();
  const preferred = new URLSearchParams(window.location.hash.split('?')[1] || '').get('case');
  const [selected, setSelected] = useState<string[]>(() => initialCases(cases, preferred));
  const [variants, setVariants] = useState<Variant[]>(['B', 'F', 'P', 'FP']);
  const [sources, setSources] = useState<Source[]>(['clean', 'attack']);
  const [repeats, setRepeats] = useState(1), [seed, setSeed] = useState(20261022);
  const [displayName, setDisplayName] = useState(''), [tagText, setTagText] = useState('');
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const documents = useResource<{ documents: DocumentEntry[] }>('/api/documents');
  const confirmed = documents.data?.documents.filter((d): d is Document => d.valid_evidence !== false).filter(d => d.confirmed) || [];
  const planned = selected.length * variants.length * sources.length * repeats;
  const valid = planned > 0 && planned <= 480 && Number.isInteger(repeats) && repeats >= 1 && repeats <= 5 && Number.isSafeInteger(seed) && seed >= 0 && seed <= 4294967295;
  async function start() {
    if (busy || active || !valid) return;
    setBusy(true); setError('');
    try {
      const document_overrides = selected.flatMap(case_id => sources.flatMap(source => overrides[`${case_id}:${source}`] ? [{ case_id, source, document_id: overrides[`${case_id}:${source}`] }] : []));
      const campaign = await post<Campaign>('/api/campaigns', { case_ids: selected, variants, sources, repeats, seed, ...(document_overrides.length ? { document_overrides } : {}), ...(displayName.trim() || tagText.trim() ? { display_name: displayName.trim(), tags: parseTags(tagText) } : {}) });
      onChange(); navigate('campaigns', { id: campaign.campaign_id });
    } catch (err) { setError(message(err)); } finally { setBusy(false); }
  }
  return <div className="launch-layout"><Panel title="Neuen Mock-Versuch vorbereiten" subtitle="Einzelne Kombination oder systematischer Vergleich – du legst den Umfang fest." action={<button className="icon-button" aria-label="Vorbereitung schließen" onClick={() => navigate('campaigns')}><X size={18} /></button>}><form onSubmit={e => { e.preventDefault(); void start(); }}>
    <Disclosure title="Optional: Versuchsname und Tags"><MetadataFields displayName={displayName} setDisplayName={setDisplayName} tagText={tagText} setTagText={setTagText} disabled={busy} /><p className="muted">Die technische ID und die Versuchsbelege bleiben unverändert. Namen und Tags dienen nur der Organisation.</p></Disclosure>
    <fieldset><legend><span className="step-number">1</span>Fälle auswählen <span className="muted">({selected.length})</span></legend><div className="button-row selection-tools"><button type="button" className="text-button" onClick={() => setSelected(cases.map(c => c.case_id))}>Alle Fälle</button><button type="button" className="text-button" onClick={() => setSelected(cases[0] ? [cases[0].case_id] : [])}>Nur erster Fall</button><button type="button" className="text-button" onClick={() => setSelected([])}>Auswahl leeren</button></div><div className="case-check-grid">{cases.map(c => {
      const controlId = `${caseControlPrefix}-control-${c.case_id}`;
      const nameId = `${caseControlPrefix}-name-${c.case_id}`;
      const descriptionId = `${caseControlPrefix}-description-${c.case_id}`;
      return <label key={c.case_id} htmlFor={controlId} className={`check-card ${selected.includes(c.case_id) ? 'checked' : ''}`}>
        <input id={controlId} type="checkbox" aria-labelledby={nameId} aria-describedby={descriptionId} checked={selected.includes(c.case_id)} onChange={() => toggle(c.case_id, selected, setSelected)} />
        <strong id={nameId}>{c.case_id}</strong>
        <small id={descriptionId}>{c.goal} · {c.scenario_group}</small>
      </label>;
    })}</div></fieldset>
    <fieldset><legend><span className="step-number">2</span>Schutzvarianten und Quellen</legend><div className="variant-grid">{(['B', 'F', 'P', 'FP'] as const).map(v => <label key={v} className={`variant-card ${variants.includes(v) ? 'checked' : ''}`}><input type="checkbox" aria-label={`${v} ${variantNames[v]}`} checked={variants.includes(v)} onChange={() => toggle(v, variants, setVariants)} /><strong>{v}</strong><span>{variantNames[v]}</span></label>)}</div><div className="source-checks">{(['clean', 'attack'] as const).map(s => <label key={s} className="inline-check"><input type="checkbox" checked={sources.includes(s)} onChange={() => toggle(s, sources, setSources)} />{sourceNames[s]}</label>)}</div></fieldset>
    <fieldset><legend><span className="step-number">3</span>Wiederholungen und Reihenfolge</legend><div className="split"><label className="field"><span>Wiederholungen pro Kombination</span><input type="number" aria-label="Wiederholungen pro Kombination" min="1" max="5" required value={Number.isNaN(repeats) ? '' : repeats} onChange={e => setRepeats(e.target.valueAsNumber)} /><small>1 bis 5 · Wiederholungen bleiben demselben Fall zugeordnet.</small></label><label className="field"><span>Seed für die Reihenfolge</span><input type="number" aria-label="Seed für die Reihenfolge" min="0" max="4294967295" step="1" required value={Number.isNaN(seed) ? '' : seed} onChange={e => setSeed(e.target.valueAsNumber)} /><small>Bestimmt die Reihenfolge innerhalb der Fallblöcke.</small></label></div></fieldset>
    <Disclosure title="Optional: bestätigte PDF-Quellen zuweisen"><p className="muted">Eine Zuweisung ersetzt nur die ausgewählte Quelle dieses Falls. Aufgabe und Erwartungen bleiben gleich. Prüfe deshalb vorher die inhaltliche Passung.</p><ErrorBox error={documents.error} retry={documents.refresh} />{confirmed.length ? <div className="override-grid">{cases.filter(c => selected.includes(c.case_id)).flatMap(c => sources.map(source => <label className="field" key={`${c.case_id}:${source}`}><span>{c.case_id} · {sourceNames[source]}</span><select value={overrides[`${c.case_id}:${source}`] || ''} onChange={e => setOverrides({ ...overrides, [`${c.case_id}:${source}`]: e.target.value })}><option value="">Original aus dem Fallkatalog</option>{confirmed.map(d => <option key={d.document_id} value={d.document_id}>{d.filename} · {d.text_sha256.slice(0, 8)}</option>)}</select></label>))}</div> : <p>Noch keine bestätigte PDF vorhanden. Importiere und prüfe zuerst eine Quelle unter <button type="button" className="text-button" onClick={() => navigate('documents')}>PDF-Quellen</button>.</p>}</Disclosure>
    <ErrorBox error={error} />{active && <div className="notice warning">Ein Versuch ist bereits aktiv. Warte auf seinen Abschluss oder beende ihn in der Detailansicht.</div>}<div className="form-actions"><p><strong>{Number.isFinite(planned) ? planned : '—'} Läufe</strong> werden explizit gestartet.{planned > 480 && <span className="text-danger"> Maximal 480 Läufe pro Versuch.</span>}</p><button className="button primary" type="submit" disabled={busy || active || !valid}><Play size={16} />{busy ? 'Wird gestartet …' : 'Mock-Versuch starten'}</button></div>
  </form></Panel><aside className="launch-aside"><div className="run-estimate"><span className="section-label">GEPLANTER UMFANG</span><strong>{Number.isFinite(planned) ? planned : '—'}<small>Läufe</small></strong><div className="calculation"><span>{selected.length} Fälle</span><span>× {variants.length} Varianten</span><span>× {sources.length} Quellen</span><span>× {Number.isFinite(repeats) ? repeats : '—'} Wiederholungen</span></div><span className="pill green">Mock · keine API-Kosten</span></div><div className="info-card"><CheckCheck size={22} /><h3>Ein gemeinsamer Ausführungspfad</h3><p>Die Varianten unterscheiden sich nur durch aktivierte Schutzmaßnahmen. Quellen, Rechte und Protokollierung bleiben nachvollziehbar.</p></div></aside></div>;
}
function CampaignDetail({ id, brief, onChange }: Readonly<{ id: string; brief?: Campaign; onChange: () => void }>) {
  const active = !brief || activeStates.has(brief.state);
  const detail = useResource<{ manifest: Manifest; summary: Summary | null }>(`/api/campaigns/${encodeURIComponent(id)}`, active ? 1500 : 0);
  const records = useResource<{ records: RunRecord[] }>(`/api/campaigns/${encodeURIComponent(id)}/records`, active ? 1500 : 0);
  const [selectedRun, setSelectedRun] = useState(''), [filter, setFilter] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState('');
  const rows = records.data?.records || [];
  const filtered = rows.filter(r => `${r.run_id} ${r.case_id} ${r.variant} ${r.source} ${r.status}`.toLowerCase().includes(filter.toLowerCase()));
  const record = filtered.find(r => r.run_id === selectedRun) || filtered[0];
  const manifest = detail.data?.manifest;
  const state = manifest?.state || brief?.state || 'queued';
  const count = brief?.completed_runs ?? rows.length;
  const planned = brief?.planned_runs ?? manifest?.schedule?.length ?? 0;
  async function cancel() {
    setBusy('cancel'); setError('');
    try { await post(`/api/campaigns/${encodeURIComponent(id)}/cancel`); onChange(); detail.refresh(); records.refresh(); }
    catch (err) { setError(message(err)); } finally { setBusy(''); }
  }
  async function exportReview() {
    setBusy('review'); setError('');
    try { const result = await post<{ review_set_id: string }>(`/api/campaigns/${encodeURIComponent(id)}/review-export`); navigate('review', { set: result.review_set_id, slot: 'a' }); }
    catch (err) { setError(message(err)); } finally { setBusy(''); }
  }
  async function download() {
    setBusy('download'); setError('');
    try {
      await downloadFile(`/api/campaigns/${encodeURIComponent(id)}/archive`, `${id}.zip`);
    } catch (err) { setError(message(err)); } finally { setBusy(''); }
  }
  return <div className="stack">{Boolean(brief?.metadata_unpublished_writes) && <div className="notice warning" role="status">{brief!.metadata_unpublished_writes} temporäre Metadatendateien wurden nach einer unterbrochenen Speicherung erhalten. Name und Tags verwenden nur veröffentlichte Versionen. Sie werden beim nächsten Archiv- oder Sicherungsexport unverändert mitgesichert.</div>}<Panel title={<span className="title-with-pill"><span>{brief?.display_name || id}</span><Status value={state} /><Pill>{brief?.engineering_only === false ? 'CLI-Import · Laufmodus im Protokoll' : 'Mock'}</Pill></span>} subtitle={brief?.created_at ? formatDate(brief.created_at) : 'Versuch wird vorbereitet'} action={<button className="button quiet small" onClick={() => { detail.refresh(); records.refresh(); onChange(); }}><RefreshCw size={14} />Aktualisieren</button>}><div className="campaign-progress"><span><strong>{count}</strong> / {planned} Läufe protokolliert</span><span>{activeStates.has(state) ? 'Status wird automatisch aktualisiert' : 'Versuch beendet'}</span></div><progress value={count} max={Math.max(1, planned)} aria-label="Versuchsfortschritt" /><div className="button-row detail-actions"><button className="button secondary small" onClick={() => navigate('compare', { id })}><GitCompareArrows size={16} />Vergleichen</button><button className="button secondary small" disabled={Boolean(busy) || activeStates.has(state) || !rows.length} onClick={exportReview}><ClipboardCheck size={16} />{busy === 'review' ? 'Wird erstellt …' : 'Bewertungssatz erstellen'}</button><button className="button quiet small" disabled={Boolean(busy) || activeStates.has(state)} onClick={download}><ArrowDownToLine size={16} />{busy === 'download' ? 'Archiv wird geprüft …' : 'Archiv herunterladen'}</button>{activeStates.has(state) && brief?.can_cancel !== false && <button className="button danger small" disabled={Boolean(busy) || state === 'cancelling'} onClick={cancel}><Square size={14} />{busy === 'cancel' || state === 'cancelling' ? 'Abbruch angefordert …' : 'Versuch abbrechen'}</button>}</div><ErrorBox error={error || detail.error || records.error} /><Disclosure title="Konfiguration und Herkunft (Manifest)">{manifest ? <JsonBlock value={manifest} /> : <Loading />}</Disclosure></Panel>
    {!activeStates.has(state) && <MetadataEditor id={id} />}
    <CampaignRecords loading={records.loading && !records.data} active={active} rows={rows} filtered={filtered} record={record} filter={filter} setFilter={setFilter} setSelectedRun={setSelectedRun} />
  </div>;
}
function CampaignRecords({ loading, active, rows, filtered, record, filter, setFilter, setSelectedRun }: Readonly<{ loading: boolean; active: boolean; rows: RunRecord[]; filtered: RunRecord[]; record?: RunRecord; filter: string; setFilter: (filter: string) => void; setSelectedRun: (id: string) => void }>) {
  if (loading) return <Loading text="Laufprotokolle werden geladen …" />;
  if (rows.length === 0) return <Empty title={active ? 'Die ersten Läufe werden vorbereitet.' : 'Keine protokollierten Läufe'}>{active ? 'Fertige Laufprotokolle erscheinen hier automatisch.' : 'Der Versuch enthält bisher keine abgeschlossenen oder teilweise protokollierten Läufe.'}</Empty>;
  return <div className="record-layout"><Panel title="Einzelne Läufe" subtitle={`${rows.length} Protokolle`} className="record-browser"><label className="field"><span>Läufe filtern</span><input placeholder="Fall, Variante, Quelle …" value={filter} onChange={e => setFilter(e.target.value)} /></label><div className="record-list">{filtered.map(r => <button key={r.run_id} className={`run-item ${record?.run_id === r.run_id ? 'selected' : ''}`} onClick={() => setSelectedRun(r.run_id)}><span><strong className="mono">{r.run_id}</strong><Pill tone={r.source === 'attack' ? 'amber' : 'neutral'}>{r.variant}</Pill></span><small>{r.case_id}</small><span className="run-subline">{r.source === 'attack' ? 'Manipuliert' : 'Sauber'} · Wiederholung {r.repetition}</span><Status value={r.status} /></button>)}{!filtered.length && <p className="muted">Keine passenden Läufe.</p>}</div></Panel>{record ? <RunDetail record={record} /> : <Empty title="Kein Lauf ausgewählt" />}</div>;
}
function MetricResult({ metric, value }: Readonly<{ metric: string; value: Data[string] | undefined }>) {
  if (value === null || value === undefined) return <Pill tone="neutral">Bewertung offen</Pill>;
  let tone: 'green' | 'red' | 'amber';
  if (metric === 'legitimate_success') tone = value ? 'green' : 'red';
  else tone = value ? 'amber' : 'green';
  return <Pill tone={tone}>{value ? 'Ja' : 'Nein'}</Pill>;
}
export function RunDetail({ record }: Readonly<{ record: RunRecord }>) {
  const [tab, setTab] = useState('trace');
  const effects = record.events.filter(e => ['backend_read', 'backend_write'].includes(e.type)).length;
  const proposals = record.events.filter(e => e.type === 'proposal').length;
  const blocks = record.events.filter(e => ['filter_decision', 'policy_decision'].includes(e.type) && e.data.allowed === false).length;
  return <div className="stack"><Panel title={<span className="title-with-pill">{record.run_id}<Pill tone={record.is_mock ? 'green' : 'blue'}>{record.is_mock ? 'Mock' : 'LLM-Aufruf'}</Pill><Pill>{record.variant} · {variantNames[record.variant]}</Pill><Pill tone={record.source === 'attack' ? 'amber' : 'green'}>{sourceNames[record.source]}</Pill></span>} subtitle={`${record.case_id} · Wiederholung ${record.repetition}`}><div className="run-stat-row"><div><strong>{proposals}</strong><span>Vorschläge</span></div><div><strong>{blocks}</strong><span>Blockierungen</span></div><div><strong>{effects}</strong><span>Backend-Effekte</span></div><div><strong>{Number(record.duration_seconds || 0).toLocaleString('de-DE', { maximumFractionDigits: 2 })} s</strong><span>Laufzeit</span></div></div><div className="section-label">FINALE AUSGABE</div><TextBlock>{record.final_text}</TextBlock><div className="metric-chips">{['proposal_violation', 'backend_violation', 'legitimate_success', 'attacker_goal'].map(key => <span key={key}>{metricNames[key]}<MetricResult metric={key} value={record.metrics?.[key]} /></span>)}</div></Panel>
    <Panel><Tabs label="Laufdetails" items={[{id: 'trace', label: 'Ereignisprotokoll'}, {id: 'tickets', label: 'Tickets vorher / nachher'}, {id: 'input', label: 'Aufgabe & Quelle'}]} selected={tab} onChange={setTab}>
      {tab === 'trace' && <div className="timeline">{record.events.map((event, index) => <TraceEvent key={`${event.seq}-${index}`} event={event} />)}{!record.events.length && <p className="muted">Keine Ereignisse protokolliert.</p>}</div>}
      {tab === 'tickets' && <TicketDiff before={record.initial_tickets} after={record.final_tickets} />}
      {tab === 'input' && <div className="stack"><div><h3>Legitime Aufgabe</h3><TextBlock>{record.user_request}</TextBlock></div><div><h3>Tatsächlich verwendete Quelle</h3><TextBlock>{record.article_text}</TextBlock></div><Disclosure title="Sitzungsrechte und Erwartungen"><DataFields value={record.session} /><DataFields value={record.expected} /></Disclosure><Disclosure title="Vollständiges Laufprotokoll"><JsonBlock value={record} /></Disclosure></div>}
    </Tabs></Panel>
  </div>;
}
function TraceEvent({ event }: Readonly<{ event: { seq: number; type: string; data: Data } }>) {
  const labels: Record<string, string> = { proposal: 'Werkzeugvorschlag', filter_decision: 'Textfilter', policy_decision: 'Berechtigungsprüfung', backend_read: 'Ticket gelesen', backend_write: 'Notiz geschrieben', context_exposure: 'In Modellkontext übernommen', output: 'Ausgabe', final_output: 'Finale Ausgabe', model_response: 'Modellantwort', cancelled: 'Abbruch', run_cancelled: 'Abbruch', article_loaded: 'Quelle geladen' };
  const blocked = event.data.allowed === false;
  const effect = ['backend_read', 'backend_write', 'context_exposure'].includes(event.type);
  const eventClass = effect ? 'effect' : '';
  return <div className={`timeline-event ${blocked ? 'blocked' : eventClass}`}><span className="timeline-marker">{event.seq}</span><details open={blocked || event.type === 'proposal' || effect}><summary><span>{labels[event.type] || event.type}</span><EventDecision allowed={event.data.allowed} effect={effect} /><ChevronRight size={15} /></summary><div><DataFields value={event.data} /></div></details></div>;
}

function EventDecision({ allowed, effect }: Readonly<{ allowed: Data[string] | undefined; effect: boolean }>) {
  if (allowed === false) return <Pill tone="amber">Blockiert</Pill>;
  if (allowed === true) return <Pill tone="green">Zugelassen</Pill>;
  if (effect) return <Pill tone="blue">Beobachteter Effekt</Pill>;
  return null;
}

function parseTags(text: string) { return text.split(',').map(value => value.trim()).filter(Boolean); }
function MetadataFields({ displayName, setDisplayName, tagText, setTagText, disabled }: Readonly<{ displayName: string; setDisplayName: (value: string) => void; tagText: string; setTagText: (value: string) => void; disabled: boolean }>) {
  return <div className="split"><label className="field"><span>Versuchsname (optional)</span><input value={displayName} onChange={event => setDisplayName(event.target.value)} maxLength={120} disabled={disabled} placeholder="Zum Beispiel: PDF-Abnahme November" /></label><label className="field"><span>Tags (durch Komma getrennt)</span><input aria-label="Tags (durch Komma getrennt)" value={tagText} onChange={event => setTagText(event.target.value)} maxLength={500} disabled={disabled} placeholder="Abnahme, PDF, Kontrolllauf" /><small>Bis zu zwölf Tags mit jeweils höchstens 40 Zeichen.</small></label></div>;
}
function MetadataEditor({ id }: Readonly<{ id: string }>) {
  const stored = useResource<CampaignMetadata>(`/api/campaigns/${encodeURIComponent(id)}/metadata`);
  const [displayName, setDisplayName] = useState(''), [tagText, setTagText] = useState('');
  const [dirty, setDirty] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [saved, setSaved] = useState(false);
  useUnsavedChanges(dirty);
  useEffect(() => { if (stored.data) { setDisplayName(stored.data.display_name || ''); setTagText((stored.data.tags || []).join(', ')); setDirty(false); } }, [stored.data]);
  async function save() {
    if (!stored.data || busy) return;
    setBusy(true); setError(''); setSaved(false);
    try {
      await api(`/api/campaigns/${encodeURIComponent(id)}/metadata`, {method: 'PUT', body: JSON.stringify({display_name: displayName.trim(), tags: parseTags(tagText), expected_revision: stored.data.revision})});
      setDirty(false); setSaved(true); stored.refresh();
      // Campaign listings poll in place. Explicitly clearing their resource
      // would unmount this editor and erase the visible save receipt.
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }
  const available = Number.isSafeInteger(stored.data?.revision);
  return <Panel><Disclosure title="Versuchsname und Tags bearbeiten"><p className="muted">Stabile ID: <code>{id}</code>. Änderungen werden als neue Metadatenversion gesichert und mit dem Archiv exportiert.</p><ErrorBox error={error || stored.error} />{saved && <p role="status">Name und Tags gespeichert.</p>}<MetadataFields displayName={displayName} setDisplayName={value => { setDisplayName(value); setDirty(true); setSaved(false); }} tagText={tagText} setTagText={value => { setTagText(value); setDirty(true); setSaved(false); }} disabled={busy || !available} /><div className="button-row"><button className="button secondary" disabled={busy || !dirty || !available} onClick={() => void save()}>Name und Tags speichern</button><button className="button quiet" disabled={busy} onClick={() => { if (confirmDiscardChanges()) { setError(''); stored.refresh(); } }}>Aktuellen Stand laden</button></div>{!available && !stored.loading && <p className="muted">Metadaten sind mit diesem Backend noch nicht verfügbar. Bitte nach der Bereitstellung erneut laden.</p>}</Disclosure></Panel>;
}
