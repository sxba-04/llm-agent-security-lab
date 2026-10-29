import { DownloadButton } from './DownloadButton';
import { useRef, useState } from 'react';
import { ArrowDownToLine, CheckCheck, FileText, Upload } from 'lucide-react';
import { api, hosted, message, post, useResource } from './api';
import type { Document, DocumentEntry, LabCase } from './types';
import { Disclosure, Empty, ErrorBox, JsonBlock, Loading, PageHeader, Panel, Pill, Success, TextBlock } from './ui';

export function DocumentsPage({ cases }: { cases: LabCase[] }) {
  const documents = useResource<{ documents: DocumentEntry[] }>('/api/documents');
  const [selected, setSelected] = useState(''), [newDocument, setNewDocument] = useState<Document | null>(null);
  const [file, setFile] = useState<File | null>(null), [busy, setBusy] = useState(''), [error, setError] = useState(''), [success, setSuccess] = useState('');
  const [reviewedKey, setReviewedKey] = useState(''), [exampleCase, setExampleCase] = useState(cases[0]?.case_id || '');
  const input = useRef<HTMLInputElement>(null);
  const entries = documents.data?.documents || [];
  const rows = entries.filter((d): d is Document => d.valid_evidence !== false);
  const damaged = entries.filter(d => d.valid_evidence === false);
  const usableNew = newDocument && !damaged.some(d => d.document_id === newDocument.document_id) ? newDocument : null;
  const document = rows.find(d => d.document_id === selected) || (usableNew?.document_id === selected ? usableNew : null) || rows[0];
  const documentKey = document ? `${document.document_id}:${document.text_sha256}` : '';
  const reviewed = Boolean(documentKey) && reviewedKey === documentKey;
  async function upload() {
    if (!file || busy) return;
    setBusy('upload'); setError(''); setSuccess('');
    const form = new FormData(); form.append('file', file);
    try {
      const result = await api<Document>('/api/documents', { method: 'POST', body: form });
      setNewDocument(result); setSelected(result.document_id); setReviewedKey(''); setFile(null);
      if (input.current) input.current.value = '';
      documents.refresh(); setSuccess('PDF importiert. Prüfe jetzt den vollständig extrahierten Text.');
    } catch (err) { setError(message(err)); } finally { setBusy(''); }
  }
  async function confirm() {
    if (!document || !reviewed || busy) return;
    setBusy('confirm'); setError(''); setSuccess('');
    try {
      const result = await post<Document>(`/api/documents/${encodeURIComponent(document.document_id)}/confirm`, { text_sha256: document.text_sha256 });
      setNewDocument(result); documents.refresh(); setSuccess('Extraktion bestätigt. Diese Quelle kann einem Fall im neuen Versuch zugewiesen werden.');
    } catch (err) { setError(message(err)); } finally { setBusy(''); }
  }
  return <>
    <PageHeader eyebrow="QUELLENWERKSTATT" title="Aus einer PDF wird eine prüfbare Quelle." description="Importiere synthetische Dokumente, kontrolliere die Textextraktion und weise sie anschließend bewusst einem Fall zu." />
    <div className="documents-top"><Panel title="PDF importieren" subtitle={hosted ? "Die Datei wird im gemeinsamen Online-Arbeitsbereich verarbeitet und gespeichert. Es wird kein LLM aufgerufen." : "Die Datei wird lokal verarbeitet. Es wird kein LLM aufgerufen."}><form onSubmit={e => { e.preventDefault(); void upload(); }}><label className={`upload-zone ${file ? 'has-file' : ''}`}><Upload size={28} /><strong>{file ? file.name : 'Eine PDF-Datei auswählen'}</strong><span>{file ? `${(file.size / 1024).toLocaleString('de-DE', { maximumFractionDigits: 0 })} KB · bereit zum Import` : 'Synthetische, textbasierte PDF · kein OCR'}</span><input ref={input} type="file" accept="application/pdf,.pdf" aria-label="PDF-Datei auswählen" onChange={e => { setFile(e.target.files?.[0] || null); setError(''); setSuccess(''); }} /></label><div className="form-actions"><span className="muted">Nur bestätigte Extraktionen werden in Versuchen verwendet.</span><button type="submit" className="button primary" disabled={!file || Boolean(busy)}><Upload size={16} />{busy === 'upload' ? 'Wird extrahiert …' : 'PDF importieren'}</button></div></form></Panel>
      <Panel title="Mit einem Beispiel beginnen" subtitle="Die Beispiel-PDFs enthalten den jeweiligen Quelltext aus dem Fallkatalog."><label className="field"><span>Beispielfall</span><select value={exampleCase} onChange={e => setExampleCase(e.target.value)}>{cases.map(c => <option key={c.case_id} value={c.case_id}>{c.case_id}</option>)}</select></label><div className="stack compact"><DownloadButton className="button secondary" path={`/api/cases/${encodeURIComponent(exampleCase)}/articles/clean/pdf`} filename={`${exampleCase}-clean.pdf`}><ArrowDownToLine size={16} />Saubere Beispiel-PDF</DownloadButton><DownloadButton className="button secondary" path={`/api/cases/${encodeURIComponent(exampleCase)}/articles/attack/pdf`} filename={`${exampleCase}-attack.pdf`}><ArrowDownToLine size={16} />Manipulierte Beispiel-PDF</DownloadButton></div><p className="muted small-text">Herunterladen, links importieren und die Extraktion mit dem Fallkatalog vergleichen.</p></Panel></div>
    <ErrorBox error={error || documents.error} retry={documents.error ? documents.refresh : undefined} />{success && <Success>{success}</Success>}
    {damaged.length > 0 && <Panel title="Nicht prüfbare PDF-Quellen"><p className="muted">Diese Originaldateien bleiben erhalten. Sie können erst nach einer erfolgreichen Prüfung bestätigt oder einem Versuch zugewiesen werden.</p>{damaged.map(d => <div key={d.document_id}><strong className="mono">{d.document_id}</strong><ErrorBox error={d.error} /></div>)}</Panel>}
    {documents.loading && !usableNew ? <Loading /> : rows.length || usableNew ? <div className="browser-layout documents-browser"><Panel title="Quellenbestand"><div className="document-list">{(rows.length ? rows : usableNew ? [usableNew] : []).map(d => <button key={d.document_id} className={`document-item ${d.document_id === document?.document_id ? 'selected' : ''}`} onClick={() => { setSelected(d.document_id); setReviewedKey(''); setSuccess(''); }}><FileText size={20} /><span><strong>{d.filename}</strong><small>{d.page_count} {d.page_count === 1 ? 'Seite' : 'Seiten'} · {d.text_sha256.slice(0, 8)}</small><Pill tone={d.confirmed ? 'green' : 'amber'}>{d.confirmed ? 'Bestätigt' : 'Prüfung offen'}</Pill></span></button>)}</div></Panel>{document && <Panel title={document.filename} subtitle={`${document.page_count} Seiten · Extraktion: ${document.extractor}`} action={<Pill tone={document.confirmed ? 'green' : 'amber'}>{document.confirmed ? 'Bestätigte Quelle' : 'Noch nicht bestätigt'}</Pill>}><div className="section-label">EXTRAHIERTER TEXT · UNVERÄNDERLICH</div><TextBlock className="pdf-text">{document.extracted_text}</TextBlock><Disclosure title="Herkunft und Prüfsummen"><JsonBlock value={{ document_id: document.document_id, filename: document.filename, sha256: document.sha256, text_sha256: document.text_sha256, extractor: document.extractor, page_count: document.page_count }} /></Disclosure>{!document.confirmed ? <div className="confirmation-panel"><label className="inline-check"><input type="checkbox" checked={reviewed} onChange={e => setReviewedKey(e.target.checked ? documentKey : '')} /><span>Ich habe den extrahierten Text mit der PDF verglichen und geprüft, dass die relevante Quelle vollständig und korrekt enthalten ist.</span></label><button className="button primary" disabled={!reviewed || Boolean(busy)} onClick={confirm}><CheckCheck size={17} />{busy === 'confirm' ? 'Wird bestätigt …' : 'Extraktion bestätigen'}</button></div> : <div className="notice success"><CheckCheck size={19} /><span>Für eine explizite Zuweisung beim nächsten Mock-Versuch verfügbar. Der bestehende Fallkatalog wird dadurch nicht verändert.</span></div>}</Panel>}</div> : <Empty title={damaged.length ? "Keine prüfbaren PDF-Quellen vorhanden" : "Deine Quellenwerkstatt ist noch leer"}>Importiere eine eigene synthetische PDF oder beginne mit einer Beispiel-PDF aus dem Fallkatalog.</Empty>}
  </>;
}
