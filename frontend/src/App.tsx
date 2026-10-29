import { useEffect, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowRight, BookOpen, ChevronRight, CircleHelp, ClipboardCheck, FileText, FlaskConical, GitCompareArrows, LayoutDashboard, Menu, Play, ShieldCheck, X } from 'lucide-react';
import { confirmDiscardChanges, hosted, navigate, signOut, useResource, useRoute } from './api';
import { AccessGate } from './AccessGate';
import { DownloadButton } from './DownloadButton';
import type { Campaign, Health, LabCase } from './types';
import { Empty, EngineeringNote, ErrorBox, formatDate, GoButton, goalNames, hasActiveWorker, isDamagedCampaign, Loading, PageHeader, Panel, Pill, SourceDiff, Status, Disclosure, DataFields, JsonBlock } from './ui';
import { CampaignsPage } from './Campaigns';
import { ComparePage } from './Compare';
import { ReviewsPage } from './Reviews';
import { DocumentsPage } from './Documents';

const pages = [
  { id: 'overview', label: 'Übersicht', icon: LayoutDashboard },
  { id: 'cases', label: 'Fälle', icon: BookOpen },
  { id: 'campaigns', label: 'Versuche', icon: FlaskConical },
  { id: 'compare', label: 'Vergleich', icon: GitCompareArrows },
  { id: 'review', label: 'Bewertung', icon: ClipboardCheck },
  { id: 'documents', label: 'PDF-Quellen', icon: FileText },
];
export default function App() { return <AccessGate><Workbench /></AccessGate>; }
function Workbench() {
  const route = useRoute();
  const health = useResource<Health>('/api/health', 10000);
  const cases = useResource<{ cases: LabCase[] }>('/api/cases');
  const campaigns = useResource<{ campaigns: Campaign[] }>('/api/campaigns', 2500);
  const [menu, setMenu] = useState(false);
  const current = pages.find(item => item.id === route.page) || pages[0];
  useEffect(() => { setMenu(false); document.title = `${current.label} · Agent Security Lab`; }, [current.label]);
  const caseRows = cases.data?.cases || [];
  const campaignRows = campaigns.data?.campaigns || [];
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>Zum Inhalt springen</a>
    {menu && <button aria-label="Menü schließen" className="sidebar-backdrop" onClick={() => setMenu(false)} />}
    <aside className={`sidebar ${menu ? 'open' : ''}`}>
      <a className="brand" href="#overview" aria-label="Agent Security Lab – Übersicht"><span className="brand-mark"><ShieldCheck size={25} /></span><span>Agent Security<span>RESEARCH LAB</span></span></a>
      <div className="sidebar-section-label">ARBEITSBEREICH</div>
      <nav aria-label="Hauptnavigation">{pages.map(item => <a key={item.id} href={`#${item.id}`} aria-current={current.id === item.id ? 'page' : undefined} className={current.id === item.id ? 'active' : ''}><item.icon size={19} /><span>{item.label}</span>{current.id === item.id && <span className="nav-dot" />}</a>)}</nav>
      <div className="sidebar-footer"><div className="local-indicator"><span />{hosted ? 'Online-Werkbank' : 'Lokale Werkbank'}</div><p>Kontrollierte Szenarien.<br />Nachvollziehbare Entscheidungen.</p><div className="sidebar-version"><span>Entwicklungsphase</span><span>{health.data?.version ? `v${health.data.version}` : '—'}</span></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" aria-label={menu ? 'Menü schließen' : 'Menü öffnen'} onClick={() => setMenu(!menu)}>{menu ? <X size={20} /> : <Menu size={20} />}</button><span>Werkbank</span><ChevronRight size={14} /><strong>{current.label}</strong></div><div className="topbar-state"><span className="connection-state"><span className={`tiny-dot ${health.error ? 'offline' : ''}`} />{health.error ? 'Nicht verbunden' : health.loading && !health.data ? 'Verbinden …' : hosted ? 'Online verbunden' : 'Lokal verbunden'}</span><span className="mock-badge"><span />MOCK-MODUS</span>{hosted && <button className="button quiet small" onClick={() => { if (confirmDiscardChanges()) signOut(); }}>Abmelden</button>}</div></header>
      <main id="main-content" tabIndex={-1}>
        {health.error && <ErrorBox error={health.error} retry={health.refresh} />}
        {cases.error && <ErrorBox error={cases.error} retry={cases.refresh} />}
        {campaigns.error && <ErrorBox error={campaigns.error} retry={campaigns.refresh} />}
        {cases.loading && !cases.data ? <Loading text="Werkbank wird geladen …" /> : <>
          {current.id === 'overview' && <Overview cases={caseRows} campaigns={campaignRows} />}
          {current.id === 'cases' && <CasesPage cases={caseRows} selected={route.params.get('id')} />}
          {current.id === 'campaigns' && <CampaignsPage cases={caseRows} campaigns={campaignRows} loading={campaigns.loading} selected={route.params.get('id')} showNew={route.params.get('new') === '1'} onChange={campaigns.refresh} />}
          {current.id === 'compare' && <ComparePage campaigns={campaignRows} selected={route.params.get('id')} />}
          {current.id === 'review' && <ReviewsPage invalidCampaignIds={campaignRows.filter(isDamagedCampaign).map(c => c.campaign_id)} selected={route.params.get('set')} slot={route.params.get('slot') || 'a'} coordinating={route.params.get('mode') === 'coordination'} />}
          {current.id === 'documents' && <DocumentsPage cases={caseRows} />}
        </>}
        <footer className="page-footer"><span>LLM Agent Security Lab</span><span>Synthetische Daten · Entwicklungskatalog · {hosted ? 'Gemeinsamer Arbeitsbereich' : 'Lokal'}</span></footer>
      </main>
    </div>
  </div>;
}
function Overview({ cases, campaigns }: { cases: LabCase[]; campaigns: Campaign[] }) {
  const running = campaigns.filter(hasActiveWorker);
  const completed = campaigns.filter(c => !isDamagedCampaign(c)).reduce((count, c) => count + c.completed_runs, 0);
  const goals = new Set(cases.map(c => c.goal)).size;
  return <>
    <PageHeader eyebrow="FORSCHUNGSWERKBANK" title="Sicherheit sichtbar machen." description="Fälle verstehen, Agentenverhalten beobachten und Schutzmaßnahmen systematisch vergleichen." action={<button className="button primary" onClick={() => navigate('campaigns', { new: '1' })}><Play size={16} />Neuer Mock-Versuch</button>} />
    <div className="hero-panel"><div className="hero-copy"><span className="hero-kicker"><span className="tiny-dot" />BEREIT FÜR DEN PRAKTISCHEN TEIL</span><h2>Vom Quelltext<br />zum beobachtbaren Effekt.</h2><p>Untersuche, wie manipulierte Quellen einen Agenten beeinflussen – und an welcher Stelle Filter und Berechtigungen eingreifen.</p><button className="hero-link" onClick={() => navigate('cases')}>Fallkatalog erkunden<ArrowRight size={17} /></button></div><div className="hero-diagram" aria-label="Ein Agent erhält eine Quelle. Filter und Policy kontrollieren den Zugriff auf synthetische Tickets."><div className="diagram-label">DER VERSUCHSAUFBAU</div><div className="diagram-card source-node"><FileText size={20} /><span>Quelle<small>clean / attack</small></span></div><div className="diagram-connector" /><div className="diagram-card agent-node"><Activity size={23} /><span>Mock-Agent<small>kontrollierter Ablauf</small></span><span className="diagram-dot" /></div><div className="diagram-branches"><div><span className="guard-label">F · Textfilter</span></div><div><span className="guard-label">P · Policy</span></div></div><div className="diagram-card ticket-node"><ShieldCheck size={19} /><span>Ticket-Backend<small>lesen · Notiz ergänzen</small></span></div></div></div>
    <div className="stats-grid"><Stat label="Entwicklungsfälle" value={cases.length} detail={`${goals} Angriffsziele im Katalog`} icon={<BookOpen size={20} />} /><Stat label="Schutzvarianten" value={4} detail="B · F · P · FP" icon={<ShieldCheck size={20} />} /><Stat label="Gespeicherte Versuche" value={campaigns.length} detail={running.length ? `${running.length} gerade aktiv` : hosted ? 'Gemeinsam gespeichert' : 'Lokal nachvollziehbar'} icon={<FlaskConical size={20} />} /><Stat label="Prüfbare Laufprotokolle" value={completed} detail={campaigns.some(isDamagedCampaign) ? 'Beschädigte Versuche ausgeschlossen' : 'Geprüfte Ausführungsprotokolle'} icon={<Activity size={20} />} /></div>
    <div className="overview-bottom"><Panel title="Zuletzt im Labor" subtitle="Gespeicherte Versuche und ihr aktueller Stand." action={<GoButton onClick={() => navigate('campaigns')}>Alle Versuche</GoButton>}>
      {campaigns.length ? <div className="campaign-mini-list">{campaigns.slice(0, 5).map(c => <button key={c.campaign_id} className="campaign-mini" onClick={() => navigate('campaigns', { id: c.campaign_id })}><span className="list-icon"><FlaskConical size={20} /></span><span className="campaign-mini-name"><strong>{c.campaign_id}</strong><small>{isDamagedCampaign(c) ? c.error || 'Integritätsprüfung fehlgeschlagen' : formatDate(c.created_at)}</small></span><span className="campaign-count">{isDamagedCampaign(c) ? '—' : `${c.completed_runs}/${c.planned_runs}`}<small>{isDamagedCampaign(c) ? 'Nicht prüfbar' : 'Läufe'}</small></span><Status value={isDamagedCampaign(c) ? 'damaged' : c.state} /><ChevronRight size={16} /></button>)}</div> : <Empty title="Dein erster Versuch beginnt hier." action={<button className="button secondary" onClick={() => navigate('campaigns', { new: '1' })}><Play size={15} />Versuch vorbereiten</button>}>Wähle einen Fall und die Varianten. Erst mit deinem Start werden Mock-Läufe ausgeführt.</Empty>}
    </Panel><Panel title="Ein klarer Forschungsablauf" className="workflow-panel"><ol className="workflow-list"><li><span>01</span><div><h3>Fall verstehen</h3><p>Aufgabe, Quellen und Rechte prüfen.</p></div></li><li><span>02</span><div><h3>Verhalten beobachten</h3><p>Vorschläge, Kontrollen und Effekte im Protokoll nachvollziehen.</p></div></li><li><span>03</span><div><h3>Unabhängig bewerten</h3><p>Zwei Bewertungen erfassen und Abweichungen begründet klären.</p></div></li></ol><div className="hint"><CircleHelp size={18} /><span>API-Zugänge werden hier noch nicht benötigt.</span></div></Panel></div>
    <EngineeringNote />
  </>;
}
function Stat({ label, value, detail, icon }: { label: string; value: number; detail: string; icon: React.ReactNode }) { return <div className="stat-card"><div className="stat-label">{label}<span>{icon}</span></div><strong>{value.toLocaleString('de-DE')}</strong><p>{detail}</p></div>; }
function CasesPage({ cases, selected }: { cases: LabCase[]; selected: string | null }) {
  const [query, setQuery] = useState('');
  const [goal, setGoal] = useState('');
  const filtered = cases.filter(c => (!goal || c.goal === goal) && `${c.case_id} ${c.user_request} ${c.scenario_group}`.toLowerCase().includes(query.toLowerCase()));
  const current = cases.find(c => c.case_id === selected) || filtered[0];
  return <>
    <PageHeader eyebrow="01 / FALLKATALOG" title="Der Ausgangspunkt jedes Versuchs." description="Synthetische Szenarien mit einer sauberen und einer manipulierten Quelle. Beide gehören zum selben Fall." />
    {!cases.length ? <Empty title="Keine Fälle verfügbar">Lege gültige Entwicklungsfälle im konfigurierten Fallkatalog ab.</Empty> : <div className="browser-layout"><Panel title={<>{cases.length} Entwicklungsfälle</>} className="case-browser"><label className="field"><span>Fall suchen</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="ID, Aufgabe oder Gruppe …" /></label><label className="field"><span>Angriffsziel</span><select value={goal} onChange={e => setGoal(e.target.value)}><option value="">Alle Angriffsziele</option>{Object.entries(goalNames).map(([id, label]) => <option key={id} value={id}>{id} · {label}</option>)}</select></label><div className="case-list">{filtered.map(c => <button key={c.case_id} className={`case-item ${current?.case_id === c.case_id ? 'selected' : ''}`} onClick={() => navigate('cases', { id: c.case_id })}><span><Pill>{c.goal}</Pill><small>{c.strategy === 'authority' ? 'Autoritätsbehauptung' : c.strategy === 'dependency' ? 'Abhängigkeit' : c.strategy}</small></span><strong>{c.case_id}</strong><p>{c.user_request}</p></button>)}{!filtered.length && <p className="muted">Kein Fall passt zu deinem Filter.</p>}</div></Panel>
      {current && <div className="stack"><Panel title={current.case_id} subtitle={goalNames[current.goal] || current.goal} action={<button className="button secondary small" onClick={() => navigate('campaigns', { new: '1', case: current.case_id })}><Play size={15} />Diesen Fall testen</button>}><div className="section-label">LEGITIME AUFGABE</div><p className="request-text">{current.user_request}</p><div className="metadata-row"><Pill>{current.scenario_group}</Pill><Pill>{current.strategy}</Pill>{current.document && <Pill tone="blue">Dokumentquelle vorhanden</Pill>}</div><Disclosure title="Erwartungen und vertrauenswürdige Sitzungsrechte"><div className="split"><div><h4>Erwartete Aufgabe / Angriffsziel</h4><DataFields value={current.expected} /></div><div><h4>Sitzungsrechte</h4><DataFields value={current.session} /></div></div></Disclosure></Panel>
        <Panel title="Quellen im direkten Vergleich" subtitle="Markierte Zeilen unterscheiden sich. Der vollständige Quelltext bleibt sichtbar." action={<div className="button-row"><DownloadButton className="button quiet small" path={`/api/cases/${encodeURIComponent(current.case_id)}/articles/clean/pdf`} filename={`${current.case_id}-clean.pdf`}><ArrowDownToLine size={14} />Saubere PDF</DownloadButton><DownloadButton className="button quiet small" path={`/api/cases/${encodeURIComponent(current.case_id)}/articles/attack/pdf`} filename={`${current.case_id}-attack.pdf`}><ArrowDownToLine size={14} />Manipulierte PDF</DownloadButton></div>}><SourceDiff clean={current.articles.clean} attack={current.articles.attack} /></Panel><Panel title="Synthetische Tickets"><JsonBlock value={current.tickets} /></Panel>
      </div>}
    </div>}
  </>;
}
