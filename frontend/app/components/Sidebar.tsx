'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-[220px] z-30 bg-surface-container-low border-r border-surface-container flex flex-col justify-between select-none">
      <div className="flex flex-col">
        <div className="h-14 px-space-base flex items-center border-b border-surface-container">
          <div className="flex items-center gap-space-sm">
            <div className="w-5 h-5 rounded-lg bg-primary flex items-center justify-center">
              <span className="material-symbols-outlined text-[14px] text-on-primary">layers</span>
            </div>
            <span className="font-headline-sm text-headline-sm text-on-surface tracking-tight">Fact Layer</span>
          </div>
        </div>
        
        <div className="p-space-sm">
          <nav className="flex flex-col gap-space-2xs">
            <Link 
              href="/" 
              className={`flex items-center gap-space-sm px-space-sm py-space-xs rounded-lg transition-colors ${pathname === '/' ? 'bg-primary-fixed/20 text-primary font-medium border-l-2 border-primary' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'}`}
            >
              <span className="material-symbols-outlined text-[18px]">description</span>
              <span className="font-body-sm text-body-sm">Documents</span>
            </Link>
            
            <Link 
              href="/facts" 
              className={`flex items-center gap-space-sm px-space-sm py-space-xs rounded-lg transition-colors ${pathname === '/facts' ? 'bg-primary-fixed/20 text-primary font-medium border-l-2 border-primary' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'}`}
            >
              <span className="material-symbols-outlined text-[18px]">verified</span>
              <span className="font-body-sm text-body-sm">Facts</span>
            </Link>

            <Link 
              href="/relations" 
              className={`flex items-center gap-space-sm px-space-sm py-space-xs rounded-lg transition-colors ${pathname === '/relations' ? 'bg-primary-fixed/20 text-primary font-medium border-l-2 border-primary' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'}`}
            >
              <span className="material-symbols-outlined text-[18px]">hub</span>
              <span className="font-body-sm text-body-sm">Relations</span>
            </Link>

            <Link 
              href="/insights" 
              className={`flex items-center gap-space-sm px-space-sm py-space-xs rounded-lg transition-colors ${pathname === '/insights' ? 'bg-primary-fixed/20 text-primary font-medium border-l-2 border-primary' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'}`}
            >
              <span className="material-symbols-outlined text-[18px]">insights</span>
              <span className="font-body-sm text-body-sm">Insights</span>
            </Link>
          </nav>
        </div>
      </div>
      
      <div className="p-space-base border-t border-surface-container bg-surface-container-low flex flex-col gap-space-xs">
        <div className="flex items-center justify-between">
          <span className="font-caption-ui text-caption-ui text-outline uppercase tracking-wider">Workspace</span>
          <span className="w-1.5 h-1.5 rounded-full bg-secondary"></span>
        </div>
        <span className="font-body-sm text-body-sm font-medium text-on-surface truncate">Production</span>
        <div className="mt-space-2xs pt-space-xs border-t border-surface-container">
          <span className="font-label-code-sm text-label-code-sm text-outline block">Active</span>
        </div>
      </div>
    </aside>
  );
}
