'use client';

import { useState, useEffect } from 'react';
import { fetchApi } from '../lib/api';

interface FactBase {
  fact_id: string;
  doc_id: string;
  subject_raw: string;
  predicate_raw: string;
  object_type: string;
  object_value: { raw: string; value?: any };
  qualifiers: Record<string, any>;
  evidence: { quote: string; page: number };
}

interface RelationDetail {
  relation_id: string;
  fact_id_a: string;
  fact_id_b: string;
  verdict: 'CORROBORATES' | 'CONTRADICTS' | 'RECONCILED_BY_CONTEXT' | 'SUPERSEDED' | 'UNRELATED';
  rule_id: string;
  reason: string;
  confidence?: number;
  fact_a: FactBase;
  fact_b: FactBase;
}

export default function RelationsPage() {
  const [relations, setRelations] = useState<RelationDetail[]>([]);
  const [activeTab, setActiveTab] = useState<'CORROBORATES' | 'CONTRADICTS' | 'RECONCILED_BY_CONTEXT' | 'ALL'>('CORROBORATES');
  const [docFilter, setDocFilter] = useState('');

  const loadRelations = async () => {
    try {
      const params = new URLSearchParams();
      if (activeTab !== 'ALL') {
        params.append('verdict', activeTab);
      }
      if (docFilter) params.append('doc_id', docFilter);

      const data = await fetchApi<RelationDetail[]>(`/relations?${params.toString()}`);
      setRelations(data);
    } catch (err) {
      console.error('Failed to load relations:', err);
    }
  };

  useEffect(() => {
    loadRelations();
  }, [activeTab, docFilter]);

  const getVerdictStyles = (verdict: string) => {
    switch (verdict) {
      case 'CORROBORATES':
        return {
          badge: 'bg-secondary-container/40 text-on-secondary-container border-secondary/20',
          icon: 'verified',
          iconColor: 'text-secondary',
          border: 'border-secondary',
          bgLight: 'bg-secondary-container/10',
          textHover: 'text-secondary'
        };
      case 'CONTRADICTS':
        return {
          badge: 'bg-error-container text-on-error-container border-error/20',
          icon: 'cancel',
          iconColor: 'text-error',
          border: 'border-error',
          bgLight: 'bg-error-container/10',
          textHover: 'text-error'
        };
      case 'RECONCILED_BY_CONTEXT':
      case 'SUPERSEDED':
        return {
          badge: 'bg-amber-50 text-amber-800 border-amber-200',
          icon: 'sync_alt',
          iconColor: 'text-amber-700',
          border: 'border-amber-400',
          bgLight: 'bg-amber-50/60',
          textHover: 'text-amber-700'
        };
      default:
        return {
          badge: 'bg-surface-container text-on-surface-variant border-surface-container',
          icon: 'help',
          iconColor: 'text-outline',
          border: 'border-outline',
          bgLight: 'bg-surface-container-low',
          textHover: 'text-outline'
        };
    }
  };

  return (
    <div className="flex flex-col w-full">
      {/* Page Header Area */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-sm pb-space-md border-b border-surface-container">
        <div className="flex flex-col">
          <div className="flex items-center gap-space-xs">
            <span className="font-headline-md text-headline-md text-on-surface">Relations</span>
            <span className="font-label-code-sm text-label-code-sm bg-surface-container px-space-xs py-0.5 rounded text-outline font-medium">engine://coreference.v4</span>
          </div>
          <p className="font-body-sm text-body-sm text-outline mt-space-2xs">Cross-document verification, entity coreference, and discrepancy analysis</p>
        </div>
        
        {/* Quick Telemetry Mini-Stats */}
        <div className="flex items-center gap-space-md self-start md:self-auto">
          <div className="flex items-center gap-space-xs bg-surface-container-low px-space-sm py-1 rounded border border-surface-container">
            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
            <span className="font-label-code-sm text-label-code-sm text-on-surface">Auto-reconciliation: Active</span>
          </div>
          <button onClick={loadRelations} className="h-7 px-space-sm bg-primary text-on-primary rounded text-caption-ui font-medium inline-flex items-center gap-1 shadow-sm hover:bg-primary-container transition-colors">
            <span className="material-symbols-outlined text-[14px]">refresh</span>
            <span>Run Pipeline</span>
          </button>
        </div>
      </div>

      {/* Primary Tab Bar */}
      <div className="flex flex-wrap items-center justify-between gap-space-base mt-space-md border-b border-surface-container">
        <div className="flex items-center gap-space-lg overflow-x-auto">
          {[
            { id: 'CORROBORATES', label: 'Corroborates' },
            { id: 'CONTRADICTS', label: 'Contradicts' },
            { id: 'RECONCILED_BY_CONTEXT', label: 'Reconciled by context' },
            { id: 'ALL', label: 'All' },
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`relative pb-2.5 px-0.5 font-body-sm text-body-sm flex items-center gap-space-xs transition-colors whitespace-nowrap ${
                  isActive ? 'font-medium text-on-surface' : 'text-outline hover:text-on-surface'
                }`}
              >
                <span>{tab.label}</span>
                {isActive && <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary"></span>}
              </button>
            );
          })}
        </div>
      </div>

      {/* Filter & Utility Sub-bar */}
      <div className="flex flex-wrap items-center justify-between gap-space-sm py-space-sm bg-surface-container-lowest border border-surface-container rounded-lg px-space-base my-space-md shadow-sm">
        <div className="flex flex-wrap items-center gap-space-sm">
          <div className="flex items-center gap-1 text-body-sm text-outline">
            <span className="material-symbols-outlined text-[15px]">apartment</span>
            <span className="font-caption-ui uppercase tracking-wider text-[11px] text-outline">Entity: All Entities</span>
          </div>
        </div>
        {/* Search Input Inside Toolbar */}
        <div className="relative flex items-center min-w-[260px]">
          <span className="material-symbols-outlined absolute left-2 text-[15px] text-outline pointer-events-none">search</span>
          <input 
            className="w-full h-7 pl-7 pr-7 font-body-sm text-body-sm bg-surface-container-low border border-surface-container rounded text-on-surface placeholder:text-outline focus:outline-none focus:border-primary focus:bg-surface-container-lowest transition-all" 
            placeholder="Filter relation pairs by Doc ID..." 
            type="text"
            value={docFilter}
            onChange={(e) => setDocFilter(e.target.value)}
          />
        </div>
      </div>

      {/* Vertical Stack of Relation Cards */}
      <div className="flex flex-col gap-space-base pb-space-2xl">
        {relations.length === 0 ? (
          <div className="bg-surface-container-lowest border border-surface-container rounded-lg p-12 text-center text-outline text-sm">
            No relation records found under this verdict tab. Upload additional documents to trigger cross-document candidate reconciliation.
          </div>
        ) : (
          relations.map((rel) => {
            const styles = getVerdictStyles(rel.verdict);
            
            return (
              <article key={rel.relation_id} className="bg-surface-container-lowest border border-surface-container rounded-lg shadow-sm overflow-hidden transition-all hover:border-outline-variant">
                {/* Top Strip */}
                <div className="flex flex-wrap items-center justify-between gap-space-sm px-space-base py-space-sm border-b border-surface-container bg-surface-container-lowest">
                  <div className="flex items-center gap-space-sm">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-caption-ui font-semibold uppercase tracking-wider border ${styles.badge}`}>
                      <span className={`material-symbols-outlined text-[13px] font-bold ${styles.iconColor}`}>{styles.icon}</span>
                      <span>{rel.verdict}</span>
                    </span>
                    <span className="font-body-sm text-body-sm font-medium text-on-surface truncate max-w-xs">{rel.fact_a.subject_raw}</span>
                  </div>
                  <div className="flex items-center gap-space-xs font-label-code-sm text-label-code-sm text-outline">
                    <span className="px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant font-medium">rule:{rel.rule_id}</span>
                    <span>·</span>
                    <span className="truncate max-w-xs">{rel.relation_id}</span>
                  </div>
                </div>

                {/* Card Body: Two Column Comparison with Center Connector */}
                <div className="relative grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-surface-container bg-surface-container-lowest">
                  {/* Connecting Center Node Indicator (Visible on desktop) */}
                  <div className="hidden md:flex absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 items-center justify-center">
                    <div className={`w-6 h-6 rounded-full bg-surface-container-lowest border flex items-center justify-center shadow-sm ${styles.border}`}>
                      {rel.verdict === 'CONTRADICTS' ? (
                         <div className={`w-2 h-2 rounded-full animate-pulse bg-error`}></div>
                      ) : rel.verdict === 'CORROBORATES' ? (
                         <span className={`material-symbols-outlined text-[12px] font-bold ${styles.iconColor}`}>link</span>
                      ) : (
                         <span className={`material-symbols-outlined text-[12px] ${styles.iconColor}`}>schedule</span>
                      )}
                    </div>
                  </div>

                  {/* Left Column (Fact A) */}
                  <div className="p-space-base flex flex-col justify-between gap-space-md">
                    <div className="flex flex-col gap-space-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-label-code-sm text-[11px] text-outline tracking-tight flex items-center gap-1">
                          <span className="material-symbols-outlined text-[13px]">picture_as_pdf</span>
                          <span>{rel.fact_a.doc_id} · p.{rel.fact_a.evidence?.page}</span>
                        </span>
                        <span className="font-label-code-sm text-[10px] uppercase font-semibold text-secondary bg-secondary-container/30 px-1 rounded">Fact A</span>
                      </div>
                      <div className="flex items-baseline gap-space-xs mt-1">
                        <span className="font-body-sm text-body-sm font-semibold text-on-surface">{rel.fact_a.subject_raw}</span>
                        <span className="font-label-code-sm text-label-code-sm text-outline">→</span>
                        <span className="font-label-code-md text-label-code-md text-primary font-medium">{rel.fact_a.predicate_raw}</span>
                      </div>
                      <div className="my-space-xs flex items-baseline gap-space-sm">
                        <span className="font-label-code-md text-xl font-semibold text-on-surface tracking-tight">{rel.fact_a.object_value.raw}</span>
                      </div>
                      
                      {/* Qualifier Chips */}
                      <div className="flex flex-wrap gap-1.5 my-space-2xs">
                        {Object.entries(rel.fact_a.qualifiers || {}).slice(0, 5).map(([k, v]) => (
                          <span key={k} className="px-2 py-0.5 rounded bg-surface-container text-on-surface-variant font-label-code-sm text-[11px]">
                            {k}: {String(v)}
                          </span>
                        ))}
                      </div>
                    </div>
                    
                    {/* Inset Evidence Quote Block */}
                    <div className={`bg-surface-container-low border-l-2 rounded-r p-2.5 font-label-code-sm text-[11.5px] leading-relaxed text-on-surface-variant ${styles.border}`}>
                      “...{rel.fact_a.evidence?.quote}...”
                    </div>
                  </div>

                  {/* Right Column (Fact B) */}
                  <div className="p-space-base flex flex-col justify-between gap-space-md bg-surface-container-lowest">
                    <div className="flex flex-col gap-space-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-label-code-sm text-[11px] text-outline tracking-tight flex items-center gap-1">
                          <span className="material-symbols-outlined text-[13px]">picture_as_pdf</span>
                          <span>{rel.fact_b.doc_id} · p.{rel.fact_b.evidence?.page}</span>
                        </span>
                        <span className="font-label-code-sm text-[10px] uppercase font-semibold text-secondary bg-secondary-container/30 px-1 rounded">Fact B</span>
                      </div>
                      <div className="flex items-baseline gap-space-xs mt-1">
                        <span className="font-body-sm text-body-sm font-semibold text-on-surface">{rel.fact_b.subject_raw}</span>
                        <span className="font-label-code-sm text-label-code-sm text-outline">→</span>
                        <span className="font-label-code-md text-label-code-md text-primary font-medium">{rel.fact_b.predicate_raw}</span>
                      </div>
                      <div className="my-space-xs flex items-baseline gap-space-sm">
                        <span className={`font-label-code-md text-xl font-semibold tracking-tight ${styles.textHover}`}>{rel.fact_b.object_value.raw}</span>
                      </div>
                      
                      {/* Qualifier Chips */}
                      <div className="flex flex-wrap gap-1.5 my-space-2xs">
                        {Object.entries(rel.fact_b.qualifiers || {}).slice(0, 5).map(([k, v]) => (
                          <span key={k} className="px-2 py-0.5 rounded bg-surface-container text-on-surface-variant font-label-code-sm text-[11px]">
                            {k}: {String(v)}
                          </span>
                        ))}
                      </div>
                    </div>
                    
                    {/* Inset Evidence Quote Block */}
                    <div className={`bg-surface-container-low border-l-2 rounded-r p-2.5 font-label-code-sm text-[11.5px] leading-relaxed text-on-surface-variant ${styles.border}`}>
                       “...{rel.fact_b.evidence?.quote}...”
                    </div>
                  </div>
                </div>

                {/* Bottom Strip: Reasoning and Action Bar */}
                <div className={`${styles.bgLight} border-t ${styles.border} px-space-base py-space-sm flex flex-col md:flex-row md:items-center justify-between gap-space-md opacity-90`}>
                  <div className="flex items-start gap-space-sm max-w-4xl">
                    <span className={`material-symbols-outlined text-[16px] shrink-0 mt-0.5 ${styles.iconColor}`}>rule</span>
                    <p className="font-body-sm text-body-sm text-on-surface leading-normal">
                      <span className={`font-semibold mr-1 ${styles.iconColor}`}>Reasoning:</span>
                      {rel.reason}
                    </p>
                  </div>
                  <div className="flex items-center gap-space-xs shrink-0 self-end md:self-auto">
                    <span className="font-label-code-sm text-[11px] text-outline mr-2">Confidence: {rel.confidence || 0.9}</span>
                  </div>
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}
