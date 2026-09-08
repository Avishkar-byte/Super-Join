'use client';

import { useState, useEffect } from 'react';
import { fetchApi } from '../lib/api';

interface RejectedFact {
  rejected_id: string;
  doc_id: string;
  chunk_id?: string;
  raw_output: any;
  reason: string;
  details: any;
  created_at: string;
}

interface QualifierKey {
  key: string;
  count: number;
  first_seen: string;
  last_seen: string;
}

interface PredicateSummary {
  pred_id: string;
  canonical_name: string;
  fact_count: number;
}

interface SystemStats {
  document_count: number;
  fact_count: number;
  rejected_fact_count: number;
  entity_count: number;
  predicate_count: number;
  relation_count: number;
  hallucination_rate: number | null;
  qualifier_key_count: number;
}

export default function InsightsPage() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [rejectedFacts, setRejectedFacts] = useState<RejectedFact[]>([]);
  const [qualifiers, setQualifiers] = useState<QualifierKey[]>([]);
  const [predicates, setPredicates] = useState<PredicateSummary[]>([]);
  const [predicateFilter, setPredicateFilter] = useState('');

  const loadData = async () => {
    try {
      const [sData, rData, qData, pData] = await Promise.all([
        fetchApi<SystemStats>('/stats'),
        fetchApi<RejectedFact[]>('/rejected'),
        fetchApi<QualifierKey[]>('/qualifiers'),
        fetchApi<PredicateSummary[]>('/predicates'),
      ]);
      setStats(sData);
      setRejectedFacts(rData);
      setQualifiers(qData);
      setPredicates(pData);
    } catch (err) {
      console.error('Failed to load insights data:', err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const maxQualifierCount = Math.max(...qualifiers.map(q => q.count), 1);

  const filteredPredicates = predicates.filter(p => 
    p.canonical_name.toLowerCase().includes(predicateFilter.toLowerCase())
  );

  return (
    <div className="flex flex-col w-full">
      {/* Header Bar */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-space-md mb-space-xl border-b border-surface-container pb-space-md">
        <div className="flex flex-col">
          <h1 className="font-headline-md text-headline-md text-on-surface tracking-tight">Insights</h1>
          <p className="font-body-sm text-body-sm text-outline mt-space-2xs">Extraction pipeline telemetry, verification precision, and schema governance</p>
        </div>
        <div className="flex items-center gap-space-sm self-start md:self-auto">
          <button 
            onClick={loadData}
            className="h-8 px-space-md bg-primary hover:bg-primary-container text-on-primary rounded-lg shadow-sm font-body-sm text-body-sm font-medium transition-colors flex items-center gap-space-xs"
          >
            <span className="material-symbols-outlined text-[16px]">refresh</span>
            <span>Refresh Metrics</span>
          </button>
        </div>
      </header>

      {/* 4-Stat Metric Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-base mb-space-base">
        {/* Stat 1 */}
        <div className="bg-surface-container-lowest p-space-base rounded-lg shadow-sm flex flex-col justify-between border border-surface-container">
          <span className="font-label-code-sm text-label-code-sm text-outline tracking-wider uppercase">FACTS EXTRACTED</span>
          <div className="mt-space-md flex items-baseline justify-between">
            <span className="font-label-code-md text-[1.5rem] leading-none font-medium text-on-surface">
              {stats?.fact_count || 0}
            </span>
          </div>
          <div className="mt-space-xs text-on-surface-variant font-caption-ui text-caption-ui">Total grounded schema tuples</div>
        </div>
        
        {/* Stat 2 */}
        <div className="bg-surface-container-lowest p-space-base rounded-lg shadow-sm flex flex-col justify-between border border-surface-container">
          <span className="font-label-code-sm text-label-code-sm text-outline tracking-wider uppercase">GROUNDING REJECTION RATE</span>
          <div className="mt-space-md flex items-baseline justify-between">
            <span className="font-label-code-md text-[1.5rem] leading-none font-medium text-on-surface">
              {stats?.hallucination_rate !== null && stats?.hallucination_rate !== undefined 
                ? `${(stats.hallucination_rate * 100).toFixed(1)}%` 
                : 'N/A'}
            </span>
            <span className="font-label-code-sm text-label-code-sm text-tertiary">
              {stats?.rejected_fact_count || 0} rejected
            </span>
          </div>
          <div className="mt-space-xs text-on-surface-variant font-caption-ui text-caption-ui">
            {stats?.rejected_fact_count || 0} rejected / {(stats?.fact_count || 0) + (stats?.rejected_fact_count || 0)} proposed
          </div>
        </div>
        
        {/* Stat 3 */}
        <div className="bg-surface-container-lowest p-space-base rounded-lg shadow-sm flex flex-col justify-between border border-surface-container">
          <span className="font-label-code-sm text-label-code-sm text-outline tracking-wider uppercase">SYSTEM DOCUMENTS</span>
          <div className="mt-space-md flex items-baseline justify-between">
            <span className="font-label-code-md text-[1.5rem] leading-none font-medium text-on-surface">
              {stats?.document_count || 0}
            </span>
          </div>
          <div className="mt-space-xs text-on-surface-variant font-caption-ui text-caption-ui">Indexed source materials</div>
        </div>
        
        {/* Stat 4 */}
        <div className="bg-surface-container-lowest p-space-base rounded-lg shadow-sm flex flex-col justify-between border border-surface-container">
          <span className="font-label-code-sm text-label-code-sm text-outline tracking-wider uppercase">RECONCILED RELATIONS</span>
          <div className="mt-space-md flex items-baseline justify-between">
            <span className="font-label-code-md text-[1.5rem] leading-none font-medium text-on-surface">
              {stats?.relation_count || 0}
            </span>
          </div>
          <div className="mt-space-xs text-on-surface-variant font-caption-ui text-caption-ui">Cross-document verification edges</div>
        </div>
      </div>

      {/* Dual Split Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-base mb-space-base">
        
        {/* Left Panel: Rejected Extractions */}
        <section className="bg-surface-container-lowest p-space-base rounded-lg shadow-sm border border-surface-container flex flex-col min-h-0">
          <div className="flex items-center justify-between pb-space-sm mb-space-xs">
            <div>
              <h2 className="font-headline-sm text-headline-sm text-on-surface">Rejected extractions</h2>
              <p className="font-body-sm text-body-sm text-outline">Facts the grounding step refused to store</p>
            </div>
            <span className="font-label-code-sm text-label-code-sm px-space-xs py-space-2xs bg-surface-container-high rounded text-on-surface-variant border border-surface-container">
              {rejectedFacts.length} events
            </span>
          </div>
          
          <div className="w-full overflow-y-auto max-h-[400px] pr-2">
            <div className="grid grid-cols-12 px-space-xs py-space-xs bg-surface-container-low rounded font-label-code-sm text-label-code-sm text-outline uppercase tracking-wider mb-space-2xs border border-surface-container">
              <span className="col-span-8">Reason / Failure Details</span>
              <span className="col-span-4 text-right">Doc ID</span>
            </div>
            <div className="flex flex-col gap-space-2xs">
              {rejectedFacts.length === 0 ? (
                <div className="p-4 text-center text-outline text-sm">No rejections found.</div>
              ) : (
                rejectedFacts.map((rf) => (
                  <div key={rf.rejected_id} className="flex flex-col rounded-lg bg-surface-container-low/40 hover:bg-surface-container-low transition-colors p-space-xs border border-surface-container border-opacity-50">
                    <div className="grid grid-cols-12 items-center text-on-surface py-space-2xs">
                      <span className="col-span-8 font-body-sm text-body-sm font-medium flex items-center gap-space-xs text-tertiary">
                        <span className="w-1.5 h-1.5 rounded-full bg-tertiary"></span>
                        {rf.reason}
                      </span>
                      <span className="col-span-4 text-right font-label-code-sm text-label-code-sm text-outline truncate" title={rf.doc_id}>
                        {rf.doc_id}
                      </span>
                    </div>
                    {/* Expanded Detail Block */}
                    <div className="mt-space-2xs mb-space-xs p-space-sm rounded-lg bg-surface-container-lowest shadow-sm flex flex-col gap-space-xs border border-surface-container">
                      <div className="flex items-center justify-between">
                        <span className="font-label-code-sm text-label-code-sm text-tertiary font-semibold uppercase tracking-wider">Failed Extraction Request</span>
                        <span className="font-label-code-sm text-[10px] text-outline">{rf.rejected_id}</span>
                      </div>
                      <div className="text-tertiary bg-error-container/30 border border-error/20 px-space-xs py-space-2xs rounded font-label-code-sm text-label-code-sm block break-words whitespace-pre-wrap">
                        {typeof rf.raw_output === 'string' 
                          ? rf.raw_output 
                          : JSON.stringify(rf.raw_output, null, 2)}
                      </div>
                      <div className="mt-space-2xs flex items-center gap-space-xs text-on-surface-variant font-caption-ui text-caption-ui">
                        <span className="material-symbols-outlined text-[14px] text-tertiary">error</span>
                        <span>{rf.details?.error_message || 'Validation pipeline failure'}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Right Panel: Schema Evolution */}
        <section className="bg-surface-container-lowest p-space-base rounded-lg shadow-sm border border-surface-container flex flex-col justify-between min-h-0">
          <div>
            <div className="flex items-center justify-between pb-space-sm mb-space-xs">
              <div>
                <h2 className="font-headline-sm text-headline-sm text-on-surface">Schema evolution</h2>
                <p className="font-body-sm text-body-sm text-outline">Qualifier keys dynamically discovered</p>
              </div>
              <span className="font-label-code-sm text-label-code-sm px-space-xs py-space-2xs bg-surface-container-high rounded text-on-surface-variant border border-surface-container">
                {qualifiers.length} keys
              </span>
            </div>
            
            {/* Qualifier List */}
            <div className="flex flex-col gap-space-sm mt-space-sm overflow-y-auto max-h-[350px] pr-2">
              {qualifiers.length === 0 ? (
                <div className="text-sm text-outline text-center py-4">No qualifiers observed yet.</div>
              ) : (
                qualifiers.sort((a,b) => b.count - a.count).map(q => {
                  const percentage = Math.max((q.count / maxQualifierCount) * 100, 2);
                  return (
                    <div key={q.key} className="flex items-center justify-between gap-space-md">
                      <div className="w-32 flex-shrink-0 flex items-center gap-space-xs">
                        <span className="font-label-code-sm text-label-code-sm font-medium text-on-surface truncate" title={q.key}>{q.key}</span>
                      </div>
                      <div className="flex-1 bg-surface-container h-1.5 rounded-full overflow-hidden">
                        <div className="bg-primary h-full rounded-full transition-all" style={{ width: `${percentage}%` }}></div>
                      </div>
                      <span className="w-12 text-right font-label-code-sm text-label-code-sm text-on-surface">{q.count}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
          
          <div className="mt-space-lg pt-space-xs flex items-center justify-between font-caption-ui text-caption-ui text-outline border-t border-surface-container">
            <span>Dynamic Key Extraction Engine</span>
            <span>Count = frequency across facts</span>
          </div>
        </section>
      </div>

      {/* Bottom Panel: Predicate Registry */}
      <section className="bg-surface-container-lowest p-space-base rounded-lg shadow-sm border border-surface-container flex flex-col mb-space-2xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-xs mb-space-base">
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Predicate registry</h2>
            <p className="font-body-sm text-body-sm text-outline">{predicates.length} active predicate types normalized from canonical schema</p>
          </div>
          <div className="flex items-center gap-space-xs">
            <span className="font-label-code-sm text-label-code-sm text-outline">Filter:</span>
            <input 
              value={predicateFilter}
              onChange={(e) => setPredicateFilter(e.target.value)}
              className="h-7 px-space-xs font-label-code-sm text-label-code-sm bg-surface-container-low rounded border border-surface-container text-on-surface outline-none focus:bg-surface-container focus:border-primary transition-all" 
              placeholder="type predicate..." 
              type="text"
            />
          </div>
        </div>
        
        {/* Wrapped Chips Grid */}
        <div className="flex flex-wrap gap-space-xs">
          {filteredPredicates.length === 0 ? (
             <div className="text-sm text-outline p-2">No predicates found.</div>
          ) : (
             filteredPredicates.map(p => (
               <div key={p.pred_id} className="bg-surface-container-low border border-surface-container hover:bg-surface-container text-on-surface font-label-code-sm text-label-code-sm px-space-sm py-space-xs rounded-lg transition-colors flex items-center gap-space-xs">
                 <span className="font-medium text-on-surface">{p.canonical_name}</span>
                 <span className="text-outline font-normal px-1 bg-surface-container-highest rounded">(sup: {p.fact_count})</span>
               </div>
             ))
          )}
        </div>
      </section>
    </div>
  );
}
