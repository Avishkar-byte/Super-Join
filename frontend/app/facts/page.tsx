'use client';

import { useState, useEffect } from 'react';
import { fetchApi, getPageImageUrl } from '../lib/api';

interface FactListItem {
  fact_id: string;
  doc_id: string;
  subject_raw: string;
  subject_canonical_name?: string;
  predicate_raw: string;
  predicate_canonical_name?: string;
  object_type: string;
  object_value: {
    type: string;
    value: any;
    unit?: string;
    raw: string;
  };
  qualifiers: Record<string, any>;
  confidence: number;
  evidence_quote: string;
  evidence_page: number;
}

interface FactDetail extends FactListItem {
  evidence: {
    doc_id: string;
    page: number;
    bbox?: [number, number, number, number];
    quote: string;
  };
  relations: Array<{
    relation_id: string;
    verdict: string;
    rule_id: string;
    reason: string;
  }>;
}

export default function FactsPage() {
  const [facts, setFacts] = useState<FactListItem[]>([]);
  const [selectedFact, setSelectedFact] = useState<FactDetail | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [docFilter, setDocFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const loadFacts = async () => {
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (docFilter) params.append('doc_id', docFilter);
      if (typeFilter) params.append('object_type', typeFilter);

      const data = await fetchApi<FactListItem[]>(`/facts?${params.toString()}`);
      setFacts(data);
    } catch (err) {
      console.error('Failed to load facts:', err);
    }
  };

  useEffect(() => {
    loadFacts();
  }, [searchQuery, docFilter, typeFilter]);

  const handleFactClick = async (factId: string) => {
    try {
      const detail = await fetchApi<FactDetail>(`/facts/${factId}`);
      setSelectedFact(detail);
    } catch (err) {
      console.error('Failed to load fact detail:', err);
    }
  };

  return (
    <div className="flex flex-col w-full">
      <div className="flex flex-col gap-space-md mb-space-base">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-space-md">
            <span className="font-headline-md text-headline-md text-on-surface">Fact Layer Engine</span>
            <span className="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>
            <span className="font-label-code-sm text-label-code-sm text-outline">EVIDENCE_SPLIT_VIEW</span>
          </div>
          <div className="flex items-center gap-space-sm">
            <span className="font-label-code-sm text-label-code-sm bg-surface-container px-space-sm py-space-2xs rounded-lg text-on-surface-variant">Session #4882-AX</span>
            <button 
              onClick={loadFacts}
              className="flex items-center gap-space-xs px-space-md py-space-2xs bg-primary text-on-primary rounded-lg font-body-sm text-body-sm hover:bg-primary-container transition-colors"
            >
              <span className="material-symbols-outlined text-[15px]">refresh</span>
              <span>Re-evaluate</span>
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-space-lg w-full items-start">
        {/* LEFT PANEL: FACT BROWSER */}
        <div className={`${selectedFact ? 'col-span-12 lg:col-span-5' : 'col-span-12'} bg-surface-container-low rounded-xl p-space-md flex flex-col gap-space-md min-w-0 transition-all duration-300`}>
          {/* Search Field */}
          <div className="flex items-center gap-space-sm bg-surface-container-lowest px-space-md py-space-xs rounded-lg">
            <span className="material-symbols-outlined text-[18px] text-outline">search</span>
            <input 
              className="w-full bg-transparent text-on-surface font-body-md text-body-md placeholder-outline focus:outline-none" 
              placeholder="Search facts..." 
              type="text" 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <kbd className="font-label-code-sm text-label-code-sm px-space-xs py-space-2xs bg-surface-container rounded text-outline uppercase">⌘K</kbd>
          </div>
          
          {/* Filter Controls */}
          <div className="flex flex-wrap items-center gap-space-xs">
            <div className="flex items-center gap-space-2xs bg-surface-container-lowest px-space-sm py-space-2xs rounded-lg border border-surface-container">
              <input
                type="text"
                placeholder="Doc ID"
                value={docFilter}
                onChange={(e) => setDocFilter(e.target.value)}
                className="bg-transparent text-on-surface font-caption-ui text-caption-ui w-24 focus:outline-none"
              />
            </div>
            
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="flex items-center gap-space-2xs bg-surface-container-lowest text-on-surface font-caption-ui text-caption-ui px-space-sm py-space-2xs rounded-lg border border-surface-container focus:outline-none"
            >
              <option value="">All Types</option>
              <option value="quantity">Quantity</option>
              <option value="date">Date</option>
              <option value="entity">Entity</option>
              <option value="status">Status</option>
              <option value="text">Text</option>
            </select>
            
            <button 
              onClick={() => {
                setSearchQuery('');
                setDocFilter('');
                setTypeFilter('');
              }}
              className="flex items-center gap-space-2xs bg-surface-container-lowest text-on-surface font-caption-ui text-caption-ui px-space-sm py-space-2xs rounded-lg hover:bg-surface-container transition-colors"
            >
              <span>Clear</span>
              <span className="material-symbols-outlined text-[14px] text-outline">close</span>
            </button>
          </div>
          
          {/* Status Indicator */}
          <div className="flex items-center justify-between px-space-2xs">
            <span className="font-label-code-sm text-label-code-sm text-outline">Showing {facts.length} facts</span>
            <span className="font-caption-ui text-caption-ui text-secondary font-medium flex items-center gap-space-2xs">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary"></span>
              Live Sync
            </span>
          </div>
          
          {/* Scrolling Fact Cards Stream */}
          <div className="flex flex-col gap-space-sm">
            {facts.length === 0 ? (
               <div className="p-6 text-center text-outline text-sm">No facts found matching filter criteria.</div>
            ) : (
              facts.map((fact) => {
                const isSelected = selectedFact?.fact_id === fact.fact_id;
                return (
                  <div 
                    key={fact.fact_id}
                    onClick={() => handleFactClick(fact.fact_id)}
                    className={`p-space-md rounded-lg relative overflow-hidden transition-all cursor-pointer ${
                      isSelected ? 'bg-surface-container-lowest' : 'bg-surface-container-lowest hover:bg-surface-container'
                    }`}
                  >
                    {isSelected && <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary"></div>}
                    <div className={`flex flex-col gap-space-xs ${isSelected ? 'pl-space-xs' : ''}`}>
                      <div className="flex items-center justify-between">
                        <span className="font-body-sm text-body-sm text-on-surface font-medium truncate">
                          {fact.subject_canonical_name || fact.subject_raw} → {fact.predicate_canonical_name || fact.predicate_raw}
                        </span>
                        <span className={`font-label-code-sm text-label-code-sm px-space-xs py-space-2xs rounded ${
                          fact.confidence > 0.9 ? 'text-secondary bg-secondary-container/30 text-on-secondary-container' : 'text-on-tertiary-container bg-tertiary-container/10'
                        }`}>
                          {fact.confidence.toFixed(2)}
                        </span>
                      </div>
                      <div className={`font-label-code-md ${isSelected ? 'text-headline-sm font-semibold' : 'text-body-lg font-semibold'} text-on-surface tracking-tight py-space-2xs`}>
                        {fact.object_value.raw}
                      </div>
                      
                      <div className="flex flex-wrap gap-space-xs pt-space-2xs">
                        {Object.entries(fact.qualifiers || {}).slice(0, 4).map(([k, v]) => (
                           <span key={k} className="bg-surface-container font-label-code-sm text-label-code-sm text-on-surface-variant px-space-xs py-space-2xs rounded">
                             {String(v)}
                           </span>
                        ))}
                      </div>
                      
                      <div className="flex items-center justify-between pt-space-xs mt-space-xs text-outline">
                        <span className="font-label-code-sm text-label-code-sm">{fact.fact_id}</span>
                        <span className="font-caption-ui text-caption-ui truncate max-w-[200px]">
                          {fact.doc_id} · p.{fact.evidence_page}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT PANEL: EVIDENCE VIEWER */}
        {selectedFact && (
          <div className="col-span-12 lg:col-span-7 flex flex-col gap-space-md min-w-0">
            {/* Viewer Toolbar */}
            <div className="bg-surface-container-low px-space-md py-space-xs rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-space-sm min-w-0">
                <span className="material-symbols-outlined text-[18px] text-outline">picture_as_pdf</span>
                <span className="font-body-sm text-body-sm font-medium text-on-surface truncate">{selectedFact.evidence.doc_id}</span>
                <span className="font-label-code-sm text-label-code-sm text-outline">p. {selectedFact.evidence.page}</span>
              </div>
              <div className="flex items-center gap-space-sm">
                <button 
                  onClick={() => setSelectedFact(null)}
                  className="flex items-center gap-space-2xs bg-surface-container-lowest text-on-surface-variant hover:text-primary font-caption-ui text-caption-ui px-space-sm py-space-xs rounded-lg hover:bg-surface-container transition-colors"
                >
                  <span>Close Viewer</span>
                  <span className="material-symbols-outlined text-[14px]">close</span>
                </button>
              </div>
            </div>
            
            {/* Realistic Document Canvas */}
            <div className="bg-surface-container-high rounded-xl p-space-lg flex justify-center items-center overflow-x-auto min-h-[400px]">
              <div className="relative border border-surface-container rounded-sm overflow-hidden bg-white max-h-[600px] overflow-y-auto shadow-sm w-full max-w-[640px]">
                <img
                  src={getPageImageUrl(selectedFact.doc_id, selectedFact.evidence.page)}
                  alt={`Page ${selectedFact.evidence.page}`}
                  className="w-full h-auto block object-contain"
                  crossOrigin="anonymous"
                />
                {/* Bounding Box Highlight Overlay */}
                {selectedFact.evidence.bbox && (
                  <div
                    className="absolute border-2 border-primary bg-primary/20 rounded shadow-sm pointer-events-none"
                    style={{
                      left: `${selectedFact.evidence.bbox[0] / 6}%`,
                      top: `${selectedFact.evidence.bbox[1] / 10}%`,
                      width: `${(selectedFact.evidence.bbox[2] - selectedFact.evidence.bbox[0]) / 6}%`,
                      height: '24px',
                    }}
                  />
                )}
              </div>
            </div>
            
            {/* Evidence Card Inspector */}
            <div className="bg-surface-container-lowest p-space-md rounded-xl flex flex-col gap-space-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-space-xs">
                  <span className="material-symbols-outlined text-[16px] text-outline">fingerprint</span>
                  <span className="font-label-code-sm text-label-code-sm text-outline">Verified evidence</span>
                </div>
                <span className="bg-secondary-container text-on-secondary-container font-label-code-sm text-label-code-sm px-space-xs py-space-2xs rounded flex items-center gap-space-2xs">
                  <span className="material-symbols-outlined text-[14px]">check</span>
                  <span>Grounded</span>
                </span>
              </div>
              <div className="bg-surface-container-low p-space-md rounded-lg">
                <p className="font-label-code-sm text-label-code-sm text-on-surface leading-relaxed font-serif italic">
                  "{selectedFact.evidence.quote}"
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-space-xs text-outline font-label-code-sm text-caption-ui pt-space-2xs">
                <div className="flex items-center gap-space-xs">
                  <span className="material-symbols-outlined text-[14px]">smart_toy</span>
                  <span>Extracted via Document Pipeline</span>
                </div>
                <div className="flex items-center gap-space-md">
                  <span>{selectedFact.fact_id}</span>
                  <span className="text-secondary font-medium">Grounding score: {selectedFact.confidence.toFixed(3)}</span>
                </div>
              </div>
            </div>
            
          </div>
        )}
      </div>
    </div>
  );
}
